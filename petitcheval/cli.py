"""CLI subcommands — all output is JSON for agent consumption."""

import json
import sys
from datetime import datetime

from .models import (
    dump_all,
    dump_workspace,
    get_steps,
    get_tasks,
    resolve_workspace,
    set_task_status,
    step_counts,
)


def cli_error(msg):
    print(json.dumps({"error": msg}), file=sys.stderr)
    sys.exit(1)


# ── Dump ────────────────────────────────────────────────────────────────────

def cli_dump(db, args):
    ws_id = None
    i = 0
    while i < len(args):
        if args[i] == "--workspace" and i + 1 < len(args):
            ws = resolve_workspace(db, args[i + 1])
            if not ws:
                cli_error(f"Workspace '{args[i + 1]}' not found")
            ws_id = ws[0]; i += 2
        else:
            i += 1

    if ws_id:
        result = dump_workspace(db, ws_id)
    else:
        result = dump_all(db)
    print(json.dumps(result, indent=2))


# ── Workspace ───────────────────────────────────────────────────────────────

def cli_workspace(db, args):
    if not args:
        cli_error("Usage: petitcheval workspace <list|add|rm>")
    cmd, rest = args[0], args[1:]

    if cmd == "list":
        rows = db.execute("SELECT id, name, created_at FROM workspaces ORDER BY id").fetchall()
        print(json.dumps([{"id": r[0], "name": r[1], "created_at": r[2]} for r in rows]))

    elif cmd == "add":
        if not rest:
            cli_error("Usage: petitcheval workspace add <name>")
        name = rest[0]
        if db.execute("SELECT 1 FROM workspaces WHERE name = ?", (name,)).fetchone():
            cli_error(f"Workspace '{name}' already exists")
        now = datetime.now().isoformat()
        cur = db.execute("INSERT INTO workspaces (name, created_at) VALUES (?, ?)", (name, now))
        db.commit()
        print(json.dumps({"id": cur.lastrowid, "name": name, "created_at": now}))

    elif cmd == "rm":
        if not rest:
            cli_error("Usage: petitcheval workspace rm <id>")
        ws_id = int(rest[0])
        if not db.execute("SELECT 1 FROM workspaces WHERE id = ?", (ws_id,)).fetchone():
            cli_error(f"Workspace {ws_id} not found")
        db.execute("DELETE FROM workspaces WHERE id = ?", (ws_id,))
        db.commit()
        print(json.dumps({"deleted": ws_id}))

    else:
        cli_error(f"Unknown workspace command: {cmd}")


# ── Task ────────────────────────────────────────────────────────────────────

