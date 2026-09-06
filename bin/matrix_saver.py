#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
"""Idle-triggered Matrix controller with separate immediate and automatic paths."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from matrix_config import ConfigError, load_config, runtime_dir, secure_private_dir
from matrix_guide_data import saver_help_text

BIN_DIR = Path(__file__).resolve().parent
STATE_DIR = runtime_dir() / "matrix-saver"
STATE_PATH = STATE_DIR / "state.json"
LOCK_PATH = STATE_DIR / "controller.lock"
STOP = False


def stop(signum, frame):
    global STOP
    STOP = True


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGHUP, stop)


class IdleMonitor:
    """Standards-based session idle/activity source, if exposed by logind."""

    name = "systemd-logind IdleHint/IdleSinceHintMonotonic"

    def idle_ms(self):
        raise NotImplementedError


class LogindIdleMonitor(IdleMonitor):
    def __init__(self, session=None):
        self.session = session or os.environ.get("XDG_SESSION_ID")

    def _values(self):
        if not self.session or not shutil.which("loginctl"):
            return None
        command = [
            "loginctl", "show-session", self.session,
            "-p", "IdleHint", "-p", "IdleSinceHintMonotonic", "--value",
        ]
        try:
            output = subprocess.check_output(
                command, text=True, stderr=subprocess.DEVNULL, timeout=2
            )
        except (OSError, subprocess.SubprocessError):
            return None
        values = []
        for line in output.splitlines():
            line = line.strip()
            if "=" in line:
                line = line.split("=", 1)[1]
            values.append(line)
        if len(values) < 2:
            return None
        idle_hint = values[0].lower() in ("1", "yes", "true")
        try:
            since_us = int(values[1])
        except ValueError:
            return None
        return idle_hint, since_us

    def idle_ms(self):
        values = self._values()
        if values is None:
            return None
        idle_hint, since_us = values
        if not idle_hint:
            return 0
        if since_us <= 0:
            return None
        now_us = time.monotonic_ns() // 1000
        return max(0, (now_us - since_us) // 1000)

    def probe(self):
        return self.idle_ms() is not None


def select_idle_monitor():
    monitor = LogindIdleMonitor()
    return monitor if monitor.probe() else None


def idle_source_name():
    monitor = select_idle_monitor()
    return monitor.name if monitor else None


def lock_command(dry_run=False):
    session = os.environ.get("XDG_SESSION_ID")
    command = ["loginctl", "lock-session"] + ([session] if session else [])
    if dry_run:
        return command
    if not shutil.which("loginctl"):
        raise RuntimeError("loginctl is unavailable; secure lock handoff is unsupported")
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return command


def battery_ok(settings):
    battery = settings.get("battery", {})
    if not battery.get("enabled", False):
        return True
    capacities = []
    for path in Path("/sys/class/power_supply").glob("*/capacity"):
        try:
            capacities.append(int(path.read_text(encoding="ascii").strip()))
        except (OSError, ValueError):
            pass
    if not capacities:
        return True
    return min(capacities) > int(battery.get("disable_below_percent", 20))


def write_state(active, reason="", child=None):
    secure_private_dir(STATE_DIR)
    payload = {
        "pid": os.getpid(),
        "active": bool(active),
        "reason": reason,
        "updated": time.time(),
        "child_pid": child,
    }
    temp = STATE_DIR / f"state.json.tmp.{os.getpid()}"
    with open(temp, "x", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temp, 0o600)
    os.replace(temp, STATE_PATH)


def remove_state():
    try:
        STATE_PATH.unlink()
    except FileNotFoundError:
        pass


def remove_controller_lock():
    try:
        LOCK_PATH.unlink()
    except FileNotFoundError:
        pass


def remove_runtime_dir_if_empty():
    try:
        STATE_DIR.rmdir()
    except OSError:
        pass


def renderer_is_owned(proc):
    if proc is None or proc.poll() is not None:
        return False
    try:
        command = Path(f"/proc/{proc.pid}/cmdline").read_bytes().replace(
            b"\0", b" "
        ).decode(errors="replace")
    except OSError:
        return False
    return "matrix-all" in command or "unimatrix-fade" in command


def renderer_process_group_is_owned(proc):
    if not renderer_is_owned(proc):
        return False
    try:
        return os.getpgid(proc.pid) == proc.pid
    except OSError:
        return False


def activate_now(dry_run=False, preset=None):
    command = [str(BIN_DIR / "matrix-all")]
    if preset:
        command.extend(["--preset", *preset])
    if dry_run:
        return None, command
    if not (BIN_DIR / "matrix-all").is_file():
        raise RuntimeError("matrix-all is missing")
    proc = subprocess.Popen(
        command,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    write_state(True, "active", proc.pid)
    return proc, command


def deactivate(proc):
    if not renderer_process_group_is_owned(proc):
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if renderer_process_group_is_owned(proc):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def wait_for_explicit_exit(proc):
    while not STOP and proc.poll() is None:
        time.sleep(0.5)


def wait_for_activity(proc, monitor):
    baseline = monitor.idle_ms() if monitor else None
    if monitor is None:
        print(
            "matrix-saver: activity-return monitoring unavailable; "
            "use q/Escape/Space/Ctrl+C in Matrix for explicit cleanup",
            file=sys.stderr,
            flush=True,
        )
        wait_for_explicit_exit(proc)
        return "explicit-exit"
    while not STOP and proc.poll() is None:
        current = monitor.idle_ms()
        if current is None:
            print(
                "matrix-saver: activity-return source disappeared; "
                "falling back to explicit Matrix-window exit",
                file=sys.stderr,
                flush=True,
            )
            wait_for_explicit_exit(proc)
            return "source-lost"
        if baseline is not None and (
            current + 1000 < baseline or (baseline > 3000 and current < 2000)
        ):
            return "activity"
        time.sleep(1)
    return "explicit-exit"


def wait_for_after_lock(proc, delay):
    """Wait for timeout, Matrix exit, interruption, or reliable activity return."""
    monitor = select_idle_monitor()
    baseline = monitor.idle_ms() if monitor else None
    if monitor:
        print(f"matrix-saver: activity-return source: {monitor.name}", flush=True)
    deadline = time.monotonic() + delay
    while not STOP and proc.poll() is None and time.monotonic() < deadline:
        if monitor:
            current = monitor.idle_ms()
            if current is None:
                monitor = None
            elif baseline is not None and (
                current + 1000 < baseline or (baseline > 3000 and current < 2000)
            ):
                break
        time.sleep(0.5)


def run_once(settings, mode, dry_run=False, preset=None):
    """Activate immediately; only visual-only may use activity monitoring afterward."""
    if dry_run:
        return {
            "mode": mode,
            "activation_command": [str(BIN_DIR / "matrix-all")] + (["--preset", *preset] if preset else []),
            "activation_performed": mode != "immediate",
            "lock_command": None if mode == "visual-only" else lock_command(True),
            "idle_monitor_required": False,
            "exit_action": {
                "visual-only": "return-unlocked",
                "immediate": "lock-immediately",
                "after": "lock-on-timeout-or-exit",
            }[mode],
        }

    if mode == "immediate":
        lock_command()
        return {
            "activated": False,
            "success": True,
            "locked": True,
            "mode": mode,
        }

    proc, _ = activate_now(preset=preset)
    try:
        if mode == "after":
            delay = max(0, int(settings.get("saver", {}).get("lock_delay_seconds", 30)))
            print(
                f"matrix-saver: Matrix active; locking after {delay} second(s)",
                flush=True,
            )
            wait_for_after_lock(proc, delay)
            # After mode is explicitly secure: timeout, Matrix exit, and
            # controller interruption all hand off to KDE locking.
            lock_command()
            return {"activated": True, "locked": True, "mode": mode}
        monitor = select_idle_monitor()
        if monitor:
            print(
                f"matrix-saver: activity-return source: {monitor.name}",
                flush=True,
            )
        else:
            print(
                "matrix-saver: Matrix activated; no reliable global activity-return "
                "source is available",
                file=sys.stderr,
                flush=True,
            )
        wait_for_activity(proc, monitor)
        return {"activated": True, "locked": False, "mode": mode}
    finally:
        deactivate(proc)
        remove_state()


def run_automatic(settings, monitor):
    """Wait for an idle threshold, then use the same activation lifecycle."""
    saver = settings.get("saver", {})
    threshold = max(1, int(saver.get("idle_minutes", 3))) * 60 * 1000
    print(
        f"matrix-saver: automatic activation source: {monitor.name}; "
        f"threshold {threshold // 60000} minute(s)",
        flush=True,
    )
    while not STOP:
        current = monitor.idle_ms()
        if current is None:
            raise RuntimeError("automatic idle source disappeared")
        if current >= threshold:
            mode = str(saver.get("lock_mode", "visual-only")).lower()
            run_once(settings, mode)
        time.sleep(2)


def acquire_controller_lock():
    secure_private_dir(STATE_DIR)
    handle = open(LOCK_PATH, "a+", encoding="utf-8")
    os.chmod(LOCK_PATH, 0o600)
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RuntimeError("another matrix-saver controller is already running")
    return handle


def main():
    parser = argparse.ArgumentParser(
        description="KDE-idle Matrix screensaver controller",
        epilog=saver_help_text(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="activate immediately; never wait for the idle threshold",
    )
    parser.add_argument(
        "mode", nargs="?", choices=("visual-only", "immediate", "after"),
        help="concise one-shot mode; equivalent to --once --lock-mode MODE",
    )
    parser.add_argument("--preset", nargs="+", metavar="NAME", help="visual preset forwarded to matrix-all")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show activation/lock operations without starting windows",
    )
    parser.add_argument(
        "--lock-mode",
        choices=("visual-only", "immediate", "after"),
        default=None,
    )
    parser.add_argument("--ignore-idle-inhibitors", action="store_true")
    args = parser.parse_args()

    try:
        settings, _ = load_config()
        saver = settings.get("saver", {})
        if args.mode:
            args.once = True
        mode = str(args.mode or args.lock_mode or saver.get("lock_mode", "visual-only")).lower()
        if mode not in ("visual-only", "immediate", "after"):
            raise ConfigError("saver.lock_mode must be visual-only, immediate, or after")
        settings["saver"] = {**saver, "lock_mode": mode}

        if settings.get("respect_idle_inhibitors", True) and not args.ignore_idle_inhibitors:
            print(
                "matrix-saver: idle-inhibitor query is not exposed reliably; "
                "no application-name heuristic will be used",
                file=sys.stderr,
            )
        if not saver.get("enabled", True) and not args.once and not args.dry_run:
            print("matrix-saver: disabled by configuration", file=sys.stderr)
            return 0
        if not battery_ok(settings):
            print("matrix-saver: battery policy is suppressing activation", file=sys.stderr)
            return 0

        # Dry-run and --once are intentionally before automatic monitor selection.
        if args.dry_run:
            print(json.dumps(run_once(settings, mode, dry_run=True, preset=args.preset), sort_keys=True))
            return 0

        controller_lock = acquire_controller_lock()
        try:
            if args.once:
                result = run_once(settings, mode, preset=args.preset)
                return 0 if result.get("success", result.get("activated")) else 1
            monitor = select_idle_monitor()
            if monitor is None:
                print(
                    "matrix-saver: automatic activation unavailable; "
                    "systemd-logind IdleHint/IdleSinceHintMonotonic is not exposed",
                    file=sys.stderr,
                )
                return 1
            run_automatic(settings, monitor)
        finally:
            controller_lock.close()
            remove_controller_lock()
            remove_state()
            remove_runtime_dir_if_empty()
    except BrokenPipeError:
        # Expected when an invoking pipe closes during normal cancellation.
        try:
            sys.stdout = open(os.devnull, "w", encoding="utf-8")
        except OSError:
            pass
        return 0
    except (ConfigError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"matrix-saver: {exc}", file=sys.stderr)
        return 1
    finally:
        remove_state()
        remove_runtime_dir_if_empty()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
