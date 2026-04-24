# `pulse-ios-dev-tool` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a centralized Python CLI `pulse-ios-dev-tool` that absorbs every non-interactive iOS build task for the Pulse app and its local Swift packages, backed by a per-worktree `pulse-ios-build/config.toml`, installed globally via `uv tool install --editable`.

**Architecture:** A Python package `pulse_ios_dev_tool` under `pulse-dev-skills/`, with a layered module design: `cli` dispatches verbs; `config`, `paths` are pure; `simulator`, `xcodebuild`, `packages` build argvs and call through a single `proc` subprocess boundary. State per worktree lives under `pulse-ios-build/` (config + derivedData). A companion skill `skills/pulse-ios-build/` tells agents when to pick this tool over `xcodebuildmcp-cli`.

**Tech Stack:** Python 3.11+ (uses stdlib `tomllib`), `tomlkit` for config writes that preserve formatting, `uv tool install` for distribution, bash shell for smoke checks, `xcrun simctl` + `xcodebuild` as the subprocess targets.

**Testing philosophy:** No automated tests per project direction. Each task ends with a manual smoke check — an actual command run — and a commit. The final task is an end-to-end dry run against a real Pulse worktree.

**Conventions this plan assumes:**
- Absolute paths only in shell snippets. Replace `<skills-repo>` with `/Users/yi.jiang/Developer/PulseProject/pulse-dev-skills` when executing.
- Commits are NEW commits (never `--amend`).
- Exit codes: `0` ok, `1` user error, `2` environment error, `3` subprocess failure.

---

## File structure

New files under `pulse-dev-skills/`:

```
pulse_ios_dev_tool/
├── pyproject.toml
├── README.md
└── src/pulse_ios_dev_tool/
    ├── __init__.py
    ├── __main__.py               # enables `python -m pulse_ios_dev_tool`
    ├── cli.py                    # argparse, verb dispatch, exit-code mapping
    ├── errors.py                 # typed error classes: UserError, EnvError, SubprocessError
    ├── proc.py                   # subprocess.run wrapper with streaming + error mapping
    ├── paths.py                  # walk-up discovery, worktree-root detection
    ├── config.py                 # tomllib read, tomlkit write, schema validation
    ├── simulator.py              # simctl list/create/boot + interactive picker
    ├── xcodebuild.py             # argv builders for build/test/run/clean
    ├── packages.py               # test-package dispatcher (per-package overrides + default convention)
    ├── bootstrap.py              # worktree-bootstrap verb body
    ├── boot.py                   # boot verb body (first-run picker + subsequent boot)
    └── runapp.py                 # run verb body (build + install + launch)

skills/pulse-ios-build/
└── SKILL.md                      # new agent-facing decision tree + verb list

skills/pulse-ios-testing/
└── SKILL.md                      # trimmed to a pointer (modify existing)
```

Responsibilities, one line each:

- `cli.py` — every user-facing verb lives here as a handler function; no subprocess calls, no filesystem work beyond reading config — it delegates to the modules below.
- `errors.py` — three exception classes, each mapped to an exit code by `cli.main()`.
- `proc.py` — the only module that runs `subprocess`. Everything else returns argvs.
- `paths.py` — walk-up from cwd to find `pulse-ios-build/config.toml`; detect worktree root for bootstrap.
- `config.py` — `Config` dataclass, `load(path) -> Config`, `write_simulator(path, sim) -> None`, schema validation with actionable error messages.
- `simulator.py` — `list_devices()`, `list_runtimes()`, `pick(...)`, `create(...)`, `boot(...)`, `is_booted(...)`.
- `xcodebuild.py` — pure argv builders: `build_argv(cfg, *, release=False)`, `test_argv(...)`, etc.
- `packages.py` — resolve `[packages.<Name>]` override or default convention, return argv + cwd.
- `bootstrap.py` — detect worktree root, scaffold `pulse-ios-build/`, update `.gitignore`.
- `boot.py` — implements the `boot` verb: decides first-run vs subsequent, picks device + runtime, creates and registers the sim.
- `runapp.py` — implements the `run` verb: build → locate `.app` → `simctl install` → `simctl launch`.

---

## Task 1: Python package skeleton

**Files:**
- Create: `pulse_ios_dev_tool/pyproject.toml`
- Create: `pulse_ios_dev_tool/src/pulse_ios_dev_tool/__init__.py`
- Create: `pulse_ios_dev_tool/src/pulse_ios_dev_tool/__main__.py`
- Create: `pulse_ios_dev_tool/README.md`

- [ ] **Step 1: Write `pulse_ios_dev_tool/pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pulse-ios-dev-tool"
version = "0.1.0"
description = "Pulse iOS build / simulator / test CLI — per-worktree config, global install."
requires-python = ">=3.11"
dependencies = [
    "tomlkit>=0.13",
]

[project.scripts]
pulse-ios-dev-tool = "pulse_ios_dev_tool.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/pulse_ios_dev_tool"]
```

- [ ] **Step 2: Write `pulse_ios_dev_tool/src/pulse_ios_dev_tool/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Write `pulse_ios_dev_tool/src/pulse_ios_dev_tool/__main__.py`**

```python
from pulse_ios_dev_tool.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Write `pulse_ios_dev_tool/README.md`**

```markdown
# pulse-ios-dev-tool

Per-worktree iOS build / simulator / test CLI for the Pulse app.

Install once per machine from the skills repo root:

    uv tool install --editable /abs/path/to/pulse-dev-skills/pulse_ios_dev_tool

Then per worktree:

    cd /path/to/worktree
    pulse-ios-dev-tool worktree-bootstrap
    pulse-ios-dev-tool boot
    pulse-ios-dev-tool build

Full design: `docs/specs/2026-04-24-pulse-ios-build-system.md`.
Skill for agents: `skills/pulse-ios-build/`.
```

