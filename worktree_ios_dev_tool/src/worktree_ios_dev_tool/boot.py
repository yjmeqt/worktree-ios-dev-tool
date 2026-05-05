# worktree_ios_dev_tool/src/worktree_ios_dev_tool/boot.py
"""Implementation of the `boot` verb."""
from __future__ import annotations

import argparse

from . import simulator as sim_mod, ui
from .config import SimulatorEntry, load, write_simulator
from .errors import UserError
from .paths import find_config


def run(args: argparse.Namespace) -> int:
    cfg_path = args.config.resolve() if args.config else find_config()
    cfg = load(cfg_path)

    sim_mod.ensure_tooling()

    existing = cfg.simulators.get("default")
    need_first_run = (
        existing is None
        or sim_mod.find_device_by_udid(existing.udid) is None
        or args.recreate
    )

    if args.recreate and existing is not None:
        dev = sim_mod.find_device_by_udid(existing.udid)
        if dev is not None:
            ui.step(f"Deleting {existing.name} ({existing.udid})…")
            sim_mod.delete(existing.udid)

    if not need_first_run:
        assert existing is not None
        sim_mod.boot(existing.udid)
        ui.done(f"Booted {existing.name} ({existing.udid}).")
        return 0

    # First run: pick + create + persist + boot.
    device, runtime = sim_mod.pick_device_and_runtime(iphone_17_only=not args.all_devices)

    prefix = cfg.project.simulator_prefix or cfg.project.scheme
    sim_name = f"{prefix}-{cfg.worktree_root.name}"

    existing = sim_mod.find_device_by_name(sim_name)
    if existing is not None:
        ui.warn(f"Simulator named '{sim_name}' already exists (udid={existing['udid']}).")
        choice = input("Reuse it? [Y/n] ").strip().lower()
        if choice in ("", "y", "yes"):
            udid = existing["udid"]
        else:
            raise UserError("Aborted. Delete the existing sim manually or use --recreate next time.")
    else:
        ui.step(f"Creating {sim_name}…")
        udid = sim_mod.create(sim_name, device, runtime)

    sim_cfg = SimulatorEntry(name=sim_name, udid=udid, device=device.name, runtime=runtime.name)
    write_simulator(cfg_path, sim_cfg)

    sim_mod.boot(udid)

    ui.sep()
    ui.done("Simulator ready")
    ui.info(f"name    = {sim_cfg.name}")
    ui.info(f"udid    = {sim_cfg.udid}")
    ui.info(f"device  = {sim_cfg.device}")
    ui.info(f"runtime = {sim_cfg.runtime}")

    return 0
