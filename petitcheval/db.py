"""Database connection, schema creation, and migrations."""

import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.expanduser("~"), ".todo.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    conn.execute(
        """CREATE TABLE IF NOT EXISTS workspaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            text TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0,
            priority TEXT NOT NULL DEFAULT 'medium',
            created_at TEXT NOT NULL,
            completed_at TEXT
        )"""
    )

    _migrate_flat_todos(conn)
    _migrate_plans(conn)

    # Ensure at least one workspace exists
    if not conn.execute("SELECT 1 FROM workspaces LIMIT 1").fetchone():
        now = datetime.now().isoformat()
        conn.execute("INSERT INTO workspaces (name, created_at) VALUES ('default', ?)", (now,))
        conn.commit()

    return conn


def _ensure_default_workspace_task(conn):
    """Return (workspace_id, task_id) for the 'default' workspace + task, creating if needed."""
    now = datetime.now().isoformat()
    row = conn.execute("SELECT id FROM workspaces WHERE name = 'default'").fetchone()
    if row:
        ws_id = row[0]
    else:
        cur = conn.execute("INSERT INTO workspaces (name, created_at) VALUES ('default', ?)", (now,))
        ws_id = cur.lastrowid

    row = conn.execute("SELECT id FROM tasks WHERE workspace_id = ? AND name = 'default'", (ws_id,)).fetchone()
    if row:
        task_id = row[0]
    else:
        cur = conn.execute(
            "INSERT INTO tasks (workspace_id, name, status, created_at) VALUES (?, 'default', 'active', ?)",
            (ws_id, now),
        )
        task_id = cur.lastrowid
    return ws_id, task_id


def _migrate_flat_todos(conn):
    """Migrate old flat `todos` table (no plan_id) into default workspace/task."""
    try:
        conn.execute("SELECT 1 FROM todos LIMIT 1")
    except sqlite3.OperationalError:
        return

    # Check if this is the plan-based schema (has plan_id column) — skip if so
    cols = [r[1] for r in conn.execute("PRAGMA table_info(todos)").fetchall()]
    if "plan_id" in cols:
        return

    _ws_id, task_id = _ensure_default_workspace_task(conn)

    old_todos = conn.execute("SELECT task, done, priority, created_at, completed_at FROM todos").fetchall()
    for t in old_todos:
        conn.execute(
            "INSERT INTO steps (task_id, text, done, priority, created_at, completed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (task_id, t[0], t[1], t[2], t[3], t[4]),
        )
    conn.execute("DROP TABLE todos")
    conn.commit()


def _migrate_plans(conn):
    """Migrate plan-based schema (workspaces + plans + todos with plan_id) into workspace/task/step."""
    try:
        conn.execute("SELECT 1 FROM plans LIMIT 1")
    except sqlite3.OperationalError:
        return

    plans = conn.execute(
        "SELECT p.id, p.workspace_id, p.name, p.status, p.created_at FROM plans p"
    ).fetchall()
    for plan in plans:
        plan_id, ws_id, pname, pstatus, pcreated = plan
        existing = conn.execute(
            "SELECT id FROM tasks WHERE workspace_id = ? AND name = ?", (ws_id, pname)
        ).fetchone()
        if existing:
            new_task_id = existing[0]
        else:
            cur = conn.execute(
                "INSERT INTO tasks (workspace_id, name, status, created_at) VALUES (?, ?, ?, ?)",
                (ws_id, pname, pstatus, pcreated),
            )
            new_task_id = cur.lastrowid
        try:
            old_todos = conn.execute(
                "SELECT task, done, priority, created_at, completed_at FROM todos WHERE plan_id = ?",
                (plan_id,),
            ).fetchall()
            for t in old_todos:
                conn.execute(
                    "INSERT INTO steps (task_id, text, done, priority, created_at, completed_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (new_task_id, t[0], t[1], t[2], t[3], t[4]),
                )
        except sqlite3.OperationalError:
            pass
    try:
        conn.execute("DROP TABLE todos")
    except sqlite3.OperationalError:
        pass
    conn.execute("DROP TABLE plans")
    conn.commit()
