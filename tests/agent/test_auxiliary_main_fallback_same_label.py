"""Main-agent safety net when the aux task and the main model share a generic
provider label (e.g. "custom") but point at different endpoints."""
from unittest.mock import MagicMock, patch

from agent import auxiliary_client as ac


def _run(main_base, failed_base):
    sentinel = MagicMock()
    with patch.object(ac, "_read_main_provider", return_value="custom"), \
         patch.object(ac, "_read_main_model", return_value="auto"), \
         patch.object(ac, "_read_main_base_url", return_value=main_base), \
         patch.object(ac, "_is_provider_unhealthy", return_value=False), \
         patch.object(ac, "resolve_provider_client", return_value=(sentinel, "auto")) as rpc:
        out = ac._try_main_agent_model_fallback(
            "custom", "compression", reason="connection error", failed_base_url=failed_base)
    return out, rpc, sentinel


def test_same_label_different_endpoint_falls_back_to_main():
    (client, model, label), rpc, sentinel = _run("http://127.0.0.1:8765/v1", "http://127.0.0.1:11434/v1/")
    assert client is sentinel and model == "auto" and label == "main-agent(custom)"
    assert rpc.call_args.kwargs["explicit_base_url"] == "http://127.0.0.1:8765/v1"


def test_same_label_same_endpoint_does_not_retry_same_backend():
    (client, _, _), rpc, _ = _run("http://127.0.0.1:8765/v1", "http://127.0.0.1:8765/v1/")
    assert client is None and not rpc.called


def test_same_label_unknown_failed_endpoint_keeps_old_skip():
    (client, _, _), rpc, _ = _run("http://127.0.0.1:8765/v1", "")
    assert client is None and not rpc.called
