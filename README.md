# worktree-ios-dev-tool

Per-worktree iOS build / simulator / test CLI plus the `worktree-ios-dev` skill that drives it.

Each git worktree gets its own simulator(s) and derived-data directory so parallel feature branches never collide. This repo holds both the Python CLI (`uv tool install`) and the skill that tells coding agents when to pick this tool over `xcodebuildmcp-cli`.

## Layout

- [`worktree_ios_dev_tool/`](worktree_ios_dev_tool/) — Python CLI package (`worktree-ios-dev-tool`); see its README for install/usage.
- [`skills/worktree-ios-dev/`](skills/worktree-ios-dev/) — skill consumed by Claude Code / Cursor / Codex.
- `docs/` — design specs and implementation plans (historical record; references to `pulse-dev-skills` paths reflect the repo of origin).

## Install the CLI

```bash
uv tool install "git+https://github.com/yjmeqt/worktree-ios-dev-tool.git#subdirectory=worktree_ios_dev_tool"
```

See [`worktree_ios_dev_tool/README.md`](worktree_ios_dev_tool/README.md) for upgrade, editable-install, and per-worktree setup steps.

## Install the skill

From any worktree:

```bash
npx skills add yjmeqt/worktree-ios-dev-tool
```

This populates `.claude/skills/worktree-ios-dev/` (and `.agents/skills/worktree-ios-dev/`) via symlinks into the local skills cache. Run `npx skills update` after pushing skill edits.
