#!/usr/bin/env python3
"""Prove the C1 progress-evidence heartbeat detects a logic loop.

Read-only against a throwaway DB; never touches the owner's kanban.db.
Three cases:
  1. worker ADVANCING (token changes)  -> must NOT be flagged stalled
  2. worker WEDGED (token repeats)    -> MUST be flagged stalled
  3. legacy caller (no token)          -> behaviour unchanged, never flagged
"""
import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, "/Users/faressystem/hermes-agent")
import hermes_cli.kanban_db as kb            # noqa: E402
import hermes_cli.kanban_db_dispatch as kbd  # noqa: E402

SCHEMA = """
CREATE TABLE tasks (
  id TEXT PRIMARY KEY, title TEXT, body TEXT, assignee TEXT, status TEXT,
  priority INTEGER DEFAULT 0, created_by TEXT, created_at INTEGER,
  started_at INTEGER, completed_at INTEGER, workspace_kind TEXT,
  workspace_path TEXT, branch_name TEXT, project_id TEXT, claim_lock TEXT,
  claim_expires INTEGER, tenant TEXT, result TEXT, idempotency_key TEXT,
  consecutive_failures INTEGER DEFAULT 0, worker_pid INTEGER,
  last_failure_error TEXT, max_runtime_seconds INTEGER, last_heartbeat_at INTEGER,
  current_run_id INTEGER, workflow_template_id TEXT, current_step_key TEXT,
  skills TEXT, model_override TEXT, provider_override TEXT,
  reasoning_effort TEXT, max_retries INTEGER, goal_mode INTEGER DEFAULT 0,
  goal_max_turns INTEGER, session_id TEXT, block_kind TEXT,
  block_recurrences INTEGER DEFAULT 0, completion_contract TEXT,
  worker_started_at INTEGER
);
CREATE TABLE task_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, run_id INTEGER,
  kind TEXT, payload TEXT, created_at INTEGER
);
CREATE TABLE task_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, profile TEXT, step_key TEXT,
  status TEXT, claim_lock TEXT, claim_expires INTEGER, worker_pid INTEGER,
  max_runtime_seconds INTEGER, last_heartbeat_at INTEGER, started_at INTEGER,
  ended_at INTEGER, outcome TEXT, summary TEXT, metadata TEXT, error TEXT,
  worker_started_at INTEGER
);
CREATE TABLE task_comments (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT,
  author TEXT, body TEXT, created_at INTEGER);
CREATE TABLE task_links (parent_id TEXT, child_id TEXT);
CREATE TABLE task_attachments (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT,
  filename TEXT, stored_path TEXT, content_type TEXT, size INTEGER,
  uploaded_by TEXT, created_at INTEGER);
CREATE TABLE kanban_notify_subs (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT,
  platform TEXT, chat_id TEXT, thread_id TEXT, user_id TEXT, user_id_alt TEXT,
  chat_type TEXT, notifier_profile TEXT, delivery_mode TEXT, delivery_metadata TEXT,
  created_at INTEGER, last_event_id INTEGER, last_ping_event_id INTEGER);
"""


def fresh():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO tasks (id,title,assignee,status,created_by,created_at) "
        "VALUES ('t_probe','probe','w','running','test',0)")
    conn.execute(
        "INSERT INTO task_runs (id,task_id,status,started_at) VALUES (1,'t_probe','running',0)")
    conn.execute("UPDATE tasks SET current_run_id=1 WHERE id='t_probe'")
    conn.commit()
    return conn, path


def events(conn):
    out = []
    for r in conn.execute(
            "SELECT payload FROM task_events WHERE kind='heartbeat' ORDER BY id"):
        try:
            out.append(json.loads(r[0] or "{}"))
        except Exception:
            out.append({})
    return out


def case(name, tokens, expect_stalled_flags):
    conn, path = fresh()
    try:
        for t in tokens:
            kbd.heartbeat_worker(conn, "t_probe", progress_token=t)
        evs = events(conn)
        flags = [e.get("progress_stalled") for e in evs]
        got = [f for f in flags if f is not None]
        ok = got == expect_stalled_flags
        print(f"  {name}")
        for i, e in enumerate(evs):
            print(f"     hb{i}: token={e.get('progress_token')!r} "
                  f"stalled={e.get('progress_stalled')}")
        print(f"     -> {flags}  expect {expect_stalled_flags}  "
              f"{'PASS' if ok else 'FAIL'}")
        return ok
    finally:
        conn.close()
        os.unlink(path)


print("C1 progress-evidence heartbeat — logic-loop detection")
print("=" * 66)
results = [
    # Three advancing heartbeats produce three explicit False flags: the first has
    # nothing to compare against, so it is healthy-by-default, never stalled.
    case("1 advancing worker (token changes)", ["a", "b", "c"], [False, False, False]),
    case("2 WEDGED worker (token repeats)", ["x", "x", "x"], [False, True, True]),
    case("3 legacy caller (no token)", [None, None], []),
]
print()
print(f"{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)