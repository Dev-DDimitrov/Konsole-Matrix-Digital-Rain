#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
"""Lock-screen Matrix profile: storage, history, and KDE wallpaper export.

The lock-screen renderer is a Plasma 6 QML wallpaper plugin that reads its
settings from kscreenlockerrc. This module owns the canonical lock-screen
profile (TOML, independent from the terminal profile), a bounded revision
history, and the one-way export that compiles the profile into the plugin's
KConfig group. Nothing here runs while the screen is locked.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from matrix_resource_guard import validate_guard
from matrix_config import (
    COLOR_RGB,
    COLORS,
    CONFIG_DIR,
    ConfigError,
    PRESETS,
    _atomic_write,
    _toml_literal,
    clamp,
    cycle_rgb,
    hue_degrees_rgb,
    load_last_effective,
    load_user_presets,
    nearest_cycle_phase,
    normalize_preset_name,
    parse_hex_color,
    rgb_to_hex,
)

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Fedora's supported Python has it
    tomllib = None

PLUGIN_ID = "io.github.devddimitrov.matrixrain"
LOCK_CONFIG_PATH = CONFIG_DIR / "lockscreen.toml"
HISTORY_DIR = CONFIG_DIR / "lockscreen-history"
HISTORY_LIMIT = 10
LOCK_PRESET_DIR = CONFIG_DIR / "lock-presets"

DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
PLUGIN_DIR = DATA_HOME / "plasma/wallpapers" / PLUGIN_ID
PROJECT_DATA_DIR = DATA_HOME / "konsole-matrix-digital-rain"
WALLPAPER_BACKUP_PATH = PROJECT_DATA_DIR / "lockscreen-wallpaper-backup.json"
KSCREENLOCKERRC = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "kscreenlockerrc"

DEFAULT_LOCK_WALLPAPER_PLUGIN = "org.kde.image"

# Balanced public defaults: terminal-parity pacing and visuals on the GPU
# shader backend. Deliberately independent from the terminal profile
# defaults in matrix_config.DEFAULTS.
LOCK_DEFAULTS = {
    "color": "green",            # named Matrix color or "#rrggbb"
    "cycle_phase": 0.0,          # spectrum anchor, 0.0-1.0
    "color_cycle": False,
    "cycle_period": 72.0,
    "cycle_direction": "forward",
    "speed": 96,
    "density": 52,
    "trail_min": 16,
    "trail_max": 38,
    "fade_levels": 6,
    "white_head_rate": 25,
    "mutation_rate": 0.8,
    "flashers": False,
    "asynchronous": True,
    "background": "#000000",     # lock background is always a direct color
    "fps_cap": 30,
    "reduced_motion": False,
    "glyph_size": 18,
    "render_scale": 1.0,
    "render_mode": "auto",
    # Adaptive resource protection (see matrix_resource_guard.py).
    "resource_guard": True,
    "guard_cpu_pause": 85,
    "guard_mem_pause": 85,
    "guard_cpu_resume": 70,
    "guard_mem_resume": 70,
    "guard_pause_secs": 8.0,
    "guard_resume_secs": 10.0,
}

# Rendering/pacing bundles for `matrix-lock quality NAME`. They never touch
# color, cycling, background, white heads, or glyph size.
QUALITY_PRESETS = {
    "balanced": {
        "render_mode": "auto", "fps_cap": 30, "speed": 96, "density": 52,
        "trail_min": 16, "trail_max": 38, "mutation_rate": 0.8,
        "flashers": False, "render_scale": 1.0,
    },
    "high": {
        "render_mode": "auto", "fps_cap": 60, "speed": 98, "density": 52,
        "trail_min": 16, "trail_max": 38, "mutation_rate": 0.8,
        "flashers": True, "render_scale": 1.0,
    },
    "battery": {
        "render_mode": "low-power", "fps_cap": 12, "speed": 62, "density": 34,
        "trail_min": 14, "trail_max": 34, "mutation_rate": 0.2,
        "flashers": False, "render_scale": 0.5,
    },
}

# Terminal background modes approximated as direct lock-screen colors.
TERMINAL_BACKGROUND_HEX = {
    "profile": "#000000",
    "black": "#000000",
    "charcoal": "#303030",
    "white": "#ffffff",
    "translucent": "#000000",
}


def normalize_color(value):
    """Canonicalize a named Matrix color or HEX string; reject anything else."""
    if not isinstance(value, str):
        raise ConfigError("color must be a named Matrix color or #RRGGBB")
    text = value.strip().lower()
    if text in COLORS:
        return text
    return rgb_to_hex(parse_hex_color(text))


def color_rgb(value):
    """Effective RGB for a canonical profile color."""
    if value in COLOR_RGB:
        return COLOR_RGB[value]
    return parse_hex_color(value)


def validate(values):
    """Return a complete, normalized lock profile; raise ConfigError otherwise."""
    if not isinstance(values, dict):
        raise ConfigError("lock-screen profile must be a table")
    unknown = set(values) - set(LOCK_DEFAULTS)
    if unknown:
        raise ConfigError(f"unknown lock-screen setting(s): {', '.join(sorted(unknown))}")
    merged = dict(LOCK_DEFAULTS)
    merged.update(values)
    try:
        merged["color"] = normalize_color(merged["color"])
        merged["cycle_phase"] = float(merged["cycle_phase"]) % 1.0
        merged["color_cycle"] = bool(merged["color_cycle"])
        merged["cycle_period"] = clamp(float(merged["cycle_period"]), 2.0, 3600.0)
        merged["cycle_direction"] = str(merged["cycle_direction"]).lower()
        if merged["cycle_direction"] not in ("forward", "reverse"):
            raise ConfigError("cycle_direction must be forward or reverse")
        merged["speed"] = int(clamp(int(merged["speed"]), 1, 100))
        merged["density"] = int(clamp(int(merged["density"]), 1, 100))
        merged["trail_min"] = max(4, int(merged["trail_min"]))
        merged["trail_max"] = max(merged["trail_min"], int(merged["trail_max"]))
        merged["fade_levels"] = int(clamp(int(merged["fade_levels"]), 3, 6))
        merged["white_head_rate"] = int(clamp(int(merged["white_head_rate"]), 0, 100))
        merged["mutation_rate"] = float(clamp(float(merged["mutation_rate"]), 0.0, 100.0))
        merged["flashers"] = bool(merged["flashers"])
        merged["asynchronous"] = bool(merged["asynchronous"])
        merged["background"] = rgb_to_hex(parse_hex_color(str(merged["background"])))
        merged["fps_cap"] = int(clamp(int(merged["fps_cap"]), 1, 60))
        merged["reduced_motion"] = bool(merged["reduced_motion"])
        merged["glyph_size"] = int(clamp(int(merged["glyph_size"]), 10, 72))
        merged["render_scale"] = float(clamp(float(merged["render_scale"]), 0.25, 1.0))
        merged["render_mode"] = str(merged["render_mode"]).lower()
        if merged["render_mode"] not in ("auto", "quality", "low-power"):
            raise ConfigError("render_mode must be auto, quality, or low-power")
        validate_guard(merged)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"invalid lock-screen value: {exc}") from exc
    if merged["reduced_motion"]:
        merged["color_cycle"] = False
        merged["flashers"] = False
        merged["mutation_rate"] = 0.0
    return merged


def effective_fixed_rgb(values):
    """The fixed (non-cycling) color the lock screen will show."""
    return color_rgb(values["color"])


def _profile_lines(values, note=None):
    lines = ["# Konsole-Matrix-Digital-Rain lock-screen profile; managed by matrix-lock.\n"]
    if note:
        lines.append(f"# {note}\n")
    lines.append("[lockscreen]\n")
    for key in LOCK_DEFAULTS:
        lines.append(f"{key} = {_toml_literal(values[key])}\n")
    return "".join(lines)


def load_profile(path=None):
    path = Path(path or LOCK_CONFIG_PATH)
    if not path.exists():
        return dict(LOCK_DEFAULTS)
    if tomllib is None:
        raise ConfigError("Python tomllib is unavailable")
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    table = data.get("lockscreen", data)
    if not isinstance(table, dict):
        raise ConfigError("[lockscreen] must be a table")
    return validate({key: table[key] for key in LOCK_DEFAULTS if key in table})


def _revision_id():
    """A revision id strictly newer than every existing one (clock-skew safe)."""
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    existing = (
        [_revision_sort_key(path) for path in HISTORY_DIR.glob("*.toml")]
        if HISTORY_DIR.exists() else []
    )
    top = max(existing, default=None)
    if top is None or top[0] < stamp:
        return stamp
    base = max(top[0], stamp)
    return f"{base}-{top[1] + 1}"


def save_profile(values, note=None, path=None):
    """Validate, persist atomically, and append a bounded history revision."""
    values = validate(values)
    content = _profile_lines(values, note=note)
    _atomic_write(Path(path or LOCK_CONFIG_PATH), content)
    revision = _revision_id()
    _atomic_write(HISTORY_DIR / f"{revision}.toml", content)
    prune_history()
    return values, revision


def _revision_sort_key(path):
    match = re.fullmatch(r"([0-9]{8}-[0-9]{6})(?:-([0-9]+))?", path.stem)
    if not match:
        return (path.stem, 0)
    return (match.group(1), int(match.group(2) or 1))


def prune_history(limit=None):
    limit = HISTORY_LIMIT if limit is None else limit
    if not HISTORY_DIR.exists():
        return
    entries = sorted(HISTORY_DIR.glob("*.toml"), key=_revision_sort_key)
    for stale in entries[:-limit] if len(entries) > limit else ():
        try:
            stale.unlink()
        except OSError:
            pass


def _revision_path(revision):
    if not re.fullmatch(r"[0-9]{8}-[0-9]{6}(?:-[0-9]+)?", str(revision)):
        raise ConfigError(f"unknown revision: {revision}")
    path = HISTORY_DIR / f"{revision}.toml"
    if not path.is_file():
        raise ConfigError(f"unknown revision: {revision}")
    return path


def load_revision(revision):
    return load_profile(_revision_path(revision))


def history_entries():
    """Newest-first (revision, values) pairs; unreadable revisions are skipped."""
    if not HISTORY_DIR.exists():
        return []
    entries = []
    for path in sorted(HISTORY_DIR.glob("*.toml"), key=_revision_sort_key, reverse=True):
        try:
            entries.append((path.stem, load_profile(path)))
        except ConfigError:
            continue
    return entries


def summarize(values):
    rgb = effective_fixed_rgb(values)
    cycling = f"cycling {values['cycle_direction']} /{values['cycle_period']:.0f}s" if values["color_cycle"] else "fixed"
    return (f"color {values['color']} ({rgb_to_hex(rgb)}) {cycling} | speed {values['speed']} | "
            f"density {values['density']} | trail {values['trail_min']}-{values['trail_max']} | "
            f"heads {values['white_head_rate']}% | fps {values['fps_cap']}")


# ---------------------------------------------------------------------------
# Terminal-profile interchange


def from_terminal_values(term):
    """Map a terminal visual capture (last-effective/preset) onto a lock profile."""
    current = load_profile()
    values = dict(current)
    for key in ("speed", "density", "trail_min", "trail_max", "fade_levels",
                "white_head_rate", "mutation_rate", "flashers", "asynchronous",
                "cycle_period", "cycle_direction", "reduced_motion"):
        if key in term:
            values[key] = term[key]
    if "fps_cap" in term:
        values["fps_cap"] = int(clamp(int(term["fps_cap"]), 1, 60))
    if "cycle_speed" in term and "cycle_period" not in term:
        from matrix_config import CYCLE_SPEEDS
        values["cycle_period"] = CYCLE_SPEEDS.get(str(term["cycle_speed"]), values["cycle_period"])
    if "background" in term:
        values["background"] = TERMINAL_BACKGROUND_HEX.get(str(term["background"]), values["background"])
    phase = float(term.get("cycle_phase", current["cycle_phase"])) % 1.0
    values["cycle_phase"] = phase
    if term.get("color_cycle"):
        if term.get("hue_hold"):
            # A held hue is an exact color selection: freeze it.
            values["color"] = rgb_to_hex(cycle_rgb(phase))
            values["color_cycle"] = False
        else:
            values["color"] = rgb_to_hex(cycle_rgb(phase))
            values["color_cycle"] = True
    elif "color" in term:
        values["color"] = normalize_color(str(term["color"]))
        values["color_cycle"] = False
    return validate(values)


def renderer_preview_arguments(values):
    """CLI arguments that make the terminal renderer approximate this profile."""
    arguments = [
        "--speed", str(values["speed"]),
        "--density", str(values["density"]),
        "--trail-min", str(values["trail_min"]),
        "--trail-max", str(values["trail_max"]),
        "--fade-levels", str(values["fade_levels"]),
        "--white-head-rate", str(values["white_head_rate"]),
        "--mutation-rate", str(values["mutation_rate"]),
        "--fps-cap", str(max(5, values["fps_cap"])),
        "--cycle-period", str(values["cycle_period"]),
        "--cycle-direction", values["cycle_direction"],
        "--flashers" if values["flashers"] else "--no-flashers",
        "--asynchronous" if values["asynchronous"] else "--sync",
    ]
    background = values["background"]
    if background == "#ffffff":
        arguments += ["--background", "white"]
    elif background == "#303030":
        arguments += ["--background", "charcoal"]
    else:
        arguments += ["--background", "black"]
    if values["reduced_motion"]:
        arguments.append("--reduced-motion")
    if values["color_cycle"]:
        arguments += ["--color-cycle", "--cycle-phase", f"{values['cycle_phase']:.6f}"]
    elif values["color"] in COLORS:
        arguments += ["--color", values["color"]]
    else:
        # Exact HEX colors preview as the nearest spectrum phase, held.
        phase = nearest_cycle_phase(parse_hex_color(values["color"]))
        arguments += ["--color-cycle", "--hue-hold", "--cycle-phase", f"{phase:.6f}"]
    return arguments


def set_hue_degrees(values, degrees):
    rgb = hue_degrees_rgb(degrees)
    values = dict(values)
    values["color"] = rgb_to_hex(rgb)
    values["cycle_phase"] = nearest_cycle_phase(rgb)
    return values


def set_color(values, text):
    canonical = normalize_color(text)
    values = dict(values)
    values["color"] = canonical
    values["cycle_phase"] = nearest_cycle_phase(color_rgb(canonical))
    return values


# Visual keys a named preset captures; the guard_* protection settings are
# deliberately excluded so applying a visual preset can never change
# adaptive resource protection or suspension behavior.
GUARD_KEYS = tuple(key for key in LOCK_DEFAULTS
                   if key == "resource_guard" or key.startswith("guard_"))
VISUAL_KEYS = tuple(key for key in LOCK_DEFAULTS if key not in GUARD_KEYS)


def lock_preset_path(name):
    canonical = normalize_preset_name(name)
    path = (LOCK_PRESET_DIR / f"{canonical}.toml").resolve()
    root = LOCK_PRESET_DIR.resolve()
    if os.path.commonpath((str(root), str(path))) != str(root):
        raise ConfigError("unsafe preset name")
    return path


def load_lock_presets():
    """{canonical: {"display_name": str, "values": visual-key dict}}."""
    if not LOCK_PRESET_DIR.exists():
        return {}
    if tomllib is None:
        raise ConfigError("Python tomllib is unavailable")
    presets = {}
    for path in sorted(LOCK_PRESET_DIR.glob("*.toml")):
        canonical = normalize_preset_name(path.stem)
        try:
            with path.open("rb") as handle:
                data = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigError(f"cannot read lock preset {path.name}: {exc}") from exc
        table = data.get("lockscreen", {})
        if not isinstance(table, dict):
            raise ConfigError(f"lock preset {path.name} must contain a [lockscreen] table")
        presets[canonical] = {
            "display_name": str(data.get("display_name", canonical)),
            "values": {key: table[key] for key in VISUAL_KEYS if key in table},
        }
    return presets


def save_lock_preset(name, values, force=False):
    """Save the visual keys of a validated profile as a named lock preset."""
    canonical = normalize_preset_name(name)
    if canonical in PRESETS:
        raise ConfigError(f"'{canonical}' is a built-in preset and cannot be replaced")
    path = lock_preset_path(canonical)
    if path.exists() and not force:
        raise ConfigError(f"preset already exists: {canonical} (use --force to replace it)")
    values = validate(values)
    lines = ["# Konsole-Matrix-Digital-Rain named lock-screen preset; managed by matrix-lock.\n",
             f"display_name = {_toml_literal(str(name).strip())}\n",
             "[lockscreen]\n"]
    for key in VISUAL_KEYS:
        lines.append(f"{key} = {_toml_literal(values[key])}\n")
    _atomic_write(path, "".join(lines))
    return canonical


def delete_lock_preset(name):
    canonical = normalize_preset_name(name)
    if canonical in PRESETS:
        raise ConfigError(f"'{canonical}' is a built-in preset and cannot be deleted")
    path = lock_preset_path(canonical)
    if not path.exists():
        raise ConfigError(f"user preset does not exist: {canonical}")
    path.unlink()


def rename_lock_preset(old, new):
    old_canonical = normalize_preset_name(old)
    if old_canonical in PRESETS:
        raise ConfigError(f"'{old_canonical}' is a built-in preset and cannot be renamed")
    new_canonical = normalize_preset_name(new)
    if new_canonical in PRESETS:
        raise ConfigError(f"'{new_canonical}' is a built-in preset name")
    entry = load_lock_presets().get(old_canonical)
    if entry is None:
        raise ConfigError(f"user preset does not exist: {old_canonical}")
    if new_canonical != old_canonical and lock_preset_path(new_canonical).exists():
        raise ConfigError(f"preset already exists: {new_canonical}")
    merged = dict(load_profile())
    merged.update(entry["values"])
    save_lock_preset(new, merged, force=new_canonical == old_canonical)
    if new_canonical != old_canonical:
        lock_preset_path(old_canonical).unlink()
    return new_canonical


def apply_preset(values, name):
    """Overlay a named lock preset, built-in, or terminal capture onto the
    lock profile. Guard settings are never part of a preset and stay put."""
    canonical = normalize_preset_name(name)
    lock_presets = load_lock_presets()
    if canonical in lock_presets:
        merged = dict(values)
        merged.update(lock_presets[canonical]["values"])
        for key in GUARD_KEYS:
            merged[key] = values[key]
        return validate(merged), canonical
    preset = PRESETS.get(canonical)
    if preset is None:
        preset = load_user_presets().get(canonical)
    if preset is None:
        raise ConfigError(f"unknown preset: {canonical}")
    merged = dict(values)
    overlay = from_terminal_values(preset)
    for key in LOCK_DEFAULTS:
        if _preset_touches(preset, key):
            merged[key] = overlay[key]
    return validate(merged), canonical


def _preset_touches(preset, lock_key):
    direct = {"speed", "density", "trail_min", "trail_max", "fade_levels",
              "white_head_rate", "mutation_rate", "flashers", "asynchronous",
              "cycle_period", "cycle_direction", "reduced_motion", "fps_cap",
              "cycle_phase", "background"}
    if lock_key in direct:
        return lock_key in preset or (lock_key == "cycle_period" and "cycle_speed" in preset)
    if lock_key in ("color", "color_cycle"):
        return "color" in preset or "color_cycle" in preset or "cycle_phase" in preset
    return False


def import_last_effective():
    return from_terminal_values(load_last_effective())


def apply_quality(values, name):
    """Overlay a rendering/pacing quality preset; visual identity untouched."""
    canonical = str(name).strip().lower()
    preset = QUALITY_PRESETS.get(canonical)
    if preset is None:
        raise ConfigError(f"unknown quality preset: {name} (choose from: {', '.join(QUALITY_PRESETS)})")
    merged = dict(values)
    merged.update(preset)
    return validate(merged), canonical


# ---------------------------------------------------------------------------
# kscreenlockerrc export (KConfig INI, nested groups, atomic, comment-safe)

_GROUP_LINE = re.compile(r"^\s*((?:\[[^\[\]]*\])+)\s*$")
_KEY_LINE = re.compile(r"^([^#;=\[][^=]*?)\s*=")


def _kconfig_header(groups):
    return "".join(f"[{group}]" for group in groups)


def _read_rc_lines(path):
    path = Path(path)
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def kconfig_read(path, groups, key):
    """Read one key from a KConfig INI file without external tools."""
    header = _kconfig_header(groups)
    active = None
    for line in _read_rc_lines(path):
        match = _GROUP_LINE.match(line)
        if match:
            active = match.group(1)
            continue
        if active != header:
            continue
        key_match = _KEY_LINE.match(line)
        if key_match and key_match.group(1).strip() == key:
            return line.split("=", 1)[1].strip()
    return None


def kconfig_set(path, groups, assignments):
    """Set keys inside one (possibly nested) group, preserving everything else."""
    path = Path(path)
    header = _kconfig_header(groups)
    lines = _read_rc_lines(path)
    pending = {key: _kconfig_literal(value) for key, value in assignments.items()}
    output = []
    index = 0
    section_found = False
    while index < len(lines):
        line = lines[index]
        match = _GROUP_LINE.match(line)
        if match and match.group(1) == header:
            section_found = True
            output.append(line)
            index += 1
            while index < len(lines) and not _GROUP_LINE.match(lines[index]):
                current = lines[index]
                key_match = _KEY_LINE.match(current)
                if key_match and key_match.group(1).strip() in pending:
                    key = key_match.group(1).strip()
                    output.append(f"{key}={pending.pop(key)}")
                else:
                    output.append(current)
                index += 1
            for key, value in pending.items():
                output.append(f"{key}={value}")
            pending = {}
            continue
        output.append(line)
        index += 1
    if not section_found and pending:
        if output and output[-1].strip():
            output.append("")
        output.append(header)
        for key, value in pending.items():
            output.append(f"{key}={value}")
    _atomic_write(path, "\n".join(output) + "\n")


def _kconfig_literal(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".") or "0"
    return str(value)


def export_assignments(values, epoch=None):
    """Compile a validated lock profile into the wallpaper plugin's KConfig keys."""
    values = validate(values)
    fixed = rgb_to_hex(effective_fixed_rgb(values))
    return {
        "FixedColor": fixed,
        "BackgroundColor": values["background"],
        "ColorCycle": values["color_cycle"],
        "CyclePhase": round(values["cycle_phase"], 6),
        "CyclePeriod": values["cycle_period"],
        "CycleDirectionReverse": values["cycle_direction"] == "reverse",
        "CycleEpoch": float(epoch if epoch is not None else time.time()),
        "Speed": values["speed"],
        "Density": values["density"],
        "TrailMin": values["trail_min"],
        "TrailMax": values["trail_max"],
        "FadeLevels": values["fade_levels"],
        "WhiteHeadRate": values["white_head_rate"],
        "MutationRate": values["mutation_rate"],
        "Flashers": values["flashers"],
        "Asynchronous": values["asynchronous"],
        "FpsCap": values["fps_cap"],
        "ReducedMotion": values["reduced_motion"],
        "GlyphSize": values["glyph_size"],
        "RenderScale": values["render_scale"],
        "RenderMode": values["render_mode"],
        "ResourceGuard": values["resource_guard"],
        "GuardCpuPause": values["guard_cpu_pause"],
        "GuardMemPause": values["guard_mem_pause"],
        "GuardCpuResume": values["guard_cpu_resume"],
        "GuardMemResume": values["guard_mem_resume"],
        "GuardPauseSecs": values["guard_pause_secs"],
        "GuardResumeSecs": values["guard_resume_secs"],
    }


