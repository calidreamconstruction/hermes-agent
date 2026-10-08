"""tool_search must not make a visible tool look nonexistent.

2026-10-08: a kanban worker (qwen3.6:35b) searched "kanban get task", the deferred catalog
held only kanban_schedule, so it concluded kanban_show/kanban_complete were unavailable and
tried to write the board database by hand. Visible matches are now reported as already loaded.
"""
from __future__ import annotations

import json
from typing import Any, Dict


def _td(name: str, description: str) -> Dict[str, Any]:
    return {"type": "function", "function": {"name": name, "description": description,
                                             "parameters": {"type": "object", "properties": {}}}}


def test_visible_tools_matching_a_query_are_reported_as_already_loaded():
    from tools.tool_search import ToolSearchConfig, dispatch_tool_search

    defs = [
        _td("kanban_complete", "Mark your kanban task complete with a summary and artifacts."),
        _td("kanban_show", "Show a kanban task with its comments and events."),
        _td("kanban_schedule", "Park your current kanban task in the scheduled state."),
    ]
    result = json.loads(dispatch_tool_search({"queries": ["kanban task complete"]}, current_tool_defs=defs,
                                             config=ToolSearchConfig.from_raw({})))
    group = result["results"][0]
    assert "kanban_complete" in group.get("already_loaded", [])
    assert "already_loaded_hint" in group
    # deferred tools still come back as normal matches; loaded ones are not duplicated into the schema map
    assert "kanban_complete" not in result["tools"]


def test_no_already_loaded_key_when_nothing_visible_matches():
    from tools.tool_search import ToolSearchConfig, dispatch_tool_search

    defs = [_td("kanban_schedule", "Park your current kanban task in the scheduled state.")]
    result = json.loads(dispatch_tool_search({"queries": ["weather forecast"]}, current_tool_defs=defs,
                                             config=ToolSearchConfig.from_raw({})))
    assert "already_loaded" not in result["results"][0]
