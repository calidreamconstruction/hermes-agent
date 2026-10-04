"""Wave-02 false-success cluster: 517, 513, 519, 521, 515, 505.

Every test here fails on pre-fix code and passes after. All of it runs against
local fixtures and synthetic DOM -- no live authenticated site, no network.
"""

import json
from unittest.mock import patch

import pytest

from tools import browser_tool as bt
from tools.browser_tool import browser_navigate, browser_type

pytest_plugins = []


@pytest.fixture(autouse=True)
def _no_camofox(monkeypatch):
    """Keep these tests on the agent-browser path regardless of local env."""
    monkeypatch.delenv("CAMOFOX_URL", raising=False)
    monkeypatch.delenv("BROWSER_CDP_URL", raising=False)


# ---------------------------------------------------------------------------
# 517 -- a bot-challenged page must not report as a completed navigation
# ---------------------------------------------------------------------------


class TestItem517BotChallenge:
    """Pre-fix: navigate() returned success:true + a bot_detection_warning, i.e. a
    Cloudflare challenge was reported as a finished page load."""

    def test_challenge_title_is_not_a_successful_navigation(self):
        response = {"success": True, "url": "https://example.com/", "title": "Just a moment..."}
        bt._annotate_navigation_outcome(response, "https://example.com/", "https://example.com/", "k")

        assert response["success"] is False, "a bot challenge must not report as completed navigation"
        assert response["status"] == "challenged"
        assert response["challenged"] is True
        assert response["bot_challenged"] is True

    def test_challenge_preserves_diagnostics(self):
        response = {"success": True, "url": "https://example.com/", "title": "Checking your browser"}
        bt._annotate_navigation_outcome(response, "https://example.com/", "https://example.com/", "k")

        assert response["bot_detection_patterns"], "structured evidence must be preserved"
        assert response["bot_detection_warning"]
        assert response["error"], "the caller must be told the page did not load"
        assert response["url"] == "https://example.com/", "diagnostics must survive"

    def test_normal_page_still_succeeds(self):
        response = {"success": True, "url": "https://example.com/", "title": "Example Domain"}
        bt._annotate_navigation_outcome(response, "https://example.com/", "https://example.com/", "k")

        assert response["success"] is True
        assert "challenged" not in response
        assert "error" not in response

    def test_cloudflare_interstitial_title_is_caught(self):
        assert bt._challenge_patterns_in_title("Attention Required! | Cloudflare")

    def test_warn_mode_keeps_legacy_success(self):
        """The escape hatch: opt back into the old flag-only behaviour."""
        with patch.object(bt, "_bot_challenge_action", return_value="warn"):
            response = {"success": True, "title": "Just a moment..."}
            bt._annotate_navigation_outcome(response, "https://x.com/", "https://x.com/", "k")

        assert response["success"] is True, "warn mode must stay backward-compatible"
        assert response["bot_challenged"] is True, "but it must still be flagged"

    def test_end_to_end_navigate_reports_challenge_not_success(self):
        """Drives the real browser_navigate entry point with a stubbed command channel."""
        responses = {
            "open": {"success": True, "data": {"title": "Just a moment...", "url": "https://shop.example/cart"}},
            "snapshot": {"success": True, "data": {"snapshot": "checking your browser", "refs": {}}},
        }

        def fake_run(task_id, command, args=None, **kwargs):
            return responses.get(command, {"success": True, "data": {}})

        with patch("tools.browser_tool_session._run_browser_command", side_effect=fake_run), \
             patch.object(bt._session, "_get_session_info", return_value={"features": {"proxies": True}}), \
             patch.object(bt, "_url_policy_error", return_value=None), \
             patch.object(bt, "_secret_url_error_normalized", side_effect=lambda u: (u, None)), \
             patch.object(bt, "_navigation_session_key", return_value="h_test"), \
             patch.object(bt, "_is_local_sidecar_key", return_value=False), \
             patch.object(bt, "_maybe_start_recording"), \
             patch.object(bt, "_post_redirect_block", return_value=None):
            payload = json.loads(browser_navigate("https://shop.example/cart", task_id="t517"))

        assert payload["success"] is False, "the challenge must not read as a completed navigation"
        assert payload["status"] == "challenged"
        assert payload["bot_challenged"] is True
        # Diagnostics preserved, not swallowed.
        assert payload["url"] == "https://shop.example/cart"
        assert payload["bot_detection_warning"]
        assert payload.get("snapshot") is not None

    def test_end_to_end_normal_navigate_still_succeeds(self):
        """The compensating case: a genuinely good navigation must not regress."""
        responses = {
            "open": {"success": True, "data": {"title": "Example Domain", "url": "https://example.com/"}},
            "snapshot": {"success": True, "data": {"snapshot": "Example Domain body", "refs": {"a": 1}}},
        }

        def fake_run(task_id, command, args=None, **kwargs):
            return responses.get(command, {"success": True, "data": {}})

        with patch("tools.browser_tool_session._run_browser_command", side_effect=fake_run), \
             patch.object(bt._session, "_get_session_info", return_value={"features": {"proxies": True}}), \
             patch.object(bt, "_url_policy_error", return_value=None), \
             patch.object(bt, "_secret_url_error_normalized", side_effect=lambda u: (u, None)), \
             patch.object(bt, "_navigation_session_key", return_value="h_test"), \
             patch.object(bt, "_is_local_sidecar_key", return_value=False), \
             patch.object(bt, "_maybe_start_recording"), \
             patch.object(bt, "_post_redirect_block", return_value=None):
            payload = json.loads(browser_navigate("https://example.com/", task_id="t517b"))

        assert payload["success"] is True
        assert payload["title"] == "Example Domain"
        assert "challenged" not in payload


