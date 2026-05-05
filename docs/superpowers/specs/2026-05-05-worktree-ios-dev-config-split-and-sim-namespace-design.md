# Worktree iOS Dev — Config Split + `sim`/`proj` Namespaces

**Date:** 2026-05-05
**Status:** Draft for review
**Affects:** `worktree_ios_dev_tool/` package, `skills/worktree-ios-dev/SKILL.md`, root `README.md`, `worktree_ios_dev_tool/README.md`

## Motivation

Today every `worktree-ios-dev/config.toml` mixes two concerns with very different change cadence:

- **Project settings** (`[project]`, `[packages_root]`, `[packages.*]`, `[extras]`) are essentially fixed for the repo. They get rewritten by `bootstrap` in every new worktree even though the values don't change.
- **Simulator settings** (`[simulator]`) are picked once per worktree and depend on which devices/runtimes the developer chose at boot time.

Mixing them obscures the structural separation, makes "did the agent need to re-pick a sim?" ambiguous, and complicates two new capabilities the team wants:

1. **Cleanup** — when a worktree is finished, destroy its sims so they don't accumulate.
2. **Disk usage / orphan pruning** — see how much disk simulators eat *across all worktrees*, not just the current one.

The CLI also needs to support **multiple simulators per worktree** (e.g. two sims sending messages to each other for integration scenarios).

## Goals

- Split `config.toml` into `project.toml` + `simulator.toml` in the same `worktree-ios-dev/` directory.
- Both files carry a `schema_version` integer for future evolution.
- Replace single-sim `[simulator]` block with named-table multi-sim `[simulators.<label>]`.
- Reorganize CLI into two namespaces: `proj <verb>` (project lifecycle) and `sim <verb>` (simulator lifecycle). Build/test/run verbs stay top-level.
- Add `sim cleanup`, `sim du`, `sim prune` for global hygiene without introducing a registry file.
- Update all docs and the `worktree-ios-dev` skill in lockstep.

## Non-Goals

- Sharing `project.toml` across worktrees of the same repo (deferred — kept per-worktree for now).
- Auto-migration from legacy `config.toml` (manual migration only; old config triggers a hard error with instructions).
- Backwards-compatible aliases for `bootstrap` / `boot` (removed; old verbs become unknown-verb errors).
- Persistent registry file mapping UDIDs to worktrees. Identification is purely by sim name prefix.

## File Layout

Both files live in `<worktree>/worktree-ios-dev/`. The whole directory remains gitignored by `proj init`'s `.gitignore` writer.

### `project.toml` (written by `proj init`; safe to hand-edit)

```toml
schema_version = 1

[project]
path = "ios/Pulse.xcodeproj"
scheme = "Pulse"
configuration = "Debug"
simulator_prefix = "Pulse"

[packages_root]
path = "ios/Packages"

[packages.SomePkg]
scheme = "SomePkgTests"

[extras]
xcodebuild_flags = []
```

Schema rules unchanged from current `[project]` / `[packages_root]` / `[packages.*]` / `[extras]` semantics. New top-level required field: `schema_version = 1`. `simulator_prefix` is **required** (was optional with fallback to `scheme`); the fallback to `scheme` is preserved at write time inside `proj init` for ergonomics, but `load()` requires the field be present in the file.

### `simulator.toml` (written by `sim pick`; do not hand-edit `udid`/`name`)

```toml
schema_version = 1

[simulators.default]
name    = "Pulse-feature-auth-default"
udid    = "ABCD-..."
device  = "iPhone 17 Pro"
runtime = "iOS 18.2"

[simulators.peer]
name    = "Pulse-feature-auth-peer"
udid    = "EFGH-..."
device  = "iPhone 17 Pro"
runtime = "iOS 18.2"
```

`name` is always `<simulator_prefix>-<worktree_basename>-<label>`. The tool synthesizes it; manual edits are not respected and may break `sim cleanup` / `sim prune` scans.

`simulator.toml` is **optional**. A worktree that just ran `proj init` has no `simulator.toml`; commands that need a sim error with a hint to run `sim pick`.

## Naming Convention (load-bearing)

```
<simulator_prefix>-<worktree_basename>-<label>
```

- `simulator_prefix` from `project.toml`. If absent, falls back to `project.scheme` at write time.
- `worktree_basename` = `Path(cfg.worktree_root).name`.
- `label` is the user-supplied (or default `default`) key under `[simulators.*]`.

**Validation rules** (enforced by `sim pick`):

- `label` matches `^[A-Za-z0-9_]+$` — no hyphens, no whitespace. Required so that `<basename>-<label>` parses unambiguously when the basename itself contains hyphens (e.g. `feature-auth`).
- `worktree_basename` may contain hyphens; reverse-parse takes everything before the **last** `-` as basename and the final segment as label.
- `simulator_prefix` may contain hyphens; the prefix is matched as a literal anchor at name start, not parsed by hyphens.