def plugin_config_groups():
    return ("Greeter", "Wallpaper", PLUGIN_ID, "General")


def export_to_lockscreen(values, rc_path=None, epoch=None):
    kconfig_set(Path(rc_path or KSCREENLOCKERRC), plugin_config_groups(),
                export_assignments(values, epoch=epoch))


def current_wallpaper_plugin(rc_path=None):
    value = kconfig_read(Path(rc_path or KSCREENLOCKERRC), ("Greeter",), "WallpaperPlugin")
    return value or DEFAULT_LOCK_WALLPAPER_PLUGIN


def plugin_installed():
    return all((PLUGIN_DIR / relative).is_file() for relative in (
        "metadata.json", "contents/ui/main.qml", "contents/config/main.xml"))


def is_enabled(rc_path=None):
    return current_wallpaper_plugin(rc_path) == PLUGIN_ID


def enable(rc_path=None):
    """Back up the previous wallpaper plugin choice, then activate Matrix."""
    rc_path = Path(rc_path or KSCREENLOCKERRC)
    if not plugin_installed():
        raise ConfigError(
            f"the Matrix wallpaper plugin is not installed at {PLUGIN_DIR}; run scripts/install.sh first")
    previous = current_wallpaper_plugin(rc_path)
    if previous != PLUGIN_ID and not WALLPAPER_BACKUP_PATH.exists():
        backup = {"wallpaper_plugin": previous, "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        _atomic_write(WALLPAPER_BACKUP_PATH, json.dumps(backup, indent=2) + "\n")
    export_to_lockscreen(load_profile(), rc_path=rc_path)
    kconfig_set(rc_path, ("Greeter",), {"WallpaperPlugin": PLUGIN_ID})
    return previous


def disable(rc_path=None):
    """Restore the wallpaper plugin recorded before Matrix was enabled."""
    rc_path = Path(rc_path or KSCREENLOCKERRC)
    previous = DEFAULT_LOCK_WALLPAPER_PLUGIN
    if WALLPAPER_BACKUP_PATH.exists():
        try:
            backup = json.loads(WALLPAPER_BACKUP_PATH.read_text(encoding="utf-8"))
            previous = str(backup.get("wallpaper_plugin") or previous)
        except (OSError, ValueError):
            pass
    kconfig_set(rc_path, ("Greeter",), {"WallpaperPlugin": previous})
    try:
        WALLPAPER_BACKUP_PATH.unlink()
    except FileNotFoundError:
        pass
    return previous
