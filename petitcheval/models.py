"""CRUD helpers for workspaces, tasks, and steps."""

from datetime import datetime


# ── Workspaces ──────────────────────────────────────────────────────────────

def resolve_workspace(db, name_or_id):
    """Return workspace row (id, name, created_at) by name or numeric id."""
    if name_or_id.isdigit():
        return db.execute("SELECT id, name, created_at FROM workspaces WHERE id = ?", (int(name_or_id),)).fetchone()
    return db.execute("SELECT id, name, created_at FROM workspaces WHERE name = ?", (name_or_id,)).fetchone()


# ── Tasks ───────────────────────────────────────────────────────────────────

TASK_STATUS_ORDER = {"active": 0, "in_progress": 1, "done": 2}


def get_tasks(db, workspace_id, status_filter=None):
    if status_filter:
        return db.execute(
            "SELECT id, workspace_id, name, status, created_at FROM tasks "
            "WHERE workspace_id = ? AND status = ? ORDER BY id",
            (workspace_id, status_filter),
        ).fetchall()
    return db.execute(
        "SELECT id, workspace_id, name, status, created_at FROM tasks WHERE workspace_id = ? "
        "ORDER BY CASE status WHEN 'in_progress' THEN 0 WHEN 'active' THEN 1 ELSE 2 END, id",
        (workspace_id,),
    ).fetchall()


def set_task_status(db, task_id, status):
    """Set task status. Valid: active, in_progress, done."""
    if status not in TASK_STATUS_ORDER:
        raise ValueError(f"Invalid status: {status}")
    db.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
    db.commit()


# ── Steps ───────────────────────────────────────────────────────────────────

def get_steps(db, task_id, status_filter="all"):
    clause = ""
    if status_filter == "pending":
        clause = " AND done = 0"
    elif status_filter == "done":
        clause = " AND done = 1"
    return db.execute(
        f"SELECT id, task_id, text, done, priority, created_at, completed_at, note FROM steps "
        f"WHERE task_id = ?{clause} "
        f"ORDER BY done, CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, id",
        (task_id,),
    ).fetchall()


def step_counts(db, task_id):
    row = db.execute(
        "SELECT COUNT(*), SUM(done) FROM steps WHERE task_id = ?", (task_id,)
    ).fetchone()
    return row[0], int(row[1] or 0)


def add_step(db, task_id, text, priority="medium", note=""):
    now = datetime.now().isoformat()
    cur = db.execute(
        "INSERT INTO steps (task_id, text, priority, note, created_at) VALUES (?, ?, ?, ?, ?)",
        (task_id, text, priority, note, now),
    )
    db.commit()
    return cur.lastrowid


# ── Dump ────────────────────────────────────────────────────────────────────

def dump_workspace(db, workspace_id):
    """Return full nested dict for a workspace: tasks → steps."""
    ws = db.execute("SELECT id, name, created_at FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
    if not ws:
        return None
    tasks = get_tasks(db, workspace_id)
    task_list = []
    for t in tasks:
        total, done = step_counts(db, t[0])
        steps = get_steps(db, t[0])
        task_list.append({
            "id": t[0], "name": t[2], "status": t[3], "created_at": t[4],
            "steps_total": total, "steps_done": done,
            "steps": [
                {"id": s[0], "text": s[2], "done": bool(s[3]), "priority": s[4],
                 "note": s[7], "created_at": s[5], "completed_at": s[6]}
                for s in steps
            ],
        })
    return {"id": ws[0], "name": ws[1], "created_at": ws[2], "tasks": task_list}


def dump_all(db):
    """Return full nested dict for all workspaces."""
    workspaces = db.execute("SELECT id FROM workspaces ORDER BY id").fetchall()
    return [dump_workspace(db, ws[0]) for ws in workspaces]
