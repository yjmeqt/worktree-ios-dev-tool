# Worktree iOS Dev — Config Split + `sim`/`proj` Namespaces — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `worktree-ios-dev/config.toml` into `project.toml` + `simulator.toml` (each carrying `schema_version`), reorganize the CLI into `proj <verb>` and `sim <verb>` namespaces with multi-sim support, and add `sim cleanup` / `sim du` / `sim prune` for simulator hygiene.

**Architecture:** Refactor `config.py` to a multi-sim model (`Config.simulators: dict[str, SimulatorEntry]`), introduce `proj.py` (project lifecycle) and `sim.py` (simulator lifecycle) modules that own subverb implementations, leave `simulator.py` as the simctl wrapper layer, and rewire `cli.py` around two nested subparsers. Legacy `config.toml` triggers a hard error with manual-migration instructions; no auto-migration or backwards-compatible verb aliases.

**Tech Stack:** Python 3.13+, `argparse`, `tomllib` (read), `tomlkit` (write, preserve comments), `xcrun simctl`, `xcodebuild`, `unittest` test runner. Existing project structure in `worktree_ios_dev_tool/`.

**Documentation requirements:** Per the project's `feedback_code_documentation` rule, every new/modified `.py` file gets a module-header `# path/to/file.py` line + module docstring; every public function/dataclass gets a docstring; non-obvious logic (especially name parsing) gets a why-comment; argparse `help=` strings read like user-facing one-liners; `UserError`/`EnvError` messages include actionable next steps.

**Reference spec:** `docs/superpowers/specs/2026-05-05-worktree-ios-dev-config-split-and-sim-namespace-design.md`.

---

## Working Conventions

- After every task, run `cd worktree_ios_dev_tool && uv run python -m unittest discover tests -v` to confirm green before committing.
- Commits use Conventional Commit prefixes (`feat:`, `refactor:`, `test:`, `docs:`, `chore:`). Each task ends with one commit unless noted.
- All file paths in this plan are relative to repo root: `/Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/`.
- The Python package root is `worktree_ios_dev_tool/src/worktree_ios_dev_tool/`. The test root is `worktree_ios_dev_tool/tests/`.

---

## Task 1: Rename `SimulatorConfig` → `SimulatorEntry` in dataclasses

**Files:**
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/config.py`
- Modify (call sites): `worktree_ios_dev_tool/src/worktree_ios_dev_tool/simulator.py`, `runapp.py`, `xcodebuild.py`, `boot.py`

This task is a pure rename to disambiguate single-instance config (`SimulatorConfig`) vs the new collection model where multiple entries coexist. No behavior change yet.

- [ ] **Step 1: Rename class in `config.py`**

In `worktree_ios_dev_tool/src/worktree_ios_dev_tool/config.py`, replace the class definition:

```python
@dataclass(frozen=True)
class SimulatorEntry:
    """One configured simulator under [simulators.<label>] in simulator.toml.

    Attributes:
        name:    The simctl device name. Always synthesized as
                 ``<simulator_prefix>-<worktree_basename>-<label>``; never hand-edit.
        udid:    The simctl-assigned UUID; the source of truth for routing
                 build/test/run destinations.
        device:  Apple device-type display name (e.g. "iPhone 17 Pro").
        runtime: Apple runtime display name (e.g. "iOS 18.2").
    """
    name: str
    udid: str
    device: str
    runtime: str
```

Keep `SimulatorConfig = SimulatorEntry` as a temporary alias at the end of the file so call sites compile in this commit; subsequent tasks remove the alias.

- [ ] **Step 2: Update call sites that reference the old name**

In each of the four files (`simulator.py`, `runapp.py`, `xcodebuild.py`, `boot.py`), replace `SimulatorConfig` imports/uses with `SimulatorEntry`. The only meaningful changes:

`simulator.py` line 13:
```python
from .config import SimulatorEntry
```

`simulator.py` `to_config` return annotation and body (lines 154-155):
```python
def to_config(name: str, udid: str, device: DeviceType, runtime: Runtime) -> SimulatorEntry:
    return SimulatorEntry(name=name, udid=udid, device=device.name, runtime=runtime.name)
```

`xcodebuild.py` line 6:
```python
from .config import Config, SimulatorEntry, require_simulator
```

`xcodebuild.py` `_destination` and `_common` signatures:
```python
def _destination(sim: SimulatorEntry) -> str:
    return f"platform=iOS Simulator,id={sim.udid}"


def _common(cfg: Config, sim: SimulatorEntry | None, *, release: bool) -> list[str]:
    ...
```

`boot.py` line 8:
```python
from .config import SimulatorEntry, load, write_simulator
```

`boot.py` line 55:
```python
sim_cfg = SimulatorEntry(name=sim_name, udid=udid, device=device.name, runtime=runtime.name)
```

`runapp.py` does not reference the class by name (it uses the `Config.simulator` attribute), so no change here yet.

- [ ] **Step 3: Run the test suite to confirm no regression**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run python -m unittest discover tests -v
```

Expected: all existing tests pass (only `test_bootstrap.py` and `test_paths.py`).

- [ ] **Step 4: Commit**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills
git add worktree_ios_dev_tool/src/worktree_ios_dev_tool/
git commit -m "refactor(config): rename SimulatorConfig to SimulatorEntry"
```

---

## Task 2: Introduce multi-sim `Config.simulators` dict + `resolve_sim` helper

**Files:**
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/config.py`
- Create: `worktree_ios_dev_tool/tests/test_resolve_sim.py`

This task changes the in-memory `Config` shape but does **not** yet change the file format on disk. `load()` continues to read the legacy `config.toml` and lift the single `[simulator]` block into a `simulators = {"default": ...}` dict. This keeps the test suite green while enabling subsequent tasks.

- [ ] **Step 1: Write the failing test**

Create `worktree_ios_dev_tool/tests/test_resolve_sim.py`:

```python
"""Tests for the single/multi-simulator resolution helper."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from worktree_ios_dev_tool.config import (  # noqa: E402
    Config,
    ProjectConfig,
    SimulatorEntry,
    resolve_sim,
)
from worktree_ios_dev_tool.errors import UserError  # noqa: E402


def _cfg(simulators: dict[str, SimulatorEntry]) -> Config:
    return Config(
        config_path=Path("/tmp/x/worktree-ios-dev/project.toml"),
        worktree_root=Path("/tmp/x"),
        derived_data=Path("/tmp/x/worktree-ios-dev/derivedData"),
        project=ProjectConfig(
            path=Path("/tmp/x/ios/App.xcodeproj"),
            scheme="App",
            configuration="Debug",
            simulator_prefix="App",
        ),
        simulators=simulators,
        packages_root=Path("/tmp/x/ios/Packages"),
    )


def _entry(name: str, udid: str = "U") -> SimulatorEntry:
    return SimulatorEntry(name=name, udid=udid, device="iPhone 17 Pro", runtime="iOS 18.2")


class ResolveSimTests(unittest.TestCase):
    def test_no_simulators_errors(self) -> None:
        with self.assertRaises(UserError) as cm:
            resolve_sim(_cfg({}), label=None)
        self.assertIn("sim pick", str(cm.exception))

    def test_single_sim_auto_picks(self) -> None:
        only = _entry("App-feat-default")
        result = resolve_sim(_cfg({"default": only}), label=None)
        self.assertIs(result, only)

    def test_multi_sim_without_label_errors(self) -> None:
        cfg = _cfg({
            "default": _entry("App-feat-default"),
            "peer": _entry("App-feat-peer"),
        })
        with self.assertRaises(UserError) as cm:
            resolve_sim(cfg, label=None)
        self.assertIn("--sim", str(cm.exception))
        self.assertIn("default", str(cm.exception))
        self.assertIn("peer", str(cm.exception))

    def test_explicit_label_resolves(self) -> None:
        peer = _entry("App-feat-peer")
        cfg = _cfg({"default": _entry("App-feat-default"), "peer": peer})
        self.assertIs(resolve_sim(cfg, label="peer"), peer)

    def test_unknown_label_errors(self) -> None:
        cfg = _cfg({"default": _entry("App-feat-default")})
        with self.assertRaises(UserError) as cm:
            resolve_sim(cfg, label="missing")
        self.assertIn("missing", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run python -m unittest tests.test_resolve_sim -v
```

Expected: `ImportError` (no `simulators`, `resolve_sim` symbols yet).

- [ ] **Step 3: Update `Config` dataclass and add `resolve_sim`**

Replace `Config` and the helper at the bottom of `config.py`:

```python
@dataclass(frozen=True)
class Config:
    """Resolved view of project.toml + simulator.toml.

    ``simulators`` is keyed by the user-chosen label (default key: ``"default"``).
    An empty dict means no simulator has been picked yet — commands that need
    one should raise via :func:`resolve_sim`.
    """
    config_path: Path                              # absolute path to project.toml
    worktree_root: Path                            # parent of worktree-ios-dev/
    derived_data: Path                             # absolute DerivedData dir
    project: ProjectConfig
    simulators: dict[str, SimulatorEntry] = field(default_factory=dict)
    packages_root: Path = field(default=Path("."))
    package_overrides: dict[str, PackageOverride] = field(default_factory=dict)
    extras_xcodebuild_flags: list[str] = field(default_factory=list)


def resolve_sim(cfg: Config, label: str | None) -> SimulatorEntry:
    """Pick the simulator a command should target.

    Resolution rules:
      * No simulators configured: raise UserError pointing at ``sim pick``.
      * ``label`` omitted and exactly one configured: return that one.
      * ``label`` omitted and multiple configured: raise UserError listing
        the available labels — destructive ambiguity is never silent.
      * ``label`` present but unknown: raise UserError listing what's available.
      * ``label`` present and known: return that entry.
    """
    if not cfg.simulators:
        raise UserError(
            "No simulators configured. Run `worktree-ios-dev-tool sim pick` first."
        )
    if label is None:
        if len(cfg.simulators) == 1:
            (only,) = cfg.simulators.values()
            return only
        labels = ", ".join(sorted(cfg.simulators))
        raise UserError(
            f"Multiple simulators configured ({labels}). "
            f"Pass `--sim <label>` to disambiguate."
        )
    try:
        return cfg.simulators[label]
    except KeyError:
        labels = ", ".join(sorted(cfg.simulators))
        raise UserError(
            f"No simulator labeled `{label}`. Configured: {labels}."
        )
```

Remove the old `simulator: SimulatorConfig | None = None` attribute and the `require_simulator` function (its callers will be migrated in Task 8). Keep the `SimulatorConfig = SimulatorEntry` alias for one more task.

- [ ] **Step 4: Adapt `load()` to populate `simulators` dict from legacy `[simulator]`**

In `load()`, replace the `simulator: SimulatorConfig | None = None` block with:

```python
    simulators: dict[str, SimulatorEntry] = {}
    if "simulator" in data:
        # Legacy single-sim shape; lifted to label "default" until Task 5
        # introduces native [simulators.<label>] parsing.
        sim = data["simulator"]
        _require_keys("simulator", sim, _ALLOWED_SIMULATOR)
        for key in _ALLOWED_SIMULATOR:
            if key not in sim:
                raise UserError(f"[simulator] missing `{key}` in {config_path}.")
        simulators["default"] = SimulatorEntry(
            name=sim["name"],
            udid=sim["udid"],
            device=sim["device"],
            runtime=sim["runtime"],
        )
```

And update the `Config(...)` constructor call to pass `simulators=simulators`. Remove the `simulator=simulator,` keyword.

- [ ] **Step 5: Migrate the two internal consumers off `cfg.simulator`**

`xcodebuild.py` `build_argv` / `test_argv`:

Replace `sim = require_simulator(cfg)` with `sim = resolve_sim(cfg, label=None)`. Add the import: `from .config import Config, SimulatorEntry, resolve_sim`. Remove the `require_simulator` import.

`packages.py` `resolve()`:

Replace `sim = require_simulator(cfg)` with `sim = resolve_sim(cfg, label=None)`. Update the import similarly.

`runapp.py` `run()`:

Replace
```python
from .config import load, require_simulator
...
sim = require_simulator(cfg)
```
with
```python
from .config import load, resolve_sim
...
sim = resolve_sim(cfg, label=None)
```

