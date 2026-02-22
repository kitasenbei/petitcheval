"""CRUD helpers for workspaces, tasks, and steps."""

from datetime import datetime


# ── Workspaces ──────────────────────────────────────────────────────────────

def resolve_workspace(db, name_or_id):
    """Return workspace row (id, name, created_at) by name or numeric id."""
    if name_or_id.isdigit():
        return db.execute("SELECT id, name, created_at FROM workspaces WHERE id = ?", (int(name_or_id),)).fetchone()
    return db.execute("SELECT id, name, created_at FROM workspaces WHERE name = ?", (name_or_id,)).fetchone()


# ── Tasks ───────────────────────────────────────────────────────────────────

def get_tasks(db, workspace_id, status_filter=None):
    if status_filter:
        return db.execute(
            "SELECT id, workspace_id, name, status, created_at FROM tasks "
            "WHERE workspace_id = ? AND status = ? ORDER BY id",
            (workspace_id, status_filter),
        ).fetchall()
    return db.execute(
        "SELECT id, workspace_id, name, status, created_at FROM tasks WHERE workspace_id = ? ORDER BY id",
        (workspace_id,),
    ).fetchall()


# ── Steps ───────────────────────────────────────────────────────────────────

def get_steps(db, task_id, status_filter="all"):
    clause = ""
    if status_filter == "pending":
        clause = " AND done = 0"
    elif status_filter == "done":
        clause = " AND done = 1"
    return db.execute(
        f"SELECT id, task_id, text, done, priority, created_at, completed_at FROM steps "
        f"WHERE task_id = ?{clause} "
        f"ORDER BY done, CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, id",
        (task_id,),
    ).fetchall()


def step_counts(db, task_id):
    row = db.execute(
        "SELECT COUNT(*), SUM(done) FROM steps WHERE task_id = ?", (task_id,)
    ).fetchone()
    return row[0], int(row[1] or 0)


def add_step(db, task_id, text, priority="medium"):
    now = datetime.now().isoformat()
    cur = db.execute(
        "INSERT INTO steps (task_id, text, priority, created_at) VALUES (?, ?, ?, ?)",
        (task_id, text, priority, now),
    )
    db.commit()
    return cur.lastrowid
