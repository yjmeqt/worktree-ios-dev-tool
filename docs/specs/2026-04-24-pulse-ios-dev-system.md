> **Superseded by:** `docs/superpowers/specs/2026-04-28-worktree-ios-dev-design.md`

# Pulse iOS Dev Management System

**Status:** Draft · **Date:** 2026-04-24

## Problem

Today the iOS build surface in Pulse worktrees is under-regulated. Developers and
agents juggle `xcodebuild` invocations, `xcodebuildmcp-cli` calls, and raw
`xcrun simctl` commands, each with scheme, configuration, destination, and
derived-data arguments that drift between invocations. Per-worktree simulators
add another degree of freedom: the UDID must be copy-pasted every time a build
runs against the right sim. The legacy `pulse-ios-testing` skill split main-app
vs. local-package tests into two different command shapes, which the model and
humans had to remember.

The result is repetitive typing, forgettable flags, cross-worktree contamination
of derived data, and agents reconstructing command strings from prose each time.

## Goal

Provide a centralized, per-worktree Python CLI — `pulse-ios-dev-tool` — that
absorbs all non-interactive iOS build tasks for the Pulse app and its local
Swift packages. Config lives in a gitignored `pulse-ios-dev/` directory in
each worktree. `xcodebuildmcp-cli` remains the tool for debugging, UI
automation, and log streaming.

## Non-goals

- Replacing `xcodebuildmcp-cli` for debugging, UI automation, screenshots, or
  log streaming.
- Archive / export-IPA / TestFlight flows.
- Cross-platform support (macOS, watchOS, tvOS, visionOS). iOS only.
- Managing CI builds. This is a local developer / agent tool.
- Automated tests for the tool itself (smoke-checked manually).

## Approach

A Python package `pulse_ios_dev_tool` ships in the `pulse-dev-skills` repo and
is installed **globally once per machine** via `uv tool install --editable`. A
companion skill `skills/pulse-ios-dev/` documents the command surface and
the decision tree between `pulse-ios-dev-tool` and `xcodebuildmcp-cli`. It
replaces the former `pulse-ios-build` + `pulse-ios-testing` pair. Skills
continue to be installed per-worktree via the existing `npx skills add` flow.

Per-worktree state lives entirely in a gitignored `pulse-ios-dev/` directory,
which holds `config.toml` and `derivedData/`. Config discovery walks up from
`cwd` until it finds `pulse-ios-dev/config.toml`. A
`pulse-ios-dev-tool worktree-bootstrap` verb creates this directory on first
use in a worktree — no separate shell script, no per-worktree shim, no `PATH`
manipulation.

## Repository layout

```
pulse-dev-skills/
├── pulse_ios_dev_tool/
│   ├── pyproject.toml                  # declares `pulse-ios-dev-tool` console script
│   ├── src/pulse_ios_dev_tool/
│   │   ├── __init__.py
│   │   ├── __main__.py                 # `python -m pulse_ios_dev_tool`
│   │   ├── cli.py                      # argparse dispatcher
│   │   ├── config.py                   # TOML discovery + parsing + schema validation
│   │   ├── simulator.py                # simctl wrappers + interactive picker
│   │   ├── xcodebuild.py               # argv builders for build/test/run/clean
│   │   ├── packages.py                 # local-package test path
│   │   ├── paths.py                    # walk-up discovery of pulse-ios-dev/
│   │   └── proc.py                     # subprocess runner
└── skills/
    └── pulse-ios-dev/
        └── SKILL.md                    # agent-facing build/test/run skill
```

### Module boundaries

- `cli.py` dispatches to verb handlers; it never calls `xcrun` / `xcodebuild`
  directly.
- `config.py` is pure: no subprocess, no filesystem mutation beyond reading.
- `simulator.py`, `xcodebuild.py`, `packages.py` depend only on `proc.py` and
  `config.py`.
- `proc.py` is the single subprocess boundary.

## CLI surface

All verbs walk up from `cwd` for `pulse-ios-dev/config.toml`. Every verb
accepts `--config <path>` to override discovery and `-v/--verbose` to stream
subprocess output and show tracebacks on error.

### Setup verbs

