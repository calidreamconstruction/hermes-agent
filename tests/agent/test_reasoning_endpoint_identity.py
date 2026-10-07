"""Reasoning probes follow detected backend identity, never loopback/port guesses."""
from unittest.mock import Mock
import pytest
from agent import model_metadata
from agent.reasoning_params import ReasoningParamsMixin

class Agent(ReasoningParamsMixin):
    def __init__(self, url):
        self.base_url = self._base_url_lower = url
        self.provider = "custom"
        self.model = "exact-model"
        self.api_key = "fixture-key"
        self._ollama_supports_thinking_cached = Mock(return_value=True)
    def _is_openrouter_url(self):
        return False

@pytest.mark.parametrize("backend", ["lm-studio", "vllm", "llamacpp", None])
@pytest.mark.parametrize("port", [11434, 18765])
def test_non_ollama_never_receives_show_probe(monkeypatch, backend, port):
    detect = Mock(return_value=backend)
    monkeypatch.setattr(model_metadata, "detect_local_server_type", detect)
    agent = Agent(f"http://127.0.0.1:{port}/v1")
    assert agent._supports_reasoning_extra_body() is False
    agent._ollama_supports_thinking_cached.assert_not_called()

@pytest.mark.parametrize("url", ["http://localhost:18765/v1", "http://[::1]:18765/v1", "http://127.0.0.1:11439/v1"])
def test_detected_ollama_at_arbitrary_port_preserves_capability(monkeypatch, url):
    detect = Mock(return_value="ollama")
    monkeypatch.setattr(model_metadata, "detect_local_server_type", detect)
    agent = Agent(url)
    assert agent._supports_reasoning_extra_body() is True
    detect.assert_called_once_with(url, api_key="fixture-key")
    agent._ollama_supports_thinking_cached.assert_called_once_with()


def test_failed_detection_does_not_guess_ollama(monkeypatch):
    monkeypatch.setattr(model_metadata, "detect_local_server_type", Mock(side_effect=RuntimeError("unavailable")))
    agent = Agent("http://localhost:11434/v1")
    assert agent._supports_reasoning_extra_body() is False
    agent._ollama_supports_thinking_cached.assert_not_called()


def test_cloud_ollama_keeps_existing_exact_host_path(monkeypatch):
    detect = Mock(side_effect=AssertionError("local discovery is unnecessary"))
    monkeypatch.setattr(model_metadata, "detect_local_server_type", detect)
    agent = Agent("https://ollama.com/v1")
    assert agent._supports_reasoning_extra_body() is True
    detect.assert_not_called()

@pytest.mark.parametrize("backend", ["vllm", "ollama"])
def test_actual_http_discovery_and_native_capability_probe(monkeypatch, backend):
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from agent.reasoning_params import ReasoningParamsMixin
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            calls.append(("GET", self.path))
            data = {"models": []} if backend == "ollama" and self.path == "/api/tags" else ({"version": "fixture"} if backend == "vllm" and self.path == "/version" else None)
            self.send_response(200 if data is not None else 404)
            self.end_headers()
            self.wfile.write(json.dumps(data or {}).encode())
        def do_POST(self):
            calls.append(("POST", self.path))
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"capabilities": ["thinking"]}).encode())
    monkeypatch.setattr(model_metadata, "_local_probe_disk_get", lambda *args: None)
    monkeypatch.setattr(model_metadata, "_local_probe_disk_put", lambda *args: None)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        agent = Agent(f"http://127.0.0.1:{server.server_port}/v1")
        del agent._ollama_supports_thinking_cached  # native HTTP method, not a mock
        first = agent._supports_reasoning_extra_body()
        after_first = list(calls)
        second = agent._supports_reasoning_extra_body()
        assert first is second is (backend == "ollama")
        assert calls == after_first  # second turn reuses backend and capability caches
        assert calls.count(("POST", "/api/show")) == (1 if backend == "ollama" else 0)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