## CLI Surface

### `proj` namespace

| Command | Description |
|---|---|
| `proj init` | Scaffold `worktree-ios-dev/`, write `project.toml`, update `.gitignore`. Replaces `bootstrap`. Flags: `--project <relpath>`, `--scheme <name>`, `--yes`, `--force`. `--force` re-writes `project.toml` only; `simulator.toml` is never touched by this verb. |
| `proj config` | Print resolved config (project + simulators) as JSON. Replaces top-level `config`. |
| `proj doctor` | Sanity checks: tooling, `project.toml`, simulators, project path. Replaces top-level `doctor`. Multi-sim aware (lists each entry). Missing `simulator.toml` is a **warn**, not an **error**. |

### `sim` namespace

| Command | Behavior |
|---|---|
| `sim pick [<label>]` | Interactively choose device + runtime, create sim, write `simulators.<label>` to `simulator.toml`. `label` defaults to `default`. Errors if entry exists; redirect to `sim recreate <label>`. Flags: `--all-devices` (drop iPhone 17 filter). |
| `sim boot [<label>]` | Boot one configured sim. No `<label>`: auto-pick if exactly one configured, else error. `--all` boots every configured sim. |
| `sim shutdown [<label>]` | Shutdown one. Resolution rules same as `boot`. `--all` for everything. |
| `sim list` | Default: list this worktree's configured sims with `simctl` state. `--global`: scan `simctl` for `<simulator_prefix>-*` and group by parsed worktree-basename. |
| `sim recreate <label>` | shutdown + delete simctl device + remove entry + re-pick + boot. `<label>` required (no defaulting on destructive operations). |
| `sim remove <label>` | Remove entry from `simulator.toml`. Default: leave simctl device alone. `--destroy`: delete simctl device too. |
| `sim cleanup` | This worktree: scan simctl matching `<simulator_prefix>-<this_worktree_basename>-*`, shutdown + delete each, then delete `simulator.toml`. Works even if `simulator.toml` is missing/corrupt. `--yes` skips confirmation. |
| `sim du` | Default global: scan `<simulator_prefix>-*` in simctl, `du -sh ~/Library/Developer/CoreSimulator/Devices/<UDID>` per device, group output by parsed worktree-basename. `--this-worktree` restricts to current. Output also includes a totals line. |
| `sim prune` | Global orphan cleanup. Run `git worktree list --porcelain` from cwd's repo, collect live worktree basenames. Sims whose parsed basename ∉ that set are orphans. List + interactive confirm + delete. `--yes` skips confirmation. Errors if not run inside a git worktree (no way to enumerate live worktrees). |

### Top-level (build verbs, unchanged shape)

`build`, `test`, `run`, `clean`, `wipe-derived`, `test-package <Name>`. All gain `--sim <label>` for sim selection (single-sim auto-picks; multi-sim requires the flag).

### Removed / replaced

- `bootstrap` → `proj init`
- `boot` → `sim pick` (first time) or `sim boot` (subsequent)
- `config` → `proj config`
- `doctor` → `proj doctor`

Old verbs are removed entirely. Invoking them yields argparse's "invalid choice" error. The error message lists the new namespaces.

## Loading & Validation

### Discovery

`paths.find_config()` becomes `paths.find_project_toml()`:

- Walk up from cwd; match `<dir>/worktree-ios-dev/project.toml`.
- If walk finds a legacy `<dir>/worktree-ios-dev/config.toml` but no `project.toml`, raise `UserError` with the manual migration message (see below).
- `simulator.toml` is looked up at `<project_toml.parent>/simulator.toml`. Missing → empty simulators dict.

`--config <path>` flag (registered in `_add_common`, available on every verb) is renamed to `--project-toml <path>`. Semantics: explicit pointer to `project.toml`; `simulator.toml` resolves at `<that path>.parent / "simulator.toml"`.

### Schema versioning

```python
SUPPORTED_PROJECT_VERSION = 1
SUPPORTED_SIMULATOR_VERSION = 1
```

On load:

- Missing `schema_version` → `UserError("<path>: missing schema_version. Re-run `proj init`.")` (project) or `UserError("<path>: missing schema_version. Re-run `sim pick`.")` (simulator).
- `schema_version != SUPPORTED_*` → `UserError("<path>: schema_version <N> not supported. Upgrade worktree-ios-dev-tool or migrate manually.")`.
- Future bumps: each version gets its own load branch; reject anything unknown.

### Legacy `config.toml` handling

Detection: walk-up finds `worktree-ios-dev/config.toml` next to a directory that has no `project.toml`. The tool refuses to do anything other than print:

