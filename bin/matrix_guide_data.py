#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
"""Canonical public command/control metadata for the Matrix utility."""

from __future__ import annotations

from matrix_config import COLORS, CYCLE_SPEEDS, PRESETS


COMMANDS = (
    ("matrix", "Run cinematic Matrix rain in the current terminal."),
    ("matrix-konsole", "Open a dedicated clean Matrix Konsole window."),
    ("matrix-full", "Run one UI-free fullscreen Matrix display."),
    ("matrix-all", "Run synchronized fullscreen Matrix rain across enabled displays; --show-cursor opts out of cursor hiding."),
    ("matrix-preview", "Preview a palette or preset in a normal Konsole window."),
    ("matrix-saver", "Run the idle-aware visual and secure saver controller."),
    ("matrix-settings", "Show and atomically manage global Matrix defaults, background, settings_lock, and exit_guard."),
    ("matrix-preset", "List, save, show, rename, or delete local user visual presets."),
    ("matrix-lock", "Configure the animated Matrix KDE lock-screen wallpaper (profile, hue, history, enable/disable)."),
    ("matrix-doctor", "Run read-only Fedora/KDE/Matrix diagnostics."),
    ("matrix-guide", "Show this command, option, and control reference."),
    ("matrix-help", "Alias for matrix-guide; accepts the same options."),
)


# Lock-screen workflow reference presented by matrix-guide --lock.
PRESET_DESCRIPTIONS = {
    "cinematic": "default high-quality green Matrix look",
    "classic": "traditional UniMatrix/CMatrix-inspired appearance",
    "ambient": "slower, lower-intensity rainfall",
    "dense": "denser rainfall",
    "minimal": "sparse and subtle rainfall",
    "cyber": "cyan-oriented colorful cycling preset",
}

LOCK_COMMANDS = (
    ("matrix-lock configure", "live preview with normal Matrix controls; offers to save on exit"),
    ("matrix-lock preview [--greeter]", "preview the profile; --greeter runs the real KDE greeter in safe testing mode"),
    ("matrix-lock save [--from-last]", "save the profile; --from-last imports the latest effective terminal settings"),
    ("matrix-lock show", "display the active lock-screen settings"),
    ("matrix-lock set hue 270", "set an exact hue in degrees (0-359)"),
    ("matrix-lock set color \"#8B5CF6\"", "set an exact HEX color or a named Matrix color"),
    ("matrix-lock set color-cycle on|off", "enable or disable automatic hue cycling"),
    ("matrix-lock capture-hue", "capture the hue most recently held with h in a Matrix session"),
    ("matrix-lock preset save \"Neon Purple\"", "save the current look as a named preset (friendly names kept)"),
    ("matrix-lock preset list|show|apply NAME", "named presets; built-ins stay read-only, undo reverses apply"),
    ("matrix-lock preset rename OLD NEW", "rename a user preset; delete NAME removes one"),
    ("matrix-lock quality [NAME]", "show or apply a rendering preset (balanced/high/battery); colors stay untouched"),
    ("matrix-lock cycle show", "hue-cycle state: exclusions, blends, visible spectrum, loop duration"),
    ("matrix-lock cycle exclude add 45 105", "exclude hues 45°-105° (degrees; --phase for exact 0-1 positions, --blend seconds)"),
    ("matrix-lock cycle exclude list|remove ID", "list exclusions; remove/enable/disable ID, set-blend ID SECS, clear"),
    ("matrix-lock cycle reset", "remove all cycle customization; matrix-lock undo reverses it"),
    ("matrix-lock configure --preset NAME", "edit a named preset live; update it, fork it, or apply on exit"),
    ("matrix-lock set resource-guard on|off", "auto-freeze the animation while system CPU/memory use is excessive"),
    ("matrix-lock set guard-cpu-pause 85", "guard thresholds: guard-mem-pause, guard-cpu/mem-resume, guard-pause/resume-secs"),
    ("matrix-lock history", "list saved lock-screen revisions"),
    ("matrix-lock undo", "restore the previous lock-screen revision"),
    ("matrix-lock restore REV", "restore a specific revision from history"),
    ("matrix-lock enable|disable", "activate the Matrix lock wallpaper or restore the previous one"),
    ("matrix-lock status|doctor", "installation state and read-only diagnostics"),
)


COLORS_INFO = (
    ("1", "green"),
    ("2", "red"),
    ("3", "blue"),
    ("4", "white / monochrome"),
    ("5", "yellow / amber"),
    ("6", "cyan"),
    ("7", "magenta"),
)

SETTINGS_LOCK_ALLOWED_KEYS = frozenset(("?", "o"))


# Every public interactive renderer key is represented here. Keep this list
# beside the generated help so tests can catch undocumented new controls.
CONTROLS = (
    ("1", "select green"),
    ("2", "select red"),
    ("3", "select blue"),
    ("4", "select white / monochrome"),
    ("5", "select yellow / amber"),
    ("6", "select cyan"),
    ("7", "select magenta"),
    ("0", "reset hue/cycle phase to the canonical Matrix green anchor"),
    ("b", "cycle profile/black/charcoal/white/translucent background"),
    ("c", "toggle gradual color cycling"),
    ("C", "reverse color-cycle direction from the exact current phase"),
    ("h / H", "toggle hue hold/play while rain and mutations continue"),
    ("x", "mark hue-exclusion start, then press again at the end (while cycling; works paused)"),
    ("X", "clear all hue exclusions (or cancel a pending mark)"),
    ("u / U", "undo / redo the most recent visual edit (session-local, bounded)"),
    ("Alt+Left / Alt+Right", "nudge hue backward/forward and hold it"),
    ("v", "slower color cycle"),
    ("V", "faster color cycle"),
    ("p / P", "pause/resume the entire animation"),
    ("+ / = / Right", "increase Matrix speed"),
    ("- / _ / Left", "decrease Matrix speed"),
    ("] / Up", "increase Matrix speed by a larger step"),
    ("[ / Down", "decrease Matrix speed by a larger step"),
    ("t / T", "decrease/increase trail length"),
    ("d / D", "decrease/increase rainfall density"),
    ("f", "toggle flashers (disabled by reduced-motion)"),
    ("a", "toggle asynchronous stream timing"),
    ("w", "cycle white leading heads: 75% -> 50% -> 25% -> 0%"),
    ("Ctrl+L", "lock/unlock live visual settings"),
    (", / .", "decrease/increase fade levels"),
    ("o", "toggle status messages"),
    ("r", "reset the editing session to its startup settings (undoable with u)"),
    ("S", "record effective visual settings for matrix-preset save NAME --from-last"),
    ("?", "show the short in-renderer control hint"),
    ("q / Escape / Space / Ctrl+C", "exit unless optional exit_guard is enabled"),
)


SAVER_MODES = (
    ("visual-only", "visual Matrix saver; exit returns to the unlocked desktop"),
    ("immediate", "invoke the real KDE lock immediately; no visual child is needed"),
    ("after", "show Matrix first, then lock on timeout or any early exit/activity"),
)


def renderer_help_text():
    return (
        "Live controls are documented by matrix-guide. "
        "Key essentials: p/P pause all; h/H hold hue; Alt+Left/Right nudge hue; "
        "b backgrounds; Ctrl+L settings lock; q/Escape/Space exit."
    )


def saver_help_text():
    return (
        "Modes: visual-only returns unlocked; immediate locks now; "
        "after locks on timeout or early exit. Use matrix-saver immediate, "
        "after, or visual-only for concise one-shot use; --dry-run to inspect "
        "the lock handoff without locking. See matrix-guide --saver."
    )
