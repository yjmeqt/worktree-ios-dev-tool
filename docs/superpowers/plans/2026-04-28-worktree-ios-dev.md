# worktree-ios-dev Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename `pulse-ios-dev-tool` → `worktree-ios-dev` and make bootstrap project-agnostic via auto-discovery and interactive fuzzy pickers.

**Architecture:** New package directory `worktree_ios_dev/` is created alongside the old one; modules are ported one at a time with updated strings and new logic; old package is deleted in the final task. Bootstrap is rewritten with `rich` + `InquirerPy` for interactive discovery and a non-interactive `--yes`/`--project`/`--scheme` path for agents.

**Tech Stack:** Python 3.11+, `tomlkit`, `rich`, `InquirerPy`, stdlib `unittest`, `uv tool install --editable`

---

## File Map

| Path | Action | Notes |
|------|--------|-------|
| `worktree_ios_dev/pyproject.toml` | Create | New package name, add rich + InquirerPy deps |
| `worktree_ios_dev/src/worktree_ios_dev/__init__.py` | Create | Version only |
| `worktree_ios_dev/src/worktree_ios_dev/__main__.py` | Create | Entry point |
| `worktree_ios_dev/src/worktree_ios_dev/errors.py` | Create | Rename PulseIosError → WorktreeIosError |
| `worktree_ios_dev/src/worktree_ios_dev/paths.py` | Create | Update CONFIG_DIRNAME, _OFFLOAD_ROOT, fix bootstrap root |
| `worktree_ios_dev/src/worktree_ios_dev/config.py` | Create | Add simulator_prefix to ProjectConfig |
| `worktree_ios_dev/src/worktree_ios_dev/proc.py` | Create | Copy, update imports |
| `worktree_ios_dev/src/worktree_ios_dev/xcodebuild.py` | Create | Copy, update imports |
| `worktree_ios_dev/src/worktree_ios_dev/runapp.py` | Create | Copy, update imports + error messages |
| `worktree_ios_dev/src/worktree_ios_dev/packages.py` | Create | Copy, update imports |
| `worktree_ios_dev/src/worktree_ios_dev/simulator.py` | Create | Replace _pick_tty with InquirerPy |
| `worktree_ios_dev/src/worktree_ios_dev/bootstrap.py` | Create | Full rewrite with discovery logic |
| `worktree_ios_dev/src/worktree_ios_dev/boot.py` | Create | Use simulator_prefix from config |
| `worktree_ios_dev/src/worktree_ios_dev/cli.py` | Create | Update prog, verbs, messages |
| `worktree_ios_dev/tests/test_paths.py` | Create | Port from pulse_ios_dev_tool with updated strings |
| `worktree_ios_dev/tests/test_bootstrap.py` | Create | New: discovery helpers unit tests |
| `pulse_ios_dev_tool/` | Delete | Task 11 |
| `skills/pulse-ios-dev/` | Rename | → `skills/worktree-ios-dev/` in Task 11 |

---

## Task 1: Package Skeleton

**Files:**
- Create: `worktree_ios_dev/pyproject.toml`
- Create: `worktree_ios_dev/src/worktree_ios_dev/__init__.py`
- Create: `worktree_ios_dev/src/worktree_ios_dev/__main__.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p worktree_ios_dev/src/worktree_ios_dev
mkdir -p worktree_ios_dev/tests
touch worktree_ios_dev/tests/__init__.py
```

- [ ] **Step 2: Write pyproject.toml**

```toml
# worktree_ios_dev/pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "worktree-ios-dev"
version = "0.1.0"
description = "Generic iOS worktree build / simulator / test CLI — per-worktree config, global install."
requires-python = ">=3.11"
dependencies = [
    "tomlkit>=0.13",
    "rich>=13.0",
    "InquirerPy>=0.3.4",
]

[project.scripts]
worktree-ios-dev = "worktree_ios_dev.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/worktree_ios_dev"]
```

- [ ] **Step 3: Write __init__.py and __main__.py**

`worktree_ios_dev/src/worktree_ios_dev/__init__.py`:
```python
__version__ = "0.1.0"
```

