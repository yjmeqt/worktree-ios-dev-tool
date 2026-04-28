# worktree_ios_dev_tool/src/worktree_ios_dev_tool/ui.py
"""Clack-style terminal UI helpers.

Interactive (TTY): ◇ / ◆ / │ prefix style with rich spinners.
Non-interactive:   plain [worktree-ios-dev-tool] prefix for agent/script output.
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import Generator

_interactive: bool = sys.stdin.isatty() and sys.stdout.isatty()
_PREFIX = "[worktree-ios-dev-tool]"


def is_interactive() -> bool:
    return _interactive


def step(msg: str) -> None:
    """An in-progress or informational step."""
    if _interactive:
        print(f"◇  {msg}")
    else:
        print(f"{_PREFIX} {msg}")


def done(msg: str) -> None:
    """A completed step or final success."""
    if _interactive:
        print(f"◆  {msg}")
    else:
        print(f"{_PREFIX} {msg}")


def info(msg: str) -> None:
    """Continuation detail line under a step."""
    if _interactive:
        print(f"│  {msg}")
    else:
        print(f"{_PREFIX}   {msg}")


def sep() -> None:
    """Vertical bar separator between steps (interactive only)."""
    if _interactive:
        print("│")


def warn(msg: str) -> None:
    if _interactive:
        print(f"▲  {msg}")
    else:
        print(f"{_PREFIX} warning: {msg}", file=sys.stderr)


def problem(msg: str) -> None:
    """A failed check (used by doctor)."""
    if _interactive:
        print(f"■  {msg}")
    else:
        print(f"{_PREFIX} error: {msg}", file=sys.stderr)


@contextmanager
def spinner(msg: str) -> Generator[None, None, None]:
    """Show a spinner while the body executes (interactive only)."""
    if _interactive:
        try:
            from rich.progress import Progress, SpinnerColumn, TextColumn
            with Progress(SpinnerColumn(), TextColumn(msg), transient=True) as p:
                p.add_task(msg)
                yield
            return
        except ImportError:
            pass
    if not _interactive:
        print(f"{_PREFIX} {msg}")
    yield