- [ ] **Step 5: Create a placeholder `cli.py` so the package imports**

File: `pulse_ios_dev_tool/src/pulse_ios_dev_tool/cli.py`

```python
def main() -> int:
    print("pulse-ios-dev-tool: not implemented yet")
    return 0
```

- [ ] **Step 6: Verify it builds and installs**

Run from `<skills-repo>`:

```bash
uv tool install --editable ./pulse_ios_dev_tool
pulse-ios-dev-tool
```

Expected output: `pulse-ios-dev-tool: not implemented yet`

- [ ] **Step 7: Commit**

```bash
cd <skills-repo>
git add pulse_ios_dev_tool/
git commit -m "feat(pulse-ios-dev-tool): package skeleton with uv tool entry point"
```

---

## Task 2: Error classes and exit-code mapping

**Files:**
- Create: `pulse_ios_dev_tool/src/pulse_ios_dev_tool/errors.py`

- [ ] **Step 1: Write `errors.py`**

```python
"""Typed error classes. Each maps to an exit code in cli.main()."""


class PulseIosError(Exception):
    """Base class; never raised directly."""

    exit_code: int = 1


class UserError(PulseIosError):
    """Bad CLI args, missing required config section, verb preconditions not met."""

    exit_code = 1


class EnvError(PulseIosError):
    """Environment problem: config not found, xcodebuild/simctl not on PATH."""

    exit_code = 2


class SubprocessError(PulseIosError):
    """An invoked tool (xcodebuild, simctl) returned non-zero."""

    exit_code = 3

    def __init__(self, message: str, *, upstream_exit: int) -> None:
        super().__init__(message)
        self.upstream_exit = upstream_exit
```

- [ ] **Step 2: Verify it imports cleanly**

```bash
cd <skills-repo>
python -c "from pulse_ios_dev_tool.errors import UserError, EnvError, SubprocessError; print('ok')"
```

Expected output: `ok`

- [ ] **Step 3: Commit**

```bash
git add pulse_ios_dev_tool/src/pulse_ios_dev_tool/errors.py
git commit -m "feat(pulse-ios-dev-tool): add typed error classes with exit-code mapping"
```

---

## Task 3: `proc.py` — single subprocess boundary

**Files:**
- Create: `pulse_ios_dev_tool/src/pulse_ios_dev_tool/proc.py`

- [ ] **Step 1: Write `proc.py`**

```python
"""The only module that actually runs subprocesses."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Sequence

from .errors import EnvError, SubprocessError


def require(binary: str) -> None:
    """Raise EnvError if `binary` is not on PATH."""
    if shutil.which(binary) is None:
        raise EnvError(
            f"`{binary}` not found on PATH. Install it or run `xcode-select --install`."
        )


def run(
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    capture: bool = False,
    verbose: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run argv. If capture=False, stdout/stderr stream to the parent tty.
    Raises SubprocessError with the upstream exit code on non-zero return."""
    if verbose:
        display_cwd = f" (cwd={cwd})" if cwd else ""
        print(f"+ {' '.join(argv)}{display_cwd}")
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
    """Capture-only convenience; returns stdout as string. Used for simctl list --json."""
    result = run(argv, capture=True, verbose=verbose)
    return result.stdout
```

- [ ] **Step 2: Verify import and a trivial run**

```bash
cd <skills-repo>
python -c "
from pulse_ios_dev_tool.proc import run
out = run(['echo', 'hi'], capture=True)
assert out.stdout.strip() == 'hi', out.stdout
print('ok')
"
```

Expected output: `ok`

- [ ] **Step 3: Commit**

```bash
git add pulse_ios_dev_tool/src/pulse_ios_dev_tool/proc.py
git commit -m "feat(pulse-ios-dev-tool): add proc.run subprocess boundary"
```

---

## Task 4: `paths.py` — config discovery + worktree-root detection

**Files:**
- Create: `pulse_ios_dev_tool/src/pulse_ios_dev_tool/paths.py`

- [ ] **Step 1: Write `paths.py`**

```python
"""Filesystem walk-up helpers. No subprocess calls."""
from __future__ import annotations

from pathlib import Path

from .errors import EnvError, UserError

CONFIG_DIRNAME = "pulse-ios-build"
CONFIG_FILENAME = "config.toml"


def find_config(start: Path | None = None) -> Path:
    """Walk up from `start` (default cwd) looking for <dir>/pulse-ios-build/config.toml.
    Stops at $HOME or filesystem root.
    Returns the absolute path to config.toml.
    Raises EnvError if not found."""
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
        f"Run `pulse-ios-dev-tool worktree-bootstrap` from your worktree to set one up."
    )


def config_dir(config_path: Path) -> Path:
    """Directory that contains config.toml (i.e. the pulse-ios-build/ dir)."""
    return config_path.parent


def worktree_root(config_path: Path) -> Path:
    """Directory that contains the pulse-ios-build/ dir — the path anchor for
    project.path, packages_root.path, .gitignore writes, etc."""
    return config_path.parent.parent


def derived_data_dir(config_path: Path) -> Path:
    """Hardcoded `<pulse-ios-build>/derivedData/`."""
    return config_dir(config_path) / "derivedData"


def find_worktree_root_for_bootstrap(start: Path | None = None) -> Path:
    """For `worktree-bootstrap`: walk up from cwd for the nearest dir that contains
    either ios/Pulse.xcodeproj or a .git entry.
    Raises UserError if neither is found."""
    cwd = (start or Path.cwd()).resolve()
    probe = cwd
    while True:
        if (probe / "ios" / "Pulse.xcodeproj").exists():
            return probe
        if (probe / ".git").exists():
            return probe
        if probe == probe.parent:
            break
        probe = probe.parent
    raise UserError(
        f"Could not find a worktree root above `{cwd}`. "
        f"Expected `ios/Pulse.xcodeproj` or a `.git` entry in an ancestor directory."
    )
```

