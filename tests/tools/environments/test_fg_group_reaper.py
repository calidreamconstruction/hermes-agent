"""Orphaned foreground process-group reaper (crash recovery).

A Hermes that dies WITHOUT firing atexit (SIGKILL, OOM, host power loss) leaves its
foreground command groups running under init. The ledger reaper at the next startup
kills exactly those groups — and only those — while:

- skipping groups whose owner Hermes PID is still alive (a live sibling supervises them),
- skipping groups younger than the age floor (a slow shutdown cleans up itself),
- refusing to signal a group whose leader start fingerprint no longer matches the
  spawn-time baseline (PID/PGID recycling onto a stranger, #43044 pattern),
- never touching a group it does not own (ledger-only, never a ppid==1 sweep).
"""

import json
import os
import signal
import subprocess
import sys
import time

import pytest

from tools.environments import fg_group_ledger


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    path = tmp_path / "fg_groups.json"
    monkeypatch.setattr(fg_group_ledger, "_ledger_path", lambda: path)
    monkeypatch.setattr(fg_group_ledger, "_reaper_ran", False)
    return path


def _spawn_group() -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


def _entry(proc, *, owner_pid, age_s=3600.0, leader_start=None) -> dict:
    return {
        "pgid": os.getpgid(proc.pid),
        "leader_pid": proc.pid,
        "leader_start": leader_start,
        "owner_pid": owner_pid,
        "spawned_at": time.time() - age_s,
        "command": "grep -rIl ... /home",
    }


def _alive(proc) -> bool:
    return proc.poll() is None


def _write(ledger, entries):
    ledger.write_text(json.dumps(entries), encoding="utf-8")


def test_reaps_group_whose_owner_is_dead(ledger):
    proc = _spawn_group()
    try:
        pgid = os.getpgid(proc.pid)
        _write(ledger, [_entry(proc, owner_pid=999_999)])
        assert _alive(proc)
        reaped = fg_group_ledger._reap_orphan_groups_now()
        assert reaped == 1
        time.sleep(0.3)
        assert not _alive(proc)
        try:
            os.killpg(pgid, 0)
            assert False, "group should be gone"
        except ProcessLookupError:
            pass
        assert json.loads(ledger.read_text()) == []
    finally:
        with pytest.raises(Exception):
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)


def test_keeps_group_whose_owner_is_alive(ledger):
    proc = _spawn_group()
    try:
        _write(ledger, [_entry(proc, owner_pid=os.getpid())])
        reaped = fg_group_ledger._reap_orphan_groups_now()
        assert reaped == 0
        assert _alive(proc)
        # entry survives: this process still owns it
        assert len(json.loads(ledger.read_text())) == 1
    finally:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)


def test_keeps_group_younger_than_floor(ledger):
    proc = _spawn_group()
    try:
        _write(ledger, [_entry(proc, owner_pid=999_999, age_s=5.0)])
        reaped = fg_group_ledger._reap_orphan_groups_now()
        assert reaped == 0
        assert _alive(proc)
        assert len(json.loads(ledger.read_text())) == 1
    finally:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)


def test_refuses_recycled_pid_with_mismatched_fingerprint(ledger):
    proc = _spawn_group()
    try:
        # Baseline deliberately wrong: the leader's real start time differs, so the
        # identity check must refuse to signal even though the owner is dead.
        _write(ledger, [_entry(proc, owner_pid=999_999, leader_start=1)])
        reaped = fg_group_ledger._reap_orphan_groups_now()
        assert reaped == 0
        assert _alive(proc), "mismatched fingerprint must not signal the group"
        assert json.loads(ledger.read_text()) == []
    finally:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)


def test_prunes_entry_for_dead_group(ledger):
    proc = _spawn_group()
    pgid = os.getpgid(proc.pid)
    entry = _entry(proc, owner_pid=999_999)
    os.killpg(pgid, signal.SIGKILL)
    proc.wait()
    assert entry["pgid"] == pgid
    _write(ledger, [entry])
    reaped = fg_group_ledger._reap_orphan_groups_now()
    assert reaped == 0
    assert json.loads(ledger.read_text()) == []


def test_register_unregister_roundtrip(ledger):
    proc = _spawn_group()
    try:
        fg_group_ledger.register_spawned_group(proc, os.getpgid(proc.pid), "sleep 120")
        entries = json.loads(ledger.read_text())
        assert len(entries) == 1
        assert entries[0]["leader_pid"] == proc.pid
        assert entries[0]["owner_pid"] == os.getpid()
        fg_group_ledger.unregister_spawned_group(proc)
        assert json.loads(ledger.read_text()) == []
    finally:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)


def test_empty_ledger_is_noop(ledger):
    assert fg_group_ledger._reap_orphan_groups_now() == 0


def test_corrupt_ledger_is_noop(ledger):
    ledger.write_text("not json{{{", encoding="utf-8")
    assert fg_group_ledger._reap_orphan_groups_now() == 0
