---
name: worktree-ios-dev
description: Use when building, testing, running, or cleaning the Pulse iOS app or its local Swift packages — routes non-interactive work to `worktree-ios-dev-tool` and reserves `xcodebuildmcp-cli` for debugging, UI automation, and log streaming.
---

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
uv tool install --editable /abs/path/to/worktree-ios-dev-tool/worktree_ios_dev_tool
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