| Verb | Behavior |
|---|---|
| `pulse-ios-dev-tool worktree-bootstrap` | Runs once per worktree. Detects worktree root by walking up from `cwd` for `ios/Pulse.xcodeproj` or a `.git` entry; errors if neither is found. Creates `<worktree-root>/pulse-ios-dev/` with a seeded `config.toml` (filled `[project]`, omitted `[simulator]`) and an empty `derivedData/`. Adds `pulse-ios-dev/` to the worktree's `.gitignore` if not already ignored. Idempotent; re-run with `--force` to re-seed `config.toml`. Prints next step: `pulse-ios-dev-tool boot`. |

### Main-app verbs

| Verb | Behavior |
|---|---|
| `pulse-ios-dev-tool boot` | First run: interactive picker for device + runtime (default filter: iPhone 17 family), creates sim, writes `[simulator]` block back into `config.toml`, boots, opens Simulator.app. Subsequent runs: boot the saved UDID, no prompts. `--recreate` deletes the named sim and re-enters first-run. `--all-devices` disables the iPhone 17 filter. |
| `pulse-ios-dev-tool build` | `xcodebuild build` using toml-resolved project / scheme / configuration / destination / derived-data. `--release` flips configuration. `--scheme <name>` overrides. |
| `pulse-ios-dev-tool test` | `xcodebuild test` with the same resolution. Passes `--only-testing <id>` / `--skip-testing <id>` through to xcodebuild. |
| `pulse-ios-dev-tool run` | `build`, locate `.app` under derivedData, `simctl install`, `simctl launch`. Prints bundle id and pid and returns. |
| `pulse-ios-dev-tool clean` | `xcodebuild clean` on the project. |
| `pulse-ios-dev-tool wipe-derived` | `rm -rf pulse-ios-dev/derivedData`. Prompts unless `--yes`. |

### Package verb

| Verb | Behavior |
|---|---|
| `pulse-ios-dev-tool test-package <Name>` | `cd ios/Packages/<Name> && xcodebuild test -project Package.swift -scheme <Name>` with the simulator destination from toml. `[packages.<Name>]` overrides apply. |

### Introspection verbs

| Verb | Behavior |
|---|---|
| `pulse-ios-dev-tool config` | Prints resolved config (toml + CLI overrides) as JSON. |
| `pulse-ios-dev-tool doctor` | Sanity checks: config found, project exists, sim UDID exists and is bootable, `xcodebuild` / `xcrun` on PATH, derivedData dir writable. Also reports whether `mint` is installed (optional; see **Pretty xcodebuild output** below). Exits non-zero on any required failure; a missing `mint` is informational only. |

### Explicitly out of scope (fall back to `xcodebuildmcp-cli`)

- Log streaming (`xcrun simctl spawn booted log stream`)
- UI automation (tap / swipe / screenshot)
- Breakpoint / debug session attach
- Archive / export-IPA
- TestFlight upload

The `pulse-ios-dev` skill names these explicitly so agents route correctly.

## Pretty xcodebuild output (optional)

When `mint` is on `PATH` and a verb streams `xcodebuild` output to the terminal
(i.e. the default, non-captured path), `proc.py` transparently pipes the merged
stdout/stderr through `mint run xcbeautify`. Behavior:

- Mint missing → `xcodebuild` output streams raw and `proc.py` prints a one-line
  note to stderr suggesting `brew install mint` for cleaner logs. The build
  itself is unaffected.
- Mint present → output is prettified. `xcodebuild`'s exit code is preserved;
  `xcbeautify`'s exit code is ignored (pipefail-style semantics with the
  primary process as the authority).
- Captured-output calls (`capture=True`, used by introspection paths like
  locating the built `.app`) bypass the pipe entirely so parsing stays
  deterministic.

This is a typing-saver, not a dependency. The tool never installs, auto-runs,
or fails because of `mint`; it only checks for its presence at invocation time.
`pulse-ios-dev-tool doctor` reports status so users can opt in.

## `config.toml` schema

Lives at `WORKTREE/pulse-ios-dev/config.toml`. The whole
`pulse-ios-dev/` directory is gitignored per worktree.

```toml
[project]
# Path to .xcodeproj relative to the worktree root (the directory that
# contains pulse-ios-dev/).
path    = "ios/Pulse.xcodeproj"
scheme  = "Pulse"
configuration = "Debug"          # default; `--release` flips to "Release"

[simulator]
# Written by `pulse-ios-dev-tool boot` on first run. Do not hand-edit UDID.
name    = "Pulse-myfeature"
udid    = "ABCD-1234-..."
device  = "iPhone 17 Pro"        # iPhone 17 family baseline
runtime = "iOS 26.0"

[packages_root]
# Directory containing local Swift packages, relative to the worktree root.
path = "ios/Packages"

# Optional per-package override. Omit entirely if the convention holds:
#   cd ios/Packages/<Name> && xcodebuild test -project Package.swift -scheme <Name>
# [packages.PulseNetworking]
# scheme = "PulseNetworkingTests"

[extras]
# Free-form raw flags appended to every xcodebuild invocation.
# Escape hatch for one-off needs without a schema change.
xcodebuild_flags = []
```