```
error: Detected legacy config.toml at <abs path>.
This tool now uses split project.toml + simulator.toml.
Manual migration:
  1. Read the legacy values:    cat <path>
  2. Write the new project.toml: worktree-ios-dev-tool proj init --force \
                                   --project <relpath> --scheme <name>
  3. Recreate the simulator:     worktree-ios-dev-tool sim pick
  4. Remove the legacy file:     rm <path>
```

No automatic conversion is performed. No `.bak` is left.

## New Module Layout

Existing files (`config.py`, `boot.py`, `bootstrap.py`, `simulator.py`, `cli.py`, etc.) are reshaped:

- `config.py`
  - `ProjectConfig` — unchanged shape minus `simulator_prefix` becoming required at the dataclass level.
  - `SimulatorEntry` — was `SimulatorConfig`, renamed for clarity since multiple coexist.
  - `Config.simulators: dict[str, SimulatorEntry]` replaces `simulator: SimulatorConfig | None`.
  - Helpers: `resolve_sim(cfg, label: str | None) -> SimulatorEntry` enforcing the single/multi rules.
  - `load_project(path) -> ProjectConfig`, `load_simulators(path) -> dict[str, SimulatorEntry]`, top-level `load(project_toml: Path) -> Config` that composes both.
  - Writers: `write_project(...)`, `write_simulator_entry(path, label, entry)`, `remove_simulator_entry(path, label)` — all using `tomlkit` to preserve comments.
- `paths.py`
  - `find_project_toml()` (replacement), keeps `derived_data_dir()` and friends. `worktree_root()` and `config_dir()` keep their meanings (parent of `worktree-ios-dev/`).
- `proj.py` (new)
  - Implementations for `proj init`, `proj config`, `proj doctor`. Most code lifted from current `bootstrap.py` + `cli._cmd_config` + `cli._cmd_doctor`.
- `sim.py` (new; replaces `boot.py`)
  - One function per sub-verb: `pick`, `boot`, `shutdown`, `list_local`, `list_global`, `recreate`, `remove`, `cleanup`, `du`, `prune`.
  - Helpers in `simulator.py` extended: `delete(udid)` (exists), `shutdown(udid)` (new), `list_devices_by_prefix(prefix)` (new), `device_data_dir(udid)` (new — returns `~/Library/Developer/CoreSimulator/Devices/<UDID>`), `du_bytes(path)` (new).
- `cli.py`
  - argparse layout becomes nested: `proj` and `sim` are both subparsers that themselves register sub-subparsers via `add_subparsers(dest="subverb", required=True)`.
  - Build/test/run verbs gain `--sim <label>`.
  - Old verbs removed; argparse will reject them with its standard error.

## Resolution Rules for `--sim` / `<label>`

Single helper `resolve_sim(cfg, label)`:

- `label is None` and `len(cfg.simulators) == 0` → `UserError("No simulators configured. Run `sim pick` first.")`
- `label is None` and `len(cfg.simulators) == 1` → return the only entry.
- `label is None` and `len(cfg.simulators) > 1` → `UserError("Multiple simulators configured (default, peer, ...). Pass `--sim <label>` to disambiguate.")`
- `label not in cfg.simulators` → `UserError("No simulator labeled '<label>'. Configured: <list>.")`
- Otherwise → return entry.

Used by every command that needs a sim: `sim boot`, `sim shutdown`, `sim recreate`, `sim remove`, `run --sim`, `test --sim`, `test-package --sim`, plus `xcodebuild` destination construction.

## `sim cleanup` Algorithm

```
prefix = cfg.project.simulator_prefix
basename = cfg.worktree_root.name
pattern = f"{prefix}-{basename}-"

devices = simctl_list_all_devices()
matched = [d for d in devices if d.name.startswith(pattern)]

for d in matched:
    if d.state == "Booted":
        simctl_shutdown(d.udid)
    simctl_delete(d.udid)

simulator_toml = config_dir / "simulator.toml"
if simulator_toml.exists():
    simulator_toml.unlink()
```

`--yes` skips the confirmation that lists matched devices before acting.

## `sim du` Output

```
Pulse simulators (prefix=Pulse):

  worktree=feature-auth
    default  ABCD-...  iPhone 17 Pro  3.2 GiB
    peer     EFGH-...  iPhone 17 Pro  2.9 GiB

  worktree=main
    default  IJKL-...  iPhone 17 Pro  4.1 GiB

Total: 10.2 GiB across 3 simulators.
```

Implementation: `simctl list devices --json` to get UDID + name + state, then `du -sk` against the device data dir for size. Sort within each worktree by label, between worktrees alphabetically.

## `sim prune` Algorithm

