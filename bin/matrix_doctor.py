#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
"""Read-only diagnostics for the local Matrix/Konsole utility."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from matrix_config import CONFIG_PATH, ConfigError, load_config, runtime_dir
from matrix_saver import idle_source_name
from matrix_cursor import status as cursor_status

BIN = Path(__file__).resolve().parent
DATA = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
PROFILE = DATA / "konsole/Matrix.profile"
SCHEME = DATA / "konsole/Matrix.colorscheme"


def report(label, status, detail):
    print(f"{status:<4} {label}: {detail}")


def command_output(command):
    try:
        return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT, timeout=4).strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def main():
    print("Konsole-Matrix-Digital-Rain doctor (read-only)")
    os_release = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                os_release[key] = value.strip('"')
    except OSError:
        pass
    report("Fedora", "PASS" if os_release.get("ID") == "fedora" else "WARN", os_release.get("PRETTY_NAME", "unknown"))
    report("Desktop", "PASS" if os.environ.get("XDG_CURRENT_DESKTOP") == "KDE" else "WARN", os.environ.get("XDG_CURRENT_DESKTOP", "unknown"))
    report("Wayland", "PASS" if os.environ.get("XDG_SESSION_TYPE") == "wayland" else "WARN", os.environ.get("XDG_SESSION_TYPE", "unknown"))
    konsole = shutil.which("konsole")
    report("Konsole", "PASS" if konsole else "FAIL", command_output(["konsole", "--version"]) if konsole else "not found")
    term = os.environ.get("TERM", "")
    colors = command_output(["tput", "colors"]) if shutil.which("tput") and term else ""
    report("TERM", "PASS" if term == "xterm-256color" else "WARN", term or "unset")
    report("Terminal colors", "PASS" if colors == "256" else "WARN", colors or "unavailable")
    kscreen = shutil.which("kscreen-doctor")
    report("KScreen", "PASS" if kscreen else "FAIL", kscreen or "not found")
    count = "unavailable"
    if kscreen:
        try:
            data = json.loads(command_output(["kscreen-doctor", "--json"]) or "{}")
            outputs = data.get("outputs", [])
            count = str(sum(bool(o.get("connected")) and (o.get("enabled", o.get("currentModeId"))) for o in outputs))
        except (ValueError, TypeError):
            pass
    report("Enabled displays", "PASS" if count.isdigit() and int(count) > 0 else "WARN", count)
    kwin = command_output(["gdbus", "introspect", "--session", "--dest", "org.kde.KWin", "--object-path", "/Scripting"])
    report("KWin scripting", "PASS" if kwin else "WARN", "available" if kwin else "session bus unavailable or KWin API not exposed")
    report("Matrix profile", "PASS" if PROFILE.is_file() else "FAIL", str(PROFILE))
    report("Matrix color scheme", "PASS" if SCHEME.is_file() else "FAIL", str(SCHEME))
    translucent_scheme = DATA / "konsole/Matrix-Translucent.colorscheme"
    translucent_profile = DATA / "konsole/Matrix-Translucent.profile"
    translucent_ok = translucent_scheme.is_file() and translucent_profile.is_file()
    report("Translucent Matrix profile", "PASS" if translucent_ok else "WARN", str(translucent_profile))
    report("Renderer", "PASS" if (BIN / "matrix_renderer.py").is_file() else "FAIL", str(BIN / "matrix_renderer.py"))
    report("Sync renderer", "PASS" if (BIN / "unimatrix-fade-sync").is_file() else "FAIL", str(BIN / "unimatrix-fade-sync"))
    guide_ok = all((BIN / name).is_file() for name in ("matrix-guide", "matrix_guide.py", "matrix_guide_data.py"))
    report("Guide", "PASS" if guide_ok else "WARN", str(BIN / "matrix-guide"))
    try:
        config, _ = load_config()
        report("Configuration", "PASS", str(CONFIG_PATH))
        report("Saver config", "PASS", str(config.get("saver", {})))
        report("Exit guard", "PASS", str(config.get("exit_guard", {})))
    except ConfigError as exc:
        report("Configuration", "FAIL", str(exc))
    kf6_runtime = Path("/usr/lib64/libKF6IdleTime.so.6").is_file()
    report(
        "KF6 KIdleTime runtime",
        "PASS" if kf6_runtime else "WARN",
        "installed in-process library; no session D-Bus service is assumed"
        if kf6_runtime else "runtime library not found",
    )
    idle_source = idle_source_name()
    report(
        "Idle activation source",
        "PASS" if idle_source else "WARN",
        idle_source or "systemd-logind IdleHint/IdleSinceHintMonotonic unavailable",
    )
    report(
        "Activity-return source",
        "PASS" if idle_source else "WARN",
        idle_source or "no reliable global return-activity source available",
    )
    report("Idle inhibitors", "WARN", "no reliable query API exposed; no application-name heuristic is used")
    report("Lock handoff", "PASS" if shutil.which("loginctl") else "FAIL", "loginctl lock-session" if shutil.which("loginctl") else "not found")
    unit = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "systemd/user/matrix-saver.service"
    report("User service unit", "PASS" if unit.is_file() else "WARN", str(unit))
    service = command_output(["systemctl", "--user", "is-enabled", "matrix-saver.service"]) if shutil.which("systemctl") else ""
    report("User service status", "PASS" if service in ("enabled", "static") else "WARN", service or "not enabled or user bus unavailable")
    rd = runtime_dir()
    try:
        mode = rd.stat().st_mode & 0o777
        report("Runtime directory", "PASS" if mode & 0o077 == 0 else "WARN", f"permissions {mode:03o}")
    except OSError as exc:
        report("Runtime directory", "WARN", str(exc))
    stale = runtime_dir() / "matrix-saver/state.json"
    report("Saver runtime state", "PASS", "none present" if not stale.exists() else "WARN: state file present; controller lock ownership should be checked")
    cursor = cursor_status()
    cursor_detail = "stock Plasma auto-hide only; continuous hide while moving is unavailable" if cursor["available"] else "stock Plasma hidecursor effect or session D-Bus unavailable"
    if cursor["stale_override"]:
        cursor_detail += "; stale Matrix cursor override marker present (next matrix-all restores it)"
    report("Cursor suppression", "WARN", cursor_detail)
    report("Live translucency", "WARN", "Matrix translucent profile is launch-time only; live b changes cannot alter existing Konsole opacity")
    report("Plugin panel suppression", "WARN", "no reliable per-window Konsole SSH/Quick Commands action API; global plugin settings untouched")
    report("Secure lock visual", "WARN", "Matrix windows are behind KDE's authoritative lock screen after lock handoff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