`boot.py` continues to read `cfg.simulator` — change it to read `cfg.simulators.get("default")` for now:
```python
existing = cfg.simulators.get("default")
need_first_run = (
    existing is None
    or sim_mod.find_device_by_udid(existing.udid) is None
    or args.recreate
)
if args.recreate and existing is not None:
    ...
if not need_first_run:
    assert existing is not None
    sim_mod.boot(existing.udid)
    ...
```

`cli.py` `_cmd_config` reads `cfg.simulator`. Replace the `"simulator"` key in the JSON payload with `"simulators"`:
```python
"simulators": {
    label: {
        "name": s.name, "udid": s.udid, "device": s.device, "runtime": s.runtime,
    } for label, s in cfg.simulators.items()
},
```

`cli.py` `_cmd_doctor` reads `cfg.simulator`. Replace with iteration over the dict:
```python
if not cfg.simulators:
    ui.problem("simulators     none configured — run `worktree-ios-dev-tool boot`")
    problems.append("No simulators. Run `worktree-ios-dev-tool boot`.")
else:
    for label, sim in cfg.simulators.items():
        dev = sim_mod.find_device_by_udid(sim.udid)
        if dev is None:
            ui.problem(f"simulators[{label}]  UDID not found: {sim.udid}")
            problems.append(f"Simulator UDID not found: {sim.udid}")
        else:
            state = dev.get("state", "?")
            ui.step(f"simulators[{label}]  {sim.name} ({sim.udid})  state={state}")
```

- [ ] **Step 6: Run all tests**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run python -m unittest discover tests -v
```

Expected: all five tests in `test_resolve_sim.py` pass plus the existing two test files. No regressions.

- [ ] **Step 7: Commit**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills
git add worktree_ios_dev_tool/
git commit -m "refactor(config): replace single simulator with simulators dict + resolve_sim"
```

---

## Task 3: Add `schema_version` field + new file split (project.toml + simulator.toml)

**Files:**
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/config.py`
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/paths.py`
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/bootstrap.py`
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/boot.py`
- Create: `worktree_ios_dev_tool/tests/test_config_schema.py`
- Create: `worktree_ios_dev_tool/tests/test_legacy_config_rejection.py`

This is the big file-format change. After this task, the tool reads `project.toml` + `simulator.toml` (each requiring `schema_version = 1`), the legacy `config.toml`-only worktree triggers a hard error, and `bootstrap` writes the new files.

- [ ] **Step 1: Write the schema-version test**

Create `worktree_ios_dev_tool/tests/test_config_schema.py`:

```python
"""Tests for project.toml + simulator.toml schema parsing and version checks."""
from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from worktree_ios_dev_tool.config import load  # noqa: E402
from worktree_ios_dev_tool.errors import UserError  # noqa: E402


def _seed(tmp: Path, project: str, simulator: str | None = None) -> Path:
    """Seed a fake worktree with project.toml (and optional simulator.toml)."""
    cfg_dir = tmp / "worktree-ios-dev"
    cfg_dir.mkdir()
    (tmp / "ios").mkdir()
    (tmp / "ios" / "Pulse.xcodeproj").mkdir()
    project_toml = cfg_dir / "project.toml"
    project_toml.write_text(textwrap.dedent(project))
    if simulator is not None:
        (cfg_dir / "simulator.toml").write_text(textwrap.dedent(simulator))
    return project_toml


class ProjectVersionTests(unittest.TestCase):
    def test_loads_v1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            path = _seed(tmp, """
                schema_version = 1
                [project]
                path = "ios/Pulse.xcodeproj"
                scheme = "Pulse"
                configuration = "Debug"
                simulator_prefix = "Pulse"
            """)
            cfg = load(path)
            self.assertEqual(cfg.project.scheme, "Pulse")
            self.assertEqual(cfg.simulators, {})

    def test_missing_version_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            path = _seed(tmp, """
                [project]
                path = "ios/Pulse.xcodeproj"
                scheme = "Pulse"
                configuration = "Debug"
                simulator_prefix = "Pulse"
            """)
            with self.assertRaises(UserError) as cm:
                load(path)
            self.assertIn("schema_version", str(cm.exception))
            self.assertIn("proj init", str(cm.exception))

    def test_unsupported_version_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            path = _seed(tmp, """
                schema_version = 99
                [project]
                path = "ios/Pulse.xcodeproj"
                scheme = "Pulse"
                configuration = "Debug"
                simulator_prefix = "Pulse"
            """)
            with self.assertRaises(UserError) as cm:
                load(path)
            self.assertIn("99", str(cm.exception))


class SimulatorTomlTests(unittest.TestCase):
    def _common_project(self) -> str:
        return """
            schema_version = 1
            [project]
            path = "ios/Pulse.xcodeproj"
            scheme = "Pulse"
            configuration = "Debug"
            simulator_prefix = "Pulse"
        """

    def test_loads_two_simulators(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            path = _seed(tmp, self._common_project(), simulator="""
                schema_version = 1

                [simulators.default]
                name = "Pulse-feat-default"
                udid = "AAAA"
                device = "iPhone 17 Pro"
                runtime = "iOS 18.2"

                [simulators.peer]
                name = "Pulse-feat-peer"
                udid = "BBBB"
                device = "iPhone 17 Pro"
                runtime = "iOS 18.2"
            """)
            cfg = load(path)
            self.assertEqual(set(cfg.simulators), {"default", "peer"})
            self.assertEqual(cfg.simulators["peer"].udid, "BBBB")

    def test_simulator_missing_version_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            path = _seed(tmp, self._common_project(), simulator="""
                [simulators.default]
                name = "Pulse-feat-default"
                udid = "AAAA"
                device = "iPhone 17 Pro"
                runtime = "iOS 18.2"
            """)
            with self.assertRaises(UserError) as cm:
                load(path)
            self.assertIn("schema_version", str(cm.exception))
            self.assertIn("sim pick", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Write the legacy-rejection test**

Create `worktree_ios_dev_tool/tests/test_legacy_config_rejection.py`:

```python
"""Tests that a worktree with only the legacy config.toml triggers a hard
UserError listing the manual migration steps."""
from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from worktree_ios_dev_tool.errors import UserError  # noqa: E402
from worktree_ios_dev_tool.paths import find_project_toml  # noqa: E402


class LegacyConfigRejectionTests(unittest.TestCase):
    def test_legacy_only_raises_with_migration_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wt = Path(tmp) / "feat-x"
            (wt / "worktree-ios-dev").mkdir(parents=True)
            (wt / "worktree-ios-dev" / "config.toml").write_text(textwrap.dedent("""
                [project]
                path = "ios/Pulse.xcodeproj"
                scheme = "Pulse"
            """))
            with self.assertRaises(UserError) as cm:
                find_project_toml(start=wt)
            msg = str(cm.exception)
            self.assertIn("legacy config.toml", msg)
            self.assertIn("proj init", msg)
            self.assertIn("sim pick", msg)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run both tests to verify they fail**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run python -m unittest tests.test_config_schema tests.test_legacy_config_rejection -v
```

Expected: `ImportError` for `find_project_toml` and assertion failures on the version checks.

- [ ] **Step 4: Implement `find_project_toml` + legacy rejection in `paths.py`**

In `worktree_ios_dev_tool/src/worktree_ios_dev_tool/paths.py`:

Add new constants near the top:

```python
PROJECT_FILENAME = "project.toml"
SIMULATOR_FILENAME = "simulator.toml"
LEGACY_FILENAME = "config.toml"
```

Replace `find_config()` with `find_project_toml()` (delete the old function):

```python
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
```

Add a `simulator_toml_for(project_toml: Path) -> Path` helper at the end:

```python
def simulator_toml_for(project_toml: Path) -> Path:
    """Return the expected simulator.toml path that pairs with *project_toml*."""
    return project_toml.parent / SIMULATOR_FILENAME
```

Keep `find_worktree_root_for_bootstrap`, `worktree_root`, `config_dir`, `derived_data_dir` as they are. The CONFIG_FILENAME constant can be deleted (no callers after this task).

- [ ] **Step 5: Rewrite `config.load()` to read both files with version checks**

In `config.py`, replace the existing `load` function:

```python
PROJECT_SCHEMA_VERSION = 1
SIMULATOR_SCHEMA_VERSION = 1

_ALLOWED_PROJECT_TOP = {"schema_version", "project", "packages_root", "packages", "extras"}
_ALLOWED_SIMULATOR_TOP = {"schema_version", "simulators"}
# (existing _ALLOWED_PROJECT, _ALLOWED_SIMULATOR, _ALLOWED_PACKAGES_ROOT,
#  _ALLOWED_PACKAGE, _ALLOWED_EXTRAS sets remain unchanged)


def load(project_toml: Path) -> Config:
    """Load and validate ``project.toml`` and (optionally) ``simulator.toml``.

    *project_toml* must point at the new split file; legacy ``config.toml``
    is rejected at discovery time by :func:`paths.find_project_toml`. Each
    file carries a ``schema_version`` integer; we currently only accept
    version 1, and unknown versions are a hard UserError so future bumps
    can carry migration logic without silent misreads.
    """
    proj_data = _read_toml(project_toml)
    _check_version(
        proj_data, project_toml,
        expected=PROJECT_SCHEMA_VERSION,
        recovery="proj init",
    )
    _require_keys("<project.toml root>", proj_data, _ALLOWED_PROJECT_TOP)

    if "project" not in proj_data:
        raise UserError(
            f"Missing [project] section in {project_toml}. "
            f"Re-run `worktree-ios-dev-tool proj init --force` to re-seed."
        )
    proj = proj_data["project"]
    _require_keys("project", proj, _ALLOWED_PROJECT)
    for key in ("path", "scheme"):
        if key not in proj:
            raise UserError(f"[project] missing `{key}` in {project_toml}.")
    wt_root = worktree_root(project_toml)
    project = ProjectConfig(
        path=(wt_root / proj["path"]).resolve(),
        scheme=proj["scheme"],
        configuration=proj.get("configuration", "Debug"),
        simulator_prefix=proj.get("simulator_prefix") or proj["scheme"],
    )

    pkg_root_cfg = proj_data.get("packages_root", {"path": "ios/Packages"})
    _require_keys("packages_root", pkg_root_cfg, _ALLOWED_PACKAGES_ROOT)
    packages_root = (wt_root / pkg_root_cfg.get("path", "ios/Packages")).resolve()

    overrides: dict[str, PackageOverride] = {}
    for name, table in (proj_data.get("packages", {}) or {}).items():
        _require_keys(f"packages.{name}", table, _ALLOWED_PACKAGE)
        overrides[name] = PackageOverride(scheme=table.get("scheme"))

    extras = proj_data.get("extras", {})
    _require_keys("extras", extras, _ALLOWED_EXTRAS)
    flags = extras.get("xcodebuild_flags", [])
    if not isinstance(flags, list) or not all(isinstance(f, str) for f in flags):
        raise UserError(
            f"[extras].xcodebuild_flags must be a list of strings in {project_toml}."
        )

    simulators = _load_simulators(simulator_toml_for(project_toml))

    return Config(
        config_path=project_toml,
        worktree_root=wt_root,
        derived_data=derived_data_dir(project_toml),
        project=project,
        simulators=simulators,
        packages_root=packages_root,
        package_overrides=overrides,
        extras_xcodebuild_flags=list(flags),
    )


def _read_toml(path: Path) -> dict:
    """Return parsed TOML, surfacing path in any error."""
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _check_version(data: dict, path: Path, *, expected: int, recovery: str) -> None:
    """Validate ``schema_version`` at the top of *data*.

    Missing → UserError citing *recovery* (the verb to re-run).
    Mismatched → UserError naming the version we found vs what we accept.
    """
    if "schema_version" not in data:
        raise UserError(
            f"{path}: missing `schema_version`. "
            f"Re-run `worktree-ios-dev-tool {recovery}` to regenerate the file."
        )
    v = data["schema_version"]
    if v != expected:
        raise UserError(
            f"{path}: schema_version {v!r} not supported (expected {expected}). "
            f"Upgrade worktree-ios-dev-tool or migrate manually."
        )