```
git worktree list --porcelain  ->  set of basenames
prefix = cfg.project.simulator_prefix

devices = simctl_list_all_devices()
matched = [d for d in devices if d.name.startswith(prefix + "-")]

orphans = []
for d in matched:
    name_tail = d.name[len(prefix) + 1:]    # "<basename>-<label>"
    if "-" not in name_tail:
        continue                             # malformed, leave alone
    basename, _, label = name_tail.rpartition("-")
    if basename not in live_basenames:
        orphans.append((d, basename, label))

if not orphans:
    print("No orphaned simulators.")
    return 0

print orphans grouped by basename
prompt y/N (skip with --yes)
shutdown + delete
```

If `git worktree list` fails (not in a repo), `UserError("`sim prune` must be run from inside a git worktree of the project repo.")`.

## Doctor Updates

`proj doctor` reports:

- `xcodebuild` / `xcrun` on PATH (existing).
- `mint` (optional, existing).
- `project.toml` exists, `schema_version == 1`, `project.path` exists.
- `simulator.toml`: if missing → warn ("run `sim pick`"). If present → for each entry, verify UDID still exists in simctl; report state.
- `worktree-ios-dev/` directory exists.

Exit 1 if any of the **errors** listed above; warns alone don't fail.

## Documentation Updates

All in scope of this change:

- `skills/worktree-ios-dev/SKILL.md` — rewrite verb table, decision flow, "common mistakes", "When the global prepare instruction fires" section.
- `worktree_ios_dev_tool/README.md` — full rewrite of CLI reference; add `[simulators.*]` schema section; document `sim cleanup` / `du` / `prune`.
- Root `README.md` — update worktree-ios-dev mentions.
- Any inline doctor strings, error messages, and `--help` text inside `cli.py` and submodules.

Search for stale references to `bootstrap`, `boot --recreate`, `config.toml` (singular) before merging. Acceptance: `rg -nP '\b(bootstrap|boot --recreate|config\.toml)\b' worktree_ios_dev_tool/ skills/ docs/ README.md` returns only intentional historical mentions (e.g., this spec).

## Tests

Existing tests under `worktree_ios_dev_tool/tests/` get adapted; key new cases:

- `test_config.py`: load valid `project.toml` v1; reject missing `schema_version`; reject unsupported version; load `simulator.toml` with 0/1/N entries.
- `test_resolve_sim.py`: empty / single / multi / unknown label paths.
- `test_legacy_config_rejection.py`: walk-up to a `config.toml` only → `UserError` with migration text.
- `test_sim_cleanup.py`: monkeypatch simctl; verify name-prefix match logic, including basenames containing hyphens.
- `test_sim_prune.py`: monkeypatch simctl + `git worktree list`; verify orphan detection across hyphenated basenames.
- `test_cli_smoke.py`: argparse rejects old verbs; new verbs route to handlers.

## Edge Cases & Decisions Log

- **Hyphenated worktree basenames**: parsed via `rpartition("-")`. Label rule (`^[A-Za-z0-9_]+$`) makes parsing total.
- **Empty `simulator_prefix`**: `proj init` falls back to `project.scheme` at write time, so the file always has a non-empty value at load time.
- **`sim cleanup` when `simulator.toml` missing**: prefix scan still runs and reports counts; toml deletion is a no-op.
- **`sim du` with zero matches**: prints `no managed simulators found (prefix: <X>)`, exit 0.
- **`run --sim peer` with peer not booted**: `run` boots it before install/launch (same flow as today's single sim case).
- **Mixed-tool simulators**: any sim whose name doesn't start with `<simulator_prefix>-` is invisible to `sim list --global`, `sim du`, `sim prune`. By design — we don't manage what we didn't create.
- **`proj doctor` after `proj init` only**: `simulator.toml` missing is a warn, exit 0. New users see a green doctor.

## Migration (one-time, manual, per worktree)

1. `cat <worktree>/worktree-ios-dev/config.toml`
2. `worktree-ios-dev-tool proj init --force --project <relpath> --scheme <name>` (re-derives `project.toml` with `schema_version`).
3. `worktree-ios-dev-tool sim pick` (creates `simulators.default` and writes `simulator.toml`).
4. `rm <worktree>/worktree-ios-dev/config.toml`.

If a developer skips step 1–4 the tool refuses to run with the legacy-config error message above.

## Out of Scope (explicit)

- Sharing `project.toml` across worktrees (committed in repo, located in `.git/`, or user-level). Revisit later as a separate spec.
- Auto-migration / `bootstrap` alias / `boot` alias.
- Registry file at `~/.local/state/worktree-ios-dev/registry.json`.
- Hooks on `git worktree remove` to auto-cleanup. `sim cleanup` is manual.
- Renaming `derived_data` location or making it per-sim.