# ---------------------------------------------------------------------------
# 519 -- bounded reload-and-retry on failed navigation
# ---------------------------------------------------------------------------


class TestItem519ReloadRetry:
    """Pre-fix: one failed `open` returned an error immediately; the reload primitive
    existed but nothing called it."""

    def test_transient_failure_is_retried_then_succeeds(self):
        calls = []

        def fake_run(task_id, command, args=None, **kwargs):
            calls.append(command)
            if command == "open":
                # The first failure is the result passed IN, so the first open executed
                # here is already the retry: it recovers.
                return {"success": True, "data": {}}
            return {"success": True}

        with patch.object(bt._session, "_run_browser_command", side_effect=fake_run):
            result, used = bt._retry_navigation_with_reload("k", "https://x.com",
                                                             {"success": False, "error": "Connection closed"})

        assert result["success"] is True
        assert used == 1
        assert "reload" in calls, "the retry must actually reload the page"

    def test_retry_is_bounded(self):
        with patch.object(bt, "_get_navigate_retries", return_value=2), \
             patch.object(bt._session, "_run_browser_command",
                          return_value={"success": False, "error": "Connection closed"}) as mock_run:
            result, used = bt._retry_navigation_with_reload("k", "https://x.com",
                                                             {"success": False, "error": "Connection closed"})

        assert result["success"] is False
        assert used == 2, "exactly navigate_retries attempts, no storm"
        opens = [c for c in mock_run.call_args_list if c.args[1] == "open"]
        assert len(opens) == 2

    def test_policy_block_is_never_retried(self):
        """A denied/blocked navigation must fail on the first attempt, unchanged."""
        with patch.object(bt._session, "_run_browser_command") as mock_run:
            result, used = bt._retry_navigation_with_reload(
                "k", "https://x.com", {"success": False, "error": "Access denied by policy"})

        assert used == 0
        assert result["success"] is False
        mock_run.assert_not_called()

    def test_retry_disabled_preserves_original_error(self):
        with patch.object(bt, "_get_navigate_retries", return_value=0), \
             patch.object(bt._session, "_run_browser_command") as mock_run:
            result, used = bt._retry_navigation_with_reload(
                "k", "https://x.com", {"success": False, "error": "Navigation timed out"})

        assert used == 0
        assert result["error"] == "Navigation timed out"
        mock_run.assert_not_called()

    def test_retries_config_is_clamped(self):
        with patch("hermes_cli.config.read_raw_config",
                   return_value={"browser": {"navigate_retries": 9999}}):
            assert bt._get_navigate_retries() == bt.MAX_NAVIGATE_RETRIES
        with patch("hermes_cli.config.read_raw_config",
                   return_value={"browser": {"navigate_retries": -5}}):
            assert bt._get_navigate_retries() == 0

    def test_navigate_reports_retry_trail(self):
        """A caller must be able to distinguish a retried failure from a first-try one."""
        responses = {
            "open": {"success": False, "error": "Connection closed"},
            "reload": {"success": True, "data": {}},
        }

        def fake_run(task_id, command, args=None, **kwargs):
            return responses.get(command, {"success": True, "data": {}})

        with patch("tools.browser_tool_session._run_browser_command", side_effect=fake_run), \
             patch.object(bt._session, "_get_session_info", return_value={"features": {}}), \
             patch.object(bt, "_url_policy_error", return_value=None), \
             patch.object(bt, "_secret_url_error_normalized", side_effect=lambda u: (u, None)), \
             patch.object(bt, "_navigation_session_key", return_value="h_test"), \
             patch.object(bt, "_is_local_sidecar_key", return_value=False), \
             patch.object(bt, "_maybe_start_recording"):
            payload = json.loads(browser_navigate("https://example.com/", task_id="t519"))

        assert payload["success"] is False
        assert payload["navigation_retries"] == bt.DEFAULT_NAVIGATE_RETRIES
        assert payload["error"], "the original failure must still surface"