def _load_simulators(simulator_toml: Path) -> dict[str, SimulatorEntry]:
    """Read ``simulator.toml``. A missing file means an empty dict (not yet picked)."""
    if not simulator_toml.exists():
        return {}
    data = _read_toml(simulator_toml)
    _check_version(
        data, simulator_toml,
        expected=SIMULATOR_SCHEMA_VERSION,
        recovery="sim pick",
    )
    _require_keys("<simulator.toml root>", data, _ALLOWED_SIMULATOR_TOP)
    out: dict[str, SimulatorEntry] = {}
    for label, entry in (data.get("simulators", {}) or {}).items():
        _require_keys(f"simulators.{label}", entry, _ALLOWED_SIMULATOR)
        for key in _ALLOWED_SIMULATOR:
            if key not in entry:
                raise UserError(
                    f"{simulator_toml}: [simulators.{label}] missing `{key}`."
                )
        out[label] = SimulatorEntry(
            name=entry["name"], udid=entry["udid"],
            device=entry["device"], runtime=entry["runtime"],
        )
    return out
```

Update the import block at the top of `config.py`:
```python
from .paths import derived_data_dir, simulator_toml_for, worktree_root
```

Delete the `SimulatorConfig = SimulatorEntry` alias added in Task 1 — all consumers are migrated.

- [ ] **Step 6: Replace `write_simulator(config_path, sim)` with multi-sim writers**

In `config.py`, replace the existing `write_simulator` function with:

```python
def write_simulators_toml(simulator_toml: Path, simulators: dict[str, SimulatorEntry]) -> None:
    """Render *simulators* to ``simulator.toml`` (creating the file).

    Uses tomlkit so future hand-edits keep their comments; we still rewrite
    every key the tool owns. ``schema_version`` is always set to
    :data:`SIMULATOR_SCHEMA_VERSION`.
    """
    doc = tomlkit.document()
    doc.add(tomlkit.comment("worktree-ios-dev/simulator.toml"))
    doc.add(tomlkit.comment(
        "Managed by `worktree-ios-dev-tool sim pick / recreate / remove`. "
        "Do not hand-edit udid or name."
    ))
    doc.add(tomlkit.nl())
    doc["schema_version"] = SIMULATOR_SCHEMA_VERSION

    if simulators:
        outer = tomlkit.table(is_super_table=True)
        for label, entry in simulators.items():
            inner = tomlkit.table()
            inner["name"] = entry.name
            inner["udid"] = entry.udid
            inner["device"] = entry.device
            inner["runtime"] = entry.runtime
            outer[label] = inner
        doc["simulators"] = outer

    simulator_toml.write_text(tomlkit.dumps(doc))


def upsert_simulator_entry(simulator_toml: Path, label: str, entry: SimulatorEntry) -> None:
    """Insert/replace a single ``[simulators.<label>]`` entry, preserving siblings."""
    existing = _load_simulators(simulator_toml) if simulator_toml.exists() else {}
    existing[label] = entry
    write_simulators_toml(simulator_toml, existing)


def remove_simulator_entry(simulator_toml: Path, label: str) -> bool:
    """Delete the ``[simulators.<label>]`` entry. Returns True if removed, False if absent."""
    if not simulator_toml.exists():
        return False
    existing = _load_simulators(simulator_toml)
    if label not in existing:
        return False
    del existing[label]
    write_simulators_toml(simulator_toml, existing)
    return True
```

Remove the `_ALLOWED_TOP_LEVEL` set (replaced by the two new ones) and the `require_simulator` function (Task 2 already removed callers). Drop the unused `from .paths import config_dir` import if redundant.

- [ ] **Step 7: Migrate `boot.py` and `bootstrap.py` to the new APIs**

`boot.py` `run()`:

Replace `from .paths import find_config` with `from .paths import find_project_toml, simulator_toml_for`. Replace `from .config import SimulatorEntry, load, write_simulator` with `from .config import SimulatorEntry, load, upsert_simulator_entry`.

Replace the body's path-derivation:

```python
    cfg_path = args.config.resolve() if args.config else find_project_toml()
    cfg = load(cfg_path)
    sim_toml = simulator_toml_for(cfg_path)
```

Replace `write_simulator(cfg_path, sim_cfg)` with `upsert_simulator_entry(sim_toml, "default", sim_cfg)`.

Update `sim_name` to include the `default` label segment:
```python
prefix = cfg.project.simulator_prefix
sim_name = f"{prefix}-{cfg.worktree_root.name}-default"
```

`bootstrap.py` `_write_config()`:

Add `schema_version = 1` and rename the file written from `config.toml` to `project.toml`. Update header comments:

```python
def _write_config(
    cfg_path: Path,            # absolute path to project.toml
    xcodeproj: Path,
    root: Path,
    scheme: str,
    sim_prefix: str,
    pkg_root: Path | None,
) -> None:
    import tomlkit
    doc = tomlkit.document()
    doc.add(tomlkit.comment("worktree-ios-dev/project.toml"))
    doc.add(tomlkit.comment("Generated by `worktree-ios-dev-tool proj init`."))
    doc.add(tomlkit.comment("Edit as needed. Run `worktree-ios-dev-tool sim pick` to populate simulator.toml."))
    doc.add(tomlkit.nl())
    doc["schema_version"] = 1
    # ...rest of function unchanged...
```

In `run()`:

```python
    pid = root / "worktree-ios-dev"
    cfg_path = pid / "project.toml"
```

Update the closing `ui.done(...)` and the "Next:" line:
```python
    ui.done("worktree-ios-dev/project.toml written")
    ...
    ui.done("Next: worktree-ios-dev-tool sim pick")
```

`cli.py` `_load_config()`:

```python
from .paths import find_project_toml
...
def _load_config(args: argparse.Namespace) -> config_mod.Config:
    path = args.config.resolve() if args.config else find_project_toml()
    return config_mod.load(path)
```

`runapp.py`:

```python
from .paths import find_project_toml
...
cfg_path = args.config.resolve() if args.config else find_project_toml()
```

`paths.py`: remove the now-unused `find_config` and `CONFIG_FILENAME` symbol references that any other module may have imported. Run `rg -n "find_config|CONFIG_FILENAME" worktree_ios_dev_tool/src/` from the repo root and update any hits.

- [ ] **Step 8: Update `tests/test_paths.py` for the rename**

Open `worktree_ios_dev_tool/tests/test_paths.py`. Search for `find_config`. If it tests the walk-up behavior, rename it to `find_project_toml` and adapt fixtures (`config.toml` → `project.toml` containing `schema_version = 1\n[project]\n...`). If `test_paths.py` only tests `_filesystem_type`/`derived_data_dir`/`find_worktree_root_for_bootstrap`, no changes needed.

- [ ] **Step 9: Run all tests**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run python -m unittest discover tests -v
```

Expected: existing tests + the new `test_config_schema.py` (5 tests) + `test_legacy_config_rejection.py` (1 test) all pass.

- [ ] **Step 10: Commit**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills
git add worktree_ios_dev_tool/
git commit -m "feat(config): split project.toml + simulator.toml with schema_version"
```

---

## Task 4: Add `simulator_prefix` validation + name parsing helpers

**Files:**
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/simulator.py`
- Create: `worktree_ios_dev_tool/tests/test_simulator_naming.py`

This task introduces the canonical name format (`<prefix>-<basename>-<label>`), label validation, and a parser used by `sim cleanup`/`du`/`prune` (and `sim list --global`).

- [ ] **Step 1: Write the test**

Create `worktree_ios_dev_tool/tests/test_simulator_naming.py`:

```python
"""Tests for label validation + reverse-parsing of simctl device names."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from worktree_ios_dev_tool.errors import UserError  # noqa: E402
from worktree_ios_dev_tool.simulator import (  # noqa: E402
    parse_managed_name,
    synth_managed_name,
    validate_label,
)


class ValidateLabelTests(unittest.TestCase):
    def test_accepts_alnum_underscore(self) -> None:
        validate_label("default")
        validate_label("peer_2")
        validate_label("ABC")

    def test_rejects_hyphen(self) -> None:
        with self.assertRaises(UserError):
            validate_label("with-dash")

    def test_rejects_empty(self) -> None:
        with self.assertRaises(UserError):
            validate_label("")

    def test_rejects_whitespace(self) -> None:
        with self.assertRaises(UserError):
            validate_label("ab cd")


class SynthNameTests(unittest.TestCase):
    def test_join(self) -> None:
        self.assertEqual(synth_managed_name("Pulse", "feat-auth", "default"),
                         "Pulse-feat-auth-default")


class ParseNameTests(unittest.TestCase):
    def test_simple(self) -> None:
        self.assertEqual(parse_managed_name("Pulse-main-default", prefix="Pulse"),
                         ("main", "default"))

    def test_basename_with_hyphen(self) -> None:
        self.assertEqual(parse_managed_name("Pulse-feat-auth-default", prefix="Pulse"),
                         ("feat-auth", "default"))

    def test_prefix_with_hyphen(self) -> None:
        self.assertEqual(parse_managed_name("My-App-feat-auth-peer", prefix="My-App"),
                         ("feat-auth", "peer"))

    def test_returns_none_when_prefix_mismatch(self) -> None:
        self.assertIsNone(parse_managed_name("Other-feat-default", prefix="Pulse"))

    def test_returns_none_when_no_label_segment(self) -> None:
        # exactly equal to "<prefix>-x" — only one trailing component, no
        # basename/label split possible.
        self.assertIsNone(parse_managed_name("Pulse-bare", prefix="Pulse"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run python -m unittest tests.test_simulator_naming -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement helpers in `simulator.py`**

At the top of `simulator.py` (after the existing imports), add:

```python
_LABEL_RE = re.compile(r"^[A-Za-z0-9_]+$")


def validate_label(label: str) -> None:
    """Reject labels that would break the reverse-parser.

    Labels must be non-empty and match ``[A-Za-z0-9_]+``. Hyphens are
    explicitly disallowed because the reverse-parser relies on the *last*
    hyphen to split ``<basename>-<label>``; a label containing a hyphen
    would corrupt that split when the basename also has hyphens.
    """
    if not label or not _LABEL_RE.match(label):
        raise UserError(
            f"Invalid simulator label `{label}`. Use alphanumerics and underscores only."
        )


def synth_managed_name(prefix: str, worktree_basename: str, label: str) -> str:
    """Build a simctl device name in the canonical managed format.

    Format: ``<simulator_prefix>-<worktree_basename>-<label>``. The prefix
    and basename may contain hyphens; only the trailing ``-<label>`` segment
    is reverse-parsed by :func:`parse_managed_name`.
    """
    return f"{prefix}-{worktree_basename}-{label}"


def parse_managed_name(name: str, *, prefix: str) -> tuple[str, str] | None:
    """Reverse the :func:`synth_managed_name` format.

    Returns ``(worktree_basename, label)`` if *name* matches the managed
    format under *prefix*, else ``None`` (so callers can ignore non-managed
    sims). The basename may contain hyphens; the label, by validation, may
    not — so we split on the *last* hyphen only.

    Empty basename ("Pulse-default" with prefix="Pulse" — no separator
    between basename and label) returns None: ambiguous, leave alone.
    """
    if not name.startswith(prefix + "-"):
        return None
    tail = name[len(prefix) + 1 :]
    if "-" not in tail:
        return None
    basename, _, label = tail.rpartition("-")
    if not basename or not label:
        return None
    return basename, label
```

- [ ] **Step 4: Wire `validate_label` into the existing `to_config` callsite**

`to_config` currently accepts a name verbatim. Leave it alone; the new `sim pick` will call `validate_label` + `synth_managed_name` directly. (No code change here in this task.)

- [ ] **Step 5: Run the test to verify it passes**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run python -m unittest tests.test_simulator_naming -v
```

Expected: all parsing/validation tests pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills
git add worktree_ios_dev_tool/
git commit -m "feat(simulator): add managed-name parser + label validation"
```

---

## Task 5: Add simctl device-listing/shutdown/disk-usage helpers

**Files:**
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/simulator.py`
- Create: `worktree_ios_dev_tool/tests/test_simulator_helpers.py`

