"""Foreground process-group ledger and orphan reaper (crash recovery).

A foreground terminal command is spawned in its own process group (``start_new_session=True``,
``tools/environments/local.py:_run_bash``) and reaped on timeout, atexit, or normal completion.
The gap: a Hermes process that dies WITHOUT firing atexit (SIGKILL, OOM, host power loss)
leaves its spawned groups running, reparented to init. A long ``grep -r``/``find``/``gitleaks``
scan from a dead session then keeps burning a core for hours and can load-spike the host
(observed: five orphaned full-disk scans driving load 70 on the owner's Mac).

Fix: every foreground spawn is recorded in a small ledger with the owner Hermes PID and the
group leader's start-time fingerprint. At the next Hermes startup a once-per-interpreter
reaper kills groups whose owner PID is dead — with the same identity checks the codebase
already uses for PID recycling (#43044) so a recycled number can never take down a stranger.

Conservative by construction:
- only groups recorded in OUR ledger are ever signalled (never a ppid==1 sweep);
- a live owner PID means the owner still supervises the group — skip it;
- the leader's start-time fingerprint must still match the spawn-time baseline;
- an age floor lets a slow shutdown finish its own cleanup;
- TERM → grace → KILL escalation, same as the timeout path.
"""

import contextlib
import json
import logging
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("tools.environments.fg_group_ledger")

# Entries older than this are pruned from the ledger on every write.
LEDGER_MAX_AGE_SECONDS = 24 * 3600
# A group is only reaped once it is at least this old AND its owner is dead: the floor
# gives a slow-shutdown Hermes time to run its own atexit cleanup (mirrors the docker
# orphan reaper's max(60, lifetime) floor).
REAP_MIN_AGE_SECONDS = 60
# TERM grace before escalating to KILL on a signalled group.
TERM_GRACE_SECONDS = 3.0

_reaper_ran = False
_reaper_lock_guard = False  # module-level, single-interpreter; no lock needed (GIL-atomic assign)


def _ledger_path() -> Path:
    """Active profile's ledger at call time (mirrors process_registry._checkpoint_path)."""
    try:
        from hermes_constants import get_hermes_home
        return get_hermes_home() / "fg_groups.json"
    except Exception:
        return Path(os.path.expanduser("~/.hermes/fg_groups.json"))


def register_spawned_group(proc: subprocess.Popen, pgid: Optional[int], command: str = "") -> None:
    """Record a freshly spawned foreground group. Never raises; ledger I/O must not
    break command execution."""
    if pgid is None:
        return
    try:
        from gateway.status import get_process_start_time
        start = get_process_start_time(proc.pid)
    except Exception:
        start = None
    entry: Dict[str, Any] = {
        "pgid": pgid,
        "leader_pid": proc.pid,
        "leader_start": start,
        "owner_pid": os.getpid(),
        "spawned_at": time.time(),
        "command": (command or "")[:200],
    }
    try:
        path = _ledger_path()
        entries = _read_ledger()
        # Replace any stale entry for this leader (should not happen; defensive).
        entries = [e for e in entries if e.get("leader_pid") != proc.pid]
        entries.append(entry)
        _write_ledger(entries)
    except Exception as e:
        logger.debug("fg-group ledger register failed: %s", e)


def unregister_spawned_group(proc) -> None:
    """Drop a finished group's entry. Never raises."""
    try:
        pid = getattr(proc, "pid", None)
        if pid is None:
            return
        entries = _read_ledger()
        kept = [e for e in entries if e.get("leader_pid") != pid]
        if len(kept) != len(entries):
            _write_ledger(kept)
    except Exception as e:
        logger.debug("fg-group ledger unregister failed: %s", e)