def cli_task(db, args):
    if not args:
        cli_error("Usage: petitcheval task <list|add|start|done|undone|rm>")
    cmd, rest = args[0], args[1:]

    if cmd == "list":
        ws_id = None
        status_filter = None
        i = 0
        while i < len(rest):
            if rest[i] == "--workspace" and i + 1 < len(rest):
                ws = resolve_workspace(db, rest[i + 1])
                if not ws:
                    cli_error(f"Workspace '{rest[i + 1]}' not found")
                ws_id = ws[0]; i += 2
            elif rest[i] == "--status" and i + 1 < len(rest):
                status_filter = rest[i + 1]; i += 2
            else:
                i += 1
        if ws_id:
            rows = get_tasks(db, ws_id, status_filter=status_filter)
        else:
            if status_filter:
                rows = db.execute(
                    "SELECT id, workspace_id, name, status, created_at FROM tasks WHERE status = ? ORDER BY id",
                    (status_filter,),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT id, workspace_id, name, status, created_at FROM tasks ORDER BY id"
                ).fetchall()
        out = []
        for r in rows:
            total, done = step_counts(db, r[0])
            out.append({
                "id": r[0], "workspace_id": r[1], "name": r[2],
                "status": r[3], "created_at": r[4],
                "steps_total": total, "steps_done": done,
            })
        print(json.dumps(out))

    elif cmd == "add":
        if not rest:
            cli_error("Usage: petitcheval task add <name> --workspace <name|id>")
        name_parts = []
        ws_val = None
        i = 0
        while i < len(rest):
            if rest[i] == "--workspace" and i + 1 < len(rest):
                ws_val = rest[i + 1]; i += 2
            else:
                name_parts.append(rest[i]); i += 1
        if not name_parts:
            cli_error("Task name is required")
        if ws_val is None:
            cli_error("--workspace is required")
        ws = resolve_workspace(db, ws_val)
        if not ws:
            cli_error(f"Workspace '{ws_val}' not found")
        name = " ".join(name_parts)
        now = datetime.now().isoformat()
        cur = db.execute(
            "INSERT INTO tasks (workspace_id, name, status, created_at) VALUES (?, ?, 'active', ?)",
            (ws[0], name, now),
        )
        db.commit()
        print(json.dumps({
            "id": cur.lastrowid, "workspace_id": ws[0], "name": name,
            "status": "active", "created_at": now,
        }))

    elif cmd == "start":
        if not rest:
            cli_error("Usage: petitcheval task start <id>")
        tid = int(rest[0])
        if not db.execute("SELECT 1 FROM tasks WHERE id = ?", (tid,)).fetchone():
            cli_error(f"Task {tid} not found")
        set_task_status(db, tid, "in_progress")
        print(json.dumps({"id": tid, "status": "in_progress"}))

    elif cmd == "done":
        if not rest:
            cli_error("Usage: petitcheval task done <id>")
        tid = int(rest[0])
        if not db.execute("SELECT 1 FROM tasks WHERE id = ?", (tid,)).fetchone():
            cli_error(f"Task {tid} not found")
        set_task_status(db, tid, "done")
        print(json.dumps({"id": tid, "status": "done"}))

    elif cmd == "undone":
        if not rest:
            cli_error("Usage: petitcheval task undone <id>")
        tid = int(rest[0])
        if not db.execute("SELECT 1 FROM tasks WHERE id = ?", (tid,)).fetchone():
            cli_error(f"Task {tid} not found")
        set_task_status(db, tid, "active")
        print(json.dumps({"id": tid, "status": "active"}))

    elif cmd == "rm":
        if not rest:
            cli_error("Usage: petitcheval task rm <id>")
        tid = int(rest[0])
        if not db.execute("SELECT 1 FROM tasks WHERE id = ?", (tid,)).fetchone():
            cli_error(f"Task {tid} not found")
        db.execute("DELETE FROM tasks WHERE id = ?", (tid,))
        db.commit()
        print(json.dumps({"deleted": tid}))

    else:
        cli_error(f"Unknown task command: {cmd}")


# ── Step ────────────────────────────────────────────────────────────────────