`worktree_ios_dev/src/worktree_ios_dev/__main__.py`:
```python
from worktree_ios_dev.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Verify package is importable**

```bash
cd worktree_ios_dev && uv run python -c "import worktree_ios_dev; print(worktree_ios_dev.__version__)"
```

Expected output: `0.1.0`

- [ ] **Step 5: Commit**

```bash
git add worktree_ios_dev/
git commit -m "feat(worktree-ios-dev): add package skeleton with pyproject.toml"
```

---

## Task 2: errors.py

**Files:**
- Create: `worktree_ios_dev/src/worktree_ios_dev/errors.py`

- [ ] **Step 1: Write errors.py**

```python
# worktree_ios_dev/src/worktree_ios_dev/errors.py
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
```

- [ ] **Step 2: Verify import**

```bash
cd worktree_ios_dev && uv run python -c "from worktree_ios_dev.errors import WorktreeIosError, UserError, EnvError, SubprocessError; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add worktree_ios_dev/src/worktree_ios_dev/errors.py
git commit -m "feat(worktree-ios-dev): add errors.py (WorktreeIosError base)"
```

---

## Task 3: paths.py + Tests

**Files:**
- Create: `worktree_ios_dev/src/worktree_ios_dev/paths.py`
- Create: `worktree_ios_dev/tests/test_paths.py`

- [ ] **Step 1: Write the failing tests**

```python
# worktree_ios_dev/tests/test_paths.py
"""Tests for worktree_ios_dev.paths (DerivedData routing)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from worktree_ios_dev.paths import (  # noqa: E402
    _filesystem_type,
    _is_on_local_filesystem,
    derived_data_dir,
    find_worktree_root_for_bootstrap,
    CONFIG_DIRNAME,
)


class FilesystemTypeTests(unittest.TestCase):
    def test_root_is_apfs_on_macos(self) -> None:
        result = _filesystem_type(Path("/"))
        if result is None:
            self.skipTest("mount(8) not available in this environment")
        self.assertEqual(result, "apfs")

    def test_returns_none_when_mount_fails(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            self.assertIsNone(_filesystem_type(Path("/")))

    def test_picks_longest_matching_mountpoint(self) -> None:
        fake_mount_output = (
            "/dev/disk1s1 on / (apfs, local, journaled)\n"
            "/dev/disk2 on /Volumes/My Shared Files "
            "(smbfs, nodev, nosuid, mounted by admin)\n"
        )

        class FakeProc:
            stdout = fake_mount_output

        with (
            patch("subprocess.run", return_value=FakeProc()),
            patch.object(Path, "exists", return_value=True),
        ):
            self.assertEqual(
                _filesystem_type(Path("/Volumes/My Shared Files/foo")),
                "smbfs",
            )


class IsLocalFilesystemTests(unittest.TestCase):
    def test_apfs_is_local(self) -> None:
        with patch("worktree_ios_dev.paths._filesystem_type", return_value="apfs"):
            self.assertTrue(_is_on_local_filesystem(Path("/")))

    def test_smbfs_is_not_local(self) -> None:
        with patch("worktree_ios_dev.paths._filesystem_type", return_value="smbfs"):
            self.assertFalse(_is_on_local_filesystem(Path("/x")))

    def test_unknown_fstype_is_treated_as_non_local(self) -> None:
        with patch("worktree_ios_dev.paths._filesystem_type", return_value="weirdfs"):
            self.assertFalse(_is_on_local_filesystem(Path("/x")))

    def test_none_fstype_is_treated_as_non_local(self) -> None:
        with patch("worktree_ios_dev.paths._filesystem_type", return_value=None):
            self.assertFalse(_is_on_local_filesystem(Path("/x")))


class DerivedDataDirTests(unittest.TestCase):
    def _config(self, root: Path) -> Path:
        """Fake config layout: <root>/worktree-ios-dev/config.toml."""
        cfg_dir = root / CONFIG_DIRNAME
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg = cfg_dir / "config.toml"
        cfg.touch()
        return cfg

    def test_local_filesystem_returns_in_tree_path(self) -> None:
        with patch("worktree_ios_dev.paths._is_on_local_filesystem", return_value=True):
            with tempfile.TemporaryDirectory() as tmp:
                wt = Path(tmp) / "feat-x"
                wt.mkdir()
                cfg = self._config(wt)
                self.assertEqual(
                    derived_data_dir(cfg),
                    wt / CONFIG_DIRNAME / "derivedData",
                )

    def test_non_local_filesystem_routes_to_offload(self) -> None:
        with patch("worktree_ios_dev.paths._is_on_local_filesystem", return_value=False):
            with tempfile.TemporaryDirectory() as tmp:
                wt = Path(tmp) / "feat-comment-scrolling"
                wt.mkdir()
                cfg = self._config(wt)
                self.assertEqual(
                    derived_data_dir(cfg),
                    Path("/tmp/worktree-ios-dev/feat-comment-scrolling/derivedData"),
                )

    def test_offload_keys_on_worktree_basename_not_full_path(self) -> None:
        with patch("worktree_ios_dev.paths._is_on_local_filesystem", return_value=False):
            with tempfile.TemporaryDirectory() as tmp:
                a = Path(tmp) / "feat-A"
                b = Path(tmp) / "feat-B"
                a.mkdir()
                b.mkdir()
                self.assertNotEqual(
                    derived_data_dir(self._config(a)),
                    derived_data_dir(self._config(b)),
                )


class FindWorktreeRootForBootstrapTests(unittest.TestCase):
    def test_finds_git_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            subdir = root / "ios" / "src"
            subdir.mkdir(parents=True)
            result = find_worktree_root_for_bootstrap(start=subdir)
            self.assertEqual(result, root)

    def test_raises_user_error_when_no_git(self) -> None:
        from worktree_ios_dev.errors import UserError
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(UserError):
                find_worktree_root_for_bootstrap(start=Path(tmp))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd worktree_ios_dev && uv run python -m unittest tests.test_paths -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'worktree_ios_dev.paths'`

- [ ] **Step 3: Write paths.py**

```python
# worktree_ios_dev/src/worktree_ios_dev/paths.py
"""Filesystem walk-up + path-routing helpers."""
from __future__ import annotations

import subprocess
from pathlib import Path

from .errors import EnvError, UserError

CONFIG_DIRNAME = "worktree-ios-dev"
CONFIG_FILENAME = "config.toml"

_LOCAL_FILESYSTEMS = frozenset({"apfs", "hfs"})
_OFFLOAD_ROOT = Path("/tmp/worktree-ios-dev")


def find_config(start: Path | None = None) -> Path:
    """Walk up from `start` (default cwd) looking for <dir>/worktree-ios-dev/config.toml.
    Stops at $HOME or filesystem root. Raises EnvError if not found."""
    cwd = (start or Path.cwd()).resolve()
    home = Path.home().resolve()
    probe = cwd
    while True:
        candidate = probe / CONFIG_DIRNAME / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
        if probe == probe.parent or probe == home:
            break
        probe = probe.parent
    raise EnvError(
        f"No `{CONFIG_DIRNAME}/{CONFIG_FILENAME}` found walking up from `{cwd}`. "
        f"Run `worktree-ios-dev bootstrap` from your worktree to set one up."
    )


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
    cwd = (start or Path.cwd()).resolve()
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd worktree_ios_dev && uv run python -m unittest tests.test_paths -v
```

Expected: all 11 tests pass

- [ ] **Step 5: Commit**

```bash
git add worktree_ios_dev/src/worktree_ios_dev/paths.py worktree_ios_dev/tests/test_paths.py
git commit -m "feat(worktree-ios-dev): add paths.py with updated CONFIG_DIRNAME and bootstrap root"
```

---

## Task 4: config.py (add simulator_prefix)

**Files:**
- Create: `worktree_ios_dev/src/worktree_ios_dev/config.py`

- [ ] **Step 1: Write config.py**

```python
# worktree_ios_dev/src/worktree_ios_dev/config.py
"""TOML read + schema validation. Writes via tomlkit to preserve comments."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomlkit

from .errors import UserError
from .paths import config_dir, derived_data_dir, worktree_root


@dataclass(frozen=True)
class ProjectConfig:
    path: Path             # absolute
    scheme: str
    configuration: str
    simulator_prefix: str | None = None


@dataclass(frozen=True)
class SimulatorConfig:
    name: str
    udid: str
    device: str
    runtime: str


@dataclass(frozen=True)
class PackageOverride:
    scheme: str | None = None


@dataclass(frozen=True)
class Config:
    config_path: Path
    worktree_root: Path
    derived_data: Path
    project: ProjectConfig
    simulator: SimulatorConfig | None
    packages_root: Path
    package_overrides: dict[str, PackageOverride] = field(default_factory=dict)
    extras_xcodebuild_flags: list[str] = field(default_factory=list)


_ALLOWED_TOP_LEVEL = {"project", "simulator", "packages_root", "packages", "extras"}
_ALLOWED_PROJECT = {"path", "scheme", "configuration", "simulator_prefix"}
_ALLOWED_SIMULATOR = {"name", "udid", "device", "runtime"}
_ALLOWED_PACKAGES_ROOT = {"path"}
_ALLOWED_PACKAGE = {"scheme"}
_ALLOWED_EXTRAS = {"xcodebuild_flags"}


def _require_keys(table_name: str, table: dict[str, Any], allowed: set[str]) -> None:
    extra = set(table) - allowed
    if extra:
        raise UserError(
            f"Unknown key(s) in [{table_name}]: {sorted(extra)}. "
            f"Allowed: {sorted(allowed)}."
        )


def load(config_path: Path) -> Config:
    """Parse and validate config.toml. Raises UserError on schema violations."""
    with config_path.open("rb") as fh:
        data = tomllib.load(fh)

    _require_keys("<root>", data, _ALLOWED_TOP_LEVEL)

    if "project" not in data:
        raise UserError(
            f"Missing [project] section in {config_path}. "
            f"Re-run `worktree-ios-dev bootstrap --force` to re-seed."
        )
    proj = data["project"]
    _require_keys("project", proj, _ALLOWED_PROJECT)
    for key in ("path", "scheme"):
        if key not in proj:
            raise UserError(f"[project] missing `{key}` in {config_path}.")
    wt_root = worktree_root(config_path)
    project = ProjectConfig(
        path=(wt_root / proj["path"]).resolve(),
        scheme=proj["scheme"],
        configuration=proj.get("configuration", "Debug"),
        simulator_prefix=proj.get("simulator_prefix") or None,
    )

    simulator: SimulatorConfig | None = None
    if "simulator" in data:
        sim = data["simulator"]
        _require_keys("simulator", sim, _ALLOWED_SIMULATOR)
        for key in _ALLOWED_SIMULATOR:
            if key not in sim:
                raise UserError(f"[simulator] missing `{key}` in {config_path}.")
        simulator = SimulatorConfig(
            name=sim["name"],
            udid=sim["udid"],
            device=sim["device"],
            runtime=sim["runtime"],
        )

    pkg_root_cfg = data.get("packages_root", {"path": "ios/Packages"})
    _require_keys("packages_root", pkg_root_cfg, _ALLOWED_PACKAGES_ROOT)
    packages_root = (wt_root / pkg_root_cfg.get("path", "ios/Packages")).resolve()

    overrides: dict[str, PackageOverride] = {}
    for name, table in (data.get("packages", {}) or {}).items():
        _require_keys(f"packages.{name}", table, _ALLOWED_PACKAGE)
        overrides[name] = PackageOverride(scheme=table.get("scheme"))

    extras = data.get("extras", {})
    _require_keys("extras", extras, _ALLOWED_EXTRAS)
    flags = extras.get("xcodebuild_flags", [])
    if not isinstance(flags, list) or not all(isinstance(f, str) for f in flags):
        raise UserError(
            f"[extras].xcodebuild_flags must be a list of strings in {config_path}."
        )

    return Config(
        config_path=config_path,
        worktree_root=wt_root,
        derived_data=derived_data_dir(config_path),
        project=project,
        simulator=simulator,
        packages_root=packages_root,
        package_overrides=overrides,
        extras_xcodebuild_flags=list(flags),
    )


