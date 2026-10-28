#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
"""Terminal reference generated from the Matrix utility's public metadata."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from matrix_config import CYCLE_SPEEDS, EXIT_GUARD_DEFAULTS, MATRIX_ALL_DEFAULTS, PRESETS, load_config, load_user_presets
from matrix_guide_data import (COLORS_INFO, COMMANDS, CONTROLS, LOCK_COMMANDS,
                               PRESET_DESCRIPTIONS, SAVER_MODES)


def heading(title):
    print(f"\n{title.upper()}\n")


def commands():
    heading("Commands")
    for name, description in COMMANDS:
        print(f"{name:<16} {description}")


def controls():
    heading("Live controls")
    for key, description in CONTROLS:
        print(f"{key:<25} {description}")
    print("\np / P freezes rain, mutations, hue, and all animation.")
    print("h / H freezes only the interpolated hue/cycle phase; rain and mutations continue.")
    print("c enables/disables gradual cycling; C reverses its derivative without moving the current hue.")
    print("Ctrl+L locks only live visual settings; p/P, exits, ?, and practical status control remain available.")


def colors():
    heading("Colors")
    for key, description in COLORS_INFO:
        print(f"{key:<4} {description}")
    print("Direct colors disable cycling. Trails retain bright-to-dark xterm-256 shading.")
    print("Background modes: profile, black, charcoal, white, translucent.")


def presets():
    heading("Presets")
    for name in PRESETS:
        print(f"{name:<12} {PRESET_DESCRIPTIONS.get(name, 'named visual preset')}")
    user = load_user_presets()
    if user:
        print("\nUser presets:")
        for name in user:
            print(f"{name:<12} local visual preset")
    print("Names normalize to lowercase with _ separators: Night Blue = night_blue = night-blue.")


def cycle():
    heading("Color cycling")
    print("--color-cycle enables gradual cycling; it is off by default.")
    print("--cycle-period SECONDS is the exact advanced full-cycle duration.")
    print("--cycle-speed takes precedence below preset/config, but an explicit period wins:")
    for name, seconds in CYCLE_SPEEDS.items():
        print(f"{name:<12} {int(seconds)} seconds")
    print("The expanded spectrum is normalized by explicit family phase spans, not anchor count.")


def saver():
    heading("Saver modes")
    for name, description in SAVER_MODES:
        print(f"{name:<12} {description}")
    print("visual-only = visual effect, no security; immediate/after use KDE's real lock handoff.")
    print("Automatic mode needs a reliable session-idle source; --once never needs one.")
    print("Recommended one-shot forms: matrix-saver visual-only | immediate | after.")
    print("Legacy matrix-saver --once --lock-mode immediate --dry-run remains supported.")


def lockscreen():
    heading("Lock screen")
    print("The KDE lock screen can show live Matrix rain as its wallpaper, with an")
    print("independent profile and GPU-rendered terminal-pace rain. Every monitor rains")
    print("independently while the hue stays synchronized. KDE authentication is never modified.")
    print("")
    for command, description in LOCK_COMMANDS:
        print(f"{command:<38} {description}")
    print("")
    print("Exact hue workflow: matrix-lock configure -> press c to cycle -> press h at the")
    print("perfect moment -> exit with q -> choose to save as the active configuration, a")
    print("named preset, or both. The held hue is captured exactly.")
    print("Named presets keep friendly names (\"Neon Purple\" lists as typed, stored as")
    print("neon_purple), capture the full visual look including exact HEX color, cycling,")
    print("hue exclusions, pacing, trails, and render mode, and never carry")
    print("resource-protection settings.")
    print("")
    print("Custom hue cycle: while cycling in matrix-lock configure, press x when an")
    print("unwanted hue range begins and x again when it ends; the cycle then bridges the")
    print("retained endpoints with a short smooth crossfade (no jump, no flicker, and the")
    print("omitted range is never traversed). u/U undo/redo edits, X clears exclusions,")
    print("r resets the session; nothing persists until you choose to save on exit.")
    print("Numerically: matrix-lock cycle exclude add 45 105 (hue degrees; --phase for")
    print("exact 0-1 cycle positions, --blend for the crossfade seconds), then list,")
    print("remove ID, enable/disable ID, set-blend ID SECS, clear, or cycle reset.")
    print("Edit a saved preset live with matrix-lock configure --preset NAME.")
    print("Built-in presets:")
    for name, description in PRESET_DESCRIPTIONS.items():
        print(f"  {name:<12} {description}")
    print("Cycling starts from the saved hue and stays synchronized across monitors.")
    print("Changes apply on the next lock; matrix-lock preview --greeter tests safely first.")
    print("Lock-screen saves never change terminal Matrix settings, and vice versa.")
    print("")
    print("Adaptive resource protection (on by default) freezes the rain while overall")
    print("system CPU or memory use is excessive and resumes it when the system recovers;")
    print("the terminal renderer honors the same [resource_guard] settings in config.toml")
    print("and never overrides a manual pause. matrix-lock doctor shows a live reading.")


def settings():
    heading("Settings and precedence")
    print("Precedence: explicit CLI option > explicit preset > user default > built-in default.")
    print("Use matrix-settings show|get|set|reset|path; ordinary configuration never requires TOML editing.")
    print("matrix-settings show separates global defaults, built-ins, and user presets.")
    values, _ = load_config()
    guard = values.get("exit_guard", EXIT_GUARD_DEFAULTS)
    print(f"Current exit_guard: enabled={guard.get('enabled', False)} binding={guard.get('binding', 'Ctrl+Y')}")
    print("exit_guard is disabled by public default and is not authentication or a screen lock.")
    print("When enabled, q/Escape/Space/Ctrl+C are guarded; the configured binding exits matrix-all.")
    matrix_all = values.get("matrix_all", MATRIX_ALL_DEFAULTS)
    print(f"matrix_all.hide_mouse_cursor = {matrix_all.get('hide_mouse_cursor', True)}; use matrix-all --show-cursor to opt out.")
    print("settings_lock.enabled controls the session-start preference lock; live Ctrl+L is temporary.")
    print("KDE/kscreenlocker remains the only security boundary. Plain Space is never a guard binding.")


def examples():
    heading("Examples")
    for command in (
        "matrix",
        "matrix --preset ambient",
        "matrix --color cyan --color-cycle --cycle-speed slow",
        "matrix-full --preset dense",
        "matrix-all --preset cyber",
        "matrix-saver --once --lock-mode visual-only",
        "matrix-saver visual-only",
        "matrix-settings set speed 96",
        "matrix-preset save \"Night Blue\" --from-last",
        "matrix-saver --once --lock-mode immediate --dry-run",
        "matrix-lock configure",
        "matrix-lock set color \"#8B5CF6\"",
        "matrix-lock preview --greeter",
        "matrix-doctor",
    ):
        print(f"  {command}")


def main():
    parser = argparse.ArgumentParser(
        description="Complete Konsole-Matrix-Digital-Rain command and control guide."
    )
    parser.add_argument("--commands", action="store_true")
    parser.add_argument("--controls", action="store_true")
    parser.add_argument("--colors", action="store_true")
    parser.add_argument("--presets", action="store_true")
    parser.add_argument("--saver", action="store_true")
    parser.add_argument("--lock", action="store_true")
    parser.add_argument("--examples", action="store_true")
    parser.add_argument("--settings", action="store_true")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    selected = any(vars(args).values())
    show_all = args.full or not selected
    if show_all or args.commands:
        commands()
    if show_all or args.controls:
        controls()
    if show_all or args.colors:
        colors()
    if show_all or args.presets:
        presets()
    if show_all or args.saver:
        saver()
    if show_all or args.lock:
        lockscreen()
    if show_all or args.settings:
        settings()
    if show_all or args.examples:
        cycle()
        examples()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