Adds the low-level wrappers `sim cleanup`/`du`/`prune` need: list all devices, shutdown a device, return its data directory, compute its on-disk size.

- [ ] **Step 1: Write the test**

Create `worktree_ios_dev_tool/tests/test_simulator_helpers.py`:

```python
"""Tests for the new simctl helpers added in Task 5.

Subprocess interactions are mocked. Filesystem-size logic is exercised
directly against a temp tree.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from worktree_ios_dev_tool.simulator import (  # noqa: E402
    device_data_dir,
    du_bytes,
    list_all_devices,
    list_devices_by_prefix,
)


_FAKE_LIST = json.dumps({
    "devices": {
        "com.apple.CoreSimulator.SimRuntime.iOS-18-2": [
            {"name": "Pulse-main-default",   "udid": "AAAA", "state": "Booted"},
            {"name": "Pulse-feat-x-peer",    "udid": "BBBB", "state": "Shutdown"},
            {"name": "Other-thing",          "udid": "CCCC", "state": "Shutdown"},
        ]
    }
})


class ListDevicesTests(unittest.TestCase):
    def test_list_all_returns_flat(self) -> None:
        with patch("worktree_ios_dev_tool.simulator.run_json", return_value=_FAKE_LIST):
            devices = list_all_devices()
        self.assertEqual({d["udid"] for d in devices}, {"AAAA", "BBBB", "CCCC"})

    def test_list_by_prefix_filters_and_keeps_runtime(self) -> None:
        with patch("worktree_ios_dev_tool.simulator.run_json", return_value=_FAKE_LIST):
            devices = list_devices_by_prefix("Pulse")
        self.assertEqual({d["udid"] for d in devices}, {"AAAA", "BBBB"})


class DiskTests(unittest.TestCase):
    def test_device_data_dir_format(self) -> None:
        result = device_data_dir("ABCD-1234")
        self.assertTrue(str(result).endswith("Library/Developer/CoreSimulator/Devices/ABCD-1234"))

    def test_du_bytes_sums_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_bytes(b"x" * 100)
            (root / "sub").mkdir()
            (root / "sub" / "b.txt").write_bytes(b"y" * 250)
            self.assertGreaterEqual(du_bytes(root), 350)

    def test_du_bytes_missing_returns_zero(self) -> None:
        self.assertEqual(du_bytes(Path("/nonexistent/path/abcd")), 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run python -m unittest tests.test_simulator_helpers -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement helpers in `simulator.py`**

Append to `simulator.py`:

```python
def list_all_devices() -> list[dict]:
    """Return a flat list of device dicts from ``simctl list devices --json``.

    Each dict is the verbatim simctl entry plus an ``_runtime`` key copying
    the runtime identifier so callers can filter / display without re-parsing.
    """
    ensure_tooling()
    data = json.loads(run_json(["xcrun", "simctl", "list", "devices", "--json"]))
    out: list[dict] = []
    for runtime_id, devices in data.get("devices", {}).items():
        for dev in devices:
            d = dict(dev)
            d["_runtime"] = runtime_id
            out.append(d)
    return out


def list_devices_by_prefix(prefix: str) -> list[dict]:
    """Return all devices whose ``name`` starts with ``<prefix>-``."""
    pattern = prefix + "-"
    return [d for d in list_all_devices() if d.get("name", "").startswith(pattern)]


def shutdown(udid: str) -> None:
    """Shutdown the device. No-op if it isn't currently booted."""
    dev = find_device_by_udid(udid)
    if dev is None:
        return
    if dev.get("state") != "Booted":
        return
    run(["xcrun", "simctl", "shutdown", udid])


def device_data_dir(udid: str) -> Path:
    """Return the macOS path where simctl stores a device's disk image and state."""
    return Path.home() / "Library" / "Developer" / "CoreSimulator" / "Devices" / udid


def du_bytes(path: Path) -> int:
    """Return the recursive on-disk size of *path* in bytes.

    Returns 0 for missing paths so callers can show "0 B" rather than crash.
    Uses ``os.walk`` to avoid the cost of forking ``du(1)`` per device.
    """
    import os
    if not path.exists():
        return 0
    total = 0
    for root, _, files in os.walk(path, followlinks=False):
        for f in files:
            try:
                total += (Path(root) / f).stat().st_size
            except (FileNotFoundError, PermissionError):
                # Devices can churn while we walk; ignore transient races.
                continue
    return total
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run python -m unittest tests.test_simulator_helpers -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills
git add worktree_ios_dev_tool/
git commit -m "feat(simulator): add list_all_devices/shutdown/device_data_dir/du_bytes helpers"
```

---

## Task 6: Create `proj.py` — `proj init`, `proj config`, `proj doctor`

**Files:**
- Create: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/proj.py`
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/cli.py`
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/bootstrap.py` (delete after migration)

This task lifts `bootstrap.run`, `_cmd_config`, `_cmd_doctor` into a single new module and wires the `proj` namespace in `cli.py`. Behavior is unchanged from Task 3 except the verbs are renamed.

- [ ] **Step 1: Create `proj.py` skeleton**

Create `worktree_ios_dev_tool/src/worktree_ios_dev_tool/proj.py`:

```python
# worktree_ios_dev_tool/src/worktree_ios_dev_tool/proj.py
"""Implementations of the `proj` namespace verbs: init, config, doctor.

All three operate on ``project.toml``; ``proj init`` writes it,
``proj config`` prints the resolved view, and ``proj doctor`` runs sanity
checks. None of them touch ``simulator.toml`` (that's the ``sim`` namespace).
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from . import simulator as sim_mod, ui
from .config import Config, load
from .errors import EnvError
from .paths import find_project_toml


def _load(args: argparse.Namespace) -> Config:
    """Resolve project.toml using --config override or walk-up discovery."""
    path = args.config.resolve() if args.config else find_project_toml()
    return load(path)


def cmd_init(args: argparse.Namespace) -> int:
    """Scaffold worktree-ios-dev/, write project.toml, update .gitignore.

    Delegates to the existing :mod:`bootstrap` implementation for the
    project-discovery / scheme-discovery flow; we only own the verb name.
    """
    from . import bootstrap
    return bootstrap.run(
        project=args.project,
        scheme=args.scheme,
        yes=args.yes,
        force=args.force,
    )


def cmd_config(args: argparse.Namespace) -> int:
    """Print the resolved project + simulators view as JSON, useful for debugging."""
    cfg = _load(args)
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
        "simulators": {
            label: {
                "name": s.name, "udid": s.udid,
                "device": s.device, "runtime": s.runtime,
            } for label, s in cfg.simulators.items()
        },
        "packages_root": str(cfg.packages_root),
        "package_overrides": {k: {"scheme": v.scheme} for k, v in cfg.package_overrides.items()},
        "extras": {"xcodebuild_flags": cfg.extras_xcodebuild_flags},
    }
    print(json.dumps(payload, indent=2))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Sanity-check the worktree's project + simulators + tooling.

    Missing simulator.toml is a *warn*, not an *error* — a worktree that
    just ran ``proj init`` should still see a green doctor.
    """
    problems: list[str] = []
    cfg: Config | None = None

    try:
        cfg = _load(args)
        ui.step(f"project.toml   {cfg.config_path}")
    except EnvError as e:
        ui.problem(f"project.toml   {e}")
        problems.append(str(e))

    for binary in ("xcodebuild", "xcrun"):
        path = shutil.which(binary)
        if path is None:
            ui.problem(f"{binary:<14} not on PATH")
            problems.append(f"`{binary}` not on PATH.")
        else:
            ui.step(f"{binary:<14} {path}")

    mint_path = shutil.which("mint")
    if mint_path is None:
        ui.warn("mint           not installed (optional — enables xcbeautify)")
    else:
        ui.step(f"mint           {mint_path}")

    if cfg is not None:
        if not cfg.project.path.exists():
            ui.problem(f"project        not found: {cfg.project.path}")
            problems.append(f"project.path does not exist: {cfg.project.path}")
        else:
            ui.step(f"project        {cfg.project.path}")

        if not cfg.simulators:
            ui.warn("simulators     none configured — run `worktree-ios-dev-tool sim pick`")
        else:
            for label, sim in cfg.simulators.items():
                dev = sim_mod.find_device_by_udid(sim.udid)
                if dev is None:
                    ui.problem(f"simulators[{label}]  UDID not found: {sim.udid}")
                    problems.append(f"Simulator UDID not found in simctl list: {sim.udid}")
                else:
                    state = dev.get("state", "?")
                    ui.step(f"simulators[{label}]  {sim.name} ({sim.udid})  state={state}")

        if not cfg.derived_data.parent.exists():
            ui.problem(f"worktree-ios-dev/  missing: {cfg.derived_data.parent}")
            problems.append(f"worktree-ios-dev/ missing: {cfg.derived_data.parent}")

    ui.sep()
    if problems:
        ui.done(f"{len(problems)} problem(s) found.")
        for p in problems:
            ui.info(f"- {p}")
        return 1

    ui.done("All checks passed.")
    return 0
```

- [ ] **Step 2: Wire `proj` subparser in `cli.py`**

In `cli.py`, replace the current `bootstrap`/`config`/`doctor` registrations and the `_cmd_bootstrap`/`_cmd_config`/`_cmd_doctor` handlers with a `proj` subparser.

Inside `build_parser()`, after the current `sub = p.add_subparsers(...)` line:

```python
    proj = sub.add_parser("proj", help="Project lifecycle: init / config / doctor.")
    proj_sub = proj.add_subparsers(dest="proj_verb", required=True)

    pi = proj_sub.add_parser("init", help="Scaffold worktree-ios-dev/ and write project.toml.")
    pi.add_argument("--project", default=None, help="Relative path to .xcodeproj (skips auto-discovery).")
    pi.add_argument("--scheme", default=None, help="Scheme name (skips auto-discovery).")
    pi.add_argument("--yes", action="store_true", help="Accept all detected defaults; error if ambiguous.")
    pi.add_argument("--force", action="store_true", help="Re-write project.toml even if it already exists.")
    _add_common(pi)
    pi.set_defaults(func=lambda a: __import__(
        "worktree_ios_dev_tool.proj", fromlist=["cmd_init"]
    ).cmd_init(a))

    pc = proj_sub.add_parser("config", help="Print the resolved project + simulators view as JSON.")
    _add_common(pc)
    pc.set_defaults(func=lambda a: __import__(
        "worktree_ios_dev_tool.proj", fromlist=["cmd_config"]
    ).cmd_config(a))

    pd = proj_sub.add_parser("doctor", help="Run sanity checks on tooling, project, and simulators.")
    _add_common(pd)
    pd.set_defaults(func=lambda a: __import__(
        "worktree_ios_dev_tool.proj", fromlist=["cmd_doctor"]
    ).cmd_doctor(a))
```

Delete the old `sub.add_parser("bootstrap", ...)` block, the `for verb in ("build", "test", "run", "clean", "wipe-derived", "config", "doctor"):` loop's references to `config` and `doctor` (keep build/test/run/clean/wipe-derived only — `config` and `doctor` are now under `proj`), and the corresponding `_cmd_bootstrap`, `_cmd_config`, `_cmd_doctor` handlers and dispatch entries.

The build-verb loop should now read:
```python
    for verb in ("build", "test", "run", "clean", "wipe-derived"):
        sp = sub.add_parser(verb)
        ...
```

- [ ] **Step 3: Smoke-test `proj` from the CLI**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run worktree-ios-dev-tool proj --help
uv run worktree-ios-dev-tool proj init --help
uv run worktree-ios-dev-tool proj doctor --help
```

Expected: all three help screens render. No tracebacks.

- [ ] **Step 4: Run all tests**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run python -m unittest discover tests -v
```

Expected: existing tests pass; nothing references `_cmd_bootstrap`/`_cmd_config`/`_cmd_doctor`.

