---
name: worktree-ios-dev
description: Use when building, testing, running, or cleaning the Pulse iOS app or its local Swift packages — routes non-interactive work to `worktree-ios-dev` and reserves `xcodebuildmcp-cli` for debugging, UI automation, and log streaming.
---

# Worktree iOS Dev

Use `worktree-ios-dev` for every non-interactive iOS build task. Keep `xcodebuildmcp-cli` for debugging, UI automation, and log streaming.

## Decision

- **Build / test / run / clean / package test / wipe derived data / create-or-boot simulator** → `worktree-ios-dev <verb>`.
- **Debug sessions, breakpoints, log streaming, UI automation (tap / swipe / screenshot), archive, export IPA, TestFlight** → `xcodebuildmcp-cli` skill.
- **Never** use `swift test` for Pulse packages.

## One-time machine setup

```bash
uv tool install --editable /abs/path/to/pulse-dev-skills/worktree_ios_dev
```

Requires `uv` on `PATH` and `~/.local/bin` on `PATH`.

Upgrade with `uv tool upgrade worktree-ios-dev`. Editable installs pick up Python source edits automatically.

Optional: `brew install mint` enables `xcbeautify` for prettier `xcodebuild` output. The tool auto-detects `mint` on `PATH`; without it, builds still work but emit a one-line stderr note suggesting the install. `worktree-ios-dev doctor` reports mint status.

## Per-worktree setup

From anywhere inside the worktree:

```bash
worktree-ios-dev bootstrap     # creates worktree-ios-dev/, seeds config.toml, updates .gitignore
worktree-ios-dev boot          # first run: interactive picker; writes [simulator] to config.toml
```

## Verb reference

| Verb | Use for |
|---|---|
| `worktree-ios-dev bootstrap` | Scaffold `worktree-ios-dev/` in a new worktree. Idempotent. `--force` re-seeds `config.toml`. |
| `worktree-ios-dev boot` | Create (first run) or boot the per-worktree simulator. `--recreate` nukes and re-picks. `--all-devices` disables the iPhone 17 filter. |
| `worktree-ios-dev build` | `xcodebuild build` on the main app. `--release` flips configuration. `--scheme <name>` overrides. |
| `worktree-ios-dev test` | `xcodebuild test` on the main app. Pass `--only-testing <id>` / `--skip-testing <id>` through. |
| `worktree-ios-dev run` | Build → locate `.app` → `simctl install` → `simctl launch`. Prints the bundle id on success. |
| `worktree-ios-dev clean` | `xcodebuild clean` on the project. |
| `worktree-ios-dev wipe-derived` | `rm -rf worktree-ios-dev/derivedData`. Prompts unless `--yes`. |
| `worktree-ios-dev test-package <Name>` | Runs `xcodebuild test` against `ios/Packages/<Name>/Package.swift` with the saved simulator destination. |
| `worktree-ios-dev config` | Prints resolved config as JSON. Use for debugging. |
| `worktree-ios-dev doctor` | Sanity checks: config, tooling, simulator, project path. Also reports optional `mint` status (enables xcbeautify). Run this first when something's off. |

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

- For the **build and run** steps, use `worktree-ios-dev build` then `worktree-ios-dev run`.
- For **debug, UI automation, screenshots, log streaming**, use `xcodebuildmcp-cli`.
- If in doubt: build/test/run/clean go through `worktree-ios-dev`; anything interactive or introspective that touches a live app goes through `xcodebuildmcp-cli`.

## Common mistakes

- Running `worktree-ios-dev` anywhere without `bootstrap` first → exit 2 with discovery error. Run bootstrap.
- Skipping `boot` → any verb that needs a simulator errors with "run `worktree-ios-dev boot` first."
- Editing `[simulator].udid` by hand → prefer `worktree-ios-dev boot --recreate`.
- Using `xcodebuildmcp-cli` for a vanilla build/test → goes through the wrong path; use `worktree-ios-dev` instead.