# ---------------------------------------------------------------------------
# 521 -- bounded re-find-and-retry on stale element detachment
# ---------------------------------------------------------------------------


class TestItem521StaleRefind:
    """Pre-fix: fill_input pre-waited, re-queried once, then raised."""

    def test_stale_detachment_is_retried_after_refind(self):
        calls = []

        def fake_run(task_id, command, args=None, **kwargs):
            calls.append(command)
            if command == "fill":
                # The detachment is the failure passed IN; the first fill executed here is
                # already the post-refind retry, and it succeeds.
                return {"success": True}
            return {"success": True}

        with patch.object(bt._session, "_run_browser_command", side_effect=fake_run):
            result, used = bt._retry_fill_after_stale_refind(
                "k", "@e1", "hello", {"success": False, "error": "Node is detached from document"})

        assert result["success"] is True
        assert used == 1
        assert "snapshot" in calls, "a stale ref must be re-found via a fresh snapshot"

    def test_refind_retries_are_bounded(self):
        with patch.object(bt._session, "_run_browser_command",
                          return_value={"success": False, "error": "stale element not found"}) as mock_run:
            result, used = bt._retry_fill_after_stale_refind(
                "k", "@e1", "hello", {"success": False, "error": "stale element not found"})

        assert result["success"] is False
        assert used == bt.MAX_STALE_REFIND_ATTEMPTS
        fills = [c for c in mock_run.call_args_list if c.args[1] == "fill"]
        assert len(fills) == bt.MAX_STALE_REFIND_ATTEMPTS

    def test_non_detachment_failure_is_not_retried(self):
        """A genuine write failure must surface exactly as it did before."""
        with patch.object(bt._session, "_run_browser_command") as mock_run:
            result, used = bt._retry_fill_after_stale_refind(
                "k", "@e1", "hello", {"success": False, "error": "Element not found"})

        assert used == 0
        assert result["error"] == "Element not found"
        mock_run.assert_not_called()

    def test_stale_detection_matches_real_agent_browser_errors(self):
        for message in ("Node is detached from document", "stale element reference",
                        "Execution context was destroyed", "Cannot find context with specified id"):
            assert bt._is_stale_detachment_error(message), message
        assert not bt._is_stale_detachment_error("Element not found")

    def test_end_to_end_type_recovers_from_stale_ref(self):
        def fake_run(task_id, command, args=None, **kwargs):
            if command == "fill":
                return {"success": True} if _state["fills"] > 1 else {
                    "success": False, "error": "Node is detached from document"}
            if command == "get":
                return {"success": True, "data": {"value": "hello"}}
            return {"success": True}

        _state = {"fills": 0}

        def counting_run(task_id, command, args=None, **kwargs):
            if command == "fill":
                _state["fills"] += 1
            return fake_run(task_id, command, args, **kwargs)

        with patch("tools.browser_tool_session._run_browser_command", side_effect=counting_run), \
             patch.object(bt, "_last_session_key", return_value="k"), \
             patch.object(bt, "_blocked_private_page_action", return_value=None):
            payload = json.loads(browser_type("@e1", "hello", task_id="t521"))

        assert payload["success"] is True
        assert payload["stale_refind_attempts"] == 1


# ---------------------------------------------------------------------------
# 513 -- readback after a browser write
# ---------------------------------------------------------------------------