- [ ] **Step 5: Commit**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills
git add worktree_ios_dev_tool/
git commit -m "feat(proj): introduce proj namespace (init/config/doctor)"
```

---

## Task 7: Create `sim.py` — `sim pick`, `sim boot`, `sim shutdown`, `sim list`

**Files:**
- Create: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/sim.py`
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/cli.py`

This task introduces the `sim` namespace with the four core verbs. Cleanup/du/prune ship in subsequent tasks. `sim pick`/`sim boot` together replace the old `boot` verb; the old `boot` is removed in Task 12.

- [ ] **Step 1: Create `sim.py` with `pick` / `boot` / `shutdown` / `list`**

Create `worktree_ios_dev_tool/src/worktree_ios_dev_tool/sim.py`:

```python
# worktree_ios_dev_tool/src/worktree_ios_dev_tool/sim.py
"""Implementations of the `sim` namespace verbs.

Each function corresponds to one ``sim <verb>`` CLI invocation. The module
owns the policy layer (single/multi-sim resolution, name synthesis, output
formatting); :mod:`simulator` owns the simctl subprocess wrappers.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from . import simulator as sim_mod, ui
from .config import (
    Config,
    SimulatorEntry,
    load,
    remove_simulator_entry,
    resolve_sim,
    upsert_simulator_entry,
)
from .errors import UserError
from .paths import find_project_toml, simulator_toml_for


# ── shared helpers ───────────────────────────────────────────────────────────

def _load(args: argparse.Namespace) -> tuple[Config, Path]:
    """Resolve project.toml and the matching simulator.toml path."""
    path = args.config.resolve() if args.config else find_project_toml()
    return load(path), simulator_toml_for(path)


def _resolve_label(cfg: Config, label: str | None) -> str:
    """Return the label of the sim a verb without an explicit arg should target.

    Same single/multi rules as :func:`config.resolve_sim`, but returns the
    *label* rather than the entry — useful for verbs like ``shutdown`` that
    operate on the entry by label.
    """
    entry = resolve_sim(cfg, label=label)
    for k, v in cfg.simulators.items():
        if v is entry:
            return k
    raise AssertionError("resolve_sim returned an entry not in cfg.simulators")


# ── verbs ────────────────────────────────────────────────────────────────────

def cmd_pick(args: argparse.Namespace) -> int:
    """Interactively pick + create a simulator and write it to simulator.toml.

    Errors if an entry with that label already exists; the user must call
    ``sim recreate <label>`` to replace one.
    """
    cfg, sim_toml = _load(args)
    label = args.label or "default"
    sim_mod.validate_label(label)

    if label in cfg.simulators:
        raise UserError(
            f"A simulator labeled `{label}` already exists. "
            f"Use `worktree-ios-dev-tool sim recreate {label}` to replace it."
        )

    sim_mod.ensure_tooling()

    device, runtime = sim_mod.pick_device_and_runtime(iphone_17_only=not args.all_devices)
    name = sim_mod.synth_managed_name(
        cfg.project.simulator_prefix, cfg.worktree_root.name, label,
    )

    existing = sim_mod.find_device_by_name(name)
    if existing is not None:
        ui.warn(f"Simulator named '{name}' already exists (udid={existing['udid']}).")
        choice = input("Reuse it? [Y/n] ").strip().lower() if ui.is_interactive() else "y"
        if choice in ("", "y", "yes"):
            udid = existing["udid"]
        else:
            raise UserError(
                "Aborted. Delete the existing sim manually or use "
                f"`sim recreate {label}` next time."
            )
    else:
        ui.step(f"Creating {name}…")
        udid = sim_mod.create(name, device, runtime)

    entry = SimulatorEntry(name=name, udid=udid, device=device.name, runtime=runtime.name)
    upsert_simulator_entry(sim_toml, label, entry)
    sim_mod.boot(udid)

    ui.sep()
    ui.done(f"Simulator ready  [{label}]")
    ui.info(f"name    = {entry.name}")
    ui.info(f"udid    = {entry.udid}")
    ui.info(f"device  = {entry.device}")
    ui.info(f"runtime = {entry.runtime}")
    return 0


def cmd_boot(args: argparse.Namespace) -> int:
    """Boot a configured simulator. ``--all`` boots every entry."""
    cfg, _ = _load(args)
    if args.all:
        if not cfg.simulators:
            raise UserError("No simulators configured. Run `sim pick` first.")
        for label, entry in cfg.simulators.items():
            ui.step(f"Booting {label} ({entry.udid})…")
            sim_mod.boot(entry.udid)
        ui.done(f"Booted {len(cfg.simulators)} simulator(s).")
        return 0

    entry = resolve_sim(cfg, label=args.label)
    sim_mod.boot(entry.udid)
    ui.done(f"Booted {entry.name} ({entry.udid}).")
    return 0


def cmd_shutdown(args: argparse.Namespace) -> int:
    """Shutdown a configured simulator. ``--all`` shuts down every entry."""
    cfg, _ = _load(args)
    if args.all:
        if not cfg.simulators:
            ui.done("No simulators configured.")
            return 0
        for label, entry in cfg.simulators.items():
            ui.step(f"Shutdown {label} ({entry.udid})…")
            sim_mod.shutdown(entry.udid)
        ui.done(f"Shut down {len(cfg.simulators)} simulator(s).")
        return 0

    entry = resolve_sim(cfg, label=args.label)
    sim_mod.shutdown(entry.udid)
    ui.done(f"Shut down {entry.name} ({entry.udid}).")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List configured simulators (default: this worktree; ``--global`` for all).

    Local mode uses ``simulator.toml`` as truth and consults simctl for state.
    Global mode scans simctl for ``<simulator_prefix>-*`` and groups by the
    parsed worktree-basename segment of each device name.
    """
    cfg, _ = _load(args)
    if args.global_:
        prefix = cfg.project.simulator_prefix
        groups: dict[str, list[dict]] = defaultdict(list)
        for dev in sim_mod.list_devices_by_prefix(prefix):
            parsed = sim_mod.parse_managed_name(dev["name"], prefix=prefix)
            if parsed is None:
                continue
            basename, _label = parsed
            groups[basename].append(dev)
        if not groups:
            ui.done(f"No managed simulators found (prefix: {prefix}).")
            return 0
        for basename in sorted(groups):
            ui.info(f"worktree={basename}")
            for dev in sorted(groups[basename], key=lambda d: d["name"]):
                state = dev.get("state", "?")
                ui.info(f"  {dev['name']:<40} {dev['udid']}  state={state}")
        return 0

    if not cfg.simulators:
        ui.done("No simulators configured. Run `sim pick`.")
        return 0
    for label, entry in cfg.simulators.items():
        dev = sim_mod.find_device_by_udid(entry.udid)
        state = dev.get("state", "?") if dev else "MISSING"
        ui.info(f"{label:<10} {entry.name:<40} {entry.udid}  state={state}")
    return 0
```

- [ ] **Step 2: Wire `sim` subparser in `cli.py`**

In `cli.py` after the `proj` subparser block, add:

```python
    sim_p = sub.add_parser("sim", help="Simulator lifecycle: pick / boot / shutdown / list / ...")
    sim_sub = sim_p.add_subparsers(dest="sim_verb", required=True)

    spk = sim_sub.add_parser("pick", help="Interactively pick + create a simulator.")
    spk.add_argument("label", nargs="?", default=None,
                     help="Label under which to register the sim. Defaults to `default`.")
    spk.add_argument("--all-devices", action="store_true",
                     help="Disable the iPhone 17 filter when picking.")
    _add_common(spk)
    spk.set_defaults(func=lambda a: __import__(
        "worktree_ios_dev_tool.sim", fromlist=["cmd_pick"]
    ).cmd_pick(a))

    sbt = sim_sub.add_parser("boot", help="Boot a configured simulator.")
    sbt.add_argument("label", nargs="?", default=None,
                     help="Sim label to boot. Single-sim setups can omit; multi-sim must pass --all or a label.")
    sbt.add_argument("--all", action="store_true", help="Boot every configured simulator.")
    _add_common(sbt)
    sbt.set_defaults(func=lambda a: __import__(
        "worktree_ios_dev_tool.sim", fromlist=["cmd_boot"]
    ).cmd_boot(a))

    ssh = sim_sub.add_parser("shutdown", help="Shutdown a configured simulator.")
    ssh.add_argument("label", nargs="?", default=None, help="Sim label to shut down.")
    ssh.add_argument("--all", action="store_true", help="Shutdown every configured simulator.")
    _add_common(ssh)
    ssh.set_defaults(func=lambda a: __import__(
        "worktree_ios_dev_tool.sim", fromlist=["cmd_shutdown"]
    ).cmd_shutdown(a))

    sls = sim_sub.add_parser("list", help="List configured simulators (or all managed sims with --global).")
    sls.add_argument("--global", dest="global_", action="store_true",
                     help="Scan simctl for every <simulator_prefix>-* device, grouped by worktree.")
    _add_common(sls)
    sls.set_defaults(func=lambda a: __import__(
        "worktree_ios_dev_tool.sim", fromlist=["cmd_list"]
    ).cmd_list(a))
```

- [ ] **Step 3: Smoke-test `sim` from the CLI**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run worktree-ios-dev-tool sim --help
uv run worktree-ios-dev-tool sim pick --help
uv run worktree-ios-dev-tool sim boot --help
uv run worktree-ios-dev-tool sim list --help
```

Expected: all four help screens render.

- [ ] **Step 4: Run all tests**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run python -m unittest discover tests -v
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills
git add worktree_ios_dev_tool/
git commit -m "feat(sim): introduce sim namespace (pick/boot/shutdown/list)"
```

---

## Task 8: Implement `sim recreate` and `sim remove`

**Files:**
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/sim.py`
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/cli.py`

`sim recreate <label>` is destructive (delete sim + re-pick). `sim remove <label>` is non-destructive by default; `--destroy` adds simctl deletion.

- [ ] **Step 1: Implement `cmd_recreate` and `cmd_remove` in `sim.py`**

Append to `sim.py`:

```python
def cmd_recreate(args: argparse.Namespace) -> int:
    """Destroy + re-pick + re-boot the simulator under *label*.

    Always requires an explicit label — destructive operations should not
    silently default. Removes the simctl device, deletes the entry from
    ``simulator.toml``, then re-runs the pick flow.
    """
    sim_mod.validate_label(args.label)
    cfg, sim_toml = _load(args)

    existing = cfg.simulators.get(args.label)
    if existing is not None:
        dev = sim_mod.find_device_by_udid(existing.udid)
        if dev is not None:
            ui.step(f"Deleting {existing.name} ({existing.udid})…")
            sim_mod.shutdown(existing.udid)
            sim_mod.delete(existing.udid)
        remove_simulator_entry(sim_toml, args.label)

    # Reuse cmd_pick by synthesising a fake namespace.
    pick_args = argparse.Namespace(
        config=args.config, verbose=args.verbose,
        label=args.label, all_devices=args.all_devices,
    )
    return cmd_pick(pick_args)


def cmd_remove(args: argparse.Namespace) -> int:
    """Remove the entry under *label* from simulator.toml.

    Default: leave the simctl device alone (the user may want to re-register
    it under a different label). ``--destroy`` shuts down + deletes the
    device too, matching ``sim recreate``'s teardown half.
    """
    sim_mod.validate_label(args.label)
    cfg, sim_toml = _load(args)
    entry = cfg.simulators.get(args.label)
    if entry is None:
        raise UserError(f"No simulator labeled `{args.label}`.")

    if args.destroy:
        sim_mod.shutdown(entry.udid)
        sim_mod.delete(entry.udid)
        ui.step(f"Deleted simctl device {entry.name} ({entry.udid}).")

    remove_simulator_entry(sim_toml, args.label)
    ui.done(f"Removed `{args.label}` from simulator.toml.")
    return 0
```

- [ ] **Step 2: Wire two more subparsers in `cli.py`**

After the `sim list` block, append inside `build_parser`:

```python
    src = sim_sub.add_parser("recreate", help="Destroy + re-pick the named simulator.")
    src.add_argument("label", help="Sim label to recreate (required; destructive).")
    src.add_argument("--all-devices", action="store_true",
                     help="Disable the iPhone 17 filter when picking.")
    _add_common(src)
    src.set_defaults(func=lambda a: __import__(
        "worktree_ios_dev_tool.sim", fromlist=["cmd_recreate"]
    ).cmd_recreate(a))

    srm = sim_sub.add_parser("remove", help="Remove a simulator entry from simulator.toml.")
    srm.add_argument("label", help="Sim label to remove.")
    srm.add_argument("--destroy", action="store_true",
                     help="Also delete the simctl device, not just the toml entry.")
    _add_common(srm)
    srm.set_defaults(func=lambda a: __import__(
        "worktree_ios_dev_tool.sim", fromlist=["cmd_remove"]
    ).cmd_remove(a))
