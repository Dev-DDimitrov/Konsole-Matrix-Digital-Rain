#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
"""matrix-lock: configure the Matrix Digital Rain KDE lock-screen wallpaper."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import matrix_lockscreen as lock
import matrix_resource_guard as resource_guard
from matrix_config import (
    CYCLE_BLEND_DEFAULT,
    COLORS,
    ConfigError,
    LAST_EFFECTIVE_PATH,
    PRESETS,
    build_cycle_path,
    clamp,
    enabled_cycle_gaps,
    hue_from_phase,
    load_user_presets,
    normalize_cycle_exclusions,
    phase_from_hue,
)
from matrix_guide_data import PRESET_DESCRIPTIONS

BIN = Path(__file__).resolve().parent
GREETER = Path("/usr/libexec/kscreenlocker_greet")

SET_KEYS = {
    "color-cycle": ("color_cycle", "bool"),
    "cycle-period": ("cycle_period", "float"),
    "cycle-direction": ("cycle_direction", "str"),
    "speed": ("speed", "int"),
    "density": ("density", "int"),
    "trail-min": ("trail_min", "int"),
    "trail-max": ("trail_max", "int"),
    "fade-levels": ("fade_levels", "int"),
    "white-heads": ("white_head_rate", "int"),
    "mutation-rate": ("mutation_rate", "float"),
    "flashers": ("flashers", "bool"),
    "async": ("asynchronous", "bool"),
    "background": ("background", "str"),
    "fps-cap": ("fps_cap", "int"),
    "reduced-motion": ("reduced_motion", "bool"),
    "glyph-size": ("glyph_size", "int"),
    "render-scale": ("render_scale", "float"),
    "render-mode": ("render_mode", "str"),
    "resource-guard": ("resource_guard", "bool"),
    "guard-cpu-pause": ("guard_cpu_pause", "int"),
    "guard-mem-pause": ("guard_mem_pause", "int"),
    "guard-cpu-resume": ("guard_cpu_resume", "int"),
    "guard-mem-resume": ("guard_mem_resume", "int"),
    "guard-pause-secs": ("guard_pause_secs", "float"),
    "guard-resume-secs": ("guard_resume_secs", "float"),
}


def _parse_bool(value):
    text = str(value).strip().lower()
    if text in ("on", "true", "yes", "1"):
        return True
    if text in ("off", "false", "no", "0"):
        return False
    raise ConfigError(f"expected on/off, got: {value}")


def _save(values, note):
    values, revision = lock.save_profile(values, note=note)
    print(f"saved lock-screen profile (revision {revision})")
    print(f"  {lock.summarize(values)}")
    if lock.is_enabled():
        lock.export_to_lockscreen(values)
        print("exported to the active KDE lock screen (applies on next lock)")
    return values


def cmd_show(_args):
    values = lock.load_profile()
    print("LOCK-SCREEN MATRIX PROFILE")
    print(f"  file = {lock.LOCK_CONFIG_PATH}")
    for key in lock.LOCK_DEFAULTS:
        print(f"  {key} = {values[key]}")
    print(f"\n  {lock.summarize(values)}")
    print(f"  enabled = {lock.is_enabled()}")
    return 0


def cmd_set(args):
    values = lock.load_profile()
    key = args.key.lower()
    if key == "hue":
        values = lock.set_hue_degrees(values, args.value)
        print(f"hue {float(args.value) % 360:.0f}° -> {values['color']}")
    elif key == "color":
        values = lock.set_color(values, args.value)
        print(f"color -> {values['color']}")
    elif key in SET_KEYS:
        leaf, kind = SET_KEYS[key]
        if kind == "bool":
            parsed = _parse_bool(args.value)
        elif kind == "int":
            parsed = int(args.value)
        elif kind == "float":
            parsed = float(args.value)
        else:
            parsed = str(args.value)
        values[leaf] = parsed
    else:
        known = ", ".join(["hue", "color", *SET_KEYS])
        raise ConfigError(f"unknown lock-screen setting: {args.key} (known: {known})")
    _save(values, note=f"matrix-lock set {key}")
    return 0


def cmd_capture_hue(_args):
    if not LAST_EFFECTIVE_PATH.exists():
        raise ConfigError("no recorded Matrix session settings; run matrix, adjust, then press S or h")
    terminal = lock.load_last_effective()
    values = lock.load_profile()
    phase = float(terminal.get("cycle_phase", 0.0)) % 1.0
    if terminal.get("color_cycle") or terminal.get("hue_hold"):
        values["cycle_phase"] = phase
        values["color"] = lock.rgb_to_hex(lock.cycle_rgb(phase))
        print(f"captured held hue: phase {phase:.4f} -> {values['color']}")
    elif "color" in terminal:
        values = lock.set_color(values, str(terminal["color"]))
        print(f"captured color: {values['color']}")
    else:
        raise ConfigError("the recorded session has no hue information")
    _save(values, note="matrix-lock capture-hue")
    return 0


def cmd_save(args):
    if args.from_last:
        values = lock.import_last_effective()
        _save(values, note="matrix-lock save --from-last")
    else:
        # Re-validate and re-save the current profile (also re-exports if enabled).
        _save(lock.load_profile(), note="matrix-lock save")
    return 0


def _run_terminal_preview(values):
    renderer = BIN / "unimatrix-fade"
    command = [str(renderer), *lock.renderer_preview_arguments(values)]
    return subprocess.call(command)


def cmd_preview(args):
    if args.greeter:
        if not GREETER.is_file():
            raise ConfigError(f"greeter not found: {GREETER}")
        if not lock.is_enabled():
            print("note: the Matrix lock wallpaper is not enabled; the greeter will show the current wallpaper")
        print("Starting the real lock-screen greeter in safe --testing mode (Esc closes it).")
        return subprocess.call([str(GREETER), "--testing"])
    values = lock.load_profile()
    print("Terminal approximation of the lock-screen profile (q exits; nothing is saved).")
    if values["color"] not in COLORS and not values["color_cycle"]:
        print(f"note: exact color {values['color']} previews as the nearest spectrum hue; the lock screen shows the exact color")
    time.sleep(1.2)
    return _run_terminal_preview(values)


def cmd_configure(args):
    preset_name = " ".join(args.preset) if getattr(args, "preset", None) else None
    if preset_name:
        values, canonical = lock.apply_preset(lock.load_profile(), preset_name)
        if lock.normalize_preset_name(preset_name) not in lock.load_lock_presets():
            print(f"note: '{canonical}' is not a named user preset; edits can be saved as a new one")
        print(f"Lock-screen configuration session — editing preset '{preset_name}'")
        print("  The saved preset stays untouched until you explicitly choose to update it.")
    else:
        values = lock.load_profile()
        print("Lock-screen configuration session")
    print("  - Use the normal Matrix controls (h holds a hue, x marks a hue exclusion,")
    print("    u/U undo/redo, X clears exclusions, r resets the session, ? shows keys).")
    print("  - Exit with q when the preview looks right.")
    if values["color"] not in COLORS and not values["color_cycle"]:
        print(f"  - note: exact color {values['color']} previews as the nearest spectrum hue.")
    time.sleep(2.0)
    before = LAST_EFFECTIVE_PATH.stat().st_mtime_ns if LAST_EFFECTIVE_PATH.exists() else -1
    _run_terminal_preview(values)
    after = LAST_EFFECTIVE_PATH.stat().st_mtime_ns if LAST_EFFECTIVE_PATH.exists() else -1
    if after == before or after < 0:
        print("No settings were recorded by the preview session; lock-screen profile unchanged.")
        return 0
    captured = lock.import_last_effective()
    print("\nCaptured effective settings:")
    print(f"  {lock.summarize(captured)}")
    if captured["cycle_exclusions"]:
        print(f"  hue exclusions: {lock.describe_exclusions(captured['cycle_exclusions'])}")
    if not sys.stdin.isatty():
        print("Non-interactive session: not saving. Use matrix-lock save --from-last to apply.")
        return 0
    if preset_name:
        print("Save this look as:")
        print(f"  [1] update preset \"{preset_name}\"")
        print("  [2] a new named preset")
        print("  [3] my active lock-screen configuration")
        print(f"  [4] both: active configuration + preset \"{preset_name}\"")
        print("  [5] discard (default)")
        choice = input("Choice [1-5]: ").strip()
        if choice in ("1", "4"):
            answer = input(f"Update preset '{preset_name}'? [y/N] ").strip().lower()
            if answer in ("y", "yes"):
                canonical = lock.save_lock_preset(preset_name, captured, force=True)
                print(f"updated preset '{preset_name}' ({canonical})")
            else:
                print(f"preset '{preset_name}' left unchanged")
        if choice == "2":
            _save_captured_as_preset(captured)
        if choice in ("3", "4"):
            _save(captured, note=f"matrix-lock configure --preset {preset_name}")
        if choice not in ("1", "2", "3", "4"):
            print("Discarded; nothing was saved.")
        return 0
    print("Save this look as:")
    print("  [1] my active lock-screen configuration")
    print("  [2] a named preset")
    print("  [3] both")
    print("  [4] discard (default)")
    choice = input("Choice [1-4]: ").strip()
    if choice in ("1", "3"):
        _save(captured, note="matrix-lock configure")
    if choice in ("2", "3"):
        _save_captured_as_preset(captured)
    if choice not in ("1", "2", "3"):
        print("Discarded; the lock-screen profile is unchanged.")
    return 0


def _save_captured_as_preset(captured):
    while True:
        name = input('Preset name (e.g. "Neon Purple", empty cancels): ').strip()
        if not name:
            print("No preset saved.")
            return
        try:
            try:
                canonical = lock.save_lock_preset(name, captured)
            except ConfigError as exc:
                if "already exists" not in str(exc):
                    raise
                answer = input(f"Preset '{name}' exists. Replace it? [y/N] ").strip().lower()
                if answer not in ("y", "yes"):
                    continue
                canonical = lock.save_lock_preset(name, captured, force=True)
            print(f"saved preset '{name}' ({canonical}); apply later with: "
                  f'matrix-lock preset apply "{name}"')
            return
        except ConfigError as exc:
            print(f"cannot save preset: {exc}")


def _format_exclusion_row(item):
    from_label = f"{hue_from_phase(item['start']):6.1f}\N{DEGREE SIGN} ({item['start']:.6f})"
    to_label = f"{hue_from_phase(item['end']):6.1f}\N{DEGREE SIGN} ({item['end']:.6f})"
    state = "yes" if item["enabled"] else "no"
    return f"{item['id']:>3}  {from_label:<22} {to_label:<22} {item['blend']:>5.2f}s  {state}"


def _print_cycle_summary(values):
    exclusions = values["cycle_exclusions"]
    try:
        gaps = enabled_cycle_gaps(exclusions)
    except ConfigError as exc:
        print(f"  (invalid exclusion set: {exc})")
        return
    if not gaps:
        print("  full spectrum: no enabled exclusions; the cycle is unchanged")
        return
    path = build_cycle_path(exclusions, values["cycle_period"])
    visible = 1.0 - sum(((end - start) % 1.0) or 1.0 for start, end, _ in gaps)
    print(f"  visible spectrum: {visible * 100:.0f}% | loop duration: "
          f"{path['total']:.1f}s (period {values['cycle_period']:g}s, "
          f"{len(gaps)} gap(s) bridged)")


def cmd_cycle(args):
    values = lock.load_profile()
    command = args.cycle_command
    if command == "show":
        state = "on" if values["color_cycle"] else "off"
        print(f"hue cycling: {state} | period {values['cycle_period']:g}s | "
              f"direction {values['cycle_direction']} | anchor phase {values['cycle_phase']:.6f}")
        if values["cycle_exclusions"]:
            print(" ID  FROM                   TO                     BLEND  ENABLED")
            for item in values["cycle_exclusions"]:
                print(_format_exclusion_row(item))
        else:
            print("  (no exclusions)")
        _print_cycle_summary(values)
        print("Degrees map exactly onto the cycle (its spectrum spans hue 120\N{DEGREE SIGN} "
              "through the wheel and back); --phase accepts exact 0-1 positions.")
        return 0
    if command == "reset":
        if not values["cycle_exclusions"]:
            print("cycle customization is already at defaults (no exclusions)")
            return 0
        values["cycle_exclusions"] = []
        print("cycle customization reset: all exclusions removed, full spectrum restored")
        print("(matrix-lock undo restores the previous customization)")
        _save(values, note="matrix-lock cycle reset")
        return 0
    # exclude subcommands
    sub = args.exclude_command
    exclusions = [dict(item) for item in values["cycle_exclusions"]]
    if sub == "list":
        if exclusions:
            print(" ID  FROM                   TO                     BLEND  ENABLED")
            for item in exclusions:
                print(_format_exclusion_row(item))
        else:
            print("(no exclusions)")
        _print_cycle_summary(values)
        return 0
    if sub == "add":
        if args.phase:
            try:
                start, end = float(args.start) % 1.0, float(args.end) % 1.0
            except ValueError as exc:
                raise ConfigError(f"--phase values must be numbers 0-1: {exc}") from exc
        else:
            start, end = phase_from_hue(args.start), phase_from_hue(args.end)
        blend = CYCLE_BLEND_DEFAULT if args.blend is None else float(args.blend)
        exclusions.append({"start": start, "end": end, "blend": blend, "enabled": True})
        values["cycle_exclusions"] = normalize_cycle_exclusions(exclusions)
        created = values["cycle_exclusions"][-1]
        print(f"added exclusion #{created['id']}: "
              f"{hue_from_phase(created['start']):.1f}\N{DEGREE SIGN} -> "
              f"{hue_from_phase(created['end']):.1f}\N{DEGREE SIGN} "
              f"(phases {created['start']:.6f} -> {created['end']:.6f}, "
              f"blend {created['blend']:g}s)")
    elif sub == "clear":
        if not exclusions:
            print("(no exclusions to clear)")
            return 0
        values["cycle_exclusions"] = []
        print("all exclusions removed (matrix-lock undo restores them)")
    else:
        target = next((item for item in exclusions if item["id"] == args.id), None)
        if target is None:
            raise ConfigError(f"no exclusion with id {args.id} (matrix-lock cycle exclude list)")
        if sub == "remove":
            exclusions.remove(target)
            print(f"removed exclusion #{args.id}")
        elif sub == "enable":
            target["enabled"] = True
            print(f"enabled exclusion #{args.id}")
        elif sub == "disable":
            target["enabled"] = False
            print(f"disabled exclusion #{args.id}")
        elif sub == "set-blend":
            target["blend"] = float(args.seconds)
            print(f"exclusion #{args.id} blend -> {float(args.seconds):g}s")
        values["cycle_exclusions"] = normalize_cycle_exclusions(exclusions)
    _save(values, note=f"matrix-lock cycle exclude {sub}")
    _print_cycle_summary(values)
    return 0


def cmd_quality(args):
    if args.name is None:
        values = lock.load_profile()
        print(f"render_mode = {values['render_mode']} | fps_cap = {values['fps_cap']} | "
              f"speed = {values['speed']} | density = {values['density']} | "
              f"flashers = {values['flashers']} | render_scale = {values['render_scale']}")
        print("Presets: balanced (default; smooth GPU rendering), high (60 FPS cap + flashes),")
        print("         battery (low-power canvas, soft trails, 12 FPS cap)")
        return 0
    values, canonical = lock.apply_quality(lock.load_profile(), args.name)
    print(f"applied quality preset: {canonical} (colors and hue settings untouched)")
    _save(values, note=f"matrix-lock quality {canonical}")
    return 0


def _print_preset_list():
    print("BUILT-IN PRESETS")
    for name in PRESETS:
        print(f"  {name:<14} {PRESET_DESCRIPTIONS.get(name, '')}".rstrip())
    print("USER PRESETS")
    entries = lock.load_lock_presets()
    terminal = {name: values for name, values in load_user_presets().items()
                if name not in entries}
    for canonical in sorted(entries):
        display = entries[canonical]["display_name"]
        suffix = f"  ({canonical})" if display != canonical else ""
        print(f"  {display}{suffix}")
    for name in sorted(terminal):
        print(f"  {name}  (terminal capture via matrix-preset)")
    if not entries and not terminal:
        print("  (none)")


def cmd_preset(args):
    command = args.preset_command
    if command == "list":
        _print_preset_list()
        return 0
    if command == "save":
        name = " ".join(args.name)
        values = lock.load_profile()
        canonical = lock.save_lock_preset(name, values, force=args.force)
        print(f"saved preset '{name.strip()}' ({canonical}) from the current lock-screen profile")
        print(f"  {lock.summarize(values)}")
        return 0
    if command == "show":
        name = " ".join(args.name)
        canonical = lock.normalize_preset_name(name)
        entry = lock.load_lock_presets().get(canonical)
        if entry is not None:
            print(f"{entry['display_name']} ({canonical})")
            for key in lock.VISUAL_KEYS:
                if key in entry["values"]:
                    print(f"  {key} = {entry['values'][key]}")
            return 0
        builtin = PRESETS.get(canonical, load_user_presets().get(canonical))
        if builtin is None:
            raise ConfigError(f"unknown preset: {canonical}")
        kind = "built-in" if canonical in PRESETS else "terminal capture"
        print(f"{canonical} ({kind})")
        if canonical in PRESET_DESCRIPTIONS:
            print(f"  {PRESET_DESCRIPTIONS[canonical]}")
        for key in sorted(builtin):
            print(f"  {key} = {builtin[key]}")
        return 0
    if command == "rename":
        canonical = lock.rename_lock_preset(args.old, args.new)
        print(f"renamed to '{args.new.strip()}' ({canonical})")
        return 0
    if command == "delete":
        lock.delete_lock_preset(" ".join(args.name))
        print("deleted")
        return 0
    # apply
    values, canonical = lock.apply_preset(lock.load_profile(), " ".join(args.name))
    print(f"applied preset: {canonical} (resource-protection settings untouched)")
    _save(values, note=f"matrix-lock preset apply {canonical}")
    return 0


def cmd_history(_args):
    entries = lock.history_entries()
    if not entries:
        print("no saved lock-screen revisions yet")
        return 0
    print(f"{'REVISION':<18} {'SAVED':<20} SUMMARY")
    for revision, values in entries:
        stamp = f"{revision[0:4]}-{revision[4:6]}-{revision[6:8]} {revision[9:11]}:{revision[11:13]}:{revision[13:15]}"
        print(f"{revision:<18} {stamp:<20} {lock.summarize(values)}")
    return 0


def cmd_undo(_args):
    entries = lock.history_entries()
    if len(entries) < 2:
        raise ConfigError("no previous revision to restore")
    current = lock.load_profile()
    target = None
    for revision, values in entries:
        if values != current:
            target = (revision, values)
            break
    if target is None:
        raise ConfigError("all recorded revisions match the current profile")
    print(f"restoring revision {target[0]}")
    _save(target[1], note=f"matrix-lock undo -> {target[0]}")
    return 0


def cmd_restore(args):
    values = lock.load_revision(args.revision)
    print(f"restoring revision {args.revision}")
    _save(values, note=f"matrix-lock restore {args.revision}")
    return 0


def cmd_enable(_args):
    previous = lock.enable()
    print(f"Matrix lock-screen wallpaper enabled (previous plugin: {previous}).")
    print("The change applies the next time the screen locks.")
    print("Test safely first with: matrix-lock preview --greeter")
    return 0


def cmd_disable(_args):
    previous = lock.disable()
    print(f"Matrix lock-screen wallpaper disabled; restored plugin: {previous}")
    return 0


def cmd_status(_args):
    print(f"plugin installed : {lock.plugin_installed()} ({lock.PLUGIN_DIR})")
    print(f"enabled          : {lock.is_enabled()} (kscreenlockerrc WallpaperPlugin = {lock.current_wallpaper_plugin()})")
    try:
        values = lock.load_profile()
        print(f"profile          : {lock.LOCK_CONFIG_PATH}")
        print(f"                   {lock.summarize(values)}")
    except ConfigError as exc:
        print(f"profile          : INVALID ({exc})")
    entries = lock.history_entries()
    print(f"history          : {len(entries)} revision(s) in {lock.HISTORY_DIR}")
    print(f"rollback backup  : {'present' if lock.WALLPAPER_BACKUP_PATH.exists() else 'none'} ({lock.WALLPAPER_BACKUP_PATH})")
    return 0


def cmd_doctor(_args):
    def report(label, status, detail):
        print(f"{status:<4} {label}: {detail}")

    print("matrix-lock doctor (read-only)")
    report("Wallpaper plugin files", "PASS" if lock.plugin_installed() else "FAIL", str(lock.PLUGIN_DIR))
    report("Greeter binary", "PASS" if GREETER.is_file() else "WARN", str(GREETER))
    report("kscreenlockerrc", "PASS" if lock.KSCREENLOCKERRC.exists() else "WARN", str(lock.KSCREENLOCKERRC))
    report("Wallpaper plugin selected", "PASS" if lock.is_enabled() else "WARN",
           lock.current_wallpaper_plugin())
    try:
        values = lock.load_profile()
        report("Lock profile", "PASS", lock.summarize(values))
    except ConfigError as exc:
        report("Lock profile", "FAIL", str(exc))
    report("Profile history", "PASS", f"{len(lock.history_entries())} revision(s)")
    report("Rollback backup", "PASS" if lock.WALLPAPER_BACKUP_PATH.exists() or not lock.is_enabled() else "WARN",
           str(lock.WALLPAPER_BACKUP_PATH))
    report("Terminal capture", "PASS" if LAST_EFFECTIVE_PATH.exists() else "WARN",
           str(LAST_EFFECTIVE_PATH) if LAST_EFFECTIVE_PATH.exists() else "no session recorded yet")
    for tool in ("kscreen-doctor", "loginctl"):
        report(tool, "PASS" if shutil.which(tool) else "WARN", shutil.which(tool) or "not found")
    report("Authentication", "PASS", "matrix-lock never modifies KScreenLocker, PAM, or SDDM; wallpaper only")
    try:
        values = lock.load_profile()
        if values["resource_guard"]:
            probe = resource_guard.ResourceGuard(cfg=values, interval_s=0.0)
            probe.poll()
            time.sleep(1.0)
            probe.poll()
            report("Resource guard", "PASS",
                   f"{probe.describe()} (pause {values['guard_cpu_pause']}%cpu/"
                   f"{values['guard_mem_pause']}%mem after {values['guard_pause_secs']:.0f}s, "
                   f"resume <{values['guard_cpu_resume']}%/{values['guard_mem_resume']}% "
                   f"for {values['guard_resume_secs']:.0f}s)")
        else:
            report("Resource guard", "WARN", "disabled (matrix-lock set resource-guard on)")
    except (ConfigError, OSError) as exc:
        report("Resource guard", "WARN", f"metrics unavailable: {exc}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="matrix-lock",
        description="Configure the Matrix Digital Rain animated KDE lock-screen wallpaper.",
        epilog="The lock-screen profile is independent from the terminal Matrix profile. "
               "Workflow: matrix-lock configure -> adjust -> save; matrix-lock enable activates it.")
    sub = parser.add_subparsers(dest="command", required=True)
    configure = sub.add_parser("configure", help="live terminal preview session; offers to save on exit")
    configure.add_argument("--preset", nargs="+", default=None, metavar="NAME",
                           help="start from a named preset and offer to update it on exit")
    preview = sub.add_parser("preview", help="preview the current lock profile")
    preview.add_argument("--greeter", action="store_true",
                         help="run the real KDE greeter in safe --testing mode")
    save = sub.add_parser("save", help="save/re-export the profile")
    save.add_argument("--from-last", action="store_true",
                      help="import the most recent effective terminal Matrix settings")
    sub.add_parser("show", help="print the active lock-screen settings")
    setter = sub.add_parser("set", help="set one lock-screen value (hue, color, color-cycle, speed, ...)")
    setter.add_argument("key")
    setter.add_argument("value")
    sub.add_parser("capture-hue", help="capture the most recently held hue from a Matrix session")
    cycle = sub.add_parser(
        "cycle",
        help="customize the automatic hue cycle (exclude ranges, blends)",
        description="Exclude parts of the hue cycle; the retained endpoints are bridged by a "
                    "short, smooth crossfade. START/END are hue degrees by default (they map "
                    "exactly onto the cycle); pass --phase for exact 0-1 cycle positions. "
                    "Every change saves a history revision, so matrix-lock undo reverses it.")
    cycle_sub = cycle.add_subparsers(dest="cycle_command", required=True)
    cycle_sub.add_parser("show", help="cycling state, exclusions, and the blended path summary")
    cycle_sub.add_parser("reset", help="remove all cycle customization (undo: matrix-lock undo)")
    exclude = cycle_sub.add_parser("exclude", help="manage excluded hue ranges")
    exclude_sub = exclude.add_subparsers(dest="exclude_command", required=True)
    exclude_add = exclude_sub.add_parser("add", help="exclude a range, e.g. add 45 105 (degrees)")
    exclude_add.add_argument("start")
    exclude_add.add_argument("end")
    exclude_add.add_argument("--phase", action="store_true",
                             help="interpret START and END as exact cycle phases (0-1)")
    exclude_add.add_argument("--blend", type=float, default=None,
                             help="bridge crossfade duration in seconds (default 1.0)")
    exclude_sub.add_parser("list", help="list exclusions with ids, degrees, phases, blends")
    for name, help_text in (("remove", "delete one exclusion by id"),
                            ("enable", "re-enable one exclusion by id"),
                            ("disable", "keep one exclusion but stop applying it")):
        entry = exclude_sub.add_parser(name, help=help_text)
        entry.add_argument("id", type=int)
    exclude_sub.add_parser("clear", help="remove every exclusion")
    set_blend = exclude_sub.add_parser("set-blend", help="change one exclusion's crossfade seconds")
    set_blend.add_argument("id", type=int)
    set_blend.add_argument("seconds", type=float)
    quality = sub.add_parser("quality", help="show or apply a rendering quality preset (balanced/high/battery)")
    quality.add_argument("name", nargs="?", default=None)
    preset = sub.add_parser(
        "preset",
        help="manage named lock-screen presets (list/show/save/apply/rename/delete)",
        description="Named lock-screen presets capture the current visual configuration "
                    "(exact color or hue cycle, pacing, trails, render mode, ...) under a "
                    "friendly name. Built-in presets are read-only; applying any preset "
                    "never changes resource-protection settings and creates a history "
                    "revision, so matrix-lock undo restores the previous appearance.")
    preset_sub = preset.add_subparsers(dest="preset_command", required=True)
    preset_sub.add_parser("list", help="built-in and user presets, listed separately")
    show_parser = preset_sub.add_parser("show", help="print one preset's stored values")
    show_parser.add_argument("name", nargs="+")
    save_parser = preset_sub.add_parser(
        "save", help='save the current lock profile as a named preset, e.g. preset save "Neon Purple"')
    save_parser.add_argument("name", nargs="+")
    save_parser.add_argument("--force", action="store_true",
                             help="replace an existing user preset of the same name")
    apply_parser = preset_sub.add_parser("apply", help="apply a named, built-in, or terminal preset")
    apply_parser.add_argument("name", nargs="+")
    rename_parser = preset_sub.add_parser("rename", help="rename a user preset")
    rename_parser.add_argument("old")
    rename_parser.add_argument("new")
    delete_parser = preset_sub.add_parser("delete", help="delete a user preset")
    delete_parser.add_argument("name", nargs="+")
    sub.add_parser("history", help="list saved lock-screen revisions")
    sub.add_parser("undo", help="restore the most recent different revision")
    restore = sub.add_parser("restore", help="restore a specific revision")
    restore.add_argument("revision")
    sub.add_parser("enable", help="activate the Matrix lock-screen wallpaper (backs up the previous one)")
    sub.add_parser("disable", help="restore the previous lock-screen wallpaper")
    sub.add_parser("status", help="show installation/activation state")
    sub.add_parser("doctor", help="read-only lock-screen diagnostics")
    args = parser.parse_args()
    handlers = {
        "configure": cmd_configure, "preview": cmd_preview, "save": cmd_save,
        "show": cmd_show, "set": cmd_set, "capture-hue": cmd_capture_hue,
        "quality": cmd_quality,
        "preset": cmd_preset, "cycle": cmd_cycle, "history": cmd_history, "undo": cmd_undo,
        "restore": cmd_restore, "enable": cmd_enable, "disable": cmd_disable,
        "status": cmd_status, "doctor": cmd_doctor,
    }
    try:
        return handlers[args.command](args)
    except ConfigError as exc:
        parser.error(str(exc))
    except (ValueError, TypeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
