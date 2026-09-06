#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
"""Shared, dependency-free configuration and xterm-256 palette helpers."""

from __future__ import annotations

import colorsys
import json
import os
import re
import stat
import tempfile
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Fedora's supported Python has it
    tomllib = None


CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "konsole-matrix-digital-rain"
CONFIG_PATH = CONFIG_DIR / "config.toml"
PRESET_DIR = CONFIG_DIR / "presets"
LAST_EFFECTIVE_PATH = CONFIG_DIR / "last-effective.toml"

DEFAULTS = {
    "speed": 96,
    "trail_min": 16,
    "trail_max": 38,
    "density": 52,
    "fade_levels": 6,
    "white_head_rate": 75,
    "mutation_rate": 0.8,
    "asynchronous": True,
    "flashers": True,
    "black_background": False,
    "background": "profile",
    "color": "green",
    "color_cycle": False,
    "cycle_period": 72.0,
    "cycle_speed": "normal",
    "cycle_direction": "forward",
    "fps_cap": 60,
    "reduced_motion": False,
    # These are visual state, not global animation pause state. They are
    # intentionally safe to persist in a user preset.
    "hue_hold": False,
    "cycle_phase": 0.0,
    "manual_hue_step": 0.015,
}

EXIT_GUARD_DEFAULTS = {"enabled": False, "binding": "Ctrl+Y"}
MATRIX_ALL_DEFAULTS = {"hide_mouse_cursor": True}
SETTINGS_LOCK_DEFAULTS = {"enabled": False}
BACKGROUND_MODES = ("profile", "black", "charcoal", "white", "translucent")

CYCLE_SPEEDS = {
    "very-slow": 144.0,
    "slow": 108.0,
    "normal": 72.0,
    "fast": 36.0,
}

PRESETS = {
    "cinematic": {},
    "classic": {
        "speed": 82, "trail_min": 10, "trail_max": 28,
        "density": 60, "fade_levels": 5, "white_head_rate": 35,
        "mutation_rate": 0.4,
    },
    "ambient": {
        "speed": 62, "trail_min": 14, "trail_max": 34,
        "density": 34, "mutation_rate": 0.2, "fps_cap": 45,
    },
    "dense": {
        "speed": 92, "trail_min": 18, "trail_max": 42,
        "density": 78,
    },
    "minimal": {
        "speed": 72, "trail_min": 8, "trail_max": 20,
        "density": 22, "fade_levels": 4, "white_head_rate": 45,
        "mutation_rate": 0.1, "fps_cap": 45,
    },
    "cyber": {
        "color": "cyan", "color_cycle": True, "cycle_speed": "slow",
        "density": 58,
    },
}

COLORS = ("green", "red", "blue", "white", "yellow", "cyan", "magenta")
COLOR_RGB = {
    "green": (0, 255, 0),
    "red": (255, 0, 0),
    "blue": (0, 96, 255),
    "white": (238, 238, 238),
    "yellow": (255, 190, 0),
    "cyan": (0, 220, 220),
    "magenta": (220, 0, 220),
}


class ConfigError(ValueError):
    pass


def normalize_preset_name(value):
    """Return a safe canonical name, or reject a filesystem escape attempt."""
    if not isinstance(value, str):
        raise ConfigError("preset name must be text")
    raw = value.strip()
    if not raw or any(char in raw for char in "/\\\0") or raw in (".", ".."):
        raise ConfigError("preset name must use letters/numbers separated by spaces, _ or -")
    canonical = re.sub(r"[\s_-]+", "_", raw.lower()).strip("_")
    if not canonical or not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", canonical):
        raise ConfigError("preset name must use letters/numbers separated by spaces, _ or -")
    return canonical