```

- [ ] **Step 3: Smoke-test help**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run worktree-ios-dev-tool sim recreate --help
uv run worktree-ios-dev-tool sim remove --help
```

Expected: both help screens render.

- [ ] **Step 4: Run all tests**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run python -m unittest discover tests -v
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills
git add worktree_ios_dev_tool/
git commit -m "feat(sim): add recreate + remove subverbs"
```

---

## Task 9: Implement `sim cleanup`

**Files:**
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/sim.py`
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/cli.py`
- Create: `worktree_ios_dev_tool/tests/test_sim_cleanup.py`

`sim cleanup` is "this worktree is done": shutdown + delete every device whose name matches `<prefix>-<this_worktree_basename>-*`, then delete `simulator.toml`. Tested with mocked simctl.

- [ ] **Step 1: Write the test**

Create `worktree_ios_dev_tool/tests/test_sim_cleanup.py`:

```python
"""Tests for the prefix-scan logic that drives ``sim cleanup``.

We don't drive the verb end-to-end (it depends on argparse + ui + the full
config); we test the pure helper :func:`sim.match_for_cleanup` which the
verb delegates to. That gives the verb body a thin shell over a tested
filter.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from worktree_ios_dev_tool.sim import match_for_cleanup  # noqa: E402


_FAKE = [
    {"name": "Pulse-feat-auth-default", "udid": "AAAA"},
    {"name": "Pulse-feat-auth-peer",    "udid": "BBBB"},
    {"name": "Pulse-main-default",      "udid": "CCCC"},
    {"name": "Pulse-feat-auth-extras",  "udid": "DDDD"},  # also matches
    {"name": "Other-feat-auth-default", "udid": "EEEE"},  # different prefix
    {"name": "Pulse-feat-auth",         "udid": "FFFF"},  # no label segment
]


class MatchForCleanupTests(unittest.TestCase):
    def test_matches_all_label_variants_for_basename(self) -> None:
        result = match_for_cleanup(_FAKE, prefix="Pulse", basename="feat-auth")
        names = {d["name"] for d in result}
        self.assertEqual(names, {
            "Pulse-feat-auth-default",
            "Pulse-feat-auth-peer",
            "Pulse-feat-auth-extras",
        })

    def test_excludes_other_basenames(self) -> None:
        result = match_for_cleanup(_FAKE, prefix="Pulse", basename="main")
        names = {d["name"] for d in result}
        self.assertEqual(names, {"Pulse-main-default"})

    def test_excludes_other_prefix(self) -> None:
        result = match_for_cleanup(_FAKE, prefix="Other", basename="feat-auth")
        names = {d["name"] for d in result}
        self.assertEqual(names, {"Other-feat-auth-default"})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run python -m unittest tests.test_sim_cleanup -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement `match_for_cleanup` and `cmd_cleanup` in `sim.py`**

Append to `sim.py`:

```python
def match_for_cleanup(devices: list[dict], *, prefix: str, basename: str) -> list[dict]:
    """Filter *devices* to those whose name starts with ``<prefix>-<basename>-``.

    Pure function so we can unit-test the prefix-scan logic without simctl.
    The trailing dash is required to distinguish ``Pulse-feat-auth-*`` from
    ``Pulse-feat-auth-extras-*`` if a future basename were a prefix of another.
    """
    needle = f"{prefix}-{basename}-"
    return [d for d in devices if d.get("name", "").startswith(needle)]


def cmd_cleanup(args: argparse.Namespace) -> int:
    """Decommission every simulator owned by this worktree.

    Algorithm:
      1. Scan simctl for all devices.
      2. Filter to ``<simulator_prefix>-<worktree_basename>-*`` (prefix-only;
         we do not consult ``simulator.toml`` so a corrupt/missing file is
         survivable).
      3. Confirm with the user (skipped under ``--yes``).
      4. Shutdown + delete each.
      5. Delete ``simulator.toml`` if present.
    """
    cfg, sim_toml = _load(args)
    prefix = cfg.project.simulator_prefix
    basename = cfg.worktree_root.name

    devices = sim_mod.list_all_devices()
    matched = match_for_cleanup(devices, prefix=prefix, basename=basename)
    if not matched:
        ui.done(f"No managed simulators found for worktree `{basename}`.")
        if sim_toml.exists():
            sim_toml.unlink()
            ui.info(f"Removed stale {sim_toml}.")
        return 0

    ui.info(f"Will shutdown + delete {len(matched)} simulator(s):")
    for d in matched:
        ui.info(f"  {d['name']}  ({d['udid']})")
    if not args.yes:
        if not ui.is_interactive():
            raise UserError(
                "`sim cleanup` requires --yes when stdin is not a TTY."
            )
        resp = input("Proceed? [y/N] ").strip().lower()
        if resp not in ("y", "yes"):
            ui.done("Aborted.")
            return 1

    for d in matched:
        sim_mod.shutdown(d["udid"])
        sim_mod.delete(d["udid"])
    if sim_toml.exists():
        sim_toml.unlink()
    ui.done(f"Cleaned up {len(matched)} simulator(s) for worktree `{basename}`.")
    return 0
```

- [ ] **Step 4: Wire `sim cleanup` subparser in `cli.py`**

After `sim remove`:

```python
    scl = sim_sub.add_parser("cleanup", help="Tear down all simulators owned by this worktree.")
    scl.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    _add_common(scl)
    scl.set_defaults(func=lambda a: __import__(
        "worktree_ios_dev_tool.sim", fromlist=["cmd_cleanup"]
    ).cmd_cleanup(a))
```

- [ ] **Step 5: Run all tests**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run python -m unittest discover tests -v
```

Expected: 3 cleanup tests pass alongside everything else.

- [ ] **Step 6: Commit**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills
git add worktree_ios_dev_tool/
git commit -m "feat(sim): add cleanup subverb (per-worktree teardown)"
```

---

## Task 10: Implement `sim du`

**Files:**
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/sim.py`
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/cli.py`

Scans every `<prefix>-*` simctl device, computes its on-disk size, prints results grouped by parsed worktree-basename. `--this-worktree` restricts output to the current basename.

- [ ] **Step 1: Implement `cmd_du`**

Append to `sim.py`:

```python
def _format_bytes(n: int) -> str:
    """Render a byte count as a power-of-1024 string with one decimal."""
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    size = float(n)
    for unit in units:
        if size < 1024:
            return f"{size:5.1f} {unit}"
        size /= 1024
    return f"{size:5.1f} PiB"


def cmd_du(args: argparse.Namespace) -> int:
    """Report disk usage for every managed simulator.

    Default: scan globally; ``--this-worktree`` filters to the current basename.
    Output is grouped by parsed worktree-basename, sorted alphabetically.
    """
    cfg, _ = _load(args)
    prefix = cfg.project.simulator_prefix
    devices = sim_mod.list_devices_by_prefix(prefix)

    rows: list[tuple[str, str, str, int]] = []  # (basename, label, name, bytes)
    for dev in devices:
        parsed = sim_mod.parse_managed_name(dev["name"], prefix=prefix)
        if parsed is None:
            continue
        basename, label = parsed
        if args.this_worktree and basename != cfg.worktree_root.name:
            continue
        size = sim_mod.du_bytes(sim_mod.device_data_dir(dev["udid"]))
        rows.append((basename, label, dev["name"], size))

    if not rows:
        scope = "this worktree" if args.this_worktree else f"prefix {prefix!r}"
        ui.done(f"No managed simulators found for {scope}.")
        return 0

    rows.sort()
    grouped: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
    total = 0
    for basename, label, name, size in rows:
        grouped[basename].append((label, name, size))
        total += size

    ui.info(f"{cfg.project.simulator_prefix} simulators (prefix={prefix}):")
    ui.sep()
    for basename in sorted(grouped):
        ui.info(f"worktree={basename}")
        for label, name, size in sorted(grouped[basename]):
            ui.info(f"  {label:<10} {name:<40} {_format_bytes(size)}")
    ui.sep()
    ui.done(f"Total: {_format_bytes(total)} across {len(rows)} simulator(s).")
    return 0
```

- [ ] **Step 2: Wire subparser in `cli.py`**

After `sim cleanup`:

```python
    sdu = sim_sub.add_parser("du", help="Report disk usage of every managed simulator.")
    sdu.add_argument("--this-worktree", action="store_true",
                     help="Restrict scan to this worktree's simulators.")
    _add_common(sdu)
    sdu.set_defaults(func=lambda a: __import__(
        "worktree_ios_dev_tool.sim", fromlist=["cmd_du"]
    ).cmd_du(a))
```

- [ ] **Step 3: Smoke-test help**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run worktree-ios-dev-tool sim du --help
```

Expected: help renders.

- [ ] **Step 4: Run all tests**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run python -m unittest discover tests -v
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills
git add worktree_ios_dev_tool/
git commit -m "feat(sim): add du subverb (managed-sim disk usage report)"
```

---

## Task 11: Implement `sim prune`

**Files:**
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/sim.py`
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/cli.py`
- Create: `worktree_ios_dev_tool/tests/test_sim_prune.py`

Detects orphaned managed sims by parsing each device's basename segment and comparing against `git worktree list`. Tested via a pure helper that takes both lists.

- [ ] **Step 1: Write the test**

Create `worktree_ios_dev_tool/tests/test_sim_prune.py`:

```python
"""Tests for the orphan-detection helper that drives ``sim prune``."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from worktree_ios_dev_tool.sim import find_orphans  # noqa: E402


_DEVICES = [
    {"name": "Pulse-main-default",     "udid": "AAAA"},
    {"name": "Pulse-feat-auth-peer",   "udid": "BBBB"},
    {"name": "Pulse-old-branch-default", "udid": "CCCC"},   # orphan
    {"name": "Other-thing-default",    "udid": "DDDD"},     # not managed
    {"name": "Pulse-malformed",        "udid": "EEEE"},     # no label segment
]