def require_simulator(cfg: Config) -> SimulatorConfig:
    if cfg.simulator is None:
        raise UserError(
            "No [simulator] block in config.toml. "
            "Run `worktree-ios-dev boot` first to create and register a simulator."
        )
    return cfg.simulator


def write_simulator(config_path: Path, sim: SimulatorConfig) -> None:
    """Rewrite the [simulator] block in-place using tomlkit to preserve comments."""
    text = config_path.read_text()
    doc = tomlkit.parse(text)
    block = tomlkit.table()
    block["name"] = sim.name
    block["udid"] = sim.udid
    block["device"] = sim.device
    block["runtime"] = sim.runtime
    doc["simulator"] = block
    config_path.write_text(tomlkit.dumps(doc))
```

- [ ] **Step 2: Verify import and simulator_prefix field**

```bash
cd worktree_ios_dev && uv run python -c "
from worktree_ios_dev.config import ProjectConfig
from pathlib import Path
p = ProjectConfig(path=Path('/x'), scheme='MyApp', configuration='Debug', simulator_prefix='MyApp')
print(p.simulator_prefix)
"
```

Expected: `MyApp`

- [ ] **Step 3: Commit**

```bash
git add worktree_ios_dev/src/worktree_ios_dev/config.py
git commit -m "feat(worktree-ios-dev): add config.py with simulator_prefix field"
```

---

## Task 5: Mechanical Port (proc, xcodebuild, runapp, packages)

**Files:**
- Create: `worktree_ios_dev/src/worktree_ios_dev/proc.py`
- Create: `worktree_ios_dev/src/worktree_ios_dev/xcodebuild.py`
- Create: `worktree_ios_dev/src/worktree_ios_dev/runapp.py`
- Create: `worktree_ios_dev/src/worktree_ios_dev/packages.py`

These files are copied from the old package with only import paths and error message strings updated.

- [ ] **Step 1: Write proc.py**

Copy `pulse_ios_dev_tool/src/pulse_ios_dev_tool/proc.py` verbatim, changing only the import line:

```python
# Line 10 — change:
from .errors import EnvError, SubprocessError
```

The rest of proc.py is identical. Full file:

```python
# worktree_ios_dev/src/worktree_ios_dev/proc.py
"""The only module that actually runs subprocesses."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from .errors import EnvError, SubprocessError


def require(binary: str) -> None:
    """Raise EnvError if `binary` is not on PATH."""
    if shutil.which(binary) is None:
        raise EnvError(
            f"`{binary}` not found on PATH. Install it or run `xcode-select --install`."
        )


def _run_xcodebuild_pretty(
    argv: Sequence[str],
    *,
    cwd: Path | None,
) -> int:
    xcb = subprocess.Popen(
        ["mint", "run", "xcbeautify"],
        stdin=subprocess.PIPE,
    )
    try:
        child = subprocess.Popen(
            list(argv),
            cwd=cwd,
            stdout=xcb.stdin,
            stderr=subprocess.STDOUT,
        )
    finally:
        assert xcb.stdin is not None
        xcb.stdin.close()
    returncode = child.wait()
    xcb.wait()
    return returncode


def run(
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    capture: bool = False,
    verbose: bool = False,
) -> subprocess.CompletedProcess[str]:
    if verbose:
        display_cwd = f" (cwd={cwd})" if cwd else ""
        print(f"+ {' '.join(argv)}{display_cwd}")

    use_pretty = (
        not capture
        and len(argv) > 0
        and argv[0] == "xcodebuild"
        and shutil.which("mint") is not None
    )

    if use_pretty:
        returncode = _run_xcodebuild_pretty(argv, cwd=cwd)
        if returncode != 0:
            raise SubprocessError(
                f"xcodebuild failed with exit code {returncode}",
                upstream_exit=returncode,
            )
        return subprocess.CompletedProcess(list(argv), returncode, stdout=None, stderr=None)

    if (
        not capture
        and len(argv) > 0
        and argv[0] == "xcodebuild"
        and shutil.which("mint") is None
    ):
        print(
            "note: `mint` not found on PATH — xcodebuild output will not be prettified "
            "through xcbeautify. Install mint (brew install mint) for cleaner logs.",
            file=sys.stderr,
        )

    result = subprocess.run(
        list(argv),
        cwd=cwd,
        text=True,
        capture_output=capture,
    )
    if result.returncode != 0:
        tool = argv[0]
        msg = f"{tool} failed with exit code {result.returncode}"
        if capture and result.stderr:
            msg += f":\n{result.stderr.rstrip()}"
        raise SubprocessError(msg, upstream_exit=result.returncode)
    return result


def run_json(argv: Sequence[str], *, verbose: bool = False) -> str:
    result = run(argv, capture=True, verbose=verbose)
    return result.stdout
```

- [ ] **Step 2: Write xcodebuild.py**

```python
# worktree_ios_dev/src/worktree_ios_dev/xcodebuild.py
"""Pure argv builders for xcodebuild. No subprocess calls."""
from __future__ import annotations

from typing import Sequence

from .config import Config, SimulatorConfig, require_simulator


def _destination(sim: SimulatorConfig) -> str:
    return f"platform=iOS Simulator,id={sim.udid}"


def _common(cfg: Config, sim: SimulatorConfig | None, *, release: bool) -> list[str]:
    configuration = "Release" if release else cfg.project.configuration
    argv: list[str] = [
        "xcodebuild",
        "-project", str(cfg.project.path),
        "-scheme", cfg.project.scheme,
        "-configuration", configuration,
        "-derivedDataPath", str(cfg.derived_data),
    ]
    if sim is not None:
        argv += ["-destination", _destination(sim)]
    argv += cfg.extras_xcodebuild_flags
    return argv


def build_argv(cfg: Config, *, release: bool = False, scheme_override: str | None = None) -> list[str]:
    sim = require_simulator(cfg)
    argv = _common(cfg, sim, release=release)
    if scheme_override:
        argv[argv.index("-scheme") + 1] = scheme_override
    return argv + ["build"]


def test_argv(
    cfg: Config,
    *,
    release: bool = False,
    only_testing: Sequence[str] = (),
    skip_testing: Sequence[str] = (),
) -> list[str]:
    sim = require_simulator(cfg)
    argv = _common(cfg, sim, release=release) + ["test"]
    for t in only_testing:
        argv += ["-only-testing", t]
    for t in skip_testing:
        argv += ["-skip-testing", t]
    return argv


def clean_argv(cfg: Config) -> list[str]:
    return _common(cfg, None, release=False) + ["clean"]
```

- [ ] **Step 3: Write runapp.py**

```python
# worktree_ios_dev/src/worktree_ios_dev/runapp.py
"""Implementation of the `run` verb: build -> install -> launch."""
from __future__ import annotations

import argparse
import plistlib
from pathlib import Path

from . import simulator as sim_mod, xcodebuild
from .config import load, require_simulator
from .errors import UserError
from .paths import find_config
from .proc import run as proc_run


def _find_app(derived_data: Path, scheme: str, configuration: str) -> Path:
    candidate_dir = derived_data / "Build" / "Products" / f"{configuration}-iphonesimulator"
    app_path = candidate_dir / f"{scheme}.app"
    if app_path.is_dir():
        return app_path
    matches = list(candidate_dir.glob("*.app"))
    if len(matches) == 1:
        return matches[0]
    raise UserError(
        f"Could not locate a built .app under {candidate_dir}. "
        f"Expected {scheme}.app. Try `worktree-ios-dev build` first."
    )


def _bundle_id(app_path: Path) -> str:
    info = app_path / "Info.plist"
    with info.open("rb") as fh:
        plist = plistlib.load(fh)
    bundle_id = plist.get("CFBundleIdentifier")
    if not bundle_id:
        raise UserError(f"CFBundleIdentifier missing in {info}.")
    return bundle_id


def run(args: argparse.Namespace) -> int:
    cfg_path = args.config.resolve() if args.config else find_config()
    cfg = load(cfg_path)
    sim = require_simulator(cfg)

    argv = xcodebuild.build_argv(cfg, release=args.release)
    proc_run(argv, verbose=args.verbose)

    configuration = "Release" if args.release else cfg.project.configuration
    app_path = _find_app(cfg.derived_data, cfg.project.scheme, configuration)
    bundle_id = _bundle_id(app_path)

    sim_mod.boot(sim.udid)
    proc_run(["xcrun", "simctl", "install", sim.udid, str(app_path)], verbose=args.verbose)
    result = proc_run(["xcrun", "simctl", "launch", sim.udid, bundle_id], capture=True, verbose=args.verbose)
    print(result.stdout.strip())
    print(f"bundle_id = {bundle_id}")
    return 0
```

- [ ] **Step 4: Write packages.py**

```python
# worktree_ios_dev/src/worktree_ios_dev/packages.py
"""Local Swift package test resolution."""
from __future__ import annotations

from pathlib import Path

from .config import Config, require_simulator
from .errors import UserError


def resolve(cfg: Config, package_name: str) -> tuple[list[str], Path]:
    """Return (argv, cwd) for testing a local package."""
    pkg_dir = cfg.packages_root / package_name
    if not pkg_dir.is_dir():
        raise UserError(
            f"Package directory not found: `{pkg_dir}`. "
            f"Check the name and `packages_root.path` in config.toml."
        )

    override = cfg.package_overrides.get(package_name)
    scheme = override.scheme if (override and override.scheme) else package_name

    sim = require_simulator(cfg)
    argv = [
        "xcodebuild",
        "test",
        "-project", "Package.swift",
        "-scheme", scheme,
        "-destination", f"platform=iOS Simulator,id={sim.udid}",
        "-derivedDataPath", str(cfg.derived_data),
    ] + cfg.extras_xcodebuild_flags
    return argv, pkg_dir
```

- [ ] **Step 5: Verify all four modules import**

```bash
cd worktree_ios_dev && uv run python -c "
from worktree_ios_dev import proc, xcodebuild, runapp, packages
print('all ok')
"
```

Expected: `all ok`

- [ ] **Step 6: Commit**

```bash
git add worktree_ios_dev/src/worktree_ios_dev/proc.py worktree_ios_dev/src/worktree_ios_dev/xcodebuild.py worktree_ios_dev/src/worktree_ios_dev/runapp.py worktree_ios_dev/src/worktree_ios_dev/packages.py
git commit -m "feat(worktree-ios-dev): port proc, xcodebuild, runapp, packages"
```

---

## Task 6: simulator.py (InquirerPy fuzzy picker)

**Files:**
- Create: `worktree_ios_dev/src/worktree_ios_dev/simulator.py`

- [ ] **Step 1: Write simulator.py**

```python
# worktree_ios_dev/src/worktree_ios_dev/simulator.py
"""xcrun simctl wrappers + interactive picker for `boot`."""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass

from .config import SimulatorConfig
from .errors import EnvError, UserError
from .proc import require, run, run_json


@dataclass(frozen=True)
class DeviceType:
    identifier: str
    name: str


@dataclass(frozen=True)
class Runtime:
    identifier: str
    name: str
    version: str


_IPHONE17_RE = re.compile(r"iPhone 17(\b| )")


def ensure_tooling() -> None:
    require("xcrun")


def list_device_types(*, iphone_17_only: bool = True) -> list[DeviceType]:
    ensure_tooling()
    data = json.loads(run_json(["xcrun", "simctl", "list", "devicetypes", "--json"]))
    types = [
        DeviceType(identifier=t["identifier"], name=t["name"])
        for t in data.get("devicetypes", [])
        if t.get("productFamily") == "iPhone"
    ]
    if iphone_17_only:
        types = [t for t in types if _IPHONE17_RE.search(t.name)]
    types.sort(key=lambda t: t.name)
    return types


def list_runtimes() -> list[Runtime]:
    ensure_tooling()
    data = json.loads(run_json(["xcrun", "simctl", "list", "runtimes", "--json"]))
    out: list[Runtime] = []
    for r in data.get("runtimes", []):
        if not r.get("isAvailable", False):
            continue
        if r.get("platform", "iOS") != "iOS":
            continue
        out.append(Runtime(identifier=r["identifier"], name=r["name"], version=r["version"]))
    out.sort(key=lambda r: [int(p) for p in r.version.split(".") if p.isdigit()], reverse=True)
    return out


def find_device_by_name(name: str) -> dict | None:
    data = json.loads(run_json(["xcrun", "simctl", "list", "devices", "--json"]))
    for runtime_key, devices in data.get("devices", {}).items():
        for dev in devices:
            if dev.get("name") == name:
                return dev
    return None


def find_device_by_udid(udid: str) -> dict | None:
    data = json.loads(run_json(["xcrun", "simctl", "list", "devices", "--json"]))
    for runtime_key, devices in data.get("devices", {}).items():
        for dev in devices:
            if dev.get("udid") == udid:
                return dev
    return None


def create(name: str, device_type: DeviceType, runtime: Runtime) -> str:
    out = run_json(["xcrun", "simctl", "create", name, device_type.identifier, runtime.identifier])
    return out.strip()


def boot(udid: str) -> None:
    dev = find_device_by_udid(udid)
    if dev is None:
        raise UserError(f"No simulator with UDID {udid}.")
    if dev.get("state") == "Booted":
        print(f"Simulator {udid} already booted.")
        return
    run(["xcrun", "simctl", "boot", udid])
    run(["open", "-a", "Simulator"])


def delete(udid: str) -> None:
    run(["xcrun", "simctl", "delete", udid])


def _is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _pick_fuzzy(prompt: str, options: list[str]) -> str:
    """Fuzzy picker using InquirerPy. Falls back to numbered list when InquirerPy
    cannot render (e.g. TERM=dumb). Raises EnvError if not on a TTY."""
    if not _is_interactive():
        raise EnvError(
            "`worktree-ios-dev boot` first-run picker needs a real terminal. "
            "Re-run from an interactive shell."
        )
    try:
        from InquirerPy import inquirer
        return inquirer.fuzzy(message=prompt, choices=options).execute()
    except Exception:
        # Fallback: numbered list (e.g. TERM=dumb, no color)
        print(prompt)
        for i, opt in enumerate(options, start=1):
            print(f"  {i}. {opt}")
        while True:
            raw = input("Choice: ").strip()
            if raw.isdigit():
                idx = int(raw)
                if 1 <= idx <= len(options):
                    return options[idx - 1]
            print(f"Enter a number 1..{len(options)}.")


def pick_device_and_runtime(*, iphone_17_only: bool) -> tuple[DeviceType, Runtime]:
    devices = list_device_types(iphone_17_only=iphone_17_only)
    if not devices:
        raise EnvError(
            "No matching iPhone device types found. "
            "Try `worktree-ios-dev boot --all-devices`."
        )
    runtimes = list_runtimes()
    if not runtimes:
        raise EnvError("No iOS runtimes installed. Install via Xcode > Settings > Platforms.")
    device_name = _pick_fuzzy("Select device type:", [d.name for d in devices])
    runtime_name = _pick_fuzzy("Select runtime:", [r.name for r in runtimes])
    device = next(d for d in devices if d.name == device_name)
    runtime = next(r for r in runtimes if r.name == runtime_name)
    return device, runtime


def to_config(name: str, udid: str, device: DeviceType, runtime: Runtime) -> SimulatorConfig:
    return SimulatorConfig(name=name, udid=udid, device=device.name, runtime=runtime.name)
```

- [ ] **Step 2: Verify import**

```bash
cd worktree_ios_dev && uv run python -c "from worktree_ios_dev.simulator import pick_device_and_runtime; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add worktree_ios_dev/src/worktree_ios_dev/simulator.py
git commit -m "feat(worktree-ios-dev): add simulator.py with InquirerPy fuzzy picker"
```

---

## Task 7: bootstrap.py — Discovery Helpers + Tests

**Files:**
- Create: `worktree_ios_dev/tests/test_bootstrap.py`
- Create: `worktree_ios_dev/src/worktree_ios_dev/bootstrap.py` (discovery helpers only first)

- [ ] **Step 1: Write failing tests for discovery helpers**

```python
# worktree_ios_dev/tests/test_bootstrap.py
"""Tests for bootstrap discovery helpers."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from worktree_ios_dev.bootstrap import (  # noqa: E402
    detect_packages_root,
    fetch_schemes,
    find_xcodeprojs,
)