- [ ] **Step 2: Verify walk-up discovery with a throwaway layout**

```bash
cd <skills-repo>
python -c "
import tempfile
from pathlib import Path
from pulse_ios_dev_tool.paths import find_config, worktree_root

with tempfile.TemporaryDirectory() as td:
    td = Path(td).resolve()
    (td / 'pulse-ios-build').mkdir()
    (td / 'pulse-ios-build' / 'config.toml').write_text('')
    deep = td / 'a' / 'b' / 'c'
    deep.mkdir(parents=True)
    found = find_config(deep)
    assert found == td / 'pulse-ios-build' / 'config.toml', found
    assert worktree_root(found) == td, worktree_root(found)
    print('ok')
"
```

Expected output: `ok`

- [ ] **Step 3: Commit**

```bash
git add pulse_ios_dev_tool/src/pulse_ios_dev_tool/paths.py
git commit -m "feat(pulse-ios-dev-tool): add walk-up config discovery and worktree-root detection"
```

---

## Task 5: `config.py` — TOML parsing + schema

**Files:**
- Create: `pulse_ios_dev_tool/src/pulse_ios_dev_tool/config.py`

- [ ] **Step 1: Write `config.py`**

```python
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
    config_path: Path                 # absolute path to config.toml
    worktree_root: Path               # directory that contains pulse-ios-build/
    derived_data: Path                # <pulse-ios-build>/derivedData
    project: ProjectConfig
    simulator: SimulatorConfig | None
    packages_root: Path               # absolute
    package_overrides: dict[str, PackageOverride] = field(default_factory=dict)
    extras_xcodebuild_flags: list[str] = field(default_factory=list)


_ALLOWED_TOP_LEVEL = {"project", "simulator", "packages_root", "packages", "extras"}
_ALLOWED_PROJECT = {"path", "scheme", "configuration"}
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

    # [project] — required
    if "project" not in data:
        raise UserError(
            f"Missing [project] section in {config_path}. "
            f"Re-run `pulse-ios-dev-tool worktree-bootstrap --force` to re-seed."
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
    )

    # [simulator] — optional at parse time
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

    # [packages_root]
    pkg_root_cfg = data.get("packages_root", {"path": "ios/Packages"})
    _require_keys("packages_root", pkg_root_cfg, _ALLOWED_PACKAGES_ROOT)
    packages_root = (wt_root / pkg_root_cfg.get("path", "ios/Packages")).resolve()

    # [packages.<Name>]
    overrides: dict[str, PackageOverride] = {}
    for name, table in (data.get("packages", {}) or {}).items():
        _require_keys(f"packages.{name}", table, _ALLOWED_PACKAGE)
        overrides[name] = PackageOverride(scheme=table.get("scheme"))

    # [extras]
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
            "Run `pulse-ios-dev-tool boot` first to create and register a simulator."
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

- [ ] **Step 2: Verify load + write on a synthetic config**

```bash
cd <skills-repo>
python -c "
import tempfile
from pathlib import Path
from pulse_ios_dev_tool.config import load, write_simulator, SimulatorConfig

with tempfile.TemporaryDirectory() as td:
    td = Path(td).resolve()
    (td / 'ios').mkdir()
    (td / 'ios' / 'Pulse.xcodeproj').mkdir()
    pib = td / 'pulse-ios-build'
    pib.mkdir()
    cfg_path = pib / 'config.toml'
    cfg_path.write_text('''
[project]
path = \"ios/Pulse.xcodeproj\"
scheme = \"Pulse\"
''')
    cfg = load(cfg_path)
    assert cfg.project.scheme == 'Pulse'
    assert cfg.simulator is None
    assert cfg.project.configuration == 'Debug'
    assert cfg.derived_data.name == 'derivedData'

    write_simulator(cfg_path, SimulatorConfig(name='X', udid='Y', device='iPhone 17', runtime='iOS 26.0'))
    cfg2 = load(cfg_path)
    assert cfg2.simulator.udid == 'Y'
    print('ok')
"
```

Expected output: `ok`

- [ ] **Step 3: Commit**

```bash
git add pulse_ios_dev_tool/src/pulse_ios_dev_tool/config.py pulse_ios_dev_tool/pyproject.toml
git commit -m "feat(pulse-ios-dev-tool): add config.py with schema validation + tomlkit writes"
```

---

## Task 6: `xcodebuild.py` — argv builders

**Files:**
- Create: `pulse_ios_dev_tool/src/pulse_ios_dev_tool/xcodebuild.py`

- [ ] **Step 1: Write `xcodebuild.py`**

```python
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
    # clean doesn't need a destination.
    return _common(cfg, None, release=False) + ["clean"]
```

- [ ] **Step 2: Verify argv shape**

```bash
cd <skills-repo>
python -c "
import tempfile
from pathlib import Path
from pulse_ios_dev_tool.config import load, write_simulator, SimulatorConfig
from pulse_ios_dev_tool.xcodebuild import build_argv, test_argv, clean_argv

