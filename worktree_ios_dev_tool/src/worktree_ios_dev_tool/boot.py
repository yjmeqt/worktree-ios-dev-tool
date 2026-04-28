# worktree_ios_dev_tool/src/worktree_ios_dev_tool/boot.py
"""Implementation of the `boot` verb."""
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

    prefix = cfg.project.simulator_prefix or cfg.project.scheme
    sim_name = f"{prefix}-{cfg.worktree_root.name}"

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