class FindXcodeprojs(unittest.TestCase):
    def test_finds_single_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proj = root / "ios" / "MyApp.xcodeproj"
            proj.mkdir(parents=True)
            self.assertEqual(find_xcodeprojs(root), [proj])

    def test_finds_multiple_projects_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "ios" / "App.xcodeproj"
            b = root / "ios" / "Ext.xcodeproj"
            b.mkdir(parents=True)
            a.mkdir(parents=True)
            result = find_xcodeprojs(root)
            self.assertEqual(result, [a, b])

    def test_empty_when_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(find_xcodeprojs(Path(tmp)), [])

    def test_does_not_recurse_inside_xcodeproj(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outer = root / "ios" / "App.xcodeproj"
            outer.mkdir(parents=True)
            (outer / "Nested.xcodeproj").mkdir()
            result = find_xcodeprojs(root)
            self.assertIn(outer, result)


class FetchSchemesTests(unittest.TestCase):
    def test_returns_schemes_from_json(self) -> None:
        mock_output = json.dumps({"project": {"schemes": ["MyApp", "MyAppTests"]}})
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = mock_output
        with patch("subprocess.run", return_value=mock_result):
            result = fetch_schemes(Path("ios/MyApp.xcodeproj"))
        self.assertEqual(result, ["MyApp", "MyAppTests"])

    def test_returns_empty_on_nonzero_exit(self) -> None:
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            result = fetch_schemes(Path("ios/MyApp.xcodeproj"))
        self.assertEqual(result, [])

    def test_returns_empty_on_invalid_json(self) -> None:
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "not json"
        with patch("subprocess.run", return_value=mock_result):
            result = fetch_schemes(Path("ios/MyApp.xcodeproj"))
        self.assertEqual(result, [])


class DetectPackagesRootTests(unittest.TestCase):
    def test_detects_sibling_packages_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xcodeproj = root / "ios" / "MyApp.xcodeproj"
            xcodeproj.mkdir(parents=True)
            packages = root / "ios" / "Packages"
            packages.mkdir()
            result = detect_packages_root(xcodeproj)
            self.assertEqual(result, packages)

    def test_returns_none_when_packages_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xcodeproj = root / "ios" / "MyApp.xcodeproj"
            xcodeproj.mkdir(parents=True)
            result = detect_packages_root(xcodeproj)
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd worktree_ios_dev && uv run python -m unittest tests.test_bootstrap -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'worktree_ios_dev.bootstrap'`

- [ ] **Step 3: Write bootstrap.py (discovery helpers only)**

```python
# worktree_ios_dev/src/worktree_ios_dev/bootstrap.py
"""Implementation of the `bootstrap` verb."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .errors import UserError
from .paths import find_worktree_root_for_bootstrap

_GITIGNORE_MARKER = "# added by worktree-ios-dev bootstrap"
_GITIGNORE_ENTRY = "worktree-ios-dev/"


def find_xcodeprojs(root: Path) -> list[Path]:
    """Find all *.xcodeproj directories under root, sorted."""
    return sorted(root.rglob("*.xcodeproj"))


def fetch_schemes(xcodeproj: Path) -> list[str]:
    """Return scheme names from xcodebuild -list -json. Returns [] on failure."""
    try:
        result = subprocess.run(
            ["xcodebuild", "-list", "-project", str(xcodeproj), "-json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout)
        return data.get("project", {}).get("schemes", [])
    except (json.JSONDecodeError, AttributeError):
        return []


def detect_packages_root(xcodeproj: Path) -> Path | None:
    """Return <xcodeproj_dir>/../Packages if it exists, else None."""
    candidate = xcodeproj.parent / "Packages"
    return candidate if candidate.is_dir() else None


# run() and helpers are added in Task 8
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd worktree_ios_dev && uv run python -m unittest tests.test_bootstrap -v
```

Expected: all 8 tests pass

- [ ] **Step 5: Commit**

```bash
git add worktree_ios_dev/src/worktree_ios_dev/bootstrap.py worktree_ios_dev/tests/test_bootstrap.py
git commit -m "feat(worktree-ios-dev): add bootstrap discovery helpers with tests"
```

---

## Task 8: bootstrap.py — run() (Interactive + Non-interactive)

**Files:**
- Modify: `worktree_ios_dev/src/worktree_ios_dev/bootstrap.py` (add run() and helpers)

- [ ] **Step 1: Append run() and helpers to bootstrap.py**

Add the following below the existing discovery helpers (after `detect_packages_root`):

```python
def _pick_one(label: str, options: list[str], yes: bool) -> str:
    """Return the single option, or prompt. Errors if non-interactive and ambiguous."""
    if len(options) == 1:
        return options[0]
    if yes or not sys.stdin.isatty() or not sys.stdout.isatty():
        lines = "\n".join(f"  {o}" for o in options)
        raise UserError(
            f"Multiple {label} found. Pass the appropriate flag:\n{lines}"
        )
    try:
        from InquirerPy import inquirer
        return inquirer.fuzzy(message=f"Select {label}:", choices=options).execute()
    except Exception:
        print(f"Select {label}:")
        for i, opt in enumerate(options, start=1):
            print(f"  {i}. {opt}")
        while True:
            raw = input("Choice: ").strip()
            if raw.isdigit():
                idx = int(raw)
                if 1 <= idx <= len(options):
                    return options[idx - 1]
            print(f"Enter a number 1..{len(options)}.")


def _ensure_gitignored(root: Path) -> None:
    gi = root / ".gitignore"
    if gi.exists():
        content = gi.read_text()
        if any(line.strip() == _GITIGNORE_ENTRY for line in content.splitlines()):
            return
        suffix = "" if content.endswith("\n") else "\n"
        gi.write_text(content + f"{suffix}{_GITIGNORE_MARKER}\n{_GITIGNORE_ENTRY}\n")
    else:
        gi.write_text(f"{_GITIGNORE_MARKER}\n{_GITIGNORE_ENTRY}\n")


def _write_config(
    cfg_path: Path,
    xcodeproj: Path,
    root: Path,
    scheme: str,
    sim_prefix: str,
    pkg_root: Path | None,
) -> None:
    import tomlkit
    doc = tomlkit.document()
    doc.add(tomlkit.comment("worktree-ios-dev/config.toml"))
    doc.add(tomlkit.comment("Generated by `worktree-ios-dev bootstrap`."))
    doc.add(tomlkit.comment("Edit as needed. Run `worktree-ios-dev boot` to populate [simulator]."))
    doc.add(tomlkit.nl())

    proj_table = tomlkit.table()
    proj_table.add("path", str(xcodeproj.relative_to(root)))
    proj_table.add("scheme", scheme)
    proj_table.add("configuration", "Debug")
    proj_table.add("simulator_prefix", sim_prefix)
    doc.add("project", proj_table)

    if pkg_root is not None:
        pkg_table = tomlkit.table()
        pkg_table.add("path", str(pkg_root.relative_to(root)))
        doc.add("packages_root", pkg_table)

    extras_table = tomlkit.table()
    extras_table.add("xcodebuild_flags", tomlkit.array())
    doc.add("extras", extras_table)

    cfg_path.write_text(tomlkit.dumps(doc))


def _log(msg: str) -> None:
    """Non-interactive log line."""
    print(f"[worktree-ios-dev] {msg}")


def run(*, project: str | None, scheme: str | None, yes: bool, force: bool) -> int:
    root = find_worktree_root_for_bootstrap()
    pid = root / "worktree-ios-dev"
    cfg_path = pid / "config.toml"
    is_interactive = sys.stdin.isatty() and sys.stdout.isatty() and not yes

    if cfg_path.exists() and not force:
        print(f"worktree-ios-dev already bootstrapped at {pid} (use --force to re-seed).")
        return 0

    # ── Discover xcodeproj ──────────────────────────────────────────────────
    if project:
        xcodeproj = (root / project).resolve()
        if not xcodeproj.exists():
            raise UserError(f"Project not found: {xcodeproj}")
    else:
        if is_interactive:
            try:
                from rich.progress import Progress, SpinnerColumn, TextColumn
                with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
                    p.add_task("Scanning for Xcode projects...")
                    projs = find_xcodeprojs(root)
            except ImportError:
                projs = find_xcodeprojs(root)
        else:
            _log("scanning for Xcode projects...")
            projs = find_xcodeprojs(root)

        if not projs:
            raise UserError("No *.xcodeproj found under the worktree root. Pass --project <path>.")

        rel_projs = [str(p.relative_to(root)) for p in projs]
        chosen_rel = _pick_one("project", rel_projs, yes)
        xcodeproj = (root / chosen_rel).resolve()

        if is_interactive and len(projs) == 1:
            print(f"✓ project: {chosen_rel}")
        elif not is_interactive:
            _log(f"found project: {chosen_rel}")

    # ── Discover scheme ─────────────────────────────────────────────────────
    if scheme:
        chosen_scheme = scheme
    else:
        if is_interactive:
            try:
                from rich.progress import Progress, SpinnerColumn, TextColumn
                with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
                    p.add_task("Fetching schemes...")
                    schemes = fetch_schemes(xcodeproj)
            except ImportError:
                schemes = fetch_schemes(xcodeproj)
        else:
            _log("fetching schemes...")
            schemes = fetch_schemes(xcodeproj)

        if not schemes:
            raise UserError(f"No schemes found in {xcodeproj}. Pass --scheme <name>.")

        chosen_scheme = _pick_one("scheme", schemes, yes)

        if is_interactive and len(schemes) == 1:
            print(f"✓ scheme: {chosen_scheme}")
        elif not is_interactive:
            _log(f"found scheme: {chosen_scheme}")

    # ── packages_root ───────────────────────────────────────────────────────
    pkg_root = detect_packages_root(xcodeproj)
    if pkg_root:
        if is_interactive:
            print(f"✓ packages_root detected: {pkg_root.relative_to(root)}")
        else:
            _log(f"packages_root: {pkg_root.relative_to(root)}")
    else:
        if not is_interactive:
            _log("packages_root: not found (optional)")

    # ── simulator_prefix ────────────────────────────────────────────────────
    sim_prefix = chosen_scheme
    if is_interactive:
        try:
            from InquirerPy import inquirer
            result = inquirer.text(
                message="Simulator prefix",
                default=chosen_scheme,
            ).execute()
            if result and result.strip():
                sim_prefix = result.strip()
        except Exception:
            raw = input(f"Simulator prefix [{chosen_scheme}]: ").strip()
            if raw:
                sim_prefix = raw

    # ── Write ───────────────────────────────────────────────────────────────
    pid.mkdir(exist_ok=True)
    (pid / "derivedData").mkdir(exist_ok=True)
    _write_config(cfg_path, xcodeproj, root, chosen_scheme, sim_prefix, pkg_root)
    _ensure_gitignored(root)

    if is_interactive:
        try:
            from rich.console import Console
            from rich.panel import Panel
            console = Console()
            lines = [
                "[project]",
                f"path             = {xcodeproj.relative_to(root)}",
                f"scheme           = {chosen_scheme}",
                f"simulator_prefix = {sim_prefix}",
            ]
            if pkg_root:
                lines += ["[packages_root]", f"path             = {pkg_root.relative_to(root)}"]
            console.print(Panel("\n".join(lines), title="worktree-ios-dev/config.toml", expand=False))
            console.print("[green]✓[/green] Created worktree-ios-dev/config.toml")
            console.print("[green]✓[/green] Updated .gitignore")
            console.print("[blue]→[/blue] Next: worktree-ios-dev boot")
        except ImportError:
            print(f"Created {cfg_path}")
    else:
        _log("bootstrap complete")

    return 0
```

- [ ] **Step 2: Verify run() is importable**

```bash
cd worktree_ios_dev && uv run python -c "from worktree_ios_dev.bootstrap import run; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Run full test suite**

```bash
cd worktree_ios_dev && uv run python -m unittest discover -s tests -v
```

Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add worktree_ios_dev/src/worktree_ios_dev/bootstrap.py
git commit -m "feat(worktree-ios-dev): add bootstrap run() with interactive + non-interactive modes"
```

---

## Task 9: boot.py (simulator_prefix)

**Files:**
- Create: `worktree_ios_dev/src/worktree_ios_dev/boot.py`

- [ ] **Step 1: Write boot.py**

The only logic change vs the old version: `sim_name = f"Pulse-{cfg.worktree_root.name}"` is replaced with `simulator_prefix`-aware naming.

```python
# worktree_ios_dev/src/worktree_ios_dev/boot.py
"""Implementation of the `boot` verb."""
from __future__ import annotations

import argparse

from . import simulator as sim_mod
from .config import SimulatorConfig, load, write_simulator
from .errors import UserError
from .paths import find_config


def run(args: argparse.Namespace) -> int:
    cfg_path = args.config.resolve() if args.config else find_config()
    cfg = load(cfg_path)

    sim_mod.ensure_tooling()

    need_first_run = (
        cfg.simulator is None
        or sim_mod.find_device_by_udid(cfg.simulator.udid) is None
        or args.recreate
    )

    if args.recreate and cfg.simulator is not None:
        existing = sim_mod.find_device_by_udid(cfg.simulator.udid)
        if existing is not None:
            print(f"Deleting existing simulator {cfg.simulator.name} ({cfg.simulator.udid})…")
            sim_mod.delete(cfg.simulator.udid)

    if not need_first_run:
        assert cfg.simulator is not None
        sim_mod.boot(cfg.simulator.udid)
        print(f"Booted {cfg.simulator.name} ({cfg.simulator.udid}).")
        return 0

    # First run: pick + create + persist + boot.
    device, runtime = sim_mod.pick_device_and_runtime(iphone_17_only=not args.all_devices)

    prefix = cfg.project.simulator_prefix or cfg.project.scheme
    sim_name = f"{prefix}-{cfg.worktree_root.name}"

    existing = sim_mod.find_device_by_name(sim_name)
    if existing is not None:
        print(f"A simulator named {sim_name} already exists (udid={existing['udid']}).")
        choice = input("Reuse it? [Y/n] ").strip().lower()
        if choice in ("", "y", "yes"):
            udid = existing["udid"]
        else:
            raise UserError("Aborted. Delete the existing sim manually or choose --recreate next time.")
    else:
        udid = sim_mod.create(sim_name, device, runtime)
        print(f"Created simulator {sim_name} ({udid}).")

    sim_cfg = SimulatorConfig(name=sim_name, udid=udid, device=device.name, runtime=runtime.name)
    write_simulator(cfg_path, sim_cfg)
    print(f"Wrote [simulator] to {cfg_path}.")

    sim_mod.boot(udid)
    print()
    print(f"name    = {sim_cfg.name}")
    print(f"udid    = {sim_cfg.udid}")
    print(f"device  = {sim_cfg.device}")
    print(f"runtime = {sim_cfg.runtime}")
    return 0
```

- [ ] **Step 2: Verify import**

```bash
cd worktree_ios_dev && uv run python -c "from worktree_ios_dev.boot import run; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add worktree_ios_dev/src/worktree_ios_dev/boot.py
git commit -m "feat(worktree-ios-dev): add boot.py using simulator_prefix from config"
```

---

## Task 10: cli.py

**Files:**
- Create: `worktree_ios_dev/src/worktree_ios_dev/cli.py`

- [ ] **Step 1: Write cli.py**

Key changes from old version: `prog="worktree-ios-dev"`, verb `worktree-bootstrap` → `bootstrap`, `bootstrap` subparser gets `--project`/`--scheme`/`--yes` flags, all error messages updated, `PulseIosError` → `WorktreeIosError`.

```python
# worktree_ios_dev/src/worktree_ios_dev/cli.py
"""worktree-ios-dev — argparse dispatcher + verb handlers."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import bootstrap, config as config_mod, packages as packages_mod, simulator as sim_mod, xcodebuild
from .errors import EnvError, WorktreeIosError, SubprocessError, UserError
from .paths import find_config
from .proc import require, run


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, default=None, help="Path to config.toml (overrides walk-up discovery).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Stream subprocess output and show tracebacks.")