def normalize_binding(value):
    if not isinstance(value, str):
        raise ConfigError("exit_guard.binding must be text")
    compact = re.sub(r"\s+", "", value)
    match = re.fullmatch(r"(?:(ctrl|shift)\+)?([A-Za-z])", compact, re.I)
    if not match:
        raise ConfigError("exit_guard.binding must be Ctrl+LETTER or Shift+LETTER")
    modifier, letter = match.groups()
    if not modifier:
        raise ConfigError("exit_guard.binding requires Ctrl+ or Shift+")
    canonical = f"{modifier.title()}+{letter.upper()}"
    # Ordinary Matrix exit inputs must never weaken the guard.
    if canonical in {"Ctrl+C", "Ctrl+L", "Ctrl+Q", "Shift+Q"}:
        raise ConfigError(f"exit_guard.binding {canonical} conflicts with an ordinary Matrix exit input")
    return canonical


def clamp(value, low, high):
    return max(low, min(high, value))


def _table(data, name):
    value = data.get(name, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"[{name}] must be a table")
    return value


def _toml_literal(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value))


def _atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _update_toml_key(path, table, key, value, reset=False):
    """Small comment-preserving updater for this utility's ordinary keys."""
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True) if path.exists() else []
    header = f"[{table}]" if table else None
    start = 0
    end = len(lines)
    if header:
        for index, line in enumerate(lines):
            if line.strip() == header:
                start = index + 1
                for candidate in range(start, len(lines)):
                    if re.fullmatch(r"\s*\[[^]]+\]\s*(?:#.*)?", lines[candidate]):
                        end = candidate
                        break
                break
        else:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            if lines and lines[-1].strip():
                lines.append("\n")
            lines.extend([header + "\n"])
            start = end = len(lines)
    else:
        for index, line in enumerate(lines):
            if re.fullmatch(r"\s*\[[^]]+\]\s*(?:#.*)?", line):
                end = index
                break
    matcher = re.compile(rf"^(\s*){re.escape(key)}\s*=.*(?:\n)?$")
    found = None
    for index in range(start, end):
        if matcher.match(lines[index]):
            found = index
            break
    if reset:
        if found is not None:
            del lines[found]
    elif found is not None:
        indent = matcher.match(lines[found]).group(1)
        lines[found] = f"{indent}{key} = {_toml_literal(value)}\n"
    else:
        lines.insert(end, f"{key} = {_toml_literal(value)}\n")
    _atomic_write(path, "".join(lines))


def settings_key(key):
    if key in DEFAULTS:
        return "rain", key
    if key in ("respect_idle_inhibitors",):
        return "", key
    if key.startswith("exit_guard.") and key.split(".", 1)[1] in EXIT_GUARD_DEFAULTS:
        return "exit_guard", key.split(".", 1)[1]
    if key.startswith("matrix_all.") and key.split(".", 1)[1] in MATRIX_ALL_DEFAULTS:
        return "matrix_all", key.split(".", 1)[1]
    if key.startswith("settings_lock.") and key.split(".", 1)[1] in SETTINGS_LOCK_DEFAULTS:
        return "settings_lock", key.split(".", 1)[1]
    raise ConfigError(f"unknown setting: {key}")


def parse_setting(key, value):
    table, leaf = settings_key(key)
    if leaf in ("color", "cycle_speed", "cycle_direction", "binding"):
        parsed = str(value)
    elif leaf in ("mutation_rate", "cycle_period", "cycle_phase", "manual_hue_step"):
        parsed = float(value)
    elif leaf in ("speed", "trail_min", "trail_max", "density", "fade_levels", "white_head_rate", "fps_cap"):
        parsed = int(value)
    elif leaf in ("color_cycle", "reduced_motion", "hue_hold", "enabled", "hide_mouse_cursor", "respect_idle_inhibitors", "asynchronous", "flashers", "black_background"):
        if str(value).lower() not in ("true", "false"):
            raise ConfigError(f"{key} must be true or false")
        parsed = str(value).lower() == "true"
    else:
        parsed = str(value)
    if key == "exit_guard.binding":
        parsed = normalize_binding(parsed)
    return table, leaf, parsed


