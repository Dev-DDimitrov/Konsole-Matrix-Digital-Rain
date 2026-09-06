#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
"""Reversible use of Plasma's stock Hide Cursor effect; no global input grab."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from matrix_config import runtime_dir

EFFECT_METADATA = Path("/usr/share/kwin-wayland/builtin-effects/hidecursor.json")
MARKER = runtime_dir() / "konsole-matrix-digital-rain-cursor.json"


def _run(command):
    return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False)


def _atomic(payload):
    MARKER.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".matrix-cursor.", dir=MARKER.parent, text=True)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.flush(); os.fsync(handle.fileno())
        os.replace(name, MARKER)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def _setting():
    sentinel = "__MATRIX_MISSING__"
    result = _run(["kreadconfig6", "--file", "kwinrc", "--group", "Plugins", "--key", "hidecursorEnabled", "--default", sentinel])
    value = result.stdout.strip()
    return None if value == sentinel else value


def _set_setting(value):
    if value is None:
        _run(["kwriteconfig6", "--file", "kwinrc", "--group", "Plugins", "--key", "hidecursorEnabled", "--delete"])
    else:
        _run(["kwriteconfig6", "--file", "kwinrc", "--group", "Plugins", "--key", "hidecursorEnabled", str(value)])
    _run(["gdbus", "call", "--session", "--dest", "org.kde.KWin", "--object-path", "/KWin", "--method", "org.kde.KWin.reconfigure"])


def _effect_loaded():
    result = _run(["gdbus", "call", "--session", "--dest", "org.kde.KWin", "--object-path", "/Effects", "--method", "org.kde.kwin.Effects.isEffectLoaded", "hidecursor"])
    return "true" in result.stdout.lower()


def available():
    return EFFECT_METADATA.is_file() and _run(["gdbus", "introspect", "--session", "--dest", "org.kde.KWin", "--object-path", "/Effects"]).returncode == 0


def restore_stale():
    if not MARKER.exists():
        return False
    try:
        payload = json.loads(MARKER.read_text(encoding="utf-8"))
        if payload.get("owner") != "konsole-matrix-digital-rain":
            return False
        _set_setting(payload.get("hidecursor_enabled"))
        if not payload.get("effect_loaded", False):
            _run(["gdbus", "call", "--session", "--dest", "org.kde.KWin", "--object-path", "/Effects", "--method", "org.kde.kwin.Effects.unloadEffect", "hidecursor"])
    finally:
        try:
            MARKER.unlink()
        except FileNotFoundError:
            pass
    return True


def activate(show_cursor=False):
    restore_stale()
    if show_cursor or not available():
        return False
    payload = {"owner": "konsole-matrix-digital-rain", "hidecursor_enabled": _setting(), "effect_loaded": _effect_loaded()}
    _atomic(payload)
    _set_setting("true")
    _run(["gdbus", "call", "--session", "--dest", "org.kde.KWin", "--object-path", "/Effects", "--method", "org.kde.kwin.Effects.loadEffect", "hidecursor"])
    return True


def restore():
    return restore_stale()


def status():
    return {"available": available(), "stale_override": MARKER.exists(), "setting": _setting()}