def _load_config(args: argparse.Namespace) -> config_mod.Config:
    path = args.config.resolve() if args.config else find_config()
    return config_mod.load(path)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="worktree-ios-dev", description="iOS worktree build / sim / test CLI.")
    sub = p.add_subparsers(dest="verb", required=True)

    bs = sub.add_parser("bootstrap", help="Create worktree-ios-dev/ in this worktree.")
    bs.add_argument("--project", default=None, help="Relative path to .xcodeproj (skips auto-discovery).")
    bs.add_argument("--scheme", default=None, help="Scheme name (skips auto-discovery).")
    bs.add_argument("--yes", action="store_true", help="Accept all detected defaults; error if ambiguous.")
    bs.add_argument("--force", action="store_true", help="Re-seed config.toml even if it already exists.")
    _add_common(bs)
    bs.set_defaults(func=_cmd_bootstrap)

    b = sub.add_parser("boot", help="Create (first run) or boot the per-worktree simulator.")
    b.add_argument("--recreate", action="store_true", help="Delete the named sim and re-enter first-run.")
    b.add_argument("--all-devices", action="store_true", help="Disable the iPhone 17 filter in the picker.")
    _add_common(b)
    b.set_defaults(func=_cmd_boot)

    for verb in ("build", "test", "run", "clean", "wipe-derived", "config", "doctor"):
        sp = sub.add_parser(verb)
        _add_common(sp)
        sp.set_defaults(func={
            "build": _cmd_build,
            "test": _cmd_test,
            "run": _cmd_run,
            "clean": _cmd_clean,
            "wipe-derived": _cmd_wipe_derived,
            "config": _cmd_config,
            "doctor": _cmd_doctor,
        }[verb])
        if verb in ("build", "test"):
            sp.add_argument("--release", action="store_true", help="Use Release configuration.")
            sp.add_argument("--scheme", default=None, help="Override project.scheme.")
        if verb == "test":
            sp.add_argument("--only-testing", action="append", default=[], metavar="TEST_ID")
            sp.add_argument("--skip-testing", action="append", default=[], metavar="TEST_ID")
        if verb == "run":
            sp.add_argument("--release", action="store_true", help="Use Release configuration.")
        if verb == "wipe-derived":
            sp.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")

    tp = sub.add_parser("test-package", help="Run a local Swift package's tests.")
    tp.add_argument("name", help="Directory / scheme name under packages_root.")
    _add_common(tp)
    tp.set_defaults(func=_cmd_test_package)

    return p


