"""protected_instruction_gate.py -- non-bypassable gate for agent-instruction files.

Ported 2026-10-02 from calidreamconstruction/hermes-agent
(fork of NousResearch/hermes-agent, HEAD 6604fd693065) tools/file_tools.py.
The fork's REAL delta: a lexical gate that blocks terminal/execute_code text
combining a file-mutation primitive (rm/mv/cp/tee/chmod/chown, sed -i,
perl -i, shell >/>> redirection, Python open(...,'wax+'),
Path.write_text/write_bytes/unlink/rename/replace, os.remove/unlink/rename/
replace, shutil.copy/copy2/copyfile/move) with a protected instruction
basename (AGENTS.md, CLAUDE.md, SOUL.md, .cursorrules). Runs BEFORE the
ordinary dangerous-command approval ladder so terminal force=True / YOLO
cannot skip it. Non-bypassable by design.

Kept as a standalone module (rather than spliced into tools/file_tools.py)
so the vps-customized local install is untouched except for thin call sites.
"""
from __future__ import annotations

import os
import re

def _expand_tilde(path: str) -> str:
    """Expand ``~`` using the effective profile home when available.

    In-process file tools share the gateway process's HOME, which may differ
    from the profile-specific HOME that interactive CLI sessions use.  This
    mirrors ``hermes_constants.get_subprocess_home()`` so that ``~`` resolves
    consistently regardless of whether the tool runs interactively or inside a
    gateway-driven cron job (#48552).
    """
    if not path or "~" not in path:
        return path
    try:
        from hermes_constants import get_subprocess_home

        home = get_subprocess_home()
    except Exception:
        home = None
    if home and (path == "~" or path.startswith("~/")):
        return home if path == "~" else os.path.join(home, path[2:])
    return os.path.expanduser(path)


#
# Scope decision (documented): basenames match in ANY directory, because
# project-context instruction files are loaded from cwd trees — an
# AGENTS.md anywhere the agent might later run from is a live target.
# Basenames match case-insensitively so case-variant spellings on
# case-insensitive filesystems (macOS/Windows) cannot slip past; on
# case-sensitive filesystems most loaders probe common case variants too,
# so the stricter behavior is kept uniform.
_PROTECTED_INSTRUCTION_BASENAMES = frozenset({
    "agents.md", "claude.md", "soul.md", ".cursorrules",
})

_real_hermes_home_cached: str | None = None
_real_hermes_home_loaded = False


def _get_real_hermes_home() -> str | None:
    """Return the realpath of the authoritative Hermes home (cached)."""
    global _real_hermes_home_cached, _real_hermes_home_loaded
    if _real_hermes_home_loaded:
        return _real_hermes_home_cached
    _real_hermes_home_loaded = True
    try:
        from hermes_constants import get_hermes_home
        _real_hermes_home_cached = os.path.realpath(str(get_hermes_home()))
    except Exception:
        try:
            _real_hermes_home_cached = os.path.realpath(_expand_tilde("~/.hermes"))
        except Exception:
            _real_hermes_home_cached = None
    return _real_hermes_home_cached


def _protected_instruction_config() -> tuple[bool, list[str]]:
    """Read the protected-instruction-files gate config.

    Returns ``(enabled, extra_patterns)``. Defaults to enabled with no extra
    patterns; config read failures keep the gate ON (fail-safe for a
    security boundary).

    Config keys (config.yaml)::

        security:
          protected_instruction_files: true       # default
          protected_instruction_extra_patterns: []  # fnmatch on basename
    """
    try:
        from hermes_cli.config import load_config, cfg_get
        cfg = load_config()
        enabled = cfg_get(cfg, "security", "protected_instruction_files",
                          default=True)
        extra = cfg_get(cfg, "security", "protected_instruction_extra_patterns",
                        default=[])
    except Exception:
        return True, []
    if not isinstance(enabled, bool):
        enabled = True
    if not isinstance(extra, list):
        extra = []
    return enabled, [str(p) for p in extra if p]


