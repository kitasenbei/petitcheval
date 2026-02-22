"""Entry point for `python -m petitcheval`."""

import curses
import sys

from .cli import cli_error, cli_step, cli_task, cli_workspace
from .db import get_db


def main():
    args = sys.argv[1:]
    if not args:
        from .tui import tui_main
        curses.wrapper(tui_main)
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