class FindOrphansTests(unittest.TestCase):
    def test_basenames_in_set_are_not_orphans(self) -> None:
        live = {"main", "feat-auth"}
        orphans = find_orphans(_DEVICES, prefix="Pulse", live_basenames=live)
        names = {d["name"] for d, _, _ in orphans}
        self.assertEqual(names, {"Pulse-old-branch-default"})

    def test_empty_live_set_makes_everything_orphan(self) -> None:
        orphans = find_orphans(_DEVICES, prefix="Pulse", live_basenames=set())
        names = {d["name"] for d, _, _ in orphans}
        self.assertEqual(names, {
            "Pulse-main-default",
            "Pulse-feat-auth-peer",
            "Pulse-old-branch-default",
        })

    def test_returns_basename_and_label_alongside_device(self) -> None:
        orphans = find_orphans(_DEVICES, prefix="Pulse", live_basenames=set())
        as_map = {d["name"]: (b, l) for d, b, l in orphans}
        self.assertEqual(as_map["Pulse-feat-auth-peer"], ("feat-auth", "peer"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run python -m unittest tests.test_sim_prune -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement `find_orphans`, `git_worktree_basenames`, `cmd_prune` in `sim.py`**

Append:

```python
def find_orphans(
    devices: list[dict], *, prefix: str, live_basenames: set[str],
) -> list[tuple[dict, str, str]]:
    """Return ``[(device, basename, label), ...]`` for every managed device
    whose worktree-basename segment is *not* in *live_basenames*.

    Pure function — gets all simctl/git work injected — so we can unit-test
    orphan detection without forking either tool.
    """
    out: list[tuple[dict, str, str]] = []
    for dev in devices:
        parsed = sim_mod.parse_managed_name(dev.get("name", ""), prefix=prefix)
        if parsed is None:
            continue
        basename, label = parsed
        if basename not in live_basenames:
            out.append((dev, basename, label))
    return out


def git_worktree_basenames(start: Path) -> set[str]:
    """Run ``git worktree list --porcelain`` from *start* and return basenames.

    A worktree's "basename" is ``Path(<worktree path>).name`` — that's the
    same string we encode into simulator names, so it's the right key for
    the orphan check.
    """
    import subprocess
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=start, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise UserError(
            "`sim prune` must be run from inside a git worktree of the project repo. "
            f"`git worktree list` failed: {result.stderr.strip()}"
        )
    basenames: set[str] = set()
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            basenames.add(Path(line[len("worktree "):]).name)
    return basenames


def cmd_prune(args: argparse.Namespace) -> int:
    """Detect + remove orphaned managed simulators (worktrees that no longer exist).

    Combines a global simctl scan with ``git worktree list`` to find any
    managed device whose basename segment is missing from the live worktrees.
    Interactive confirmation by default; ``--yes`` skips it.
    """
    cfg, _ = _load(args)
    prefix = cfg.project.simulator_prefix
    devices = sim_mod.list_devices_by_prefix(prefix)
    live = git_worktree_basenames(cfg.worktree_root)

    orphans = find_orphans(devices, prefix=prefix, live_basenames=live)
    if not orphans:
        ui.done("No orphaned simulators.")
        return 0

    by_basename: dict[str, list[tuple[dict, str]]] = defaultdict(list)
    for dev, basename, label in orphans:
        by_basename[basename].append((dev, label))

    ui.info(f"Found {len(orphans)} orphaned simulator(s):")
    for basename in sorted(by_basename):
        ui.info(f"  worktree={basename} (gone)")
        for dev, label in sorted(by_basename[basename], key=lambda t: t[1]):
            ui.info(f"    {dev['name']:<40} {dev['udid']}  label={label}")

    if not args.yes:
        if not ui.is_interactive():
            raise UserError("`sim prune` requires --yes when stdin is not a TTY.")
        resp = input("Delete these simulators? [y/N] ").strip().lower()
        if resp not in ("y", "yes"):
            ui.done("Aborted.")
            return 1

    for dev, _b, _l in orphans:
        sim_mod.shutdown(dev["udid"])
        sim_mod.delete(dev["udid"])
    ui.done(f"Pruned {len(orphans)} orphaned simulator(s).")
    return 0
```

- [ ] **Step 4: Wire subparser**

After `sim du` in `cli.py`:

```python
    spr = sim_sub.add_parser("prune", help="Find + delete simulators whose worktrees no longer exist.")
    spr.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    _add_common(spr)
    spr.set_defaults(func=lambda a: __import__(
        "worktree_ios_dev_tool.sim", fromlist=["cmd_prune"]
    ).cmd_prune(a))
```

- [ ] **Step 5: Run all tests**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run python -m unittest discover tests -v
```

Expected: 3 prune tests pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills
git add worktree_ios_dev_tool/
git commit -m "feat(sim): add prune subverb (orphan detection via git worktree list)"
```

---

## Task 12: Add `--sim <label>` to build verbs and remove old `bootstrap`/`boot` verbs

**Files:**
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/cli.py`
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/xcodebuild.py`
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/runapp.py`
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/packages.py`
- Delete: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/boot.py`
- Modify (delete legacy verb wiring): `worktree_ios_dev_tool/src/worktree_ios_dev_tool/bootstrap.py` keeps the `run()` helper but is no longer registered as a top-level verb.

`build`, `test`, `run`, `test-package` gain `--sim <label>`. `clean` and `wipe-derived` don't need a sim. The legacy `boot` and `bootstrap` verbs are removed; `bootstrap.py` is kept because `proj init` still imports `bootstrap.run`.

- [ ] **Step 1: Plumb `label` through `xcodebuild.py`**

In `xcodebuild.py`, replace `build_argv` and `test_argv` to take an optional label:

```python
def build_argv(
    cfg: Config, *,
    release: bool = False,
    scheme_override: str | None = None,
    sim_label: str | None = None,
) -> list[str]:
    """Build argv for ``xcodebuild build``. *sim_label* selects which entry
    in ``cfg.simulators`` provides the destination."""
    sim = resolve_sim(cfg, label=sim_label)
    argv = _common(cfg, sim, release=release)
    if scheme_override:
        argv[argv.index("-scheme") + 1] = scheme_override
    return argv + ["build"]


def test_argv(
    cfg: Config, *,
    release: bool = False,
    scheme_override: str | None = None,
    only_testing: Sequence[str] = (),
    skip_testing: Sequence[str] = (),
    sim_label: str | None = None,
) -> list[str]:
    sim = resolve_sim(cfg, label=sim_label)
    argv = _common(cfg, sim, release=release) + ["test"]
    if scheme_override:
        argv[argv.index("-scheme") + 1] = scheme_override
    for t in only_testing:
        argv += ["-only-testing", t]
    for t in skip_testing:
        argv += ["-skip-testing", t]
    return argv
```

- [ ] **Step 2: Plumb `label` through `runapp.py`**

In `runapp.py` `run()`:

```python
sim = resolve_sim(cfg, label=getattr(args, "sim", None))
...
argv = xcodebuild.build_argv(cfg, release=args.release, sim_label=getattr(args, "sim", None))
```

- [ ] **Step 3: Plumb `label` through `packages.py`**

```python
def resolve(cfg: Config, package_name: str, *, sim_label: str | None = None) -> tuple[list[str], Path]:
    ...
    sim = resolve_sim(cfg, label=sim_label)
    ...
```

- [ ] **Step 4: Update build-verb dispatch in `cli.py`**

Replace the build-verb argparse loop with explicit per-verb registration so each can declare `--sim`:

```python
    b = sub.add_parser("build", help="xcodebuild build the main scheme.")
    b.add_argument("--release", action="store_true", help="Use Release configuration.")
    b.add_argument("--scheme", default=None, help="Override project.scheme.")
    b.add_argument("--sim", default=None, help="Sim label when multiple are configured.")
    _add_common(b)
    b.set_defaults(func=_cmd_build)

    t = sub.add_parser("test", help="xcodebuild test the main scheme.")
    t.add_argument("--release", action="store_true", help="Use Release configuration.")
    t.add_argument("--scheme", default=None, help="Override project.scheme.")
    t.add_argument("--only-testing", action="append", default=[], metavar="TEST_ID")
    t.add_argument("--skip-testing", action="append", default=[], metavar="TEST_ID")
    t.add_argument("--sim", default=None, help="Sim label when multiple are configured.")
    _add_common(t)
    t.set_defaults(func=_cmd_test)

    rn = sub.add_parser("run", help="Build, install on the simulator, launch.")
    rn.add_argument("--release", action="store_true", help="Use Release configuration.")
    rn.add_argument("--sim", default=None, help="Sim label when multiple are configured.")
    _add_common(rn)
    rn.set_defaults(func=_cmd_run)

    cl = sub.add_parser("clean", help="xcodebuild clean.")
    _add_common(cl)
    cl.set_defaults(func=_cmd_clean)

    wd = sub.add_parser("wipe-derived", help="rm -rf the DerivedData dir.")
    wd.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    _add_common(wd)
    wd.set_defaults(func=_cmd_wipe_derived)

    tp = sub.add_parser("test-package", help="Run a local Swift package's tests.")
    tp.add_argument("name", help="Directory / scheme name under packages_root.")
    tp.add_argument("--sim", default=None, help="Sim label when multiple are configured.")
    _add_common(tp)
    tp.set_defaults(func=_cmd_test_package)
```

Update the matching handlers:

```python
def _cmd_build(args: argparse.Namespace) -> int:
    cfg = _load_config(args)
    scheme = args.scheme or cfg.project.scheme
    config = "Release" if args.release else cfg.project.configuration
    ui.step(f"Building {scheme} ({config})…")
    argv = xcodebuild.build_argv(
        cfg, release=args.release, scheme_override=args.scheme, sim_label=args.sim,
    )
    run(argv, verbose=args.verbose)
    ui.done("Build succeeded.")
    return 0


def _cmd_test(args: argparse.Namespace) -> int:
    cfg = _load_config(args)
    scheme = args.scheme or cfg.project.scheme
    config = "Release" if args.release else cfg.project.configuration
    ui.step(f"Testing {scheme} ({config})…")
    argv = xcodebuild.test_argv(
        cfg, release=args.release, scheme_override=args.scheme,
        only_testing=args.only_testing, skip_testing=args.skip_testing,
        sim_label=args.sim,
    )
    run(argv, verbose=args.verbose)
    ui.done("Tests passed.")
    return 0


def _cmd_test_package(args: argparse.Namespace) -> int:
    cfg = _load_config(args)
    ui.step(f"Testing package {args.name}…")
    argv, cwd = packages_mod.resolve(cfg, args.name, sim_label=args.sim)
    run(argv, cwd=cwd, verbose=args.verbose)
    ui.done(f"Tests passed — {args.name}.")
    return 0
```

- [ ] **Step 5: Delete legacy `bootstrap` / `boot` registrations**

In `cli.py`, remove the `sub.add_parser("bootstrap", ...)` block + its `_cmd_bootstrap` entry, and the `sub.add_parser("boot", ...)` block + its `_cmd_boot` entry. The `from .boot import run as boot_run` and `from .runapp import run as run_run` imports inside the legacy handlers can be deleted along with the handlers; the new `_cmd_run` keeps its lazy import.

`_cmd_run` after cleanup:
```python
def _cmd_run(args: argparse.Namespace) -> int:
    from .runapp import run as run_run
    return run_run(args)
```

- [ ] **Step 6: Delete `boot.py`**

```bash
rm /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool/src/worktree_ios_dev_tool/boot.py
```

- [ ] **Step 7: Smoke-test the CLI surface**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run worktree-ios-dev-tool --help
uv run worktree-ios-dev-tool build --help
uv run worktree-ios-dev-tool test --help
uv run worktree-ios-dev-tool run --help
```

Expected: top-level help shows `proj`, `sim`, `build`, `test`, `run`, `clean`, `wipe-derived`, `test-package`. No `bootstrap`/`boot`/`config`/`doctor` at top level.

Try the removed verbs and confirm they're rejected:
```bash
uv run worktree-ios-dev-tool bootstrap --help
```
Expected: argparse error: `invalid choice: 'bootstrap'`.

- [ ] **Step 8: Run all tests**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run python -m unittest discover tests -v
```

Expected: green.

- [ ] **Step 9: Commit**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills
git add worktree_ios_dev_tool/
git commit -m "feat(cli): add --sim flag to build verbs; drop legacy bootstrap/boot verbs"
```

---

## Task 13: Rename `--config` → `--project-toml`

**Files:**
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/cli.py`
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/proj.py`
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/sim.py`
- Modify: `worktree_ios_dev_tool/src/worktree_ios_dev_tool/runapp.py`

The flag points at `project.toml` now; the simulator file is derived. Renaming makes the semantics explicit.

- [ ] **Step 1: Rename in `_add_common`**

In `cli.py`:
```python
def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project-toml", dest="config", type=Path, default=None,
        help="Path to project.toml (overrides walk-up discovery). simulator.toml is resolved alongside it.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Stream subprocess output and show tracebacks.",
    )
```

Keep the namespace attribute as `config` (it's read everywhere as `args.config`), so call sites don't change.

- [ ] **Step 2: Smoke-test help text**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run worktree-ios-dev-tool proj doctor --help
```

Expected: help shows `--project-toml` instead of `--config`.

- [ ] **Step 3: Run tests**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run python -m unittest discover tests -v
```

Expected: green.

- [ ] **Step 4: Commit**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills
git add worktree_ios_dev_tool/
git commit -m "refactor(cli): rename --config to --project-toml"
```

---

## Task 14: Update SKILL.md

**Files:**
- Modify: `skills/worktree-ios-dev/SKILL.md`

Rewrite the verb table, decision flow, and "common mistakes" section to match the new namespaces and capabilities.

- [ ] **Step 1: Replace the SKILL.md content**

Open `skills/worktree-ios-dev/SKILL.md` and replace its body (keep the frontmatter `name`/`description` lines intact) with:

```markdown
# Worktree iOS Dev

Use `worktree-ios-dev-tool` for every non-interactive iOS build task. Keep `xcodebuildmcp-cli` for debugging, UI automation, and log streaming.

## Decision

- **Build / test / run / clean / package test / wipe derived data** → `worktree-ios-dev-tool <verb>` (top-level).
- **Project lifecycle (init, inspect config, doctor)** → `worktree-ios-dev-tool proj <verb>`.
- **Simulator lifecycle (pick, boot, shutdown, list, recreate, remove, cleanup, du, prune)** → `worktree-ios-dev-tool sim <verb>`.
- **Debug sessions, breakpoints, log streaming, UI automation (tap / swipe / screenshot), archive, export IPA, TestFlight** → `xcodebuildmcp-cli` skill.
- **Never** use `swift test` for Pulse packages.

## One-time machine setup

```bash
uv tool install --editable /abs/path/to/pulse-dev-skills/worktree_ios_dev_tool
```

Requires `uv` on `PATH` and `~/.local/bin` on `PATH`.

Upgrade with `uv tool upgrade worktree-ios-dev-tool`. Editable installs pick up Python source edits automatically.

Optional: `brew install mint` enables `xcbeautify` for prettier `xcodebuild` output. The tool auto-detects `mint` on `PATH`; without it, builds still work but emit a one-line stderr note suggesting the install. `worktree-ios-dev-tool proj doctor` reports mint status.

## Per-worktree setup

From anywhere inside the worktree:

```bash
worktree-ios-dev-tool proj init     # creates worktree-ios-dev/, seeds project.toml, updates .gitignore
worktree-ios-dev-tool sim pick      # first run: interactive picker; writes [simulators.default] to simulator.toml
```

For peer-to-peer scenarios that need a second sim:

```bash
worktree-ios-dev-tool sim pick peer
worktree-ios-dev-tool run --sim peer
```

## Agent (non-interactive) usage

When stdin is not a TTY the tool switches automatically to flat `[worktree-ios-dev-tool] <msg>` output. For `proj init`, supply `--project` and `--scheme` explicitly and add `--yes` to suppress prompts:

```bash
worktree-ios-dev-tool proj init \
  --project ios/Pulse.xcodeproj \
  --scheme Pulse \
  --yes
```

`sim pick` picks the simulator non-interactively when stdin is not a TTY; pass `--all-devices` if the default iPhone 17 Pro filter is too narrow. `sim cleanup` and `sim prune` require `--yes` outside a TTY.

## Verb reference

### `proj`

| Verb | Use for |
|---|---|
| `proj init` | Scaffold `worktree-ios-dev/` in a new worktree. Idempotent. `--force` re-seeds `project.toml`; never touches `simulator.toml`. |
| `proj config` | Print resolved project + simulators view as JSON. Debugging. |
| `proj doctor` | Sanity checks: tooling, project.toml, simulators, project path. Run this first when something's off. Missing `simulator.toml` is a warn, not a fail. |

### `sim`

| Verb | Use for |
|---|---|
| `sim pick [<label>]` | Interactively pick + create + boot a simulator. `<label>` defaults to `default`. |
| `sim boot [<label>]` / `sim boot --all` | Boot one configured sim or every sim. |
| `sim shutdown [<label>]` / `sim shutdown --all` | Shutdown one or all. |
| `sim list` / `sim list --global` | List this worktree's sims (default) or every managed sim grouped by worktree. |
| `sim recreate <label>` | Destroy + re-pick + re-boot. Always requires explicit label. |
| `sim remove <label>` | Drop the entry from simulator.toml. Default keeps the simctl device; `--destroy` deletes it too. |
| `sim cleanup` | Tear down every sim owned by this worktree (prefix scan, name-based) and delete simulator.toml. Run before `git worktree remove`. |
| `sim du` / `sim du --this-worktree` | Disk-usage report for managed simulators, grouped by worktree. |
| `sim prune` | Find managed sims whose worktree is gone (via `git worktree list`) and delete them. |

### Build verbs (top-level)

| Verb | Use for |
|---|---|
| `build` | `xcodebuild build`. Flags: `--release`, `--scheme <name>`, `--sim <label>`. |
| `test` | `xcodebuild test`. Flags: `--release`, `--scheme <name>`, `--only-testing`, `--skip-testing`, `--sim <label>`. |
| `run` | Build → install → launch. Flags: `--release`, `--sim <label>`. |
| `clean` | `xcodebuild clean`. |
| `wipe-derived` | `rm -rf worktree-ios-dev/derivedData`. Prompts unless `--yes`. |
| `test-package <Name>` | Test a local Swift package via xcodebuild. Flags: `--sim <label>`. |

`--sim <label>` is required only when more than one entry exists under `[simulators.*]` in `simulator.toml`. Single-sim setups inherit the only entry.

## Global flags

- `--project-toml <path>` — override walk-up discovery (was `--config` pre-2026-05-05).
- `-v` / `--verbose` — stream subprocess output, show tracebacks on error.

## Exit codes

- `0` ok
- `1` user error (bad CLI args, bad config, verb refused)
- `2` environment error (project.toml not found, xcodebuild / simctl missing)
- `3` subprocess failure (xcodebuild / simctl returned non-zero; upstream code is included in the message)

## When the global "prepare build/run" instruction fires

The global user instruction says: "when iOS code is finished, invoke the xcodebuildmcp-cli skill to prepare build and run." Interpret that in this project as:

- For the **build and run** steps, use `worktree-ios-dev-tool build` then `worktree-ios-dev-tool run`.
- For **debug, UI automation, screenshots, log streaming**, use `xcodebuildmcp-cli`.
- If in doubt: build/test/run/clean go through `worktree-ios-dev-tool`; anything interactive or introspective that touches a live app goes through `xcodebuildmcp-cli`.

## Common mistakes

- Running any verb without `proj init` first → exit 2 with discovery error. Run `proj init`.
- Skipping `sim pick` → any verb that needs a simulator errors with "run `sim pick` first."
- Editing `[simulators.*].udid` by hand → prefer `sim recreate <label>`.
- Using `xcodebuildmcp-cli` for a vanilla build/test → goes through the wrong path; use `worktree-ios-dev-tool` instead.
- Encountering a legacy `worktree-ios-dev/config.toml` → manual migration: read it, run `proj init --force`, then `sim pick`, then `rm config.toml`. The tool refuses to run with a legacy file present.
- Forgetting `sim cleanup` before `git worktree remove` → orphaned simulators accumulate. `sim prune` cleans them later, or run `sim du` to see what's piling up.
```

- [ ] **Step 2: Verify markdown lints (if a linter is configured)**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills
ls .pre-commit-config.yaml 2>/dev/null && pre-commit run --files skills/worktree-ios-dev/SKILL.md || true
```

Expected: either no linter exists or it passes.

- [ ] **Step 3: Commit**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills
git add skills/worktree-ios-dev/SKILL.md
git commit -m "docs(worktree-ios-dev): rewrite SKILL.md for proj/sim namespaces"
```

---

## Task 15: Update `worktree_ios_dev_tool/README.md` and root `README.md`

**Files:**
- Modify: `worktree_ios_dev_tool/README.md`
- Modify: `README.md`

The tool README needs the new schema example, full verb reference, and migration note. The root README needs only stale-name fixes.

- [ ] **Step 1: Read both files first**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills
cat worktree_ios_dev_tool/README.md
cat README.md
```

- [ ] **Step 2: Update `worktree_ios_dev_tool/README.md`**

Replace any reference to:
- `bootstrap` → `proj init`
- `boot` → `sim pick` / `sim boot` (use the appropriate verb based on context)
- `config.toml` (singular file) → `project.toml` + `simulator.toml`
- `--config` → `--project-toml`
- The single-`[simulator]`-block example → the new `[simulators.<label>]` form with `schema_version = 1`

Add a new section "Multiple simulators per worktree" describing the `sim pick peer` flow plus `--sim peer` on build verbs.

Add a new section "Cleanup and disk usage" describing `sim cleanup`, `sim du`, `sim prune`.

Add a "Migrating from the legacy config.toml" subsection echoing the four-step manual migration.

- [ ] **Step 3: Update root `README.md`**

Search for `bootstrap`, `boot`, `config.toml`:
```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills
grep -nE 'bootstrap|\bboot\b|config\.toml' README.md
```

Replace each with the new term. Most likely places: a "Skills" overview that mentions the worktree-ios-dev verb names.

- [ ] **Step 4: Commit**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills
git add README.md worktree_ios_dev_tool/README.md
git commit -m "docs(readme): update worktree-ios-dev references for proj/sim namespaces"
```

---

## Task 16: Final smoke + stale-reference grep

**Files:**
- Read-only sweep.

Catch any reference we missed.

- [ ] **Step 1: Grep for stale identifiers**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills
rg -nP '\b(bootstrap|boot --recreate|find_config|SimulatorConfig|require_simulator)\b' \
   worktree_ios_dev_tool/ skills/ docs/ README.md \
   --glob '!docs/superpowers/specs/**' --glob '!docs/superpowers/plans/**'
```

Expected: zero hits in non-spec/plan files. Hits inside `docs/superpowers/specs/` or `docs/superpowers/plans/` are the design/plan documents themselves and are intentional.

If the rg has hits, fix each by editing the offending file with the appropriate replacement (`proj init`, `sim recreate <label>`, `find_project_toml`, `SimulatorEntry`, `resolve_sim`).

- [ ] **Step 2: Run all tests one more time**

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills/worktree_ios_dev_tool
uv run python -m unittest discover tests -v
```

Expected: every test green.

- [ ] **Step 3: Smoke the CLI top to bottom**

```bash
uv run worktree-ios-dev-tool --help
uv run worktree-ios-dev-tool proj --help
uv run worktree-ios-dev-tool sim --help
```

Expected: `proj` lists `init / config / doctor`, `sim` lists `pick / boot / shutdown / list / recreate / remove / cleanup / du / prune`, top-level lists those two namespaces plus `build / test / run / clean / wipe-derived / test-package`.

- [ ] **Step 4: Commit any cleanup hits from Step 1, then ship**

If Step 1 found anything:

```bash
cd /Users/yi.jiang/Developer/PulseProject/pulse-dev-skills
git add -p
git commit -m "chore: clean up stale references after proj/sim rename"
```

Otherwise no-op.

---

## Spec Coverage Check

Cross-referencing every section of the spec at `docs/superpowers/specs/2026-05-05-worktree-ios-dev-config-split-and-sim-namespace-design.md` against this plan:

| Spec section | Implemented in |
|---|---|
| File Layout (project.toml + simulator.toml) | Task 3 |
| `schema_version = 1` per file | Task 3 |
| Naming convention `<prefix>-<basename>-<label>` | Task 4 (helpers), Task 7 (`sim pick`) |
| `proj init` | Task 6 |
| `proj config` | Task 6 |
| `proj doctor` (multi-sim aware, missing-sim-warn) | Task 6 |
| `sim pick` | Task 7 |
| `sim boot` (single auto / multi require label / `--all`) | Task 7 |
| `sim shutdown` | Task 7 |
| `sim list` (local + `--global`) | Task 7 |
| `sim recreate` | Task 8 |
| `sim remove` (`--destroy`) | Task 8 |
| `sim cleanup` | Task 9 |
| `sim du` (`--this-worktree`) | Task 10 |
| `sim prune` (via `git worktree list`) | Task 11 |
| `--sim <label>` on build / test / run / test-package | Task 12 |
| Removal of `bootstrap` / `boot` aliases | Task 12 |
| `--config` → `--project-toml` | Task 13 |
| Schema version mismatch / missing handling | Task 3 |
| Legacy `config.toml` rejection | Task 3 |
| `resolve_sim` rules | Task 2 |
| SKILL.md update | Task 14 |
| README updates | Task 15 |
| Stale-reference grep | Task 16 |
| Documentation conventions (docstrings, comments, help, error msgs) | Embedded throughout (every code block in this plan follows the conventions). |
| Tests (`test_resolve_sim.py`, `test_config_schema.py`, `test_legacy_config_rejection.py`, `test_simulator_naming.py`, `test_simulator_helpers.py`, `test_sim_cleanup.py`, `test_sim_prune.py`) | Tasks 2, 3, 4, 5, 9, 11 |