### Resolution rules

- `project.path` is resolved relative to the directory containing
  `pulse-ios-dev/` — not necessarily a git worktree root.
- Derived-data path is hardcoded to `<config-dir>/derivedData` (i.e. sibling
  to `config.toml` inside `pulse-ios-dev/`). Not user-settable. Preserves
  the "everything under `pulse-ios-dev/`" invariant.
- `[simulator]` is optional at parse time but required for any verb that needs
  a destination. Missing → error: "run `pulse-ios-dev-tool boot` first."
- `[packages]` table entries merge over the default convention; unknown keys
  error out to catch typos.
- Schema is validated on load. Errors name the offending key and suggest a fix.
- Config writes (from `boot`) use `tomlkit` to preserve comments and layout.

## `pulse-ios-dev-tool boot` behavior

### First run

Triggered when `[simulator]` is absent, or `udid` is missing, or the saved UDID
is not present in `simctl list`.

1. Query `xcrun simctl list devices available --json` and `xcrun simctl list
   runtimes --json`.
2. Filter device types to the iPhone 17 family by default. `--all-devices`
   skips the filter.
3. Interactive picker (two prompts). Falls back to numeric menu if stdin is
   not a TTY. If stdin is fully detached, fail with a clear message to run
   from a real terminal.
   - **Device type** — e.g. `iPhone 17`, `iPhone 17 Pro`, `iPhone 17 Pro Max`.
   - **Runtime** — latest iOS 26.x preselected.
4. Derive sim name as `Pulse-<worktree-dir-basename>`. If that name already
   exists in `simctl list`, reuse its UDID after a confirmation prompt rather
   than creating a duplicate.
5. `xcrun simctl create "<name>" <deviceTypeId> <runtimeId>` → capture UDID.
6. Write `[simulator]` back into `config.toml` via `tomlkit`.
7. `xcrun simctl boot <udid>`; `open -a Simulator`.
8. Print name, UDID, device, runtime.

### Subsequent runs

1. Verify UDID still exists via `simctl list devices --json`. If not, fall
   through to first-run flow and update config.
2. If already `Booted`, no-op with a message. Otherwise `simctl boot <udid>`
   and `open -a Simulator`.
3. No prompts; safe to script.

### Edge cases

- Simulator deleted outside the tool → auto-recover via first-run flow.
- Name collisions across worktrees → reuse-or-confirm path prevents dupes.
- `xcrun` / `simctl` missing → error early with `xcode-select --install`
  suggestion.

## Installation and discovery

### One-time machine setup