def _read_ledger() -> List[Dict[str, Any]]:
    path = _ledger_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_ledger(entries: List[Dict[str, Any]]) -> None:
    cutoff = time.time() - LEDGER_MAX_AGE_SECONDS
    pruned = [e for e in entries if float(e.get("spawned_at") or 0) >= cutoff]
    try:
        from utils import atomic_json_write
        atomic_json_write(_ledger_path(), pruned)
    except Exception:
        # Fall back to a direct write if the shared helper is unavailable.
        _ledger_path().write_text(json.dumps(pruned), encoding="utf-8")


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, not ours to signal — still alive
    except Exception:
        return True  # fail-safe: treat unreadable as alive (never reap on doubt)


def _leader_is_recorded_group(pgid: int, entry: Dict[str, Any]) -> bool:
    """The recorded leader still exists, still leads its own group, and still carries the
    spawn-time start fingerprint. A recycled PID/PGID fails the fingerprint and is never
    signalled (#43044 pattern, drift-tolerant per #117505)."""
    if pgid != int(entry.get("leader_pid") or -1):
        return False
    recorded_start = entry.get("leader_start")
    if recorded_start is None:
        return True  # no baseline: legacy best-effort (matches _leader_is_ours)
    try:
        from gateway.status import get_process_start_time, start_time_fingerprints_match
        current = get_process_start_time(pgid)
        if current is None:
            return True
        return start_time_fingerprints_match(recorded_start, current)
    except Exception:
        return True


def _reap_group(pgid: int) -> bool:
    """TERM the group, grace, then KILL. Returns True when the group was signalled."""
    try:
        os.killpg(pgid, signal.SIGTERM)  # posix-only module; callers gate on platform
    except ProcessLookupError:
        return False
    except PermissionError:
        return False
    deadline = time.monotonic() + TERM_GRACE_SECONDS
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            break
        time.sleep(0.1)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    return True


def maybe_reap_orphan_groups() -> int:
    """Once per interpreter: kill ledger groups whose owning Hermes process is dead.

    Called from the local-environment spawn path (same hook shape as
    ``_maybe_reap_docker_orphans``). Config gate ``terminal.fg_orphan_reaper: false``
    lets an operator with several Hermes processes sharing a profile opt out.
    Returns the number of groups reaped. Never raises.
    """
    global _reaper_ran
    if _reaper_ran:
        return 0
    _reaper_ran = True
    try:
        from hermes_cli.config import load_config
        cfg = (load_config() or {}).get("terminal") or {}
        if not cfg.get("fg_orphan_reaper", True):
            return 0
    except Exception:
        pass  # config unreadable: proceed with the conservative default
    return _reap_orphan_groups_now()


def _reap_orphan_groups_now() -> int:
    entries = _read_ledger()
    if not entries:
        return 0
    now = time.time()
    survivors: List[Dict[str, Any]] = []
    reaped = 0
    for entry in entries:
        try:
            pgid = int(entry.get("pgid") or 0)
            leader_pid = int(entry.get("leader_pid") or 0)
            owner_pid = int(entry.get("owner_pid") or 0)
            age = now - float(entry.get("spawned_at") or 0)
        except (TypeError, ValueError):
            continue
        if owner_pid == os.getpid():
            survivors.append(entry)  # ours: normal completion path unregisters it
            continue
        if owner_pid and _pid_alive(owner_pid):
            survivors.append(entry)  # a live sibling Hermes still supervises this group
            continue
        if age < REAP_MIN_AGE_SECONDS:
            survivors.append(entry)  # fresh: a slow shutdown may still clean up itself
            continue
        # Group gone already: just drop the entry.
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            continue
        except PermissionError:
            survivors.append(entry)
            continue
        except Exception:
            survivors.append(entry)
            continue
        if not _leader_is_recorded_group(pgid, entry):
            continue  # recycled PID: refuse to signal, drop the stale entry
        if _reap_group(pgid):
            reaped += 1
            logger.info(
                "Reaped orphaned foreground process group pgid=%d (dead owner pid=%d): %s",
                pgid, owner_pid, str(entry.get("command", ""))[:60])
    _write_ledger(survivors)
    return reaped
