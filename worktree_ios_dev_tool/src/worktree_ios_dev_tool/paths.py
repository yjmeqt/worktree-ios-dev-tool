# worktree_ios_dev_tool/src/worktree_ios_dev_tool/paths.py
"""Filesystem walk-up + path-routing helpers."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .errors import EnvError, UserError

CONFIG_DIRNAME = "worktree-ios-dev"
PROJECT_FILENAME = "project.toml"
SIMULATOR_FILENAME = "simulator.toml"
LEGACY_FILENAME = "config.toml"

_LOCAL_FILESYSTEMS = frozenset({"apfs", "hfs"})
_OFFLOAD_ROOT = Path("/tmp/worktree-ios-dev")


def find_project_toml(start: Path | None = None) -> Path:
    """Walk up from *start* (default: cwd) to find ``worktree-ios-dev/project.toml``.

    Stops at $HOME or filesystem root. If a legacy ``config.toml`` is found at
    a step where ``project.toml`` is missing, raise :class:`UserError` with
    the manual-migration recipe (we never auto-convert).

    Raises:
        UserError: when a legacy config.toml is found instead of project.toml.
        EnvError:  when nothing is found by the time we reach $HOME / root.
    """
    cwd = (start or Path.cwd()).resolve()
    home = Path.home().resolve()
    probe = cwd
    while True:
        cfg_dir = probe / CONFIG_DIRNAME
        new = cfg_dir / PROJECT_FILENAME
        legacy = cfg_dir / LEGACY_FILENAME
        if new.is_file():
            return new
        if legacy.is_file() and not new.is_file():
            raise UserError(_legacy_message(legacy))
        if probe == probe.parent or probe == home:
            break
        probe = probe.parent
    raise EnvError(
        f"No `{CONFIG_DIRNAME}/{PROJECT_FILENAME}` found walking up from `{cwd}`. "
        f"Run `worktree-ios-dev-tool proj init` from your worktree to set one up."
    )


def _legacy_message(legacy_path: Path) -> str:
    """Build the migration instructions printed when a legacy config.toml is detected."""
    return (
        f"Detected legacy config.toml at {legacy_path}.\n"
        f"This tool now uses split project.toml + simulator.toml.\n"
        f"Manual migration:\n"
        f"  1. Read the legacy values:    cat {legacy_path}\n"
        f"  2. Write the new project.toml: worktree-ios-dev-tool proj init --force "
        f"--project <relpath> --scheme <name>\n"
        f"  3. Recreate the simulator:     worktree-ios-dev-tool sim pick\n"
        f"  4. Remove the legacy file:     rm {legacy_path}"
    )


def simulator_toml_for(project_toml: Path) -> Path:
    """Return the expected simulator.toml path that pairs with *project_toml*."""
    return project_toml.parent / SIMULATOR_FILENAME


def config_dir(config_path: Path) -> Path:
    """Directory that contains config.toml (i.e. the worktree-ios-dev/ dir)."""
    return config_path.parent


def worktree_root(config_path: Path) -> Path:
    """Directory that contains the worktree-ios-dev/ dir."""
    return config_path.parent.parent


def _filesystem_type(path: Path) -> str | None:
    """Return the fstype of the mount point containing *path*, lower-cased.

    Parses `mount(8)` output, selects longest matching ancestor mount point.
    Returns None on error or when mount(8) is unavailable.
    """
    target = path.resolve()
    while not target.exists() and target != target.parent:
        target = target.parent
    try:
        result = subprocess.run(
            ["mount"], capture_output=True, text=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None

    best: tuple[int, str] | None = None
    for line in result.stdout.splitlines():
        try:
            _, rest = line.split(" on ", 1)
            mount_str, paren = rest.split(" (", 1)
            mountpoint = Path(mount_str.strip()).resolve()
            fstype = paren.split(",", 1)[0].strip().lower()
        except (ValueError, IndexError):
            continue
        try:
            target.relative_to(mountpoint)
        except ValueError:
            continue
        depth = len(mountpoint.parts)
        if best is None or depth > best[0]:
            best = (depth, fstype)
    return best[1] if best else None


def _is_on_local_filesystem(path: Path) -> bool:
    """True iff *path* is on APFS or HFS. Unknown/non-local fstypes return False."""
    fstype = _filesystem_type(path)
    return fstype in _LOCAL_FILESYSTEMS


def derived_data_dir(config_path: Path) -> Path:
    """Resolve where xcodebuild's DerivedData should live.

    Defaults to <worktree-ios-dev>/derivedData. Falls back to
    /tmp/worktree-ios-dev/<worktree-basename>/derivedData when the in-tree
    path is on a non-local filesystem (Tart VirtIOFS, SMB, NFS, etc.) —
    SPM XCFramework extraction requires symlinks that non-local filesystems
    don't preserve.
    """
    default = config_dir(config_path) / "derivedData"
    if _is_on_local_filesystem(default):
        return default
    return _OFFLOAD_ROOT / worktree_root(config_path).name / "derivedData"


def find_worktree_root_for_bootstrap(start: Path | None = None) -> Path:
    """Walk up from cwd for the nearest directory containing a .git entry.
    Raises UserError if not found."""
    cwd = Path(os.path.abspath(start or Path.cwd()))
    probe = cwd
    while True:
        if (probe / ".git").exists():
            return probe
        if probe == probe.parent:
            break
        probe = probe.parent
    raise UserError(
        f"Could not find a git worktree root above `{cwd}`. "
        f"Run from inside a git repository."
    )
