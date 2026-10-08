"""A route chosen before the first turn survives durable session resume."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("selection", ["startup", "switch"])
def test_initial_route_survives_resume(tmp_path, selection):
    env = dict(os.environ, HERMES_HOME=str(tmp_path), HERMES_DISABLE_LAZY_INSTALLS="1")
    env.pop("HERMES_RUNTIME_DIR", None)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), selection], env=env,
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _exercise_native_cli(selection):
    from unittest.mock import patch

    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    home = Path(os.environ["HERMES_HOME"])
    home.mkdir(parents=True, exist_ok=True)
    default_url, selected_url = "http://127.0.0.1:11439/v1", "http://127.0.0.1:11434/v1"
    model = "qwen3.6:35b"
    cfg = {
        "model": {"default": "qwen3-coder:30b", "provider": "route-default", "base_url": default_url,
                  "ollama_num_ctx": 262144},
        "providers": {
            name: {"api": url, "api_key": "test-only", "default_model": model,
                   "models": [{"id": model}]} for name, url in
            (("route-default", default_url), ("route-selected", selected_url))},
        "agent": {"reasoning_effort": "high"},
        "mcp_servers": {}, "fallback_providers": [], "fallback_model": None,
        "auxiliary": {"title_generation": {"enabled": False}},
        "display": {"streaming": False},
    }
    (home / "config.yaml").write_text(json.dumps(cfg), encoding="utf-8")
    fixture = home / "nonce.txt"
    nonce = "session-route-contract-7f386"
    fixture.write_text(nonce, encoding="utf-8")

    def deny_network(event, args):
        if event == "socket.connect":
            raise RuntimeError("network forbidden in session route contract")

    sys.addaudithook(deny_network)
    import httpx
    routes = []
    wire_options = []

    def send(client, request, *args, **kwargs):
        if request.method == "GET" and request.url.path.endswith("/models"):
            return httpx.Response(200, request=request, json={
                "object": "list", "data": [{"id": model, "object": "model"}]})
        assert request.method == "POST" and request.url.path.endswith("/chat/completions")
        payload = json.loads(request.content)
        routes.append((str(request.url), payload["model"]))
        wire_options.append({k: payload[k] for k in ("options", "reasoning_effort", "reasoning") if k in payload})
        results = [m for m in payload["messages"] if m.get("role") == "tool"]
        if results:
            assert nonce in str(results[-1]["content"])
            message, reason = {"role": "assistant", "content": nonce}, "stop"
        else:
            assert any(t["function"]["name"] == "read_file" for t in payload["tools"])
            message, reason = {"role": "assistant", "content": None, "tool_calls": [{
                "id": "call_read", "type": "function", "function": {
                    "name": "read_file", "arguments": json.dumps({"path": str(fixture)})}}]}, "tool_calls"
        body = {"id": "chatcmpl-test", "object": "chat.completion", "created": 1,
                "model": payload["model"], "choices": [{"index": 0, "message": message,
                    "finish_reason": reason}],
                "usage": {"prompt_tokens": 200, "completion_tokens": 30, "total_tokens": 230}}
        if payload.get("stream"):
            body["object"] = "chat.completion.chunk"
            if message.get("tool_calls"):
                message["tool_calls"][0]["index"] = 0
            body["choices"] = [{"index": 0, "delta": message, "finish_reason": reason}]
            return httpx.Response(200, request=request, headers={"content-type": "text/event-stream"},
                                  content="data: " + json.dumps(body) + "\n\ndata: [DONE]\n\n")
        return httpx.Response(200, request=request, json=body)

    with patch.object(httpx.Client, "send", send):
        from cli import HermesCLI
        selected = {"model": model, "provider": "route-selected"} if selection == "startup" else {}
        first = HermesCLI(compact=True, ignore_rules=True, toolsets=["file"], **selected)
        assert first._ensure_runtime_credentials()
        if selection == "switch":
            first._handle_model_switch(f"/model {model} --provider route-selected --session")
        assert first._init_agent()
        result = first.agent.run_conversation("Read the fixture and repeat its nonce.")
        assert result["final_response"] == nonce
        assert routes == [(selected_url + "/chat/completions", model)] * 2
        assert wire_options[0]["options"]["num_ctx"] == 262144
        assert wire_options[0]["reasoning_effort"] == "high"
        second = HermesCLI(compact=True, ignore_rules=True, toolsets=["file"], resume=first.session_id)
        assert second._init_agent()
        result = second.agent.run_conversation("Repeat the nonce.", conversation_history=second.conversation_history)
        assert result["final_response"] == nonce
        assert routes[-1] == routes[0], f"resume changed the outgoing route: {routes}"
        assert second.requested_provider == "route-selected"
        assert second.agent.provider == first.agent.provider == "custom"
        assert second.agent.requested_provider == "route-selected"
        assert wire_options[-1] == wire_options[0], f"resume changed provider request shaping: {wire_options}"
        # Mid-chat resume must keep the named route through later primary-runtime restoration.
        second._restore_session_model(second._session_db.get_session(first.session_id))
        assert second.agent.provider == "custom"
        assert second.agent.requested_provider == "route-selected"
        assert second.agent._primary_runtime["requested_provider"] == "route-selected"
        first.agent.close()
        second.agent.close()
        first._session_db.close()


if __name__ == "__main__":
    _exercise_native_cli(sys.argv[1])
