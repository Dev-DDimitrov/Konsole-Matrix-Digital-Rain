#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
"""Safe local user-preset management for Matrix visual settings."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import matrix_config as config


def joined(values):
    return " ".join(values)


def main():
    parser = argparse.ArgumentParser(description="Manage Matrix user visual presets.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    show = sub.add_parser("show"); show.add_argument("name", nargs="+")
    delete = sub.add_parser("delete"); delete.add_argument("name", nargs="+")
    rename = sub.add_parser("rename"); rename.add_argument("old"); rename.add_argument("new")
    save = sub.add_parser("save"); save.add_argument("name", nargs="+"); save.add_argument("--from-last", action="store_true"); save.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "list":
            print("BUILT-IN PRESETS")
            for name in config.PRESETS: print(f"  {name}")
            print("USER PRESETS")
            for name in config.load_user_presets(): print(f"  {name}")
        elif args.command == "show":
            name = config.normalize_preset_name(joined(args.name))
            if name in config.PRESETS: values = config.PRESETS[name]
            else: values = config.load_user_presets().get(name)
            if values is None: raise config.ConfigError(f"unknown preset: {name}")
            print(name)
            for key in sorted(values): print(f"  {key} = {values[key]}")
        elif args.command == "delete":
            config.delete_user_preset(joined(args.name)); print("deleted")
        elif args.command == "rename":
            old = config.normalize_preset_name(args.old); new = config.normalize_preset_name(args.new)
            values = config.load_user_presets().get(old)
            if values is None: raise config.ConfigError(f"user preset does not exist: {old}")
            config.save_user_preset(new, values, display_name=args.new)
            config.delete_user_preset(old); print(new)
        elif args.command == "save":
            if not args.from_last: raise config.ConfigError("use --from-last; live renderer saving is intentionally not interactive")
            name = joined(args.name)
            print(config.save_user_preset(name, config.load_last_effective(), display_name=name, force=args.force))
    except config.ConfigError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
