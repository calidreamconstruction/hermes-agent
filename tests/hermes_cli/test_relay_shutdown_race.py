from types import SimpleNamespace

import pytest

from hermes_cli.observability import relay_shared_metrics


def _runtime(start_task):
    runtime = object.__new__(relay_shared_metrics._Runtime)
    session = SimpleNamespace(tasks={})
    runtime._task_session = lambda event, **kwargs: None
    runtime.start_task = start_task
    runtime._session_after_start = session
    return runtime, session


def test_task_pair_ignores_late_shutdown_hook():
    def closing(_event):
        raise RuntimeError("Hermes Relay session is closing")

    runtime, _ = _runtime(closing)
    assert runtime._task_pair({"task_id": "late"}, start=True) == (None, None)


def test_task_pair_preserves_unexpected_runtime_errors():
    def broken(_event):
        raise RuntimeError("database corruption")

    runtime, _ = _runtime(broken)
    with pytest.raises(RuntimeError, match="database corruption"):
        runtime._task_pair({"task_id": "bad"}, start=True)


def test_task_pair_keeps_normal_task_start():
    task = object()
    runtime, session = _runtime(lambda _event: task)
    runtime._task_session = lambda event, **kwargs: session
    assert runtime._task_pair({"task_id": "ok"}, start=True) == (session, task)