def cli_step(db, args):
    if not args:
        cli_error("Usage: petitcheval step <list|add|done|undone|edit|note|rm>")
    cmd, rest = args[0], args[1:]

    if cmd == "list":
        task_id = None
        ws_id = None
        status_filter = "all"
        i = 0
        while i < len(rest):
            if rest[i] == "--task" and i + 1 < len(rest):
                task_id = int(rest[i + 1]); i += 2
            elif rest[i] == "--workspace" and i + 1 < len(rest):
                ws = resolve_workspace(db, rest[i + 1])
                if not ws:
                    cli_error(f"Workspace '{rest[i + 1]}' not found")
                ws_id = ws[0]; i += 2
            elif rest[i] == "--status" and i + 1 < len(rest):
                status_filter = rest[i + 1]; i += 2
            else:
                i += 1

        if task_id:
            rows = get_steps(db, task_id, status_filter)
        elif ws_id:
            task_rows = get_tasks(db, ws_id)
            rows = []
            for t in task_rows:
                rows.extend(get_steps(db, t[0], status_filter))
        else:
            rows = db.execute(
                "SELECT id, task_id, text, done, priority, created_at, completed_at, note FROM steps ORDER BY id"
            ).fetchall()

        print(json.dumps([
            {"id": r[0], "task_id": r[1], "text": r[2], "done": bool(r[3]),
             "priority": r[4], "note": r[7], "created_at": r[5], "completed_at": r[6]}
            for r in rows
        ]))

    elif cmd == "add":
        if not rest:
            cli_error("Usage: petitcheval step add <text> --task <id> [-p high|medium|low] [--note <text>]")
        text_parts = []
        task_id = None
        priority = "medium"
        note = ""
        i = 0
        while i < len(rest):
            if rest[i] == "--task" and i + 1 < len(rest):
                task_id = int(rest[i + 1]); i += 2
            elif rest[i] == "-p" and i + 1 < len(rest):
                priority = rest[i + 1]; i += 2
            elif rest[i] == "--note" and i + 1 < len(rest):
                note = rest[i + 1]; i += 2
            else:
                text_parts.append(rest[i]); i += 1
        if not text_parts:
            cli_error("Step text is required")
        if task_id is None:
            cli_error("--task is required")
        if not db.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone():
            cli_error(f"Task {task_id} not found")
        text = " ".join(text_parts)
        now = datetime.now().isoformat()
        cur = db.execute(
            "INSERT INTO steps (task_id, text, priority, note, created_at) VALUES (?, ?, ?, ?, ?)",
            (task_id, text, priority, note, now),
        )
        db.commit()
        print(json.dumps({
            "id": cur.lastrowid, "task_id": task_id, "text": text,
            "priority": priority, "note": note, "done": False,
        }))

    elif cmd == "done":
        if not rest:
            cli_error("Usage: petitcheval step done <id>")
        sid = int(rest[0])
        if not db.execute("SELECT 1 FROM steps WHERE id = ?", (sid,)).fetchone():
            cli_error(f"Step {sid} not found")
        db.execute("UPDATE steps SET done = 1, completed_at = ? WHERE id = ?", (datetime.now().isoformat(), sid))
        db.commit()
        print(json.dumps({"id": sid, "done": True}))

    elif cmd == "undone":
        if not rest:
            cli_error("Usage: petitcheval step undone <id>")
        sid = int(rest[0])
        if not db.execute("SELECT 1 FROM steps WHERE id = ?", (sid,)).fetchone():
            cli_error(f"Step {sid} not found")
        db.execute("UPDATE steps SET done = 0, completed_at = NULL WHERE id = ?", (sid,))
        db.commit()
        print(json.dumps({"id": sid, "done": False}))

    elif cmd == "edit":
        if len(rest) < 2:
            cli_error("Usage: petitcheval step edit <id> <text>")
        sid = int(rest[0])
        new_text = " ".join(rest[1:])
        if not db.execute("SELECT 1 FROM steps WHERE id = ?", (sid,)).fetchone():
            cli_error(f"Step {sid} not found")
        db.execute("UPDATE steps SET text = ? WHERE id = ?", (new_text, sid))
        db.commit()
        print(json.dumps({"id": sid, "text": new_text}))

    elif cmd == "note":
        if len(rest) < 2:
            cli_error("Usage: petitcheval step note <id> <text>")
        sid = int(rest[0])
        new_note = " ".join(rest[1:])
        if not db.execute("SELECT 1 FROM steps WHERE id = ?", (sid,)).fetchone():
            cli_error(f"Step {sid} not found")
        db.execute("UPDATE steps SET note = ? WHERE id = ?", (new_note, sid))
        db.commit()
        print(json.dumps({"id": sid, "note": new_note}))

    elif cmd == "rm":
        if not rest:
            cli_error("Usage: petitcheval step rm <id>")
        sid = int(rest[0])
        if not db.execute("SELECT 1 FROM steps WHERE id = ?", (sid,)).fetchone():
            cli_error(f"Step {sid} not found")
        db.execute("DELETE FROM steps WHERE id = ?", (sid,))
        db.commit()
        print(json.dumps({"deleted": sid}))

    else:
        cli_error(f"Unknown step command: {cmd}")
