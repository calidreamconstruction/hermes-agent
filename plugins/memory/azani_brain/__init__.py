"""Azani Brain memory plugin — writes Hermes memory directly into the Faressystem brain DB.

Avoids duplication by sharing /opt/faressystem/memory/brain.db with the rest of the
Azani system. Uses the existing `memories` table schema.

Config (hermes config.yaml under azani_brain:):
  azani_brain.db_path — override DB path (default: /opt/faressystem/memory/brain.db)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider

logger = logging.getLogger(__name__)

_DEFAULT_DB = "/opt/faressystem/memory/brain.db"


def _get_db_path() -> str:
    """Return the brain DB path from env or config."""
    env = os.environ.get("AZANI_BRAIN_DB")
    if env:
        return env
    try:
        from hermes_cli.config import cfg_get
        import yaml
        from hermes_constants import get_hermes_home
        config_path = get_hermes_home() / "config.yaml"
        if config_path.exists():
            with open(config_path, encoding="utf-8-sig") as f:
                all_config = yaml.safe_load(f) or {}
            override = cfg_get(all_config, "azani_brain", "db_path")
            if override:
                return str(override)
    except Exception:
        pass
    return _DEFAULT_DB


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

PROFILE_SCHEMA = {
    "name": "brain_profile",
    "description": "Get the user's stable profile from Azani Brain.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}

SEARCH_SCHEMA = {
    "name": "brain_search",
    "description": "Search memories in Azani Brain by keyword.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Keyword to search for."},
            "limit": {"type": "integer", "description": "Max results (default: 10)."},
        },
        "required": ["query"],
    },
}

REMEMBER_SCHEMA = {
    "name": "brain_remember",
    "description": "Persist a fact to Azani Brain.",
    "parameters": {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "The fact to remember."},
            "tags": {"type": "string", "description": "Comma-separated tags (optional)."},
        },
        "required": ["content"],
    },
}

READ_SCHEMA = {
    "name": "brain_read",
    "description": "Read recent memories from Azani Brain.",
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Max entries (default: 20)."},
        },
        "required": [],
    },
}


class AzaniBrainMemoryProvider(MemoryProvider):
    """Hermes memory provider backed by the Azani brain SQLite DB."""

    @property
    def name(self) -> str:
        return "azani_brain"

    def is_available(self) -> bool:
        db_path = _get_db_path()
        return Path(db_path).exists() and Path(db_path).stat().st_size > 0

    def initialize(self, session_id: str, **kwargs) -> None:
        db_path = _get_db_path()
        logger.info("AzaniBrainMemoryProvider: connecting to %s", db_path)
        self._db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create tables if they don't exist (idempotent)."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    content_hash TEXT UNIQUE,
                    source TEXT,
                    tags TEXT,
                    created_at TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_hash ON memories(content_hash)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at)"
            )
            conn.commit()

    def system_prompt_block(self) -> str:
        return (
            "Azani Brain memory: connected. "
            "Use brain_remember(content=...) to save facts, "
            "brain_search(query=...) to recall, "
            "brain_read(limit=...) to list recent."
        )

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [PROFILE_SCHEMA, SEARCH_SCHEMA, REMEMBER_SCHEMA, READ_SCHEMA]

    def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        try:
            if tool_name == "brain_profile":
                return self._profile()
            elif tool_name == "brain_search":
                return self._search(arguments.get("query", ""), arguments.get("limit", 10))
            elif tool_name == "brain_remember":
                return self._remember(arguments.get("content", ""), arguments.get("tags", ""))
            elif tool_name == "brain_read":
                return self._read(arguments.get("limit", 20))
            return json.dumps({"success": False, "error": f"Unknown tool: {tool_name}"})
        except Exception as e:
            logger.exception("brain tool %s failed", tool_name)
            return json.dumps({"success": False, "error": str(e)})

    def _profile(self) -> str:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT content FROM memories WHERE source = 'user_profile' ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
        entries = [r["content"] for r in rows]
        return json.dumps({"success": True, "entries": entries, "count": len(entries)})

    def _search(self, query: str, limit: int = 10) -> str:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            like = f"%{query}%"
            rows = conn.execute(
                "SELECT id, content, source, tags, created_at FROM memories WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?",
                (like, limit),
            ).fetchall()
        results = [
            {"id": r["id"], "content": r["content"], "source": r["source"], "tags": r["tags"], "created_at": r["created_at"]}
            for r in rows
        ]
        return json.dumps({"success": True, "results": results, "count": len(results)})

    def _remember(self, content: str, tags: str = "") -> str:
        if not content:
            return json.dumps({"success": False, "error": "content required"})
        h = hashlib.sha256(content.encode()).hexdigest()[:16]
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            try:
                conn.execute(
                    "INSERT INTO memories (content, content_hash, source, tags, created_at) VALUES (?, ?, ?, ?, ?)",
                    (content, h, "hermes", tags, now),
                )
                conn.commit()
                return json.dumps({"success": True, "hash": h})
            except sqlite3.IntegrityError:
                # Duplicate hash — update tags if provided
                if tags:
                    conn.execute(
                        "UPDATE memories SET tags = ? WHERE content_hash = ?",
                        (tags, h),
                    )
                    conn.commit()
                return json.dumps({"success": True, "hash": h, "note": "already_exists"})

    def _read(self, limit: int = 20) -> str:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, content, source, tags, created_at FROM memories ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        results = [
            {"id": r["id"], "content": r["content"], "source": r["source"], "tags": r["tags"], "created_at": r["created_at"]}
            for r in rows
        ]
        return json.dumps({"success": True, "results": results, "count": len(results)})

    def on_memory_write(self, action: str, target: str, content: str, metadata: Optional[Dict] = None) -> None:
        """Mirror built-in memory tool writes into the brain DB."""
        if action != "add" or not content:
            return
        source = "user_profile" if target == "user" else "hermes"
        tags = metadata.get("tags", "") if metadata else ""
        try:
            self._remember(content, tags)
        except Exception:
            logger.debug("on_memory_write mirror failed", exc_info=True)

    def shutdown(self) -> None:
        pass


def register_memory_provider(collector):
    collector.register_memory_provider(AzaniBrainMemoryProvider())
