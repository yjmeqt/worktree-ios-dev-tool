# worktree_ios_dev_tool/src/worktree_ios_dev_tool/cli.py
"""worktree-ios-dev-tool — argparse dispatcher + verb handlers."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import bootstrap, config as config_mod, packages as packages_mod, simulator as sim_mod, xcodebuild
from .errors import EnvError, WorktreeIosError
from .paths import find_config
from .proc import run


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, default=None, help="Path to config.toml (overrides walk-up discovery).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Stream subprocess output and show tracebacks.")


def _load_config(args: argparse.Namespace) -> config_mod.Config:
    path = args.config.resolve() if args.config else find_config()
    return config_mod.load(path)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="worktree-ios-dev-tool", description="iOS worktree build / sim / test CLI.")
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
        scheme_override=args.scheme,
        only_testing=args.only_testing,
        skip_testing=args.skip_testing,
    )
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
            problems.append("No [simulator] block. Run `worktree-ios-dev-tool boot`.")
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
