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
    ("matrix-doctor", "Run read-only Fedora/KDE/Matrix diagnostics."),
    ("matrix-guide", "Show this command, option, and control reference."),
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
    ("r", "restore the startup settings"),
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
