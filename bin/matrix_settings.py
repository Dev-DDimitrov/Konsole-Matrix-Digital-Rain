#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
"""User-facing, atomic management for Matrix defaults and exit guard."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import matrix_config as config


def effective_settings():
    values, _ = config.load_config()
    return values


def show():
    values = effective_settings()
    print("GLOBAL USER DEFAULTS")
    for key in config.DEFAULTS:
        print(f"  {key} = {values.get(key, config.DEFAULTS[key])}")
    print(f"  respect_idle_inhibitors = {values.get('respect_idle_inhibitors', True)}")
    print("\nMATRIX-ALL")
    for key, default in config.MATRIX_ALL_DEFAULTS.items():
        print(f"  matrix_all.{key} = {values.get('matrix_all', {}).get(key, default)}")
    print("\nEXIT GUARD (UI guard only; not a security lock)")
    for key, default in config.EXIT_GUARD_DEFAULTS.items():
        print(f"  exit_guard.{key} = {values.get('exit_guard', {}).get(key, default)}")
    print("\nSETTINGS LOCK")
    for key, default in config.SETTINGS_LOCK_DEFAULTS.items():
        print(f"  settings_lock.{key} = {values.get('settings_lock', {}).get(key, default)}")
    print("\nBUILT-IN PRESETS")
    for name in config.PRESETS:
        print(f"  {name}")
    print("\nUSER PRESETS")
    user = config.load_user_presets()
    if user:
        for name in user:
            print(f"  {name}")
    else:
        print("  (none)")


def get(key):
    table, leaf = config.settings_key(key)
    values = effective_settings()
    if table == "rain":
        value = values.get(leaf, config.DEFAULTS[leaf])
    elif table == "exit_guard":
        value = values.get("exit_guard", {}).get(leaf, config.EXIT_GUARD_DEFAULTS[leaf])
    elif table == "matrix_all":
        value = values.get("matrix_all", {}).get(leaf, config.MATRIX_ALL_DEFAULTS[leaf])
    elif table == "settings_lock":
        value = values.get("settings_lock", {}).get(leaf, config.SETTINGS_LOCK_DEFAULTS[leaf])
    else:
        value = values.get(leaf, True)
    print(value)


def set_value(key, value):
    table, leaf, parsed = config.parse_setting(key, value)
    config._update_toml_key(config.CONFIG_PATH, table, leaf, parsed)
    print(f"set {key} = {parsed}")


def reset(key):
    table, leaf = config.settings_key(key)
    config._update_toml_key(config.CONFIG_PATH, table, leaf, None, reset=True)
    print(f"reset {key} to the built-in default")


def main():
    parser = argparse.ArgumentParser(description="Manage Konsole-Matrix-Digital-Rain user defaults.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("show")
    sub.add_parser("path")
    get_parser = sub.add_parser("get"); get_parser.add_argument("key")
    set_parser = sub.add_parser("set"); set_parser.add_argument("key"); set_parser.add_argument("value")
    reset_parser = sub.add_parser("reset"); reset_parser.add_argument("key")
    guard = sub.add_parser("exit-guard")
    guard_sub = guard.add_subparsers(dest="guard_command", required=True)
    guard_sub.add_parser("show")
    guard_sub.add_parser("enable")
    guard_sub.add_parser("disable")
    bind = guard_sub.add_parser("bind"); bind.add_argument("binding")
    args = parser.parse_args()
    try:
        if args.command == "show": show()
        elif args.command == "path": print(config.CONFIG_PATH)
        elif args.command == "get": get(args.key)
        elif args.command == "set": set_value(args.key, args.value)
        elif args.command == "reset": reset(args.key)
        elif args.guard_command == "show":
            get("exit_guard.enabled"); get("exit_guard.binding")
        elif args.guard_command == "enable": set_value("exit_guard.enabled", "true")
        elif args.guard_command == "disable": set_value("exit_guard.enabled", "false")
        elif args.guard_command == "bind": set_value("exit_guard.binding", args.binding)
    except config.ConfigError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