with tempfile.TemporaryDirectory() as td:
    td = Path(td).resolve()
    (td / 'ios').mkdir()
    (td / 'ios' / 'Pulse.xcodeproj').mkdir()
    pib = td / 'pulse-ios-build'
    pib.mkdir()
    cfg_path = pib / 'config.toml'
    cfg_path.write_text('[project]\npath = \"ios/Pulse.xcodeproj\"\nscheme = \"Pulse\"\n')
    write_simulator(cfg_path, SimulatorConfig(name='X', udid='U', device='iPhone 17', runtime='iOS 26.0'))
    cfg = load(cfg_path)

    argv = build_argv(cfg)
    assert argv[0] == 'xcodebuild' and argv[-1] == 'build', argv
    assert '-destination' in argv and 'platform=iOS Simulator,id=U' in argv, argv
    assert '-configuration' in argv and 'Debug' in argv, argv

    argv_r = build_argv(cfg, release=True)
    assert 'Release' in argv_r, argv_r

    argv_t = test_argv(cfg, only_testing=['MyTests/Foo'])
    assert '-only-testing' in argv_t and 'MyTests/Foo' in argv_t, argv_t

    argv_c = clean_argv(cfg)
    assert argv_c[-1] == 'clean' and '-destination' not in argv_c, argv_c
    print('ok')
"
```

Expected output: `ok`

- [ ] **Step 3: Commit**

```bash
git add pulse_ios_dev_tool/src/pulse_ios_dev_tool/xcodebuild.py
git commit -m "feat(pulse-ios-dev-tool): add xcodebuild argv builders"
```

---

## Task 7: `packages.py` — local Swift package test dispatcher

**Files:**
- Create: `pulse_ios_dev_tool/src/pulse_ios_dev_tool/packages.py`

- [ ] **Step 1: Write `packages.py`**

```python
"""Local Swift package test resolution.

Default convention (matches the existing pulse-ios-testing skill):

    cd ios/Packages/<Name> && xcodebuild test \
        -project Package.swift \
        -scheme <Name>

Overrides from [packages.<Name>] in config.toml merge over the convention.
"""
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

- [ ] **Step 2: Verify resolution with and without override**

```bash
cd <skills-repo>
python -c "
import tempfile
from pathlib import Path
from pulse_ios_dev_tool.config import load, write_simulator, SimulatorConfig
from pulse_ios_dev_tool.packages import resolve

with tempfile.TemporaryDirectory() as td:
    td = Path(td).resolve()
    (td / 'ios' / 'Pulse.xcodeproj').mkdir(parents=True)
    (td / 'ios' / 'Packages' / 'PulseNetworking').mkdir(parents=True)
    (td / 'pulse-ios-build').mkdir()
    cfg_path = td / 'pulse-ios-build' / 'config.toml'
    cfg_path.write_text('''
[project]
path = \"ios/Pulse.xcodeproj\"
scheme = \"Pulse\"

[packages.PulseNetworking]
scheme = \"PulseNetworkingTests\"
''')
    write_simulator(cfg_path, SimulatorConfig(name='X', udid='U', device='iPhone 17', runtime='iOS 26.0'))
    cfg = load(cfg_path)

    argv, cwd = resolve(cfg, 'PulseNetworking')
    assert cwd == td / 'ios' / 'Packages' / 'PulseNetworking', cwd
    assert 'PulseNetworkingTests' in argv, argv

    # Add a sibling package with no override, verify default naming.
    (td / 'ios' / 'Packages' / 'PulseFeed').mkdir()
    argv2, _ = resolve(cfg, 'PulseFeed')
    assert 'PulseFeed' in argv2 and 'PulseNetworkingTests' not in argv2, argv2
    print('ok')
"
```

Expected output: `ok`

- [ ] **Step 3: Commit**

```bash
git add pulse_ios_dev_tool/src/pulse_ios_dev_tool/packages.py
git commit -m "feat(pulse-ios-dev-tool): add local-package test dispatcher"
```

---

## Task 8: `simulator.py` — simctl wrappers + interactive picker

**Files:**
- Create: `pulse_ios_dev_tool/src/pulse_ios_dev_tool/simulator.py`

- [ ] **Step 1: Write `simulator.py`**

```python
"""xcrun simctl wrappers + interactive picker for `boot`.

Only this module and proc.py touch simctl.
"""
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
    identifier: str     # e.g. com.apple.CoreSimulator.SimDeviceType.iPhone-17-Pro
    name: str           # e.g. iPhone 17 Pro


@dataclass(frozen=True)
class Runtime:
    identifier: str     # e.g. com.apple.CoreSimulator.SimRuntime.iOS-26-0
    name: str           # e.g. iOS 26.0
    version: str        # e.g. 26.0


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
        # iOS-only tool; platform defaults to "iOS" if simctl omits it.
        if r.get("platform", "iOS") != "iOS":
            continue
        out.append(Runtime(identifier=r["identifier"], name=r["name"], version=r["version"]))
    # Newest first.
    out.sort(key=lambda r: [int(p) for p in r.version.split(".") if p.isdigit()], reverse=True)
    return out


def find_device_by_name(name: str) -> dict | None:
    """Return the first device dict matching name, or None."""
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
    """Create a simulator and return the new UDID."""
    out = run_json(["xcrun", "simctl", "create", name, device_type.identifier, runtime.identifier])
    return out.strip()


def boot(udid: str) -> None:
    """Boot the simulator. No-ops if already booted."""
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


def _pick_tty(prompt: str, options: list[str]) -> int:
    """Numeric menu picker. Returns the chosen index."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise EnvError(
            "`pulse-ios-dev-tool boot` first-run picker needs a real terminal. "
            "Re-run from an interactive shell."
        )
    print(prompt)
    for i, opt in enumerate(options, start=1):
        print(f"  {i}. {opt}")
    while True:
        raw = input("Choice: ").strip()
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(options):
                return idx - 1
        print(f"Enter a number 1..{len(options)}.")


def pick_device_and_runtime(*, iphone_17_only: bool) -> tuple[DeviceType, Runtime]:
    devices = list_device_types(iphone_17_only=iphone_17_only)
    if not devices:
        raise EnvError(
            "No matching iPhone device types found. "
            "Try `pulse-ios-dev-tool boot --all-devices`."
        )
    runtimes = list_runtimes()
    if not runtimes:
        raise EnvError("No iOS runtimes installed. Install via Xcode > Settings > Platforms.")
    di = _pick_tty("Pick a device type:", [d.name for d in devices])
    ri = _pick_tty("Pick a runtime:", [r.name for r in runtimes])
    return devices[di], runtimes[ri]


def to_config(name: str, udid: str, device: DeviceType, runtime: Runtime) -> SimulatorConfig:
    return SimulatorConfig(name=name, udid=udid, device=device.name, runtime=runtime.name)
```

