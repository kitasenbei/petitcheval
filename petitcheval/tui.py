"""Curses-based TUI — collapsible tree view of tasks and steps."""

import curses
from datetime import datetime

from .models import get_steps, get_tasks, step_counts


# ── Input widgets ───────────────────────────────────────────────────────────

def textbox_input(stdscr, prompt, prefill=""):
    """Single-line text input at the bottom of screen. Returns string or None on ESC."""
    h, w = stdscr.getmaxyx()
    y = h - 2
    stdscr.attron(curses.A_REVERSE)
    stdscr.addnstr(y, 0, " " * (w - 1), w - 1)
    stdscr.addnstr(y, 1, prompt, w - 2)
    stdscr.attroff(curses.A_REVERSE)
    stdscr.refresh()

    curses.curs_set(1)
    buf = list(prefill)
    cursor = len(buf)

    while True:
        input_y = y + 1
        stdscr.move(input_y, 0)
        stdscr.clrtoeol()
        display = "".join(buf)
        stdscr.addnstr(input_y, 1, display, w - 2)
        stdscr.move(input_y, 1 + cursor)
        stdscr.refresh()

        ch = stdscr.get_wch()
        if ch == "\n":
            curses.curs_set(0)
            return "".join(buf)
        elif ch == "\x1b":
            curses.curs_set(0)
            return None
        elif ch in (curses.KEY_BACKSPACE, "\x7f", "\b"):
            if cursor > 0:
                buf.pop(cursor - 1)
                cursor -= 1
        elif ch == curses.KEY_DC:
            if cursor < len(buf):
                buf.pop(cursor)
        elif ch == curses.KEY_LEFT:
            cursor = max(0, cursor - 1)
        elif ch == curses.KEY_RIGHT:
            cursor = min(len(buf), cursor + 1)
        elif ch == curses.KEY_HOME:
            cursor = 0
        elif ch == curses.KEY_END:
            cursor = len(buf)
        elif isinstance(ch, str) and len(ch) == 1 and ch.isprintable():
            buf.insert(cursor, ch)
            cursor += 1


def popup_select(stdscr, title, items, label_fn):
    """Centered popup list. Returns selected item or None on ESC."""
    h, w = stdscr.getmaxyx()
    box_w = min(w - 4, 50)
    box_h = min(h - 4, len(items) + 2)
    start_y = (h - box_h) // 2
    start_x = (w - box_w) // 2
    sel = 0
    scroll = 0
    inner_h = box_h - 2

    while True:
        for row in range(box_h):
            stdscr.addnstr(start_y + row, start_x, " " * box_w, box_w, curses.A_REVERSE)
        stdscr.addnstr(start_y, start_x + 1, title[:box_w - 2], box_w - 2, curses.A_REVERSE | curses.A_BOLD)

        for i in range(inner_h):
            idx = i + scroll
            if idx >= len(items):
                break
            label = label_fn(items[idx])[:box_w - 4]
            attr = curses.A_REVERSE
            if idx == sel:
                attr = curses.color_pair(1) | curses.A_BOLD
            stdscr.addnstr(start_y + 1 + i, start_x + 1, f" {label:<{box_w - 3}}", box_w - 2, attr)
        stdscr.refresh()

        ch = stdscr.get_wch()
        if ch == "\x1b":
            return None
        elif ch in ("k", curses.KEY_UP):
            sel = max(0, sel - 1)
            if sel < scroll:
                scroll = sel
        elif ch in ("j", curses.KEY_DOWN):
            sel = min(len(items) - 1, sel + 1)
            if sel >= scroll + inner_h:
                scroll = sel - inner_h + 1
        elif ch == "\n":
            return items[sel]


# ── Tree model ──────────────────────────────────────────────────────────────