def _protected_instruction_reason(filepath: str, task_id: str = "default",
                                  *, enabled: bool | None = None,
                                  extra_patterns: list[str] | None = None) -> str | None:
    """Return a short label when ``filepath`` targets a protected
    agent-instruction file, else ``None``.

    Matching runs on BOTH the normalized input path and its realpath so
    neither a symlink pointing AT a protected file (#41351) nor a protected
    name that is itself a symlink escapes the gate. ``..`` traversal is
    neutralized by normpath/realpath before the basename compare.
    """
    if enabled is None or extra_patterns is None:
        enabled, extra_patterns = _protected_instruction_config()
    if not enabled:
        return None

    normalized = os.path.normpath(_expand_tilde(filepath))
    try:
        from tools.file_tools import _resolve_path_for_task as _rptf
        resolved = os.path.realpath(str(_rptf(filepath, task_id)))
    except (OSError, ValueError, RuntimeError):
        resolved = os.path.realpath(normalized)

    # The authoritative ~/.hermes home is governed by its own guards
    # (config.yaml hard-block, cross-profile guard, write_approval); this
    # gate targets PROJECT-LOCAL instruction files only. Checked before the
    # ``.hermes`` component rule below, which would otherwise match the
    # home directory itself.
    real_home = _get_real_hermes_home()
    if real_home and (resolved == real_home
                      or resolved.startswith(real_home + os.sep)):
        return None

    import fnmatch
    for candidate in (normalized, resolved):
        base = os.path.basename(candidate)
        base_lower = base.lower()
        if base_lower in _PROTECTED_INSTRUCTION_BASENAMES:
            return base
        for pattern in extra_patterns:
            if fnmatch.fnmatch(base_lower, pattern.lower()):
                return base
        # Project-local .hermes config dirs (e.g. <repo>/.hermes/config.yaml)
        # are loaded as project context and steer behavior the same way.
        # Scope: the file's IMMEDIATE parent must be ``.hermes`` — matching
        # any ancestor named .hermes would gate every write inside a
        # checkout that happens to live under ~/.hermes (e.g. the
        # hermes-agent repo itself at ~/.hermes/hermes-agent).
        parts = candidate.replace("\\", "/").rstrip("/").split("/")
        if len(parts) >= 2 and parts[-2] == ".hermes":
            return candidate
    return None


def _request_protected_instruction_approval(
        reasons: list[str], task_id: str = "default") -> str | None:
    """Ask the human to approve a write to protected instruction file(s).

    Returns ``None`` when approved, or a BLOCKED error string. This gate
    intentionally does NOT route through ``_run_approval_gate``: that gate
    honors --yolo and session/permanent allowlists, and the entire point
    here is one-operation approval EVERY time, with no persistent scope
    and no yolo bypass. Fail-closed when no human channel exists.
    """
    targets = ", ".join(dict.fromkeys(reasons))
    description = (
        f"Write to protected agent-instruction file(s): {targets}. "
        "These files steer future agent behavior; approval is always "
        "required (not bypassed by auto-approve)."
    )
    display = f"<write to {targets}>"
    blocked = (
        f"BLOCKED: write to protected agent-instruction file(s) ({targets}) "
        "{why} The user has NOT consented to this write. Do NOT retry it or "
        "attempt the same edit via another path (terminal, execute_code, "
        "etc.)."
    )

    try:
        import tools.approval as _approval
    except Exception:
        return blocked.format(why="requires approval but the approval "
                                  "subsystem is unavailable.")

    # Gateway surface: block on the button round-trip when a notify callback
    # is registered for this session (Telegram/Discord/Slack). One-operation
    # only — no session/permanent buttons are offered.
    session_key = _approval.get_current_session_key()
    notify_cb = None
    try:
        with _approval._lock:
            notify_cb = _approval._gateway_notify_cbs.get(session_key)
    except Exception:
        notify_cb = None

    if notify_cb is not None:
        approval_data = {
            "command": display,
            "pattern_key": "protected_instruction_file",
            "pattern_keys": ["protected_instruction_file"],
            "description": description,
            "allow_permanent": False,
            "allow_session": False,
        }
        decision = _approval._await_gateway_decision(
            session_key, notify_cb, approval_data, surface="gateway",
        )
        if decision.get("notify_failed"):
            return blocked.format(
                why="requires approval but the approval request could not "
                    "be delivered.")
        choice = decision.get("choice")
        if decision.get("resolved") and choice in {"once", "session", "always"}:
            # One-operation grant regardless of the tapped scope — nothing
            # is persisted for this gate.
            return None
        if not decision.get("resolved"):
            return blocked.format(
                why="approval prompt timed out without a user response. "
                    "Silence is not consent.")
        return blocked.format(why="was denied by the user.")

    # CLI surface: per-thread approval callback (prompt_toolkit panel).
    callback = None
    try:
        from tools.terminal_tool import _get_approval_callback
        callback = _get_approval_callback()
    except Exception:
        callback = None

    if callback is not None:
        choice = _approval.prompt_dangerous_approval(
            display, description,
            allow_permanent=False,
            approval_callback=callback,
        )
        if choice in {"once", "session", "always"}:
            # One-operation grant; never persisted (see docstring).
            return None
        if choice == "timeout":
            return blocked.format(
                why="approval prompt timed out without a user response. "
                    "Silence is not consent.")
        return blocked.format(why="was denied by the user.")

    # No human channel at all (script, cron, background thread): fail
    # closed. Auto-approving here would recreate the persistence vector.
    return blocked.format(
        why="requires approval but no interactive user or gateway is "
            "present to approve it.")


