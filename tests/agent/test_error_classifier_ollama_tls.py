"""Regression: upstream TLS verification behind HTTP502 is not transient."""
import httpx
import pytest
from openai import APIStatusError
from agent.error_classifier import FailoverReason, classify_api_error

@pytest.mark.parametrize("status", [500, 502, 503, 504, 526])
def test_wrapped_cert_failure_fails_fast(status):
    detail = 'Post "https://ollama.com:443/v1/chat/completions": tls: failed to verify certificate: x509: "www.routerlogin.net" certificate is not standards compliant'
    response = httpx.Response(status, request=httpx.Request("POST", "http://127.0.0.1:11434/v1/chat/completions"))
    error = APIStatusError(detail, response=response, body={"error": detail})
    result = classify_api_error(error, provider="ollama-launch", approx_tokens=172000, context_length=262144)
    assert result.reason is FailoverReason.ssl_cert_verification
    assert result.retryable is False
    assert result.should_compress is False
    assert result.should_rotate_credential is False
    assert result.should_fallback is True

@pytest.mark.parametrize("detail", ["upstream temporarily unavailable", "net/http: TLS handshake timeout"])
def test_transient_gateway_failure_keeps_retry(detail):
    response = httpx.Response(502, request=httpx.Request("POST", "http://127.0.0.1:11434/v1/chat/completions"))
    result = classify_api_error(APIStatusError(detail, response=response, body={"error": detail}), provider="ollama-launch")
    assert result.retryable is True
    assert result.reason is not FailoverReason.ssl_cert_verification