def build_tree(db, workspace_id, collapsed, search_query=""):
    """Build a flat list of rows from the task→step tree for rendering."""
    rows = []
    query = search_query.lower()
    tasks = get_tasks(db, workspace_id, status_filter="active")
    for t in tasks:
        tid = t[0]
        total, done = step_counts(db, tid)
        steps = get_steps(db, tid)

        if query:
            task_matches = query in t[2].lower()
            matching_steps = [s for s in steps if query in s[2].lower()]
            if not task_matches and not matching_steps:
                continue
            rows.append({
                "type": "task", "id": tid, "name": t[2], "total": total, "done": done,
                "collapsed": tid in collapsed,
            })
            if tid not in collapsed:
                for s in (matching_steps if not task_matches else steps):
                    rows.append({
                        "type": "step", "id": s[0], "task_id": s[1],
                        "text": s[2], "done": s[3], "priority": s[4],
                    })
        else:
            rows.append({
                "type": "task", "id": tid, "name": t[2], "total": total, "done": done,
                "collapsed": tid in collapsed,
            })
            if tid not in collapsed:
                for s in steps:
                    rows.append({
                        "type": "step", "id": s[0], "task_id": s[1],
                        "text": s[2], "done": s[3], "priority": s[4],
                    })
    return rows


# ── Drawing ─────────────────────────────────────────────────────────────────