- [ ] **Step 2: Smoke: listing runs against real simctl (requires Xcode)**

```bash
cd <skills-repo>
python -c "
from pulse_ios_dev_tool.simulator import list_device_types, list_runtimes
dts = list_device_types(iphone_17_only=False)
print(f'{len(dts)} device types found (sample: {dts[0].name if dts else None})')
rts = list_runtimes()
print(f'{len(rts)} runtimes found (sample: {rts[0].name if rts else None})')
"
```

Expected: two non-zero counts and sample strings. If you're on a machine without Xcode, skip this — the code path is exercised end-to-end in Task 14.

- [ ] **Step 3: Commit**

```bash
git add pulse_ios_dev_tool/src/pulse_ios_dev_tool/simulator.py
git commit -m "feat(pulse-ios-dev-tool): add simulator module with picker"
```

---

## Task 9: `bootstrap.py` — worktree-bootstrap verb body

**Files:**
- Create: `pulse_ios_dev_tool/src/pulse_ios_dev_tool/bootstrap.py`

- [ ] **Step 1: Write `bootstrap.py`**

```python
"""Implementation of the `worktree-bootstrap` verb."""
from __future__ import annotations

from pathlib import Path

from .errors import UserError
from .paths import find_worktree_root_for_bootstrap

_GITIGNORE_MARKER = "# added by pulse-ios-dev-tool worktree-bootstrap"
_GITIGNORE_ENTRY = "pulse-ios-build/"

_CONFIG_TEMPLATE = """\
# pulse-ios-build/config.toml
# Generated by `pulse-ios-dev-tool worktree-bootstrap`.
# Edit project.scheme / configuration as needed. Run `pulse-ios-dev-tool boot`
# to populate [simulator].

[project]
path    = "ios/Pulse.xcodeproj"
scheme  = "Pulse"
configuration = "Debug"

[packages_root]
path = "ios/Packages"

[extras]
xcodebuild_flags = []
"""


def run(*, force: bool = False) -> int:
    root = find_worktree_root_for_bootstrap()
    pib = root / "pulse-ios-build"
    cfg_path = pib / "config.toml"
    derived = pib / "derivedData"

    pib.mkdir(exist_ok=True)
    derived.mkdir(exist_ok=True)

    if cfg_path.exists() and not force:
        print(f"pulse-ios-build already bootstrapped at {pib} (use --force to re-seed config.toml).")
    else:
        cfg_path.write_text(_CONFIG_TEMPLATE)
        print(f"Wrote {cfg_path}")

    _ensure_gitignored(root)
    print()
    print("Next: `pulse-ios-dev-tool boot` to create and register a simulator.")
    return 0


def _ensure_gitignored(root: Path) -> None:
    gi = root / ".gitignore"
    if gi.exists():
        content = gi.read_text()
        lines = content.splitlines()
        if any(line.strip() == _GITIGNORE_ENTRY for line in lines):
            return
        suffix = "" if content.endswith("\n") else "\n"
        gi.write_text(content + f"{suffix}{_GITIGNORE_MARKER}\n{_GITIGNORE_ENTRY}\n")
    else:
        gi.write_text(f"{_GITIGNORE_MARKER}\n{_GITIGNORE_ENTRY}\n")
    print(f"Updated {gi} to ignore `{_GITIGNORE_ENTRY}`.")
```

- [ ] **Step 2: Verify bootstrap against a fake worktree**

```bash
cd <skills-repo>
python -c "
import os, tempfile
from pathlib import Path
from pulse_ios_dev_tool.bootstrap import run

with tempfile.TemporaryDirectory() as td:
    td = Path(td).resolve()
    (td / 'ios' / 'Pulse.xcodeproj').mkdir(parents=True)
    (td / '.git').mkdir()
    os.chdir(td / 'ios')
    run()
    assert (td / 'pulse-ios-build' / 'config.toml').is_file()
    assert (td / 'pulse-ios-build' / 'derivedData').is_dir()
    assert 'pulse-ios-build/' in (td / '.gitignore').read_text()
    # idempotent
    run()
    print('ok')
"
```

Expected output: `ok` (plus some prose log lines above it).

- [ ] **Step 3: Commit**

```bash
git add pulse_ios_dev_tool/src/pulse_ios_dev_tool/bootstrap.py
git commit -m "feat(pulse-ios-dev-tool): add worktree-bootstrap verb implementation"
```

---

## Task 10: `cli.py` — dispatcher + simple verbs (bootstrap, config, clean, wipe-derived)

**Files:**
- Modify: `pulse_ios_dev_tool/src/pulse_ios_dev_tool/cli.py` (replace placeholder)

- [ ] **Step 1: Overwrite `cli.py`**