class TestItem513WriteReadback:
    """Pre-fix: a write reported success with nothing reading the value back."""

    def test_matching_readback_verifies_the_write(self):
        def fake_run(task_id, command, args=None, **kwargs):
            if command == "fill":
                return {"success": True}
            if command == "get":
                return {"success": True, "data": {"value": "hello"}}
            return {"success": True}

        with patch("tools.browser_tool_session._run_browser_command", side_effect=fake_run), \
             patch.object(bt, "_last_session_key", return_value="k"), \
             patch.object(bt, "_blocked_private_page_action", return_value=None):
            payload = json.loads(browser_type("@e1", "hello", task_id="t513"))

        assert payload["success"] is True
        assert payload["write_verified"] is True
        assert payload["write_readback"]["performed"] is True
        assert payload["write_readback"]["matches"] is True

    def test_mismatched_readback_is_reported_not_swallowed(self):
        """The site rejected/reformatted the input: the write must not silently claim success."""
        def fake_run(task_id, command, args=None, **kwargs):
            if command == "fill":
                return {"success": True}
            if command == "get":
                return {"success": True, "data": {"value": "h***@example.com"}}
            return {"success": True}

        with patch("tools.browser_tool_session._run_browser_command", side_effect=fake_run), \
             patch.object(bt, "_last_session_key", return_value="k"), \
             patch.object(bt, "_blocked_private_page_action", return_value=None):
            payload = json.loads(browser_type("@e1", "hunter2", task_id="t513b"))

        assert payload["success"] is True, "a successful write must not be retro-failed"
        assert payload["write_verified"] is False
        assert payload["write_verification_warning"]

    def test_unavailable_readback_records_the_skip_reason(self):
        """Probe unavailable is a skip, not a hidden error and not a failed write."""
        def fake_run(task_id, command, args=None, **kwargs):
            if command == "fill":
                return {"success": True}
            if command == "get":
                return {"success": False, "error": "unknown command"}
            return {"success": True}

        with patch("tools.browser_tool_session._run_browser_command", side_effect=fake_run), \
             patch.object(bt, "_last_session_key", return_value="k"), \
             patch.object(bt, "_blocked_private_page_action", return_value=None):
            payload = json.loads(browser_type("@e1", "hello", task_id="t513c"))

        assert payload["success"] is True
        assert payload["write_readback"]["performed"] is False
        assert payload["write_readback"]["reason"]

    def test_readback_probe_raising_does_not_break_the_write(self):
        def fake_run(task_id, command, args=None, **kwargs):
            if command == "fill":
                return {"success": True}
            if command == "get":
                raise RuntimeError("daemon died mid-probe")
            return {"success": True}

        with patch("tools.browser_tool_session._run_browser_command", side_effect=fake_run), \
             patch.object(bt, "_last_session_key", return_value="k"), \
             patch.object(bt, "_blocked_private_page_action", return_value=None):
            payload = json.loads(browser_type("@e1", "hello", task_id="t513d"))

        assert payload["success"] is True
        assert payload["write_readback"]["performed"] is False

    def test_readback_never_echoes_the_typed_value(self):
        """A masked/rejected field must not leak the typed secret through the probe."""
        secret = "sk-live-9f8a7b6c5d4e"

        def fake_run(task_id, command, args=None, **kwargs):
            if command == "fill":
                return {"success": True}
            if command == "get":
                return {"success": True, "data": {"value": ""}}
            return {"success": True}

        with patch("tools.browser_tool_session._run_browser_command", side_effect=fake_run), \
             patch.object(bt, "_last_session_key", return_value="k"), \
             patch.object(bt, "_blocked_private_page_action", return_value=None):
            payload = json.loads(browser_type("@e1", secret, task_id="t513e"))

        assert secret not in json.dumps(payload), "typed value must not appear in the readback"
        assert payload["write_readback"]["expected_length"] == len(secret)

    def test_readback_can_be_disabled(self):
        with patch.object(bt, "_readback_on_write", return_value=False):
            response = {"success": True}
            bt._attach_write_readback(response, "k", "@e1", "hello")

        assert response["write_readback"]["performed"] is False
        assert "off" in response["write_readback"]["reason"]


# ---------------------------------------------------------------------------
# 515 -- login-redirect detection
# ---------------------------------------------------------------------------