def draw_tree(stdscr, rows, cursor_pos, scroll_offset, status_msg, ws_name, search_query=""):
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    TITLE = curses.color_pair(1) | curses.A_BOLD
    HIGH = curses.color_pair(2)
    MED = curses.color_pair(3)
    LOW = curses.color_pair(4)
    DIM = curses.color_pair(5)
    HELP = curses.color_pair(6)
    STATUS = curses.color_pair(7) | curses.A_BOLD
    SELECTED = curses.A_REVERSE
    priority_attr = {"high": HIGH, "medium": MED, "low": LOW}
    priority_icon = {"high": "!!!", "medium": " ! ", "low": " . "}

    # Title bar
    title = f" petitcheval  [{ws_name}] "
    if search_query:
        title += f" / \"{search_query}\" "
    stdscr.attron(TITLE)
    stdscr.addnstr(0, 0, " " * (w - 1), w - 1)
    stdscr.addnstr(0, 1, title[:w - 2], w - 2)
    stdscr.attroff(TITLE)

    # List area
    list_top = 2
    list_bottom = h - 3
    visible = list_bottom - list_top

    if not rows:
        msg = "No tasks yet. Press 'A' to add a task."
        stdscr.addnstr(list_top + 1, max(0, (w - len(msg)) // 2), msg, w - 1, DIM)
    else:
        for i in range(visible):
            idx = i + scroll_offset
            if idx >= len(rows):
                break
            row_y = list_top + i
            r = rows[idx]
            is_sel = idx == cursor_pos
            base = SELECTED if is_sel else 0

            stdscr.addnstr(row_y, 0, " " * (w - 1), w - 1, base)

            if r["type"] == "task":
                arrow = "▸" if r.get("collapsed") else "▾"
                count_s = f"[{r['done']}/{r['total']}]"
                all_done = r["total"] > 0 and r["done"] == r["total"]
                name_attr = base | (DIM if all_done else curses.A_BOLD)
                stdscr.addnstr(row_y, 1, arrow, 1, base)
                stdscr.addnstr(row_y, 3, r["name"][:w - 15], w - 15, name_attr)
                stdscr.addnstr(row_y, max(3, w - len(count_s) - 2), count_s, len(count_s),
                               base | (LOW if all_done else MED))
            else:
                check = "[x]" if r["done"] else "[ ]"
                prio = r["priority"]
                ptag = priority_icon.get(prio, " ? ")
                text = r["text"]
                step_attr = base | (DIM if r["done"] else 0)

                stdscr.addnstr(row_y, 3, check, 3, step_attr)
                stdscr.addnstr(row_y, 7, ptag, 3, base | priority_attr.get(prio, 0))
                max_tw = w - 12
                stdscr.addnstr(row_y, 11, text[:max_tw], max_tw, step_attr)

    # Status message
    if status_msg:
        stdscr.attron(STATUS)
        stdscr.addnstr(h - 3, 0, " " * (w - 1), w - 1)
        stdscr.addnstr(h - 3, 1, status_msg[:w - 2], w - 2)
        stdscr.attroff(STATUS)

    # Help bar
    help_text = " A:task  a:step  enter:toggle  e:edit  p:priority  d:del  f:search  w:workspace  q:quit "
    stdscr.attron(HELP)
    stdscr.addnstr(h - 1, 0, " " * (w - 1), w - 1)
    stdscr.addnstr(h - 1, max(0, (w - len(help_text)) // 2), help_text[:w - 1], w - 1)
    stdscr.attroff(HELP)

    stdscr.refresh()


# ── Main loop ───────────────────────────────────────────────────────────────

def tui_main(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)

    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(2, curses.COLOR_RED, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_GREEN, -1)
    curses.init_pair(5, curses.COLOR_WHITE + 8 if curses.COLORS > 8 else curses.COLOR_WHITE, -1)
    curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(7, curses.COLOR_YELLOW, -1)

    from .db import get_db
    db = get_db()

    # Pick initial workspace
    ws_row = db.execute("SELECT id, name FROM workspaces ORDER BY id LIMIT 1").fetchone()
    current_ws_id, current_ws_name = ws_row[0], ws_row[1]

    collapsed = set()
    cursor_pos = 0
    scroll_offset = 0
    status_msg = ""
    search_query = ""

    while True:
        rows = build_tree(db, current_ws_id, collapsed, search_query)
        h, w = stdscr.getmaxyx()
        visible = h - 5

        if rows:
            cursor_pos = max(0, min(cursor_pos, len(rows) - 1))
            if cursor_pos < scroll_offset:
                scroll_offset = cursor_pos
            if cursor_pos >= scroll_offset + visible:
                scroll_offset = cursor_pos - visible + 1
        else:
            cursor_pos = 0
            scroll_offset = 0

        draw_tree(stdscr, rows, cursor_pos, scroll_offset, status_msg, current_ws_name, search_query)
        status_msg = ""

        try:
            ch = stdscr.get_wch()
        except curses.error:
            continue

        if ch == "q" or ch == "Q":
            break

        elif ch == "k" or ch == curses.KEY_UP:
            cursor_pos = max(0, cursor_pos - 1)

        elif ch == "j" or ch == curses.KEY_DOWN:
            if rows:
                cursor_pos = min(len(rows) - 1, cursor_pos + 1)

        elif ch == "g":
            cursor_pos = 0

        elif ch == "G":
            if rows:
                cursor_pos = len(rows) - 1

        # Toggle collapse on task / toggle done on step
        elif ch == "\n" or ch == " ":
            if rows:
                r = rows[cursor_pos]
                if r["type"] == "task":
                    tid = r["id"]
                    if tid in collapsed:
                        collapsed.discard(tid)
                    else:
                        collapsed.add(tid)
                else:
                    sid = r["id"]
                    if r["done"]:
                        db.execute("UPDATE steps SET done = 0, completed_at = NULL WHERE id = ?", (sid,))
                    else:
                        db.execute(
                            "UPDATE steps SET done = 1, completed_at = ? WHERE id = ?",
                            (datetime.now().isoformat(), sid),
                        )
                    db.commit()
                    status_msg = f"{'Unchecked' if r['done'] else 'Completed'}: {r['text']}"

        # New task (A)
        elif ch == "A":
            name = textbox_input(stdscr, "New task name (ESC to cancel):")
            if name and name.strip():
                name = name.strip()
                now = datetime.now().isoformat()
                db.execute(
                    "INSERT INTO tasks (workspace_id, name, status, created_at) VALUES (?, ?, 'active', ?)",
                    (current_ws_id, name, now),
                )
                db.commit()
                status_msg = f"Created task: {name}"

        # New step under current task (a)
        elif ch == "a":
            if rows:
                r = rows[cursor_pos]
                task_id = r["id"] if r["type"] == "task" else r["task_id"]
                text = textbox_input(stdscr, "New step (ESC to cancel):")
                if text and text.strip():
                    text = text.strip()
                    now = datetime.now().isoformat()
                    db.execute(
                        "INSERT INTO steps (task_id, text, priority, created_at) VALUES (?, ?, 'medium', ?)",
                        (task_id, text, now),
                    )
                    db.commit()
                    collapsed.discard(task_id)
                    status_msg = f"Added: {text}"
            else:
                status_msg = "Create a task first (A)"

        # Edit
        elif ch == "e":
            if rows:
                r = rows[cursor_pos]
                if r["type"] == "task":
                    new_name = textbox_input(stdscr, "Edit task name:", prefill=r["name"])
                    if new_name and new_name.strip():
                        db.execute("UPDATE tasks SET name = ? WHERE id = ?", (new_name.strip(), r["id"]))
                        db.commit()
                        status_msg = "Updated task"
                else:
                    new_text = textbox_input(stdscr, "Edit step:", prefill=r["text"])
                    if new_text and new_text.strip():
                        db.execute("UPDATE steps SET text = ? WHERE id = ?", (new_text.strip(), r["id"]))
                        db.commit()
                        status_msg = "Updated step"

        # Delete
        elif ch == "d" or ch == curses.KEY_DC:
            if rows:
                r = rows[cursor_pos]
                if r["type"] == "task":
                    db.execute("DELETE FROM tasks WHERE id = ?", (r["id"],))
                    db.commit()
                    collapsed.discard(r["id"])
                    status_msg = f"Deleted task: {r['name']}"
                else:
                    db.execute("DELETE FROM steps WHERE id = ?", (r["id"],))
                    db.commit()
                    status_msg = f"Deleted: {r['text']}"

        # Cycle priority (steps only)
        elif ch == "p":
            if rows:
                r = rows[cursor_pos]
                if r["type"] == "step":
                    order = ["low", "medium", "high"]
                    idx = (order.index(r["priority"]) + 1) % 3
                    db.execute("UPDATE steps SET priority = ? WHERE id = ?", (order[idx], r["id"]))
                    db.commit()

        # Search
        elif ch == "f":
            query = textbox_input(stdscr, "Search (ESC to clear):")
            if query is None:
                search_query = ""
            else:
                search_query = query.strip()
            cursor_pos, scroll_offset = 0, 0

        # Workspace switcher
        elif ch == "w":
            workspaces = db.execute("SELECT id, name FROM workspaces ORDER BY id").fetchall()
            options = list(workspaces) + [(-1, "+ New workspace")]
            picked = popup_select(stdscr, "Switch workspace", options, lambda r: r[1])
            if picked:
                if picked[0] == -1:
                    name = textbox_input(stdscr, "Workspace name:")
                    if name and name.strip():
                        name = name.strip()
                        now = datetime.now().isoformat()
                        if db.execute("SELECT 1 FROM workspaces WHERE name = ?", (name,)).fetchone():
                            status_msg = f"Workspace '{name}' already exists"
                        else:
                            cur = db.execute(
                                "INSERT INTO workspaces (name, created_at) VALUES (?, ?)", (name, now)
                            )
                            db.commit()
                            current_ws_id, current_ws_name = cur.lastrowid, name
                            collapsed.clear()
                            cursor_pos, scroll_offset = 0, 0
                            status_msg = f"Created workspace: {name}"
                else:
                    current_ws_id, current_ws_name = picked[0], picked[1]
                    collapsed.clear()
                    cursor_pos, scroll_offset = 0, 0
                    status_msg = f"Switched to: {current_ws_name}"
