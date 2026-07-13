"""Regression tests for production writers and unscoped Git mutations."""

import pytest

from tools.approval import check_all_command_guards, detect_dangerous_command


@pytest.mark.parametrize(
    ("command", "expected_description"),
    [
        (
            "wrangler pages deploy public --project-name tradecalcs",
            "direct Cloudflare production deployment",
        ),
        (
            "npx wrangler@4.95.0 pages deploy . --project-name=tradecalcs",
            "direct Cloudflare production deployment",
        ),
        ("wrangler deploy", "direct Cloudflare production deployment"),
        ("firebase deploy --only hosting", "direct Firebase production deployment"),
        ("git add -A", "broad Git staging"),
        ("git add --all", "broad Git staging"),
        ("git add .", "broad Git staging"),
        ("git commit -am 'broad'", "broad Git commit"),
        ("git commit --all -m 'broad'", "broad Git commit"),
    ],
)
def test_production_writers_and_broad_git_require_approval(
    command: str,
    expected_description: str,
):
    dangerous, _pattern_key, description = detect_dangerous_command(command)

    assert dangerous, command
    assert description == expected_description


@pytest.mark.parametrize(
    "command",
    [
        "wrangler pages project list",
        "wrangler whoami",
        "firebase projects:list",
        "git add -- scripts/a.py tests/test_a.py",
        "git commit -m 'exact'",
        "git status",
    ],
)
def test_read_only_provider_and_exact_path_git_commands_remain_unblocked(command: str):
    dangerous, _pattern_key, description = detect_dangerous_command(command)

    assert not dangerous, (command, description)


@pytest.mark.parametrize(
    "command",
    [
        "wrangler pages deploy public --project-name tradecalcs",
        "git add -A",
    ],
)
def test_unattended_cron_denies_protected_writers(command: str, monkeypatch):
    monkeypatch.setenv("HERMES_CRON_SESSION", "1")
    monkeypatch.delenv("HERMES_INTERACTIVE", raising=False)
    monkeypatch.delenv("HERMES_GATEWAY_SESSION", raising=False)
    monkeypatch.delenv("HERMES_EXEC_ASK", raising=False)
    monkeypatch.delenv("HERMES_YOLO_MODE", raising=False)
    monkeypatch.setattr("tools.approval._get_cron_approval_mode", lambda: "deny")

    result = check_all_command_guards(command, "local")

    assert not result["approved"]
    assert "BLOCKED" in result["message"]


@pytest.mark.parametrize(
    "command",
    [
        "wrangler pages project list",
        "git add -- scripts/a.py tests/test_a.py",
    ],
)
def test_unattended_cron_keeps_safe_work_available(command: str, monkeypatch):
    monkeypatch.setenv("HERMES_CRON_SESSION", "1")
    monkeypatch.delenv("HERMES_INTERACTIVE", raising=False)
    monkeypatch.delenv("HERMES_GATEWAY_SESSION", raising=False)
    monkeypatch.delenv("HERMES_EXEC_ASK", raising=False)
    monkeypatch.delenv("HERMES_YOLO_MODE", raising=False)
    monkeypatch.setattr("tools.approval._get_cron_approval_mode", lambda: "deny")

    result = check_all_command_guards(command, "local")

    assert result["approved"]
