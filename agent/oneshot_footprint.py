"""What a finite one-shot session (``hermes chat -q`` / ``--oneshot``, ``hermes -z``) does NOT do.

A one-shot run has no later session in its HERMES_HOME to learn for: the process answers one query and
exits. The interactive self-improvement loop is pure overhead there, and a measured one — across 21
one-shot benchmark trajectories the agent authored 7 new skills and patched a bundled one mid-task, 37 of
~215 tool calls were ``skill_view``/``skill_manage``, and skill text was 34% of every tool-result byte fed
back into context. Three rules follow, all keyed on the same session marker the approval gate and the
delegation dispatcher already read (``HERMES_SINGLE_QUERY_SESSION``), so interactive sessions are untouched:

* ``skill_manage`` is not offered (``skills_list``/``skill_view`` stay: reading a domain skill can still win);
* the ## Skills prompt drops the "record it / patch it / offer to save" coaching and the "load process skills
  even for tasks you already know" push, keeping only "load a skill when it adds knowledge you lack";
* delegation is capped per session (``delegation.oneshot_max_children``): subagents each re-pay a cold
  system prompt and re-explore the repo, and the observed spawns were mostly "independent review of my own
  work" rather than parallel work.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

ONESHOT_HIDDEN_TOOLS = frozenset({"skill_manage"})


def is_single_query_session() -> bool:
    """The finite ``-q`` marker, read through the session env so gateway-bound sessions never see it."""
    try:
        from gateway.session_context import get_session_env
    except Exception:
        import os
        get_session_env = os.environ.get
    return str(get_session_env("HERMES_SINGLE_QUERY_SESSION", "") or "") == "1"


def prune_oneshot_tools(tools: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """*tools* minus ``ONESHOT_HIDDEN_TOOLS``; identity when the session is not one-shot."""
    tools = list(tools)
    if not is_single_query_session():
        return tools
    return [t for t in tools if (t.get("function") or {}).get("name") not in ONESHOT_HIDDEN_TOOLS]


ONESHOT_SKILLS_LOAD_GUIDANCE = (
    "## Skills\n"
    "Scan the skills below and load one with skill_view(name) only when it carries domain knowledge you lack "
    "for THIS task (an API, a tool's commands, a project's conventions). Do not load general process skills "
    "(testing, debugging, review methodology) for work you already know how to do, and do not create or edit "
    "skills: this is a one-shot run with no later session to reuse them.\n"
)


# --- Local-model lean tool surface (2026-10-06, owner "do all") -----------------------------------
# Measured: the default toolset costs ~27k tokens on every turn's first call (39 tool schemas ~17k,
# skills index ~4k, system prompt ~6k). At local prefill speed that is minutes. When the ACTIVE model is
# served by a local backend, drop the schemas a local model rarely needs. Cloud models are untouched.
# Override/disable via config.yaml ``agent.local_lean`` ({enabled: false, providers: [...], drop_tools: [...]}).
LOCAL_LEAN_PROVIDERS = frozenset({"ollama-mirror", "ollama-launch", "mlx-local", "rapid-mlx"})
LOCAL_LEAN_DROP_PREFIXES = ("kanban_", "browser_", "computer_use")
LOCAL_LEAN_DROP_TOOLS = frozenset({
    "text_to_speech", "image_generate", "vision_analyze", "cronjob", "execute_code",
    "skill_manage", "skills_list", "skill_view",  # no skills tools => no skills index in the prompt
})


def _local_lean_cfg() -> Dict[str, Any]:
    try:
        from hermes_cli.config import load_config_readonly
        raw = (load_config_readonly().get("agent") or {}).get("local_lean")
    except Exception:
        raw = None
    return raw if isinstance(raw, dict) else {}


def is_local_lean_route(provider: Any, model: Any, base_url: Any = "") -> bool:
    cfg = _local_lean_cfg()
    if cfg.get("enabled") is False:
        return False
    providers = set(cfg.get("providers") or LOCAL_LEAN_PROVIDERS)
    # Named providers resolve to provider="custom" at runtime (billing_provider=custom), so also match the
    # loopback endpoint: local Ollama 11434/11439 and MLX 11441.
    from urllib.parse import urlparse
    try:
        u = urlparse(str(base_url or ""))
        loopback = (u.hostname in ("127.0.0.1", "localhost", "::1")) and u.port in (11434, 11439, 11441)
    except Exception:
        loopback = False
    if str(provider or "") not in providers and not loopback:
        return False
    # ollama-launch (:11434) also serves ``*:cloud`` / ``*-cloud`` models: those are cloud, keep the full toolset.
    return not str(model or "").endswith((":cloud", "-cloud"))


def prune_local_lean_tools(tools: Iterable[Dict[str, Any]], provider: Any, model: Any, base_url: Any = "") -> List[Dict[str, Any]]:
    """*tools* minus the local-lean drop set when the active route is a local model; identity otherwise."""
    tools = list(tools)
    if not is_local_lean_route(provider, model, base_url):
        return tools
    cfg = _local_lean_cfg()
    drop = frozenset(cfg.get("drop_tools") or LOCAL_LEAN_DROP_TOOLS)
    pref = tuple(cfg.get("drop_prefixes") or LOCAL_LEAN_DROP_PREFIXES)
    def keep(t):
        n = (t.get("function") or {}).get("name") or ""
        return n not in drop and not n.startswith(pref)
    return [t for t in tools if keep(t)]