Prerequisite: `uv` on `PATH` (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
and `~/.local/bin` on `PATH` (uv's default tool install location).

Install the CLI globally once per machine:

```bash
uv tool install --editable /abs/path/to/pulse-dev-skills/pulse_ios_dev_tool
```

`--editable` points the installed `pulse-ios-dev-tool` entry point at the
working copy of the skills repo. Edits under `pulse_ios_dev_tool/src/` take
effect on the next invocation with no reinstall. `pulse-ios-dev-tool` is then
on `PATH` for every shell and every worktree — there is no per-worktree shim
and no `PATH` manipulation per worktree.

Optional: `brew install mint` enables `xcbeautify` for prettier `xcodebuild`
output. See **Pretty xcodebuild output** above for exact behavior.

### Upgrade model

| Changed | Action |
|---|---|
| Python source under `pulse_ios_dev_tool/src/` | None. Editable install reflects the new source automatically after `git pull`. |
| Dependencies in `pulse_ios_dev_tool/pyproject.toml` | `uv tool install --reinstall --editable /abs/path/to/pulse-dev-skills/pulse_ios_dev_tool` (or `uv tool upgrade pulse-ios-dev-tool`). |
| New / renamed console script entry in `pyproject.toml` | Same `--reinstall`. |
| Skills repo moved to a new path | `uv tool uninstall pulse-ios-dev-tool` then reinstall from the new path. |

`uv tool upgrade pulse-ios-dev-tool` is the safe catch-all when unsure what
changed.

Uninstall: `uv tool uninstall pulse-ios-dev-tool`.

### Per-worktree setup

```bash
cd /path/to/pulse/.worktrees/my-feature
pulse-ios-dev-tool worktree-bootstrap   # creates pulse-ios-dev/, seeds config.toml, updates .gitignore
pulse-ios-dev-tool boot                 # interactive: pick device + runtime, creates sim, writes [simulator]
pulse-ios-dev-tool build                # etc.
```

Nothing per-worktree is added to `PATH`. The globally-installed
`pulse-ios-dev-tool` locates the right `config.toml` by walking up from `cwd`,
so changing worktrees is just `cd`.

### Skills (unchanged)

Skills continue to be installed per-worktree via the existing flow documented
in the repo README:

```bash
cd /path/to/worktree
npx skills add /abs/path/to/pulse-dev-skills
```

This populates `.claude/skills/` (and `.agents/skills/`) with symlinks to this
repo, including the new `pulse-ios-dev` skill.

### Discovery

`pulse_ios_dev_tool.paths.find_config()` walks up from `cwd` for a
`pulse-ios-dev/config.toml`. First match wins; stops at `$HOME` or
filesystem root.

- Found → use it; the parent of `pulse-ios-dev/` is the "worktree root"
  used to resolve `project.path`, `packages_root.path`, etc.
- Not found → exit code 2 with:
  *"No `pulse-ios-dev/config.toml` found walking up from `<cwd>`.
  Run `pulse-ios-dev-tool worktree-bootstrap` from your worktree to set one up."*
- `--config <path>` bypasses discovery.

## Skill integration

### Unified skill: `skills/pulse-ios-dev/SKILL.md`

Agent-facing decision tree and command reference. Covers both build and test
verbs (replaces the former `pulse-ios-build` + `pulse-ios-testing` split).

- **Use `pulse-ios-dev-tool <verb>`** for: boot sim, build, run, main-app test,
  package test, clean, wipe derived data.
- **Use `xcodebuildmcp-cli`** for: log streaming, UI automation
  (tap / swipe / screenshot), debug session / breakpoints, archive /
  export-IPA, TestFlight upload.
- First-time machine setup:
  `uv tool install --editable <abs-path-to-skills-repo>/pulse_ios_dev_tool`.
- First-time worktree setup: `pulse-ios-dev-tool worktree-bootstrap`, then
  `pulse-ios-dev-tool boot`.
- Lists the v1 CLI surface verbatim (verbs + one-line descriptions).
- Clarifies the global user preference "when iOS code finishes, invoke
  xcodebuildmcp-cli to prepare build/run": once `pulse-ios-dev` is adopted,
  the build/run steps route through `pulse-ios-dev-tool`; `xcodebuildmcp-cli`
  still handles the debug / UI-automation side.

### Unchanged

`skills/pulse-ios-perf-tracing/` — already defers to tooling and does not
prescribe build commands.

## Error handling

- Exit codes:
  - `0` ok
  - `1` user error (bad config, bad CLI args, verb refused because sim is
    missing)
  - `2` environment error (config not discovered, `xcodebuild` / `simctl`
    missing from PATH)
  - `3` subprocess failure (xcodebuild / simctl returned non-zero). The
    upstream exit code is reported in the error message for debugging.
- Every error message names the failing thing and the likely fix.
- No bare tracebacks for expected errors. `-v/--verbose` enables them.
- `pulse-ios-dev-tool doctor` is the canonical "something is off, run this
  first" verb and covers the top failure modes.
- No retries or fallback command construction. If `xcodebuild` fails, the tool
  surfaces its output verbatim and exits. This is a typing-saver, not a
  resilience layer.

## Open questions

None at spec time.

## Rollout

1. Land `pulse_ios_dev_tool/` package in `pulse-dev-skills` with the
   `worktree-bootstrap`, `boot`, `build`, `test`, `run`, `test-package`,
   `clean`, `wipe-derived`, `config`, and `doctor` verbs.
2. Land `skills/pulse-ios-dev/SKILL.md` (the unified build+test skill).
3. `uv tool install --editable` the tool from the skills repo; in the author's
   current Pulse worktree run `pulse-ios-dev-tool worktree-bootstrap`, then
   step through `boot`, `build`, `test`, `run`, `test-package <Name>` manually
   to smoke-check.
4. Announce to the team; add install / upgrade commands and a link to the
   new skill in the repo README.
