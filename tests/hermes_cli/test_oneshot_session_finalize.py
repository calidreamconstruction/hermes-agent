import sys
from types import ModuleType

import pytest

import hermes_cli.oneshot as oneshot


def _module(name, **attrs):
    module = ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def _install_runtime(monkeypatch, agent_type, session_db):
    monkeypatch.setitem(sys.modules, "run_agent", _module("run_agent", AIAgent=agent_type))
    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.config",
        _module("hermes_cli.config", load_config=lambda: {"model": {"default": "m"}}),
    )
    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.models",
        _module("hermes_cli.models", detect_provider_for_model=lambda *_a, **_k: None),
    )
    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.runtime_provider",
        _module(
            "hermes_cli.runtime_provider",
            resolve_runtime_provider=lambda **_kwargs: {
                "api_key": "k",
                "base_url": "u",
                "provider": "p",
                "api_mode": "chat_completions",
                "credential_pool": None,
            },
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.tools_config",
        _module("hermes_cli.tools_config", _get_platform_tools=lambda *_a, **_k: set()),
    )
    monkeypatch.setattr(oneshot, "_create_session_db_for_oneshot", lambda: session_db)
    monkeypatch.setattr(oneshot, "get_fallback_chain", lambda _cfg: [])


def test_finalize_oneshot_agent_orders_memory_session_agent_and_db_cleanup():
    calls = []
    messages = [{"role": "user", "content": "hello"}]

    class FakeDB:
        def end_session(self, session_id, reason):
            calls.append(("end_session", session_id, reason))

        def close(self):
            calls.append(("db_close",))

    class FakeAgent:
        session_id = "oneshot-session"
        _session_messages = messages

        def shutdown_memory_provider(self, session_messages):
            calls.append(("memory", session_messages))

        def close(self):
            calls.append(("agent_close",))

    oneshot._finalize_oneshot_agent(
        FakeAgent(), FakeDB(), end_reason="oneshot_complete"
    )

    assert calls == [
        ("memory", messages),
        ("end_session", "oneshot-session", "oneshot_complete"),
        ("agent_close",),
        ("db_close",),
    ]


def test_run_agent_preserves_success_when_every_cleanup_step_fails(monkeypatch):
    calls = []

    class FakeDB:
        def end_session(self, session_id, reason):
            calls.append(("end_session", session_id, reason))
            raise RuntimeError("end failed")

        def close(self):
            calls.append(("db_close",))
            raise RuntimeError("db close failed")

    db = FakeDB()

    class FakeAgent:
        def __init__(self, **_kwargs):
            self.session_id = "oneshot-session"
            self._session_messages = ["message"]

        def chat(self, prompt):
            calls.append(("chat", prompt))
            return "original result"

        def shutdown_memory_provider(self, messages):
            calls.append(("memory", messages))
            raise RuntimeError("memory failed")

        def close(self):
            calls.append(("agent_close",))
            raise RuntimeError("agent close failed")

    _install_runtime(monkeypatch, FakeAgent, db)

    assert oneshot._run_agent("hello") == "original result"
    assert calls == [
        ("chat", "hello"),
        ("memory", ["message"]),
        ("end_session", "oneshot-session", "oneshot_complete"),
        ("agent_close",),
        ("db_close",),
    ]


def test_run_agent_preserves_original_failure_and_marks_session_failed(monkeypatch):
    calls = []
    original = ValueError("provider failed")

    class FakeDB:
        def end_session(self, session_id, reason):
            calls.append(("end_session", session_id, reason))

        def close(self):
            calls.append(("db_close",))

    db = FakeDB()

    class FakeAgent:
        def __init__(self, **_kwargs):
            self.session_id = "oneshot-session"
            self._session_messages = []

        def chat(self, prompt):
            calls.append(("chat", prompt))
            raise original

        def shutdown_memory_provider(self, messages):
            calls.append(("memory", messages))

        def close(self):
            calls.append(("agent_close",))

    _install_runtime(monkeypatch, FakeAgent, db)

    with pytest.raises(ValueError) as exc_info:
        oneshot._run_agent("hello")

    assert exc_info.value is original
    assert calls == [
        ("chat", "hello"),
        ("memory", []),
        ("end_session", "oneshot-session", "oneshot_failed"),
        ("agent_close",),
        ("db_close",),
    ]