def _check_protected_instruction_write(paths: list[str],
                                       task_id: str = "default") -> str | None:
    """Gate a write/patch touching protected instruction files.

    Returns ``None`` when no target is protected or the human approved;
    otherwise a BLOCKED error string. For multi-file V4A patches, ONE
    protected file gates the ENTIRE patch: a single prompt lists every
    protected target, and a deny applies nothing (including innocent
    files) — partial application of an approved-in-part patch would be
    more surprising than an atomic all-or-nothing outcome.
    """
    enabled, extra = _protected_instruction_config()
    if not enabled:
        return None
    reasons: list[str] = []
    for p in paths:
        reason = _protected_instruction_reason(
            p, task_id, enabled=enabled, extra_patterns=extra)
        if reason:
            reasons.append(reason)
    if not reasons:
        return None
    return _request_protected_instruction_approval(reasons, task_id)


_PROTECTED_INSTRUCTION_MUTATION_RE = re.compile(
    r"(?:"
    r"(?:^|[;&|\s])(?:rm|mv|cp|install|touch|truncate|chmod|chown|tee)\b"
    r"|(?:^|[;&|\s])(?:sed\s+-[^\s;|]*i|perl\s+-[^\s;|]*i)\b"
    r"|(?:^|[^>])>{1,2}(?!>)"
    r"|\bopen\s*\([^)]{0,500},\s*['\"][wax+][^'\"]*['\"]"
    r"|\.(?:write_text|write_bytes|unlink|rename|replace)\s*\("
    r"|\bos\.(?:remove|unlink|rename|replace)\s*\("
    r"|\bshutil\.(?:copy|copy2|copyfile|move)\s*\("
    r")",
    re.IGNORECASE | re.DOTALL,
)


def _check_protected_instruction_command(text: str,
                                         task_id: str = "default") -> str | None:
    """Gate terminal/execute_code text that can mutate instruction files.

    File tools already know their exact destination paths. Shell and Python
    execution are less structured, so this intentionally uses a conservative
    lexical gate: a protected basename (or configured extra pattern) must be
    present together with a file-mutation primitive. Read-only references are
    left alone. The gate is non-bypassable by terminal ``force=True`` because
    callers invoke it before the normal dangerous-command approval ladder.
    """
    if not text or not _PROTECTED_INSTRUCTION_MUTATION_RE.search(text):
        return None
    enabled, extra = _protected_instruction_config()
    if not enabled:
        return None

    reasons: list[str] = []
    lowered = text.casefold()
    for basename in sorted(_PROTECTED_INSTRUCTION_BASENAMES):
        if basename.casefold() in lowered:
            reasons.append(basename)

    if extra:
        import fnmatch
        tokens = re.findall(r"[^\s'\"`<>|;&()]+", text)
        for token in tokens:
            base = os.path.basename(token.replace("\\", "/")).casefold()
            for pattern in extra:
                if fnmatch.fnmatch(base, pattern.casefold()):
                    reasons.append(base)
                    break

    if not reasons:
        return None
    return _request_protected_instruction_approval(reasons, task_id)
