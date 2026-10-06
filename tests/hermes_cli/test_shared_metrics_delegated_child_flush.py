"""A delegate_task child never blocks on the Relay flush barrier (2026-10-06 deadlock)."""

from types import SimpleNamespace

from agent.delegation_context import delegated_child_context
from hermes_cli.observability import relay_shared_metrics


def _runtime(calls):
    rt = object.__new__(relay_shared_metrics._Runtime)
    rt.relay = SimpleNamespace(subscribers=SimpleNamespace(flush=lambda: calls.append("flush")))
    rt._export = lambda: calls.append("export")
    return rt


def test_delegated_child_skips_blocking_flush_parent_still_flushes():
    calls = []
    rt = _runtime(calls)
    with delegated_child_context("child-session"):
        rt._flush_and_export("child flush failed")
    assert calls == []  # the barrier would wait on the parent's open delegate_task scope
    rt._flush_and_export("parent flush failed")
    assert calls == ["flush", "export"]