def load_config(path=CONFIG_PATH):
    if not Path(path).exists():
        return {}, None
    if tomllib is None:
        raise ConfigError("Python tomllib is unavailable")
    try:
        with open(path, "rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("configuration must be a TOML table")
    values = {}
    for key in DEFAULTS:
        if key in data:
            values[key] = data[key]
    rain = _table(data, "rain")
    for key in DEFAULTS:
        if key in rain:
            values[key] = rain[key]
    # Keep saver/battery tables available to the controller without allowing
    # arbitrary values to become renderer arguments.
    values["saver"] = _table(data, "saver")
    values["battery"] = _table(data, "battery")
    saver = values["saver"]
    if str(saver.get("lock_mode", "visual-only")) not in ("visual-only", "immediate", "after"):
        raise ConfigError("saver.lock_mode must be visual-only, immediate, or after")
    try:
        if int(saver.get("idle_minutes", 3)) < 1:
            raise ConfigError("saver.idle_minutes must be at least 1")
        if float(saver.get("lock_delay_seconds", 30)) < 0:
            raise ConfigError("saver.lock_delay_seconds cannot be negative")
    except (TypeError, ValueError) as exc:
        raise ConfigError("saver idle/lock delay values must be numeric") from exc
    values["respect_idle_inhibitors"] = bool(data.get("respect_idle_inhibitors", True))
    guard = _table(data, "exit_guard")
    values["exit_guard"] = {
        "enabled": bool(guard.get("enabled", EXIT_GUARD_DEFAULTS["enabled"])),
        "binding": normalize_binding(str(guard.get("binding", EXIT_GUARD_DEFAULTS["binding"]))),
    }
    matrix_all = _table(data, "matrix_all")
    values["matrix_all"] = {
        "hide_mouse_cursor": bool(matrix_all.get("hide_mouse_cursor", MATRIX_ALL_DEFAULTS["hide_mouse_cursor"])),
    }
    lock = _table(data, "settings_lock")
    values["settings_lock"] = {
        "enabled": bool(lock.get("enabled", SETTINGS_LOCK_DEFAULTS["enabled"])),
    }
    return values, None


def _cli_values(namespace):
    result = {}
    for key in DEFAULTS:
        value = getattr(namespace, key, None)
        if value is not None:
            result[key] = value
    return result


def resolve(namespace):
    config, _ = load_config()
    preset_name = getattr(namespace, "preset", None)
    if isinstance(preset_name, (list, tuple)):
        preset_name = " ".join(preset_name)
    preset_name = normalize_preset_name(preset_name) if preset_name else None
    user_presets = load_user_presets()
    if preset_name and preset_name not in PRESETS and preset_name not in user_presets:
        raise ConfigError(f"unknown preset: {preset_name}")
    preset_values = PRESETS.get(preset_name, user_presets.get(preset_name, {})) if preset_name else {}
    values = dict(DEFAULTS)
    values.update({k: v for k, v in config.items() if k in DEFAULTS})
    values.update(preset_values)
    values.update(_cli_values(namespace))
    cli_period = getattr(namespace, "cycle_period", None)
    cli_speed = getattr(namespace, "cycle_speed", None)
    if cli_period is not None:
        values["cycle_period"] = cli_period
    elif cli_speed is not None:
        values["cycle_period"] = CYCLE_SPEEDS[cli_speed]
    elif "cycle_period" in preset_values:
        values["cycle_period"] = preset_values["cycle_period"]
    elif preset_values.get("cycle_speed"):
        values["cycle_period"] = CYCLE_SPEEDS[preset_values["cycle_speed"]]
    elif "cycle_period" in config:
        values["cycle_period"] = config["cycle_period"]
    elif config.get("cycle_speed"):
        values["cycle_period"] = CYCLE_SPEEDS[config["cycle_speed"]]
    if getattr(namespace, "reduced_motion", None):
        values["reduced_motion"] = True
    if values["reduced_motion"]:
        values["flashers"] = False
        values["color_cycle"] = False
        values["mutation_rate"] = 0.0
    values["speed"] = int(clamp(int(values["speed"]), 1, 100))
    values["trail_min"] = max(4, int(values["trail_min"]))
    values["trail_max"] = max(values["trail_min"], int(values["trail_max"]))
    values["density"] = int(clamp(int(values["density"]), 1, 100))
    values["fade_levels"] = int(clamp(int(values["fade_levels"]), 3, 6))
    values["white_head_rate"] = int(clamp(int(values["white_head_rate"]), 0, 100))
    values["mutation_rate"] = float(clamp(float(values["mutation_rate"]), 0.0, 100.0))
    values["cycle_period"] = max(2.0, float(values["cycle_period"]))
    values["cycle_speed"] = str(values["cycle_speed"]).lower()
    if values["cycle_speed"] not in CYCLE_SPEEDS:
        raise ConfigError("cycle_speed must be very-slow, slow, normal, or fast")
    values["cycle_direction"] = str(values["cycle_direction"]).lower()
    if values["cycle_direction"] not in ("forward", "reverse"):
        raise ConfigError("cycle_direction must be forward or reverse")
    values["color"] = str(values["color"]).lower()
    if values["color"] not in COLORS:
        raise ConfigError(f"color must be one of: {', '.join(COLORS)}")
    values["fps_cap"] = int(clamp(int(values["fps_cap"]), 1, 240))
    values["asynchronous"] = bool(values["asynchronous"])
    values["flashers"] = bool(values["flashers"])
    values["black_background"] = bool(values["black_background"])
    values["background"] = str(values["background"]).lower()
    if values["background"] not in BACKGROUND_MODES:
        raise ConfigError(f"background must be one of: {', '.join(BACKGROUND_MODES)}")
    # Preserve the older --black-background/--no-black-background interface.
    # An explicit background value always wins over the compatibility flag.
    if getattr(namespace, "background", None) is None:
        if getattr(namespace, "black_background", None) is True:
            values["background"] = "black"
        elif getattr(namespace, "black_background", None) is False:
            values["background"] = "profile"
        elif "background" not in config and "background" not in preset_values and values["black_background"]:
            values["background"] = "black"
    values["black_background"] = values["background"] == "black"
    values["color_cycle"] = bool(values["color_cycle"])
    values["reduced_motion"] = bool(values["reduced_motion"])
    values["hue_hold"] = bool(values["hue_hold"])
    values["cycle_phase"] = float(values["cycle_phase"]) % 1.0
    values["manual_hue_step"] = clamp(float(values["manual_hue_step"]), 0.001, 0.1)
    values["preset_name"] = preset_name
    values["exit_guard"] = config.get("exit_guard", dict(EXIT_GUARD_DEFAULTS))
    values["matrix_all"] = config.get("matrix_all", dict(MATRIX_ALL_DEFAULTS))
    values["settings_lock"] = config.get("settings_lock", dict(SETTINGS_LOCK_DEFAULTS))
    return values


def add_cli_arguments(parser):
    parser.add_argument("--preset", nargs="+", default=None, metavar="NAME")
    parser.add_argument("-s", "--speed", type=int, default=None)
    parser.add_argument("--trail-min", dest="trail_min", type=int, default=None)
    parser.add_argument("--trail-max", dest="trail_max", type=int, default=None)
    parser.add_argument("-d", "--density", type=int, default=None)
    parser.add_argument("--fade-levels", dest="fade_levels", type=int, default=None)
    parser.add_argument("--white-head-rate", dest="white_head_rate", type=int, default=None)
    parser.add_argument("--mutation-rate", dest="mutation_rate", type=float, default=None)
    parser.add_argument("--flashers", dest="flashers", action="store_true", default=None)
    parser.add_argument("--no-flashers", dest="flashers", action="store_false")
    parser.add_argument("--asynchronous", dest="asynchronous", action="store_true", default=None)
    parser.add_argument("--sync", dest="asynchronous", action="store_false")
    parser.add_argument("--black-background", dest="black_background", action="store_true", default=None)
    parser.add_argument("--no-black-background", dest="black_background", action="store_false")
    parser.add_argument("--background", choices=BACKGROUND_MODES, default=None)
    parser.add_argument("--color", choices=COLORS, default=None)
    parser.add_argument("--color-cycle", dest="color_cycle", action="store_true", default=None)
    parser.add_argument("--no-color-cycle", dest="color_cycle", action="store_false")
    parser.add_argument("--cycle-period", type=float, default=None)
    parser.add_argument("--cycle-speed", choices=tuple(CYCLE_SPEEDS), default=None)
    parser.add_argument("--cycle-direction", choices=("forward", "reverse"), default=None)
    parser.add_argument("--fps-cap", type=int, default=None)
    parser.add_argument("--reduced-motion", action="store_true", default=None)
    parser.add_argument("--manual-hue-step", type=float, default=None)
    parser.add_argument("--spacing", type=int, default=2)
    parser.add_argument("--chars", type=str, default=None)
    parser.add_argument("-o", "--status-off", action="store_true", default=False)


def user_preset_path(name):
    canonical = normalize_preset_name(name)
    path = (PRESET_DIR / f"{canonical}.toml").resolve()
    root = PRESET_DIR.resolve()
    if os.path.commonpath((str(root), str(path))) != str(root):
        raise ConfigError("unsafe preset name")
    return path


def _preset_values(data):
    values = data.get("preset", data)
    if not isinstance(values, dict):
        raise ConfigError("preset must be a TOML table")
    result = {key: values[key] for key in DEFAULTS if key in values}
    # A preset cannot resurrect a captured global animation pause state.
    result.pop("paused", None)
    return result


def load_user_presets():
    if not PRESET_DIR.exists():
        return {}
    if tomllib is None:
        raise ConfigError("Python tomllib is unavailable")
    presets = {}
    for path in sorted(PRESET_DIR.glob("*.toml")):
        canonical = normalize_preset_name(path.stem)
        if canonical in PRESETS:
            continue
        try:
            with path.open("rb") as handle:
                presets[canonical] = _preset_values(tomllib.load(handle))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigError(f"cannot read user preset {path.name}: {exc}") from exc
    return presets


def save_user_preset(name, values, display_name=None, force=False):
    canonical = normalize_preset_name(name)
    if canonical in PRESETS:
        raise ConfigError("user presets cannot shadow a built-in preset")
    path = user_preset_path(canonical)
    if path.exists() and not force:
        raise ConfigError(f"preset already exists: {canonical} (use --force to replace it)")
    clean = {key: values[key] for key in DEFAULTS if key in values}
    clean["hue_hold"] = bool(clean.get("hue_hold", False))
    lines = ["# Konsole-Matrix-Digital-Rain user visual preset.\n", "[preset]\n"]
    if display_name:
        lines.append(f"display_name = {_toml_literal(display_name)}\n")
    for key in DEFAULTS:
        if key in clean:
            lines.append(f"{key} = {_toml_literal(clean[key])}\n")
    _atomic_write(path, "".join(lines))
    return canonical


def delete_user_preset(name):
    path = user_preset_path(name)
    if not path.exists():
        raise ConfigError(f"user preset does not exist: {normalize_preset_name(name)}")
    path.unlink()


def save_last_effective(values):
    save_user_preset_file = {key: values[key] for key in DEFAULTS if key in values}
    lines = ["# Most recently effective visual settings; generated locally.\n", "[preset]\n"]
    for key in DEFAULTS:
        if key in save_user_preset_file:
            lines.append(f"{key} = {_toml_literal(save_user_preset_file[key])}\n")
    _atomic_write(LAST_EFFECTIVE_PATH, "".join(lines))


def load_last_effective():
    if not LAST_EFFECTIVE_PATH.exists():
        raise ConfigError("no last effective Matrix settings have been recorded")
    if tomllib is None:
        raise ConfigError("Python tomllib is unavailable")
    with LAST_EFFECTIVE_PATH.open("rb") as handle:
        return _preset_values(tomllib.load(handle))


def xterm_rgb(index):
    if 16 <= index <= 231:
        index -= 16
        return tuple(round(255 * (v / 5)) if v else 0 for v in (index // 36, (index // 6) % 6, index % 6))
    if 232 <= index <= 255:
        value = 8 + (index - 232) * 10
        return value, value, value
    basic = ((0, 0, 0), (205, 0, 0), (0, 205, 0), (205, 205, 0),
             (0, 0, 238), (205, 0, 205), (0, 205, 205), (229, 229, 229))
    return basic[index % 8]


def nearest_xterm(rgb):
    candidates = range(16, 256)
    return min(candidates, key=lambda index: sum((a - b) ** 2 for a, b in zip(rgb, xterm_rgb(index))))


def _hue_rgb(hue, saturation=1.0, value=1.0):
    return tuple(round(v * 255) for v in colorsys.hsv_to_rgb((hue % 360) / 360.0, saturation, value))


# Explicit normalized family spans keep anchor density from changing dwell
# time. More waypoints improve the shape within a span, but the spans remain
# intentionally balanced around the full cycle.
CYCLE_FAMILY_SPANS = {
    "green-cyan": (0.00, 0.22),
    "blue": (0.22, 0.40),
    "purple-pink": (0.40, 0.62),
    "red-orange": (0.62, 0.80),
    "yellow-lime": (0.80, 1.00),
}

CYCLE_WAYPOINTS = (
    # Green family through cyan.
    (0.000, 120), (0.025, 130), (0.055, 145), (0.085, 155),
    (0.115, 165), (0.145, 175), (0.170, 180), (0.195, 188),
    (0.220, 200),
    # Cyan through blue.
    (0.245, 210), (0.270, 218), (0.295, 225), (0.320, 235),
    (0.345, 245), (0.370, 255), (0.400, 265),
    # Blue-violet through pink.
    (0.430, 275), (0.460, 285), (0.490, 295), (0.525, 310),
    (0.560, 325), (0.585, 337), (0.605, 345), (0.620, 350),
    # Pink through red and orange.
    (0.640, 355), (0.660, 360), (0.700, 375), (0.740, 390),
    (0.770, 405), (0.800, 420),
    # Yellow through lime and back to green.
    (0.835, 435), (0.870, 450), (0.905, 465), (0.940, 475),
    (1.000, 480),
)


def cycle_rgb(phase, direction="forward"):
    position = phase % 1.0
    if direction == "reverse":
        position = (-position) % 1.0
    for index in range(len(CYCLE_WAYPOINTS) - 1):
        start_phase, start_hue = CYCLE_WAYPOINTS[index]
        end_phase, end_hue = CYCLE_WAYPOINTS[index + 1]
        if position <= end_phase:
            amount = (position - start_phase) / max(1e-9, end_phase - start_phase)
            return _hue_rgb(start_hue + (end_hue - start_hue) * amount)
    return _hue_rgb(CYCLE_WAYPOINTS[-1][1])


def ramp_indices(color, phase=0.0, direction="forward"):
    if color == "white":
        rgb_values = [(255, 255, 255), (238, 238, 238), (192, 192, 192),
                      (140, 140, 140), (82, 82, 82), (35, 35, 35)]
    else:
        base = cycle_rgb(phase, direction) if color == "cycle" else COLOR_RGB[color]
        hsv = colorsys.rgb_to_hsv(*(v / 255.0 for v in base))
        brightness = (1.0, 0.82, 0.63, 0.46, 0.30, 0.16)
        rgb_values = [
            _hue_rgb(hsv[0] * 360.0, max(0.72, hsv[1]), min(1.0, hsv[2] * level))
            for level in brightness
        ]
    return [nearest_xterm(rgb) for rgb in rgb_values]


def runtime_dir():
    return Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))


def secure_private_dir(path):
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    st = path.stat()
    if st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) & 0o077:
        raise ConfigError(f"runtime directory is not private: {path}")
    return path