class TestItem515LoginRedirect:
    def test_login_url_redirect_is_detected(self):
        markers = bt._login_redirect_markers("https://shop.example/cart", "https://shop.example/login?next=cart")
        assert markers

    def test_same_page_is_not_a_login_redirect(self):
        assert bt._login_redirect_markers("https://shop.example/cart", "https://shop.example/cart") == []

    def test_normal_cross_page_navigation_is_not_flagged(self):
        assert bt._login_redirect_markers("https://shop.example/", "https://shop.example/products/9") == []

    def test_sso_path_is_detected(self):
        assert bt._login_redirect_markers("https://app.example/reports", "https://app.example/sso/authorize")

    def test_response_is_annotated_with_diagnostics(self):
        response = {"success": True, "url": "https://shop.example/login", "title": "Sign in",
                    "snapshot": "Please sign in to continue"}
        bt._annotate_navigation_outcome(response, "https://shop.example/cart",
                                         "https://shop.example/login", "k")

        assert response["login_redirect"] is True
        assert response["login_redirect_markers"]
        assert response["requested_url"] == "https://shop.example/cart"
        assert response["login_redirect_warning"]
        # Additive only: the page really did load, so success must not flip.
        assert response["success"] is True

    def test_authenticated_page_is_not_flagged(self):
        response = {"success": True, "url": "https://shop.example/cart", "title": "Cart",
                    "snapshot": "Subtotal $42.00 Checkout"}
        bt._annotate_navigation_outcome(response, "https://shop.example/cart",
                                         "https://shop.example/cart", "k")

        assert "login_redirect" not in response


# ---------------------------------------------------------------------------
# 505 -- auth-expiry pre-flight probe
# ---------------------------------------------------------------------------


class TestItem505AuthExpiry:
    def test_session_expiry_is_detected(self):
        assert bt._auth_expiry_markers("Your session has expired. Please sign in again.")

    def test_normal_page_has_no_expiry_markers(self):
        assert bt._auth_expiry_markers("Cart Subtotal $42.00") == []

    def test_expired_session_is_reported_on_a_200_response(self):
        """The false-success shape: HTTP 200 plus an expired-session body."""
        response = {"success": True, "url": "https://app.example/dash", "title": "Dashboard",
                    "snapshot": "Your session has expired. Please sign in again."}
        bt._annotate_navigation_outcome(response, "https://app.example/dash", "https://app.example/dash", "k")

        assert response["auth_expired"] is True
        assert response["auth_expired_markers"]
        assert response["auth_expiry_warning"]

    def test_live_session_is_not_flagged(self):
        response = {"success": True, "url": "https://app.example/dash", "title": "Dashboard",
                    "snapshot": "Welcome back, Fares. Recent activity."}
        bt._annotate_navigation_outcome(response, "https://app.example/dash", "https://app.example/dash", "k")

        assert "auth_expired" not in response

    def test_probe_adds_no_extra_browser_call(self):
        """The probe must read the snapshot navigate already fetched -- no new traffic."""
        response = {"success": True, "url": "https://app.example/dash", "title": "Dashboard",
                    "snapshot": "Your session has expired."}
        with patch.object(bt._session, "_run_browser_command") as mock_run:
            bt._annotate_navigation_outcome(response, "https://app.example/dash",
                                             "https://app.example/dash", "k")

        mock_run.assert_not_called()  # 505/515 must probe text the page already produced


# ---------------------------------------------------------------------------
# Cross-cutting: no error that used to surface is now swallowed
# ---------------------------------------------------------------------------


class TestNoRegression:
    def test_hard_navigation_error_still_surfaces_verbatim(self):
        error = "Target page, context or browser has been closed"
        responses = {
            "open": {"success": False, "error": error},
            "reload": {"success": False, "error": error},
        }

        def fake_run(task_id, command, args=None, **kwargs):
            return responses.get(command, {"success": True, "data": {}})

        with patch("tools.browser_tool_session._run_browser_command", side_effect=fake_run), \
             patch.object(bt._session, "_get_session_info", return_value={"features": {}}), \
             patch.object(bt, "_url_policy_error", return_value=None), \
             patch.object(bt, "_secret_url_error_normalized", side_effect=lambda u: (u, None)), \
             patch.object(bt, "_navigation_session_key", return_value="h_test"), \
             patch.object(bt, "_is_local_sidecar_key", return_value=False), \
             patch.object(bt, "_maybe_start_recording"):
            payload = json.loads(browser_navigate("https://example.com/", task_id="tX"))

        assert payload["success"] is False
        assert error in payload["error"], "the original error must remain visible"

    def test_failed_write_still_reports_its_error(self):
        with patch("tools.browser_tool_session._run_browser_command",
                   return_value={"success": False, "error": "Element not found"}), \
             patch.object(bt, "_last_session_key", return_value="k"), \
             patch.object(bt, "_blocked_private_page_action", return_value=None):
            payload = json.loads(browser_type("@e1", "hello", task_id="tX2"))

        assert payload["success"] is False
        assert payload["error"] == "Element not found"

    def test_annotate_never_raises_on_missing_fields(self):
        for response in ({}, {"success": True}, {"title": None, "url": None, "snapshot": None}):
            bt._annotate_navigation_outcome(response, "", "", "k")