```python
"""pulse-ios-dev-tool — argparse dispatcher + verb handlers.

Handler functions return an int exit code; main() maps exceptions to codes.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import bootstrap, config as config_mod, packages as packages_mod, simulator as sim_mod, xcodebuild
from .errors import EnvError, PulseIosError, SubprocessError, UserError
from .paths import find_config
from .proc import require, run


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, default=None, help="Path to config.toml (overrides walk-up discovery).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Stream subprocess output and show tracebacks.")


def _load_config(args: argparse.Namespace) -> config_mod.Config:
    path = args.config.resolve() if args.config else find_config()
    return config_mod.load(path)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pulse-ios-dev-tool", description="Pulse iOS build / sim / test CLI.")
    sub = p.add_subparsers(dest="verb", required=True)

    wb = sub.add_parser("worktree-bootstrap", help="Create pulse-ios-build/ in this worktree.")
    wb.add_argument("--force", action="store_true", help="Re-seed config.toml even if it already exists.")
    _add_common(wb)
    wb.set_defaults(func=_cmd_worktree_bootstrap)

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
    tp.add_argument("name", help="Directory / scheme name under packages_root (e.g. PulseNetworking).")
    _add_common(tp)
    tp.set_defaults(func=_cmd_test_package)

    return p


# ---- handlers ----------------------------------------------------------------

def _cmd_worktree_bootstrap(args: argparse.Namespace) -> int:
    return bootstrap.run(force=args.force)


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
    from .boot import run as boot_run      # lazy import — see Task 11
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
    from .runapp import run as run_run     # lazy import — see Task 12
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

    if cfg is not None:
        if not cfg.project.path.exists():
            problems.append(f"project.path does not exist: {cfg.project.path}")
        else:
            print(f"project: {cfg.project.path}")
        if cfg.simulator is None:
            problems.append("No [simulator] block. Run `pulse-ios-dev-tool boot`.")
        else:
            dev = sim_mod.find_device_by_udid(cfg.simulator.udid)
            if dev is None:
                problems.append(f"Simulator UDID not found in simctl list: {cfg.simulator.udid}")
            else:
                print(f"simulator: {cfg.simulator.name} ({cfg.simulator.udid}) — state={dev.get('state')}")
        if not cfg.derived_data.parent.exists():
            problems.append(f"pulse-ios-build/ missing: {cfg.derived_data.parent}")

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
    except PulseIosError as e:
        print(f"error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return e.exit_code
    except KeyboardInterrupt:
        return 130
```

- [ ] **Step 2: Reinstall (dependency tree unchanged but entry layout grew)**

```bash
cd <skills-repo>
uv tool install --reinstall --editable ./pulse_ios_dev_tool
pulse-ios-dev-tool --help
```

Expected: help text listing `worktree-bootstrap`, `boot`, `build`, `test`, `run`, `clean`, `wipe-derived`, `test-package`, `config`, `doctor`.

- [ ] **Step 3: Commit**

```bash
git add pulse_ios_dev_tool/src/pulse_ios_dev_tool/cli.py
git commit -m "feat(pulse-ios-dev-tool): add argparse dispatcher + bootstrap/config/clean/doctor verbs"
```

---

## Task 11: `boot.py` — the `boot` verb body

**Files:**
- Create: `pulse_ios_dev_tool/src/pulse_ios_dev_tool/boot.py`

- [ ] **Step 1: Write `boot.py`**

