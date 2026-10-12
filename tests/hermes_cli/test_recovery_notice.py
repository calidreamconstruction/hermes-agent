"""Crash-recovery startup notice: a session killed mid-turn must tell the user
how to pick it back up.

The exit summary prints the resume hint only on a CLEAN exit. SIGHUP/SIGKILL/OOM
deaths never reach it, so the last interactive session ends with no record of how
to continue — even though the transcript is fully persisted in state.db. The
notice closes that gap: on chat startup, an ``interrupted`` MRU session gets a
one-line resume command on stderr.

Suppression matrix (each verified below): already resuming, quiet mode,
stream-json (structured stdout), the HERMES_NO_RECOVERY_NOTICE opt-out, a
complete/empty/error MRU session, a missing session, and any internal failure.
"""

import os

import pytest

from hermes_cli import recovery_notice


class FakeArgs:
    """Minimal argparse-shaped object for the gate checks."""

    def __init__(self, *, resume=None, continue_last=False, quiet=False):
        self.resume = resume
        self.continue_last = continue_last
        self.quiet = quiet


class _FakeSessionDB:
    """Stand-in for SessionDB under the conftest's isolated HERMES_HOME (real
    sessions live in the developer's home, which tests must not read)."""

    def __init__(self, statuses, sessions):
        self._statuses = statuses
        self._sessions = sessions

    def session_lifecycle_statuses(self, ids):
        return {sid: self._statuses.get(sid, "empty") for sid in ids}

    def get_session(self, sid):
        return self._sessions.get(sid)

    def close(self):
        pass


def _patch_state_db(monkeypatch, statuses, sessions=None):
    import hermes_state

    fake = _FakeSessionDB(statuses, sessions or {})
    monkeypatch.setattr(hermes_state, "SessionDB", lambda read_only=False: fake)


INTERRUPTED_SESSION = "20261009_115135_bee560"
COMPLETE_SESSION = "20261011_031637_73d08b"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("HERMES_NO_RECOVERY_NOTICE", raising=False)
    monkeypatch.delenv("HERMES_QUIET", raising=False)


def _patch_latest(monkeypatch, session_id):
    import hermes_cli.main as m
    monkeypatch.setattr(m, "_latest_session_id", lambda use_tui: session_id)
    monkeypatch.setattr(m, "_resolve_use_tui", lambda args: False)


def test_interrupted_session_prints_notice(monkeypatch, capsys):
    _patch_latest(monkeypatch, INTERRUPTED_SESSION)
    _patch_state_db(
        monkeypatch,
        {INTERRUPTED_SESSION: "interrupted"},
        {INTERRUPTED_SESSION: {"display_name": "Upgrade local models and controllers"}},
    )
    result = recovery_notice.print_interrupted_session_notice(FakeArgs())
    assert result == INTERRUPTED_SESSION
    err = capsys.readouterr().err
    assert "interrupted mid-turn" in err
    assert f"hermes --resume {INTERRUPTED_SESSION}" in err
    assert "Upgrade local models" in err


def test_complete_session_prints_nothing(monkeypatch, capsys):
    _patch_latest(monkeypatch, COMPLETE_SESSION)
    _patch_state_db(monkeypatch, {COMPLETE_SESSION: "complete"})
    assert recovery_notice.print_interrupted_session_notice(FakeArgs()) is None
    assert capsys.readouterr().err == ""


def test_empty_session_prints_nothing(monkeypatch, capsys):
    _patch_latest(monkeypatch, "some-empty-session")
    _patch_state_db(monkeypatch, {})
    assert recovery_notice.print_interrupted_session_notice(FakeArgs()) is None
    assert capsys.readouterr().err == ""


def test_error_session_prints_nothing(monkeypatch, capsys):
    _patch_latest(monkeypatch, "some-error-session")
    _patch_state_db(monkeypatch, {"some-error-session": "error"})
    assert recovery_notice.print_interrupted_session_notice(FakeArgs()) is None
    assert capsys.readouterr().err == ""


def test_resuming_suppresses_notice(monkeypatch, capsys):
    _patch_latest(monkeypatch, INTERRUPTED_SESSION)
    assert recovery_notice.print_interrupted_session_notice(FakeArgs(resume="x")) is None
    assert capsys.readouterr().err == ""


def test_continue_last_suppresses_notice(monkeypatch, capsys):
    _patch_latest(monkeypatch, INTERRUPTED_SESSION)
    assert recovery_notice.print_interrupted_session_notice(FakeArgs(continue_last=True)) is None
    assert capsys.readouterr().err == ""


def test_quiet_suppresses_notice(monkeypatch, capsys):
    _patch_latest(monkeypatch, INTERRUPTED_SESSION)
    assert recovery_notice.print_interrupted_session_notice(FakeArgs(quiet=True)) is None
    assert capsys.readouterr().err == ""


def test_hermes_quiet_env_suppresses_notice(monkeypatch, capsys):
    monkeypatch.setenv("HERMES_QUIET", "1")
    _patch_latest(monkeypatch, INTERRUPTED_SESSION)
    assert recovery_notice.print_interrupted_session_notice(FakeArgs()) is None
    assert capsys.readouterr().err == ""


def test_optout_env_suppresses_notice(monkeypatch, capsys):
    monkeypatch.setenv("HERMES_NO_RECOVERY_NOTICE", "1")
    _patch_latest(monkeypatch, INTERRUPTED_SESSION)
    assert recovery_notice.print_interrupted_session_notice(FakeArgs()) is None
    assert capsys.readouterr().err == ""


def test_missing_session_is_noop(monkeypatch, capsys):
    _patch_latest(monkeypatch, "nonexistent-session-id-xyz")
    _patch_state_db(monkeypatch, {})
    assert recovery_notice.print_interrupted_session_notice(FakeArgs()) is None
    assert capsys.readouterr().err == ""


def test_no_previous_session_is_noop(monkeypatch, capsys):
    _patch_latest(monkeypatch, None)
    assert recovery_notice.print_interrupted_session_notice(FakeArgs()) is None
    assert capsys.readouterr().err == ""


def test_internal_failure_never_raises(monkeypatch, capsys):
    """A broken lookup must degrade to silence, never break startup."""
    import hermes_cli.main as m

    def _boom(use_tui):
        raise RuntimeError("state.db exploded")

    monkeypatch.setattr(m, "_latest_session_id", _boom)
    monkeypatch.setattr(m, "_resolve_use_tui", lambda args: False)
    assert recovery_notice.print_interrupted_session_notice(FakeArgs()) is None
    assert capsys.readouterr().err == ""
