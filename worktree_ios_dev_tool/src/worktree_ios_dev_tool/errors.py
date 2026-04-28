# worktree_ios_dev_tool/src/worktree_ios_dev_tool/errors.py
"""Typed error classes. Each maps to an exit code in cli.main()."""


class WorktreeIosError(Exception):
    """Base class; never raised directly."""

    exit_code: int = 1


class UserError(WorktreeIosError):
    """Bad CLI args, missing required config section, verb preconditions not met."""

    exit_code = 1


class EnvError(WorktreeIosError):
    """Environment problem: config not found, xcodebuild/simctl not on PATH."""

    exit_code = 2


class SubprocessError(WorktreeIosError):
    """An invoked tool (xcodebuild, simctl) returned non-zero."""

    exit_code = 3

    def __init__(self, message: str, *, upstream_exit: int) -> None:
        super().__init__(message)
        self.upstream_exit = upstream_exit