# ---- handlers ----------------------------------------------------------------

def _cmd_bootstrap(args: argparse.Namespace) -> int:
    return bootstrap.run(
        project=args.project,
        scheme=args.scheme,
        yes=args.yes,
        force=args.force,
    )


def _cmd_config(args: argparse.Namespace) -> int:
    cfg = _load_config(args)
    payload = {
        "config_path": str(cfg.config_path),
        "worktree_root": str(cfg.worktree_root),
        "derived_data": str(cfg.derived_data),
        "project": {
            "path": str(cfg.project.path),
            "scheme": cfg.project.scheme,
            "configuration": cfg.project.configuration,
            "simulator_prefix": cfg.project.simulator_prefix,
        },
        "simulator": None if cfg.simulator is None else {
            "name": cfg.simulator.name,
            "udid": cfg.simulator.udid,
            "device": cfg.simulator.device,
            "runtime": cfg.simulator.runtime,
        },
        "packages_root": str(cfg.packages_root),
        "package_overrides": {k: {"scheme": v.scheme} for k, v in cfg.package_overrides.items()},
        "extras": {"xcodebuild_flags": cfg.extras_xcodebuild_flags},
    }
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_clean(args: argparse.Namespace) -> int:
    cfg = _load_config(args)
    argv = xcodebuild.clean_argv(cfg)
    run(argv, verbose=args.verbose)
    return 0


