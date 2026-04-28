# worktree-ios-dev: Rename & Project-Agnostic Redesign

**Date:** 2026-04-28  
**Status:** Approved  
**Replaces:** `pulse-ios-dev-tool` (pulse_ios_dev_tool package)

---

## Problem

`pulse-ios-dev-tool` is 80% generic iOS worktree management but hardcodes Pulse-specific values throughout — project path (`ios/Pulse.xcodeproj`), scheme (`Pulse`), simulator prefix (`Pulse-`). It cannot be reused for any other iOS project without modifying source code.

## Goal

Rename and refactor the tool to be fully project-agnostic. Any iOS project should be able to use it by running `worktree-ios-dev bootstrap` in its worktree.

## Non-Goals

- No change to the core build/test/run/clean logic
- No CI support
- No archive/export/TestFlight
- No replacement of xcodebuildmcp for interactive debug/UI work

---

## Rename Scope

| Old | New |
|-----|-----|
| Package directory `pulse_ios_dev_tool/` | `worktree_ios_dev/` |
| Python module `pulse_ios_dev_tool` | `worktree_ios_dev` |
| PyPI name `pulse-ios-dev-tool` | `worktree-ios-dev` |
| CLI command `pulse-ios-dev-tool` | `worktree-ios-dev` |
| Per-worktree config dir `pulse-ios-dev/` | `worktree-ios-dev/` |
| `/tmp/pulse-ios-dev/` offload root | `/tmp/worktree-ios-dev/` |
| Exception base `PulseIosError` | `WorktreeIosError` |
| Skill `skills/pulse-ios-dev/` | `skills/worktree-ios-dev/` |

All docs, plans, and specs that reference the old names are updated in-place.

Existing worktrees require a one-time manual migration:
```bash
mv pulse-ios-dev worktree-ios-dev
```

---

## Bootstrap Redesign

Bootstrap is the only command that previously contained project-specific hardcoded values. It is redesigned to discover or prompt for all project-specific information.

### Discovery Logic

1. **xcodeproj:** Recursively search worktree root for `*.xcodeproj`. If exactly one is found, use it. If multiple are found, prompt the user.
2. **scheme:** Run `xcodebuild -list -project <path> -json` to enumerate schemes. If exactly one is found, use it. If multiple are found, prompt the user.
3. **packages_root:** Check if `<xcodeproj_dir>/../Packages` exists. If yes, populate automatically. Otherwise leave empty (optional field).
4. **simulator_prefix:** Default to the selected scheme name. User may override at the prompt.

### Modes

**Interactive (TTY present):**

Steps are presented with `InquirerPy` fuzzy-search pickers. Each step is skipped if the answer is unambiguous (single result auto-selected with a confirmation line). Terminal shows a `rich` spinner while scanning/fetching.

```
⠸ Scanning for Xcode projects...

? Select project  [Type to filter]
❯ ios/MyApp.xcodeproj
  ios/Extension.xcodeproj

⠸ Fetching schemes...

? Select scheme  [Type to filter]
❯ MyApp
  MyAppTests

✓ packages_root detected: ios/Packages

? Simulator prefix  (default: MyApp) ▌

╭─ worktree-ios-dev/config.toml ──────────────╮
│ [project]                                   │
│ path             = ios/MyApp.xcodeproj      │
│ scheme           = MyApp                    │
│ simulator_prefix = MyApp                    │
│ [packages_root]                             │
│ path             = ios/Packages             │
╰─────────────────────────────────────────────╯

✓ Created worktree-ios-dev/config.toml
✓ Updated .gitignore
→ Next: worktree-ios-dev boot
```

**Non-interactive (no TTY or `--yes`):**

Auto-detect everything. Unambiguous results are used silently with a log line. Ambiguous results cause a non-zero exit with a clear error message instructing the user to pass explicit flags.

```
[worktree-ios-dev] found project: ios/MyApp.xcodeproj
[worktree-ios-dev] found scheme: MyApp
[worktree-ios-dev] packages_root: ios/Packages
[worktree-ios-dev] bootstrap complete
```

**CLI flags (agent or scripted use):**

```bash
worktree-ios-dev bootstrap --project ios/MyApp.xcodeproj --scheme MyApp
```

Flags bypass discovery and prompts for the corresponding step. `--yes` accepts all detected defaults without prompting; fails if any step is ambiguous.

### Updated config.toml Schema

```toml
[project]
path              = "ios/MyApp.xcodeproj"   # required
scheme            = "MyApp"                  # required
configuration     = "Debug"                  # optional, default Debug
simulator_prefix  = "MyApp"                  # optional, default = scheme

[packages_root]
path              = "ios/Packages"           # optional section

[simulator]
name = "MyApp-feat-login"   # written by `boot`, not by bootstrap
udid = "..."
```

---

## Simulator Naming

Simulator name is constructed at runtime as:

```
{simulator_prefix}-{worktree-basename}
```

If `simulator_prefix` is absent or empty, the name is just `{worktree-basename}`.

`simulator_prefix` is written into `config.toml` by bootstrap (defaulting to the scheme name) and can be changed manually at any time. The `boot` command reads it when creating the simulator.

---

## CLI UX

**Dependencies added:**
- `rich` — spinner, progress, colored output, config summary panel, error panels
- `InquirerPy` — fuzzy-search picker for interactive prompts

**Degradation:**
- `NO_COLOR` env var or `TERM=dumb`: `rich` strips ANSI automatically; `InquirerPy` falls back to numbered list + stdin input
- No TTY (pipe/agent): non-interactive mode, no prompts rendered

**Error presentation:** All user-facing errors use a `rich` panel:
```
╭─ Error ─────────────────────────────────────────────╮
│ Multiple Xcode projects found. Pass --project:      │
│   ios/MyApp.xcodeproj                               │
│   ios/Extension.xcodeproj                           │
╰─────────────────────────────────────────────────────╯
```

---

## Module Changes Summary

| Module | Change |
|--------|--------|
| `bootstrap.py` | Full rewrite: discovery logic, interactive + non-interactive modes, `--project`/`--scheme`/`--yes` flags |
| `boot.py` | Read `simulator_prefix` from config; remove hardcoded `Pulse-` prefix |
| `errors.py` | Rename `PulseIosError` → `WorktreeIosError` and subclasses |
| `paths.py` | Update hardcoded `pulse-ios-dev` strings → `worktree-ios-dev` |
| `config.py` | Add `simulator_prefix` field to `ProjectConfig`; update schema validation |
| `cli.py` | Update command name, help text, entry point |
| `proc.py` | No logic change |
| `simulator.py` | Remove `_pick_tty()`; replace with `InquirerPy` picker; use `simulator_prefix` from config |
| `xcodebuild.py` | No logic change |
| `runapp.py` | No logic change |
| `packages.py` | No logic change |
| `__init__.py` | Version bump |
| `pyproject.toml` | Rename package/command; add `rich`, `InquirerPy` deps |
| `tests/test_paths.py` | Update `pulse-ios-dev` string references |

---

## Installation

Unchanged workflow, new command name:

```bash
uv tool install --editable ./worktree_ios_dev
worktree-ios-dev --help
```

Or ephemeral via uvx once published to PyPI:

```bash
uvx worktree-ios-dev bootstrap
```
