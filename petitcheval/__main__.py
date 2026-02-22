"""Entry point for `python -m petitcheval`."""

import curses
import sys

from .cli import cli_error, cli_step, cli_task, cli_workspace
from .db import get_db

HELP = """\
petitcheval — hierarchical TODO TUI & CLI

Usage:
  petitcheval                          Launch the TUI
  petitcheval <command> [args]         Run a CLI command (JSON output)
  petitcheval --help | -h              Show this help

Commands:
  workspace list                       List all workspaces
  workspace add <name>                 Create a workspace
  workspace rm <id>                    Delete a workspace

  task list [--workspace <name|id>]    List tasks
  task add <name> --workspace <name|id>
  task rm <id>

  step list [--task <id>] [--workspace <name|id>] [--status pending|done|all]
  step add <text> --task <id> [-p high|medium|low]
  step done <id>
  step undone <id>
  step edit <id> <text>
  step rm <id>

TUI keybindings:
  j/k        Navigate down/up
  Enter      Toggle collapse (task) / toggle done (step)
  A          New task
  a          New step under current task
  e          Edit selected item
  d          Delete selected item
  p          Cycle step priority
  f          Search / filter
  w          Switch workspace
  g/G        Jump to top/bottom
  q          Quit
"""


def main():
    args = sys.argv[1:]
    if not args:
        from .tui import tui_main
        curses.wrapper(tui_main)
        return

    if args[0] in ("--help", "-h"):
        print(HELP)
        return

    db = get_db()
    resource = args[0]
    rest = args[1:]

    if resource == "workspace":
        cli_workspace(db, rest)
    elif resource == "task":
        cli_task(db, rest)
    elif resource == "step":
        cli_step(db, rest)
    else:
        cli_error(f"Unknown command: {resource}. Use workspace, task, or step.")


if __name__ == "__main__":
    main()