def _cmd_wipe_derived(args: argparse.Namespace) -> int:
    cfg = _load_config(args)
    target = cfg.derived_data
    if not target.exists():
        print(f"Nothing to wipe: {target} does not exist.")
        return 0
    if not args.yes:
        resp = input(f"Delete {target}? [y/N] ").strip().lower()
        if resp not in ("y", "yes"):
            print("Aborted.")
            return 1
    shutil.rmtree(target)
    target.mkdir()
    print(f"Wiped {target}.")
    return 0


def _cmd_boot(args: argparse.Namespace) -> int:
    from .boot import run as boot_run
    return boot_run(args)


def _cmd_build(args: argparse.Namespace) -> int:
    cfg = _load_config(args)
    argv = xcodebuild.build_argv(cfg, release=args.release, scheme_override=args.scheme)
    run(argv, verbose=args.verbose)
    return 0


def _cmd_test(args: argparse.Namespace) -> int:
    cfg = _load_config(args)
    argv = xcodebuild.test_argv(
        cfg,
        release=args.release,
        only_testing=args.only_testing,
        skip_testing=args.skip_testing,
    )
    if args.scheme:
        argv[argv.index("-scheme") + 1] = args.scheme
    run(argv, verbose=args.verbose)
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    from .runapp import run as run_run
    return run_run(args)


