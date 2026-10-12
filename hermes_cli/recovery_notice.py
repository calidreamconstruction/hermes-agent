"""Startup recovery notice: tell the user how to pick a crashed session back up.

The exit summary (``cli_session_mixin._print_exit_summary``) prints the resume
hint only on a CLEAN exit. A session killed by SIGHUP/SIGKILL, an OOM event, or
a host power loss never reaches it — the user's last interactive session then
ends with no record of how to continue it, and every crash looks like lost work
even though the transcript is fully persisted in state.db.

This module closes that gap at the producer boundary: on chat startup, when the
most-recent session for this interface ended ``interrupted`` (its last message
row is a user/tool row, or an assistant row with pending tool_calls — see
``classify_session_status``), print a one-line notice with the exact resume
command. Deterministic, zero LLM calls, zero network — reads state.db only.

Suppressed when:
- the user is already resuming a session (``--resume``/``--continue`` present),
- quiet/stream-json modes (structured stdout is a protocol),
- HERMES_NO_RECOVERY_NOTICE=1 (operator opt-out),
- the MRU session is not ``interrupted`` (nothing was lost mid-turn),
- anything at all fails — a notice must never break startup.
"""

from __future__ import annotations

import os
import sys
from typing import Optional


def _notice_enabled(args) -> bool:
    if os.environ.get("HERMES_NO_RECOVERY_NOTICE", "").strip() == "1":
        return False
    # Already continuing: the notice would be noise.
    if getattr(args, "resume", None) or getattr(args, "continue_last", False):
        return False
    # Structured stdout is a protocol — never print prose into it.
    try:
        from hermes_cli.stream_json import stream_json_requested
        if stream_json_requested(args):
            return False
    except Exception:
        pass
    if getattr(args, "quiet", False) or os.environ.get("HERMES_QUIET", "") == "1":
        return False
    return True


def print_interrupted_session_notice(args) -> Optional[str]:
    """Print the resume notice for an interrupted MRU session; returns the session id noticed.

    Never raises — any failure is swallowed (a notice is convenience, never a
    startup dependency). Returns None when nothing was printed.
    """
    if not _notice_enabled(args):
        return None
    try:
        from hermes_cli.main import _latest_session_id, _resolve_use_tui
        use_tui = _resolve_use_tui(args)
        last_id = _latest_session_id(use_tui)
        if not last_id:
            return None
        from hermes_state import SessionDB
        db = SessionDB(read_only=True)
        try:
            statuses = db.session_lifecycle_statuses([last_id])
        finally:
            db.close()
        status = statuses.get(last_id)
        if status != "interrupted":
            return None  # complete/error/empty — no mid-turn work was lost
        session = None
        db2 = SessionDB(read_only=True)
        try:
            session = db2.get_session(last_id)
        finally:
            db2.close()
        title = (session or {}).get("display_name") or (session or {}).get("title") or ""
        title_part = f" ({title[:40]})" if title else ""
        print(
            f"↩ previous session {last_id}{title_part} was interrupted mid-turn "
            f"(crash/kill). Its transcript is saved.",
            file=sys.stderr,
        )
        print(
            f"  pick it back up with:  hermes --resume {last_id}",
            file=sys.stderr,
        )
        return last_id
    except Exception:
        return None