```python
"""Implementation of the `boot` verb. Uses simulator.py for picker + simctl I/O."""
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
    sim_name = f"Pulse-{cfg.worktree_root.name}"

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

- [ ] **Step 2: Verify it imports and `--help` still works**

```bash
cd <skills-repo>
pulse-ios-dev-tool boot --help
```

Expected: help text with `--recreate` and `--all-devices`.

- [ ] **Step 3: Commit**

```bash
git add pulse_ios_dev_tool/src/pulse_ios_dev_tool/boot.py
git commit -m "feat(pulse-ios-dev-tool): add boot verb with first-run picker"
```

---

## Task 12: `runapp.py` — the `run` verb body

**Files:**
- Create: `pulse_ios_dev_tool/src/pulse_ios_dev_tool/runapp.py`

- [ ] **Step 1: Write `runapp.py`**

```python
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
    # xcodebuild writes to Build/Products/<Configuration>-iphonesimulator/<scheme>.app
    candidate_dir = derived_data / "Build" / "Products" / f"{configuration}-iphonesimulator"
    app_path = candidate_dir / f"{scheme}.app"
    if app_path.is_dir():
        return app_path
    # Fallback: glob.
    matches = list(candidate_dir.glob("*.app"))
    if len(matches) == 1:
        return matches[0]
    raise UserError(
        f"Could not locate a built .app under {candidate_dir}. "
        f"Expected {scheme}.app. Try `pulse-ios-dev-tool build` first."
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

    # 1. Build
    argv = xcodebuild.build_argv(cfg, release=args.release)
    proc_run(argv, verbose=args.verbose)

    # 2. Locate .app
    configuration = "Release" if args.release else cfg.project.configuration
    app_path = _find_app(cfg.derived_data, cfg.project.scheme, configuration)
    bundle_id = _bundle_id(app_path)

    # 3. Boot sim if needed, install, launch.
    sim_mod.boot(sim.udid)
    proc_run(["xcrun", "simctl", "install", sim.udid, str(app_path)], verbose=args.verbose)
    result = proc_run(["xcrun", "simctl", "launch", sim.udid, bundle_id], capture=True, verbose=args.verbose)
    print(result.stdout.strip())
    print(f"bundle_id = {bundle_id}")
    return 0
```

- [ ] **Step 2: Verify import + help**

```bash
cd <skills-repo>
pulse-ios-dev-tool run --help
```

Expected: help text mentioning `--release`.

- [ ] **Step 3: Commit**

```bash
git add pulse_ios_dev_tool/src/pulse_ios_dev_tool/runapp.py
git commit -m "feat(pulse-ios-dev-tool): add run verb (build+install+launch)"
```

---

## Task 13: Companion skill `skills/pulse-ios-build/`

**Files:**
- Create: `pulse-dev-skills/skills/pulse-ios-build/SKILL.md`

- [ ] **Step 1: Write `SKILL.md`**

```markdown
---
name: pulse-ios-build
description: Use when building, testing, running, or cleaning the Pulse iOS app / local Swift packages — routes to `pulse-ios-dev-tool` for non-interactive work and keeps `xcodebuildmcp-cli` reserved for debugging, UI automation, and log streaming.
---

# Pulse iOS Build

Use `pulse-ios-dev-tool` for every non-interactive iOS build task. Keep `xcodebuildmcp-cli` for debugging, UI automation, and log streaming.

## Decision

- **Build / test / run / clean / package test / wipe derived data / create-or-boot simulator** → `pulse-ios-dev-tool <verb>`.
- **Debug sessions, breakpoints, log streaming, UI automation (tap / swipe / screenshot), archive, export IPA, TestFlight** → `xcodebuildmcp-cli` skill.
- **Never** use `swift test` for Pulse packages.

## One-time machine setup

```bash
uv tool install --editable /abs/path/to/pulse-dev-skills/pulse_ios_dev_tool
```

Requires `uv` on `PATH` and `~/.local/bin` on `PATH`.

Upgrade with `uv tool upgrade pulse-ios-dev-tool`. Editable installs pick up Python source edits automatically.

## Per-worktree setup

From anywhere inside the worktree:

```bash
pulse-ios-dev-tool worktree-bootstrap     # creates pulse-ios-build/, seeds config.toml, updates .gitignore
pulse-ios-dev-tool boot                   # first run: interactive picker; writes [simulator] to config.toml
```

## Verb reference

| Verb | Use for |
|---|---|
| `pulse-ios-dev-tool worktree-bootstrap` | Scaffold `pulse-ios-build/` in a new worktree. Idempotent. `--force` re-seeds `config.toml`. |
| `pulse-ios-dev-tool boot` | Create (first run) or boot the per-worktree simulator. `--recreate` nukes and re-picks. `--all-devices` disables the iPhone 17 filter. |
| `pulse-ios-dev-tool build` | `xcodebuild build` on the main app. `--release` flips configuration. `--scheme <name>` overrides. |
| `pulse-ios-dev-tool test` | `xcodebuild test` on the main app. Pass `--only-testing <id>` / `--skip-testing <id>` through. |
| `pulse-ios-dev-tool run` | Build → locate `.app` → `simctl install` → `simctl launch`. Prints the bundle id on success. |
| `pulse-ios-dev-tool clean` | `xcodebuild clean` on the project. |
| `pulse-ios-dev-tool wipe-derived` | `rm -rf pulse-ios-build/derivedData`. Prompts unless `--yes`. |
| `pulse-ios-dev-tool test-package <Name>` | Runs `xcodebuild test` against `ios/Packages/<Name>/Package.swift` with the saved simulator destination. |
| `pulse-ios-dev-tool config` | Prints resolved config as JSON. Use for debugging. |
| `pulse-ios-dev-tool doctor` | Sanity checks: config, tooling, simulator, project path. Run this first when something's off. |

## Global flags

- `--config <path>` — override walk-up discovery.
- `-v` / `--verbose` — stream subprocess output, show tracebacks on error.

## Exit codes

- `0` ok
- `1` user error (bad CLI args, bad config, verb refused)
- `2` environment error (config not found, xcodebuild / simctl missing)
- `3` subprocess failure (xcodebuild / simctl returned non-zero; upstream code is included in the message)

## When the global "prepare build/run" instruction fires

The global user instruction says: "when iOS code is finished, invoke the xcodebuildmcp-cli skill to prepare build and run." Interpret that in this project as:

- For the **build and run** steps, use `pulse-ios-dev-tool build` then `pulse-ios-dev-tool run`.
- For **debug, UI automation, screenshots, log streaming**, use `xcodebuildmcp-cli`.
- If in doubt: build/test/run/clean go through `pulse-ios-dev-tool`; anything interactive or introspective that touches a live app goes through `xcodebuildmcp-cli`.

## Common mistakes

- Running `pulse-ios-dev-tool` anywhere without `worktree-bootstrap` first → exit 2 with discovery error. Run bootstrap.
- Skipping `boot` → any verb that needs a simulator errors with "run `pulse-ios-dev-tool boot` first."
- Editing `[simulator].udid` by hand → prefer `pulse-ios-dev-tool boot --recreate`.
- Using `xcodebuildmcp-cli` for a vanilla build/test → goes through the wrong path; use `pulse-ios-dev-tool` instead.
```

- [ ] **Step 2: Commit**

```bash
cd <skills-repo>
git add skills/pulse-ios-build/SKILL.md
git commit -m "feat(skills): add pulse-ios-build skill documenting pulse-ios-dev-tool"
```

---

## Task 14: Trim the `pulse-ios-testing` skill

**Files:**
- Modify: `pulse-dev-skills/skills/pulse-ios-testing/SKILL.md` (full rewrite)

- [ ] **Step 1: Replace `SKILL.md` with the pointer**

```markdown
---
name: pulse-ios-testing
description: Use when running iOS tests in the Pulse project — delegates to the `pulse-ios-build` skill and the `pulse-ios-dev-tool` CLI for main-app and local-package tests.
---

# Pulse iOS Testing

Delegates to `pulse-ios-dev-tool` via the `pulse-ios-build` skill.

- Main app tests: `pulse-ios-dev-tool test`
- Local Swift package tests: `pulse-ios-dev-tool test-package <Name>`

Never use `swift test` for Pulse packages — they depend on iOS-only SDKs that `swift test` can't resolve.

See `skills/pulse-ios-build/SKILL.md` for the full command list, install instructions, and flag reference.
```

- [ ] **Step 2: Validate skills structure**

```bash
cd <skills-repo>
./scripts/validate-skills.sh
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add skills/pulse-ios-testing/SKILL.md
git commit -m "docs(skills): trim pulse-ios-testing to a pointer to pulse-ios-build"
```

---

## Task 15: End-to-end smoke check in a real worktree

**Files:**
- (no code changes; verification only)

- [ ] **Step 1: Install the tool from this skills repo**

```bash
cd <skills-repo>
uv tool install --reinstall --editable ./pulse_ios_dev_tool
which pulse-ios-dev-tool
```

Expected: path under `~/.local/bin/`.

- [ ] **Step 2: Bootstrap the author's active Pulse worktree**

```bash
cd /Users/yi.jiang/Developer/PulseProject/Pulse    # or your chosen worktree
pulse-ios-dev-tool worktree-bootstrap
```

Expected: prints creation of `pulse-ios-build/config.toml`, `pulse-ios-build/derivedData/`, and an update to `.gitignore`.

- [ ] **Step 3: Inspect resolved config**

```bash
pulse-ios-dev-tool config
```

Expected: JSON with `project.path` pointing at `ios/Pulse.xcodeproj`, `simulator: null`.

- [ ] **Step 4: Create the per-worktree simulator**

```bash
pulse-ios-dev-tool boot
```

Expected: interactive device and runtime picker (iPhone 17 family by default), a `Pulse-<worktree-dirname>` sim created, `[simulator]` written to `config.toml`, Simulator.app opens.

- [ ] **Step 5: Run doctor**

```bash
pulse-ios-dev-tool doctor
```

Expected: "All checks passed."

- [ ] **Step 6: Build**

```bash
pulse-ios-dev-tool build -v
```

Expected: xcodebuild runs, produces a `Pulse.app` under `pulse-ios-build/derivedData/Build/Products/Debug-iphonesimulator/`, exits 0. If it fails, fix the underlying issue and re-run — do not paper over errors.

- [ ] **Step 7: Run on simulator**

```bash
pulse-ios-dev-tool run
```

Expected: "bundle_id = com.applovin.Pulse" (or the project's actual bundle id), app launches on the booted sim.

- [ ] **Step 8: Main-app tests**

```bash
pulse-ios-dev-tool test -v
```

Expected: xcodebuild test runs against the main `Pulse` scheme, exits 0 (or failing tests surface verbatim). This is slow — several minutes on a full run. For a fast dry-run, scope it:

```bash
pulse-ios-dev-tool test --only-testing PulseTests/SomeFastSuite -v
```

- [ ] **Step 9: Test one local package**

```bash
pulse-ios-dev-tool test-package PulseNetworking
```

Expected: xcodebuild test runs against `ios/Packages/PulseNetworking/Package.swift`, exits 0 (or failing tests surface verbatim).

- [ ] **Step 10: Record the smoke-check outcome in the commit log**

```bash
cd <skills-repo>
git commit --allow-empty -m "chore(pulse-ios-dev-tool): end-to-end smoke check passed (bootstrap/boot/build/run/test/test-package)"
```

---

## Task 16: Update the repo README

**Files:**
- Modify: `pulse-dev-skills/README.md`

- [ ] **Step 1: Find the "Skill Set" section and insert a new bullet**

Locate the list starting with `- \`figma-extract-nodes\`` and add a bullet for `pulse-ios-build`:

```markdown
- `figma-extract-nodes`
- `pulse-api`
- `pulse-ios-build`
- `pulse-ios-perf-tracing`
- `pulse-prd`
- `pulse-ui`
```

- [ ] **Step 2: Add an "iOS build CLI" subsection after "Install To One Worktree"**

```markdown
## iOS build CLI (`pulse-ios-dev-tool`)

Centralized per-worktree iOS build / simulator / test CLI. Design:
`docs/specs/2026-04-24-pulse-ios-build-system.md`. Agent-facing decision
tree and verb reference: `skills/pulse-ios-build/SKILL.md`.

Install once per machine from this repo:

    uv tool install --editable <abs-path-to-this-repo>/pulse_ios_dev_tool

Then per worktree:

    pulse-ios-dev-tool worktree-bootstrap
    pulse-ios-dev-tool boot
    pulse-ios-dev-tool build

Upgrade: `uv tool upgrade pulse-ios-dev-tool`.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): add pulse-ios-dev-tool install + link to pulse-ios-build skill"
```

---

## Done criteria

1. `pulse-ios-dev-tool` on `PATH` after a fresh `uv tool install --editable`.
2. `pulse-ios-dev-tool worktree-bootstrap` creates `pulse-ios-build/{config.toml, derivedData/}`, updates `.gitignore`, and is idempotent.
3. `pulse-ios-dev-tool boot` first-run picks device + runtime, creates a `Pulse-<worktree>` sim, writes `[simulator]`, and opens Simulator.app. Subsequent runs just boot.
4. `pulse-ios-dev-tool build / test / run / clean / wipe-derived / test-package <Name> / config / doctor` all work against a real Pulse worktree.
5. `skills/pulse-ios-build/SKILL.md` documents the verb list and the decision boundary with `xcodebuildmcp-cli`.
6. `skills/pulse-ios-testing/SKILL.md` points at the new skill.
7. Repo README mentions the CLI and links to the skill.