def _cmd_test_package(args: argparse.Namespace) -> int:
    cfg = _load_config(args)
    argv, cwd = packages_mod.resolve(cfg, args.name)
    run(argv, cwd=cwd, verbose=args.verbose)
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    problems: list[str] = []
    try:
        cfg = _load_config(args)
        print(f"config.toml: {cfg.config_path}")
    except EnvError as e:
        problems.append(str(e))
        cfg = None

    for binary in ("xcodebuild", "xcrun"):
        if shutil.which(binary) is None:
            problems.append(f"`{binary}` not on PATH.")
        else:
            print(f"{binary}: {shutil.which(binary)}")

    mint_path = shutil.which("mint")
    if mint_path is None:
        print("mint: not installed (optional — enables xcbeautify for prettier xcodebuild output).")
    else:
        print(f"mint: {mint_path}")

    if cfg is not None:
        if not cfg.project.path.exists():
            problems.append(f"project.path does not exist: {cfg.project.path}")
        else:
            print(f"project: {cfg.project.path}")
        if cfg.simulator is None:
            problems.append("No [simulator] block. Run `worktree-ios-dev boot`.")
        else:
            dev = sim_mod.find_device_by_udid(cfg.simulator.udid)
            if dev is None:
                problems.append(f"Simulator UDID not found in simctl list: {cfg.simulator.udid}")
            else:
                print(f"simulator: {cfg.simulator.name} ({cfg.simulator.udid}) — state={dev.get('state')}")
        if not cfg.derived_data.parent.exists():
            problems.append(f"worktree-ios-dev/ missing: {cfg.derived_data.parent}")

    if problems:
        print()
        print("Problems:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print()
    print("All checks passed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except WorktreeIosError as e:
        print(f"error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return e.exit_code
    except KeyboardInterrupt:
        return 130
```

- [ ] **Step 2: Test --help output**

```bash
cd worktree_ios_dev && uv run python -m worktree_ios_dev --help
```

Expected: shows `worktree-ios-dev` in usage line with all verbs listed

- [ ] **Step 3: Test bootstrap --help**

```bash
cd worktree_ios_dev && uv run python -m worktree_ios_dev bootstrap --help
```

Expected: shows `--project`, `--scheme`, `--yes`, `--force` flags

- [ ] **Step 4: Run full test suite**

```bash
cd worktree_ios_dev && uv run python -m unittest discover -s tests -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add worktree_ios_dev/src/worktree_ios_dev/cli.py
git commit -m "feat(worktree-ios-dev): add cli.py (prog=worktree-ios-dev, bootstrap verb with discovery flags)"
```

---

## Task 11: Cleanup — Delete Old Package, Rename Skill, Update Docs

**Files:**
- Delete: `pulse_ios_dev_tool/`
- Rename: `skills/pulse-ios-dev/` → `skills/worktree-ios-dev/`
- Update: `skills/worktree-ios-dev/SKILL.md`
- Update: `docs/specs/2026-04-24-pulse-ios-dev-system.md`
- Update: `README.md` (if it references pulse-ios-dev-tool)

- [ ] **Step 1: Delete old package**

```bash
rm -rf pulse_ios_dev_tool/
```

- [ ] **Step 2: Rename skill directory**

```bash
git mv skills/pulse-ios-dev skills/worktree-ios-dev
```

- [ ] **Step 3: Update SKILL.md — replace all pulse references**

Edit `skills/worktree-ios-dev/SKILL.md`:
- Replace every occurrence of `pulse-ios-dev-tool` with `worktree-ios-dev`
- Replace every occurrence of `pulse-ios-dev` with `worktree-ios-dev`
- Replace `worktree-bootstrap` with `bootstrap` in verb listings

- [ ] **Step 4: Update existing docs**

Edit `docs/specs/2026-04-24-pulse-ios-dev-system.md`: add a note at the top:

```markdown
> **Superseded by:** `docs/superpowers/specs/2026-04-28-worktree-ios-dev-design.md`
```

Edit `docs/plans/2026-04-24-pulse-ios-dev-tool.md`: add a note at the top:

```markdown
> **Superseded by:** `docs/superpowers/plans/2026-04-28-worktree-ios-dev.md`
```

- [ ] **Step 5: Check for any remaining pulse references**

```bash
grep -r "pulse-ios-dev" . --include="*.md" --include="*.toml" --include="*.py" -l | grep -v ".git"
```

Fix any files listed that are not the old design doc (which just has the superseded notice).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: delete pulse_ios_dev_tool, rename skill to worktree-ios-dev, update docs"
```

---

## Task 12: Install + Smoke Test

- [ ] **Step 1: Install the new package globally**

```bash
uv tool install --editable ./worktree_ios_dev
```

Expected output ends with: `Installed 1 executable: worktree-ios-dev`

- [ ] **Step 2: Verify CLI is on PATH**

```bash
which worktree-ios-dev && worktree-ios-dev --help
```

Expected: path printed, then usage showing all verbs

- [ ] **Step 3: Run full test suite one final time**

```bash
cd worktree_ios_dev && uv run python -m unittest discover -s tests -v
```

Expected: all tests pass

- [ ] **Step 4: Verify doctor runs without crashing**

Run from a directory that has a `worktree-ios-dev/config.toml`:

```bash
worktree-ios-dev doctor
```

Expected: either "All checks passed." or a structured problems list — no Python tracebacks

- [ ] **Step 5: Verify non-interactive bootstrap reports correctly**

```bash
cd /tmp && mkdir smoke-test-wt && cd smoke-test-wt && git init && mkdir -p ios/MyApp.xcodeproj && worktree-ios-dev bootstrap --project ios/MyApp.xcodeproj --scheme MyApp
```

Expected:
```
[worktree-ios-dev] found scheme: MyApp
[worktree-ios-dev] bootstrap complete
```
And `worktree-ios-dev/config.toml` exists with correct content.

- [ ] **Step 6: Final commit**

```bash
git add worktree_ios_dev/
git commit -m "chore(worktree-ios-dev): install verified, smoke tests passed"
```
