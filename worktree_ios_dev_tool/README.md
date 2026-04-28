# worktree-ios-dev-tool

Per-worktree iOS build / simulator / test CLI. Each git worktree gets its own simulator and derived-data directory so parallel feature branches never collide.

## Install

Once per machine, from GitHub:

```bash
uv tool install "git+https://github.com/yi-jiang-applovin/pulse-dev-skills.git#subdirectory=worktree_ios_dev_tool"
```

Upgrade to the latest `main` (`uv upgrade` caches the resolved commit — use `--reinstall`):

```bash
uv tool install --reinstall "git+https://github.com/yi-jiang-applovin/pulse-dev-skills.git#subdirectory=worktree_ios_dev_tool"
```

Local development (editable, picks up source edits automatically):

```bash
uv tool install --editable /abs/path/to/pulse-dev-skills/worktree_ios_dev_tool
```

Requires `uv` and `~/.local/bin` on `PATH`. Optional: `brew install mint` enables `xcbeautify` for prettier build output.

## Per-worktree setup

Run once from anywhere inside the worktree:

```bash
worktree-ios-dev-tool bootstrap   # scaffold worktree-ios-dev/, write config.toml, update .gitignore
worktree-ios-dev-tool boot        # create and boot the per-worktree simulator
```

`bootstrap` discovers the Xcode project and scheme interactively, then writes `worktree-ios-dev/config.toml`. `boot` creates a simulator named `<simulator_prefix>-<sanitized-branch>-iPhone17Pro` and boots it.

Interactive output uses a clack-style step format:

```
◇  Project: ios/Pulse.xcodeproj
⠋  Fetching schemes...
◇  Scheme: Pulse
│
◆  worktree-ios-dev/config.toml written
│  project          = ios/Pulse.xcodeproj
│  scheme           = Pulse
│  simulator_prefix = Pulse
│
◆  Next: worktree-ios-dev-tool boot
```

Non-interactive (agent / non-TTY) output uses flat `[worktree-ios-dev-tool] <msg>` lines instead.

## Verb reference

| Verb | Description |
|---|---|
| `bootstrap` | Scaffold `worktree-ios-dev/` and seed `config.toml`. Idempotent; `--force` re-seeds. |
| `boot` | Create (first run) or boot the per-worktree simulator. `--recreate` nukes and re-picks. `--all-devices` disables the iPhone 17 Pro filter. |
| `build` | `xcodebuild build`. `--release` switches configuration. `--scheme <name>` overrides. |
| `test` | `xcodebuild test`. Accepts `--only-testing <id>` / `--skip-testing <id>`. |
| `run` | Build → install → launch on the per-worktree simulator. Prints bundle id on success. |
| `clean` | `xcodebuild clean`. |
| `wipe-derived` | Delete `worktree-ios-dev/derivedData`. Prompts unless `--yes`. |
| `test-package <Name>` | `xcodebuild test` against `ios/Packages/<Name>/Package.swift`. |
| `config` | Print resolved config as JSON (useful for debugging). |
| `doctor` | Check config, toolchain, simulator, and optional `mint` status. Run first when something is off. |

## Global flags

- `--config <path>` — override walk-up config discovery.
- `-v` / `--verbose` — stream subprocess output and show tracebacks on error.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | OK |
| `1` | User error (bad args, bad config, refused verb) |
| `2` | Environment error (config not found, missing toolchain) |
| `3` | Subprocess failure (xcodebuild / simctl non-zero) |

## Agent (non-interactive) usage

The tool detects a non-TTY environment automatically and switches to flat `[worktree-ios-dev-tool] <msg>` output instead of the clack-style step format.

For `bootstrap`, supply `--project` and `--scheme` explicitly — without them, ambiguity causes an immediate error exit. Add `--yes` to suppress any remaining prompts:

```bash
worktree-ios-dev-tool bootstrap \
  --project ios/Pulse.xcodeproj \
  --scheme Pulse \
  --yes
```

All other verbs (`build`, `test`, `run`, `clean`, etc.) are non-interactive by design — no extra flags needed.

## Why is `bootstrap` slow the first time?

Scheme discovery runs `xcodebuild -list -project ... -json`, which triggers Xcode to parse the project on cold start — expect 10–30 seconds on a large project. Subsequent runs are faster due to Xcode's internal cache.

Skip it entirely by passing `--scheme` directly:

```bash
worktree-ios-dev-tool bootstrap --scheme Pulse
```

## Config file

`worktree-ios-dev/config.toml` (gitignored) is the source of truth for a worktree. Example:

```toml
[project]
path             = "ios/Pulse.xcodeproj"
scheme           = "Pulse"
configuration    = "Debug"
simulator_prefix = "Pulse"

[packages_root]
path = "ios/Packages"

[extras]
xcodebuild_flags = []
```

Edit by hand or re-run `bootstrap --force` to regenerate. Run `worktree-ios-dev-tool boot --recreate` to repick the simulator without touching the rest of the config.
