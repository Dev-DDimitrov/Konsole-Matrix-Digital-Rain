#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Konsole Matrix Digital Rain renderer.
#
# This file contains substantially modified and derived work based on
# UniMatrix: https://github.com/will8211/unimatrix
# Original upstream author: William Mannard
# Original UniMatrix source date: 2018-01-19
# UniMatrix states that it is based on CMatrix by Chris Allegretta and
# Abishek V. Ashok. The current project adds extensive local changes,
# including configurable trails, palettes, synchronization, settings, and
# KDE/Konsole integration; those additions are not authored by William Mannard.
"""Cinematic xterm-256 Matrix rain renderer, optionally synchronized."""

import argparse
import curses
import json
import os
import signal
import stat
import sys
import time
from random import choice, randint, random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from matrix_config import (  # noqa: E402
    BACKGROUND_MODES,
    COLOR_RGB,
    CYCLE_SPEEDS,
    DEFAULTS,
    ConfigError,
    add_cli_arguments,
    ramp_indices,
    resolve,
    save_last_effective,
)
from matrix_guide_data import SETTINGS_LOCK_ALLOWED_KEYS, renderer_help_text  # noqa: E402

KATAKANA = 'ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ'
DIGITS = '1234567890'
SYMBOLS = '-=*_+|:<">'
DEFAULT_CHARS = KATAKANA + (DIGITS * 2) + (SYMBOLS * 4)

parser = argparse.ArgumentParser(
    description='Matrix-style terminal rain with cinematic 256-color fading trails.',
    epilog=renderer_help_text(),
)
add_cli_arguments(parser)
parser.add_argument('--sync-state', default=None, help='private shared-state file used by matrix-all')
parser.add_argument('--window-tag', default=None, help='unique window title marker used for KWin placement')
args = parser.parse_args()

try:
    SETTINGS = resolve(args)
except ConfigError as exc:
    parser.error(str(exc))

for key, value in SETTINGS.items():
    if key not in ('saver', 'battery', 'respect_idle_inhibitors'):
        setattr(args, key, value)
args.chars = args.chars or DEFAULT_CHARS
args.spacing = max(1, args.spacing)

STARTUP_SETTINGS = {key: getattr(args, key) for key in DEFAULTS}
args.paused = False
args.pause_started = 0.0
args.cycle_paused_elapsed = 0.0
args.hue_hold = bool(getattr(args, "hue_hold", False))
args.hue_hold_phase = float(getattr(args, "cycle_phase", 0.0)) % 1.0
args.cycle_phase = float(getattr(args, "cycle_phase", 0.0)) % 1.0
args.exit_guard = SETTINGS.get("exit_guard", {"enabled": False, "binding": "Ctrl+Y"})
args.settings_lock = bool(SETTINGS.get("settings_lock", {}).get("enabled", False))
STOP_REQUESTED = False
GUARD_INTERRUPT = False


def _request_stop(signum, frame):
    global STOP_REQUESTED, GUARD_INTERRUPT
    if signum == signal.SIGINT and args.exit_guard.get("enabled", False):
        GUARD_INTERRUPT = True
    else:
        STOP_REQUESTED = True


signal.signal(signal.SIGHUP, _request_stop)
signal.signal(signal.SIGTERM, _request_stop)
signal.signal(signal.SIGINT, _request_stop)


def clamp(value, low, high):
    return max(low, min(high, value))


class SyncState:
    """Private, atomic JSON state for synchronized Matrix windows."""

    SETTINGS_KEYS = tuple(DEFAULTS)

    def __init__(self, path):
        self.path = os.path.abspath(os.path.expanduser(path))
        self.parent = os.path.dirname(self.path)
        self.pid = os.getpid()
        self.last_generation = -1
        self.last_mtime_ns = -1
        self._validate_location()

    def _validate_location(self):
        runtime = os.path.realpath(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
        parent = os.path.realpath(self.parent)
        if os.path.commonpath([runtime, parent]) != runtime:
            raise RuntimeError(f'sync-state must live inside XDG_RUNTIME_DIR ({runtime})')
        st = os.stat(parent)
        if st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) & 0o077:
            raise RuntimeError('sync-state directory must be private and user-owned')
        if os.path.islink(self.path):
            raise RuntimeError('sync-state file must not be a symlink')

    def _read(self):
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
        try:
            fd = os.open(self.path, flags)
        except FileNotFoundError:
            return None
        try:
            st = os.fstat(fd)
            if st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) & 0o077:
                raise RuntimeError('sync-state file must be private and user-owned')
            with os.fdopen(fd, encoding='utf-8') as handle:
                fd = None
                return json.load(handle)
        finally:
            if fd is not None:
                os.close(fd)

    def _write(self, payload):
        tmp = f'{self.path}.tmp.{self.pid}.{time.time_ns()}'
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(tmp, flags, 0o600)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                fd = None
                json.dump(payload, handle, separators=(',', ':'), sort_keys=True)
                handle.write('\n')
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
            os.chmod(self.path, 0o600)
        finally:
            if fd is not None:
                os.close(fd)
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass

    @staticmethod
    def _settings(raw):
        if not isinstance(raw, dict):
            raise RuntimeError('invalid synchronized settings')
        values = dict(STARTUP_SETTINGS)
        values.update({key: raw[key] for key in DEFAULTS if key in raw})
        values['speed'] = clamp(int(values['speed']), 1, 100)
        values['trail_min'] = max(4, int(values['trail_min']))
        values['trail_max'] = max(values['trail_min'], int(values['trail_max']))
        values['density'] = clamp(int(values['density']), 1, 100)
        values['fade_levels'] = clamp(int(values['fade_levels']), 3, 6)
        values['white_head_rate'] = clamp(int(values['white_head_rate']), 0, 100)
        values['mutation_rate'] = clamp(float(values['mutation_rate']), 0.0, 100.0)
        values['color'] = str(values['color'])
        if values['color'] not in ('green', 'red', 'blue', 'white', 'yellow', 'cyan', 'magenta'):
            raise RuntimeError('invalid synchronized color')
        values['cycle_period'] = max(2.0, float(values['cycle_period']))
        values['cycle_speed'] = str(values['cycle_speed'])
        if values['cycle_speed'] not in CYCLE_SPEEDS:
            raise RuntimeError('invalid synchronized cycle speed')
        values['cycle_direction'] = str(values['cycle_direction'])
        if values['cycle_direction'] not in ('forward', 'reverse'):
            raise RuntimeError('invalid synchronized cycle direction')
        values['background'] = str(values['background'])
        if values['background'] not in BACKGROUND_MODES:
            raise RuntimeError('invalid synchronized background')
        values['fps_cap'] = clamp(int(values['fps_cap']), 1, 240)
        return values

    def publish(self, status_enabled, message='', quit_requested=False):
        generation = time.time_ns()
        payload = {
            'generation': generation,
            'writer': self.pid,
            'quit': bool(quit_requested),
            'message': str(message)[:160],
            'status_enabled': bool(status_enabled),
            'paused': bool(getattr(args, 'paused', False)),
            'pause_started': float(getattr(args, 'pause_started', 0.0)),
            'cycle_paused_elapsed': float(getattr(args, 'cycle_paused_elapsed', 0.0)),
            'cycle_epoch': getattr(args, 'cycle_epoch', time.monotonic()),
            'cycle_phase': float(getattr(args, 'cycle_phase', 0.0)),
            'hue_hold': bool(getattr(args, 'hue_hold', False)),
            'hue_hold_phase': float(getattr(args, 'hue_hold_phase', 0.0)),
            'settings_lock': bool(getattr(args, 'settings_lock', False)),
            'settings': {key: getattr(args, key) for key in self.SETTINGS_KEYS},
        }
        self._write(payload)
        self.last_generation = generation
        try:
            self.last_mtime_ns = os.stat(self.path).st_mtime_ns
        except OSError:
            pass

    def poll(self, status, columns, force=False):
        try:
            mtime_ns = os.stat(self.path).st_mtime_ns
        except FileNotFoundError:
            return False
        if not force and mtime_ns == self.last_mtime_ns:
            return False
        payload = self._read()
        if not isinstance(payload, dict):
            return False
        generation = int(payload.get('generation', -1))
        if not force and generation <= self.last_generation:
            return bool(payload.get('quit', False))
        old_async = args.asynchronous
        values = self._settings(payload.get('settings', {}))
        for key, value in values.items():
            setattr(args, key, value)
        args.paused = bool(payload.get('paused', False))
        args.pause_started = float(payload.get('pause_started', 0.0))
        args.cycle_paused_elapsed = max(
            0.0, float(payload.get('cycle_paused_elapsed', 0.0))
        )
        args.cycle_epoch = float(payload.get('cycle_epoch', time.monotonic()))
        args.cycle_phase = float(payload.get('cycle_phase', 0.0)) % 1.0
        args.hue_hold = bool(payload.get('hue_hold', False))
        args.hue_hold_phase = float(payload.get('hue_hold_phase', args.cycle_phase)) % 1.0
        args.settings_lock = bool(payload.get('settings_lock', False))
        if old_async != args.asynchronous:
            for col in columns:
                if col.stream:
                    col.stream.resync()
        if isinstance(payload.get('status_enabled'), bool):
            status.enabled = payload['status_enabled']
        message = payload.get('message', '')
        if message and status.enabled:
            status.show(str(message))
        self.last_generation = generation
        self.last_mtime_ns = mtime_ns
        return bool(payload.get('quit', False))


class Stream:
    def __init__(self, rows):
        self.length = randint(args.trail_min, args.trail_max)
        self.head = -randint(0, max(1, self.length // 2))
        self.step_every = randint(1, 3) if args.asynchronous else 1
        self.white_head = randint(1, 100) <= args.white_head_rate
        self.cells = {}
        self.done = False
        self.rows = rows

    def resync(self):
        self.step_every = randint(1, 3) if args.asynchronous else 1

    def advance(self):
        self.head += 1
        if 0 <= self.head < self.rows:
            self.cells[self.head] = choice(args.chars)
        oldest = self.head - self.length
        for y in tuple(self.cells):
            if y < oldest:
                del self.cells[y]
        if self.head - self.length >= self.rows:
            self.done = True

    def maybe_mutate(self):
        if not args.flashers or args.mutation_rate <= 0:
            return
        for y in tuple(self.cells):
            if random() < args.mutation_rate / 100.0:
                self.cells[y] = choice(args.chars)


class Column:
    def __init__(self, x, rows, initial=True):
        self.x = x
        self.rows = rows
        self.stream = None
        self.cooldown = self.new_cooldown(initial)

    def new_cooldown(self, initial=False):
        max_gap = max(2, int(self.rows * (110 - args.density) / 100))
        return randint(0, max_gap) if initial else randint(max(1, max_gap // 5), max_gap)

    def tick(self, frame):
        if self.stream is None:
            if self.cooldown <= 0:
                self.stream = Stream(self.rows)
            else:
                self.cooldown -= 1
            return
        if frame % self.stream.step_every == 0:
            self.stream.advance()
        self.stream.maybe_mutate()
        if self.stream.done:
            self.stream = None
            self.cooldown = self.new_cooldown()


class Palette:
    def __init__(self):
        self.bg = -1
        self.background_mode = None
        self.pairs = []
        self.white = 0
        self.status = 0
        self.background_attr = 0
        self.indices = None
        self.update(force=True)

    def update(self, force=False):
        if args.color_cycle:
            phase = current_phase()
            indices = ramp_indices('cycle', phase)
        else:
            indices = ramp_indices(args.color)
        background_mode = args.background
        if not force and indices == self.indices and background_mode == self.background_mode:
            return
        self.background_mode = background_mode
        self.bg = {
            'profile': -1,
            'black': curses.COLOR_BLACK,
            'charcoal': 236,
            'white': 255,
            'translucent': -1,
        }[background_mode]
        self.indices = indices
        self.pairs = []
        for pair_id, color in enumerate(indices, start=1):
            curses.init_pair(pair_id, color, self.bg)
            attr = curses.color_pair(pair_id)
            if pair_id == 1:
                attr |= curses.A_BOLD
            if pair_id == len(indices):
                attr |= curses.A_DIM
            self.pairs.append(attr)
        head_color = 16 if background_mode == 'white' else 231
        status_color = 16 if background_mode == 'white' else 255
        curses.init_pair(10, head_color, self.bg)
        self.white = curses.color_pair(10) | curses.A_BOLD
        curses.init_pair(11, status_color, self.bg)
        self.status = curses.color_pair(11) | curses.A_REVERSE
        curses.init_pair(12, 0, self.bg)
        self.background_attr = curses.color_pair(12)

    def active_trail(self):
        if args.fade_levels == len(self.pairs):
            return self.pairs
        last = len(self.pairs) - 1
        indexes = [round(i * last / (args.fade_levels - 1)) for i in range(args.fade_levels)]
        return [self.pairs[i] for i in indexes]


class Status:
    def __init__(self):
        self.text = ''
        self.until = 0.0
        self.enabled = not args.status_off

    def show(self, text):
        if self.enabled:
            self.text = text
            self.until = time.monotonic() + 1.15

    def draw(self, screen, palette):
        if self.enabled and self.text and time.monotonic() < self.until:
            _, cols = screen.getmaxyx()
            try:
                screen.addstr(0, 0, (' ' + self.text + ' ')[:max(0, cols - 1)], palette.status)
            except curses.error:
                pass


def trail_attr(stream, y, palette):
    distance = max(0, stream.head - y)
    if distance == 0 and stream.white_head:
        return palette.white
    colors = palette.active_trail()
    ratio = min(1.0, distance / max(1, stream.length - 1))
    return colors[min(len(colors) - 1, int(ratio * len(colors)))]


def _cycle_time():
    return effective_animation_time()


def current_phase():
    """Current spectrum position. Direction affects only the derivative.

    `cycle_phase` is an anchored, displayed spectrum position. Reversing sets
    that anchor to the current position before changing sign, so the rendered
    color cannot jump to another anchor or family.
    """
    if args.hue_hold:
        return args.hue_hold_phase
    sign = -1.0 if args.cycle_direction == 'reverse' else 1.0
    return (args.cycle_phase + sign * ((_cycle_time() - args.cycle_epoch) / args.cycle_period)) % 1.0


def anchor_cycle_phase(phase):
    args.cycle_phase = float(phase) % 1.0
    args.cycle_epoch = _cycle_time()
    if args.hue_hold:
        args.hue_hold_phase = args.cycle_phase


def reverse_cycle_direction():
    phase = current_phase()
    args.cycle_direction = 'reverse' if args.cycle_direction == 'forward' else 'forward'
    anchor_cycle_phase(phase)


def nearest_cycle_phase(rgb):
    """Map a static direct palette color onto the nearest spectrum sample."""
    best = 0.0
    best_distance = float('inf')
    for step in range(720):
        phase = step / 720.0
        from matrix_config import cycle_rgb
        distance = sum((left - right) ** 2 for left, right in zip(cycle_rgb(phase), rgb))
        if distance < best_distance:
            best, best_distance = phase, distance
    return best


def effective_animation_time():
    """Monotonic animation time with paused wall-clock intervals removed."""
    now = args.pause_started if args.paused else time.monotonic()
    return now - args.cycle_paused_elapsed


def change_cycle_speed(delta):
    phase = current_phase()
    names = tuple(CYCLE_SPEEDS)
    current = args.cycle_speed if args.cycle_speed in names else 'normal'
    index = max(0, min(len(names) - 1, names.index(current) + delta))
    args.cycle_speed = names[index]
    args.cycle_period = CYCLE_SPEEDS[args.cycle_speed]
    anchor_cycle_phase(phase)
    return f'Color cycle: {args.cycle_speed} ({int(args.cycle_period)}s)'


def reset_startup(columns):
    for key, value in STARTUP_SETTINGS.items():
        setattr(args, key, value)
    args.cycle_epoch = time.monotonic()
    args.paused = False
    args.pause_started = 0.0
    args.cycle_paused_elapsed = 0.0
    args.hue_hold = bool(STARTUP_SETTINGS['hue_hold'])
    args.hue_hold_phase = float(STARTUP_SETTINGS['cycle_phase'])
    args.cycle_phase = float(STARTUP_SETTINGS['cycle_phase'])
    for col in columns:
        if col.stream:
            col.stream.resync()


def changed_color(key, status, columns, sync):
    names = ('green', 'red', 'blue', 'white', 'yellow', 'cyan', 'magenta')
    if key < ord('1') or key > ord('7'):
        return False
    args.color = names[key - ord('1')]
    args.color_cycle = False
    args.hue_hold = False
    args.cycle_phase = nearest_cycle_phase(COLOR_RGB[args.color])
    status.show(f'Color: {args.color}')
    if sync:
        sync.publish(status.enabled, message=f'Color: {args.color}')
    return True


def toggle_pause(status, sync):
    if args.paused:
        args.cycle_paused_elapsed += max(
            0.0, time.monotonic() - args.pause_started
        )
        args.paused = False
        args.pause_started = 0.0
        message = 'Resumed'
    else:
        args.paused = True
        args.pause_started = time.monotonic()
        message = 'Paused'
    status.show(message)
    if sync:
        sync.publish(status.enabled, message=message)


def advance_simulation(columns, frame):
    """Advance rainfall exactly once unless the complete frame is paused."""
    if args.paused:
        return False
    for col in columns:
        col.tick(frame)
    return True


def toggle_hue_hold(status, sync):
    if not args.color_cycle:
        status.show('Hue hold is available while color cycling')
        return
    if args.hue_hold:
        anchor_cycle_phase(args.hue_hold_phase)
        args.hue_hold = False
        message = 'Hue cycling resumed'
    else:
        args.hue_hold_phase = current_phase()
        args.hue_hold = True
        message = 'Hue held'
    status.show(message)
    if sync:
        sync.publish(status.enabled, message=message)


def reset_cycle_green():
    if args.color_cycle:
        anchor_cycle_phase(0.0)
        if args.hue_hold:
            args.hue_hold_phase = 0.0
    else:
        args.color = 'green'
        args.hue_hold = False
        args.cycle_phase = 0.0


def cycle_white_heads(status, sync):
    standard = (75, 50, 25, 0)
    current = min(standard, key=lambda value: abs(value - args.white_head_rate))
    args.white_head_rate = standard[(standard.index(current) + 1) % len(standard)]
    message = f'White heads: {args.white_head_rate}%'
    record_effective_settings()
    status.show(message)
    if sync:
        sync.publish(status.enabled, message=message)


def cycle_background(status, sync):
    try:
        index = BACKGROUND_MODES.index(args.background)
    except ValueError:
        index = 0
    args.background = BACKGROUND_MODES[(index + 1) % len(BACKGROUND_MODES)]
    args.black_background = args.background == 'black'
    message = f'Background: {args.background}'
    if args.background == 'translucent':
        message += ' (dedicated windows require the Matrix translucent profile)'
    record_effective_settings()
    status.show(message)
    if sync:
        sync.publish(status.enabled, message=message)


def manual_hue_nudge(delta, status, sync):
    phase = (current_phase() + delta) % 1.0
    args.color_cycle = True
    args.hue_hold = True
    anchor_cycle_phase(phase)
    args.hue_hold_phase = phase
    message = f'Hue: {phase:.3f} (held)'
    record_effective_settings()
    status.show(message)
    if sync:
        sync.publish(status.enabled, message=message)


def toggle_settings_lock(status, sync):
    args.settings_lock = not args.settings_lock
    message = 'Settings locked' if args.settings_lock else 'Settings unlocked'
    status.show(message)
    if sync:
        sync.publish(status.enabled, message=message)


def alt_arrow(screen, key):
    """Decode common ESC+arrow forms without remapping Shift+arrow."""
    if key != 27:
        return None
    suffix = []
    for _ in range(3):
        part = screen.getch()
        if part == -1:
            break
        suffix.append(part)
        if part in (curses.KEY_LEFT, curses.KEY_RIGHT):
            break
    if curses.KEY_LEFT in suffix or suffix[-2:] == [91, 68]:
        return -1
    if curses.KEY_RIGHT in suffix or suffix[-2:] == [91, 67]:
        return 1
    return None


def guard_binding_matches(key):
    binding = str(args.exit_guard.get('binding', 'Ctrl+Y'))
    if binding == 'Ctrl+Y':
        return key == 25
    if binding == 'Shift+Y':
        return key == ord('Y')
    if binding.startswith('Ctrl+'):
        return key == ord(binding[-1].lower()) - ord('a') + 1
    if binding.startswith('Shift+'):
        return key == ord(binding[-1].upper())
    return False


def record_effective_settings():
    """Best-effort convenience state must never interrupt an active visual."""
    try:
        save_last_effective({key: getattr(args, key) for key in DEFAULTS})
    except OSError:
        pass


def handle_key(screen, status, columns, sync):
    key = screen.getch()
    if key == -1:
        return False
    guarded = bool(args.exit_guard.get('enabled', False))
    if guarded and guard_binding_matches(key):
        if sync:
            sync.publish(status.enabled, message='Matrix all: closing', quit_requested=True)
        return True
    if key == 12:  # Ctrl+L is owned only while Matrix curses is active.
        toggle_settings_lock(status, sync)
        return False
    # Alt+Arrow is delivered by Konsole as an ESC-prefixed sequence. Decode it
    # before treating a bare ESC as Matrix exit; Shift+Arrow is intentionally
    # never remapped because Konsole owns those tab-navigation shortcuts.
    alt_direction = alt_arrow(screen, key)
    if alt_direction is not None:
        if not args.settings_lock and not args.reduced_motion:
            manual_hue_nudge(alt_direction * args.manual_hue_step, status, sync)
        return False
    if key in (ord('q'), ord(' '), 27):
        if guarded:
            status.show(f'Exit guard enabled — use {args.exit_guard["binding"]} to exit')
            return False
        if sync:
            sync.publish(status.enabled, message='Matrix all: closing', quit_requested=True)
        return True
    if key in (ord('p'), ord('P')):
        toggle_pause(status, sync)
        return False
    if args.settings_lock:
        if chr(key) == '?':
            status.show('Settings locked | Ctrl+L unlocks')
        elif chr(key) == 'o' and 'o' in SETTINGS_LOCK_ALLOWED_KEYS:
            status.enabled = not status.enabled
        elif chr(key) not in SETTINGS_LOCK_ALLOWED_KEYS:
            return False
    if args.paused:
        return False
    if changed_color(key, status, columns, sync):
        return False
    changed = False
    message = ''
    if key in (ord('+'), ord('='), curses.KEY_RIGHT):
        args.speed = clamp(args.speed + 1, 1, 100); message = f'Speed: {args.speed}'; changed = True
    elif key in (ord('-'), ord('_'), curses.KEY_LEFT):
        args.speed = clamp(args.speed - 1, 1, 100); message = f'Speed: {args.speed}'; changed = True
    elif key in (ord(']'), curses.KEY_UP):
        args.speed = clamp(args.speed + 10, 1, 100); message = f'Speed: {args.speed}'; changed = True
    elif key in (ord('['), curses.KEY_DOWN):
        args.speed = clamp(args.speed - 10, 1, 100); message = f'Speed: {args.speed}'; changed = True
    elif key == ord('t'):
        args.trail_min = max(4, args.trail_min - 2); args.trail_max = max(args.trail_min, args.trail_max - 2); message = f'Trail: {args.trail_min}-{args.trail_max}'; changed = True
    elif key == ord('T'):
        args.trail_min += 2; args.trail_max += 2; message = f'Trail: {args.trail_min}-{args.trail_max}'; changed = True
    elif key == ord('d'):
        args.density = clamp(args.density - 5, 1, 100); message = f'Density: {args.density}'; changed = True
    elif key == ord('D'):
        args.density = clamp(args.density + 5, 1, 100); message = f'Density: {args.density}'; changed = True
    elif key == ord('f') and not args.reduced_motion:
        args.flashers = not args.flashers; message = f'Flash: {"on" if args.flashers else "off"}'; changed = True
    elif key == ord('a'):
        args.asynchronous = not args.asynchronous
        for col in columns:
            if col.stream: col.stream.resync()
        message = f'Async: {"on" if args.asynchronous else "off"}'; changed = True
    elif key == ord('w'):
        cycle_white_heads(status, sync); return False
    elif key == ord('b'):
        cycle_background(status, sync); return False
    elif key == ord(','):
        args.fade_levels = clamp(args.fade_levels - 1, 3, 6); message = f'Fade levels: {args.fade_levels}'; changed = True
    elif key == ord('.'):
        args.fade_levels = clamp(args.fade_levels + 1, 3, 6); message = f'Fade levels: {args.fade_levels}'; changed = True
    elif key == ord('c') and not args.reduced_motion:
        if args.color_cycle:
            args.color_cycle = False; args.hue_hold = False
        else:
            anchor_cycle_phase(nearest_cycle_phase(COLOR_RGB[args.color])); args.color_cycle = True
        message = f'Color cycle: {"on" if args.color_cycle else "off"}'; changed = True
    elif key == ord('C') and not args.reduced_motion:
        reverse_cycle_direction(); message = f'Cycle direction: {args.cycle_direction}'; changed = True
    elif key in (ord('h'), ord('H')) and not args.reduced_motion:
        toggle_hue_hold(status, sync); return False
    elif key == ord('0') and not args.reduced_motion:
        reset_cycle_green(); message = 'Hue reset to Matrix green'; changed = True
    elif key == ord('v') and not args.reduced_motion:
        message = change_cycle_speed(-1); changed = True
    elif key == ord('V') and not args.reduced_motion:
        message = change_cycle_speed(1); changed = True
    elif key == ord('o'):
        status.enabled = not status.enabled; message = f'Status: {"on" if status.enabled else "off"}'; changed = True
    elif key == ord('r'):
        reset_startup(columns); message = 'Session preset restored'; changed = True
    elif key == ord('S'):
        record_effective_settings(); message = 'Settings saved for matrix-preset save NAME --from-last'; changed = True
    elif key == ord('?'):
        status.show('p/P pause | h/H hue | Alt+arrows nudge | b background | w heads | Ctrl+L lock | q exit')
    if changed:
        record_effective_settings()
        status.show(message)
        if sync:
            sync.publish(status.enabled, message=message)
    return False


def run(screen, sync=None):
    curses.curs_set(0)
    curses.use_default_colors()
    screen.nodelay(True)
    screen.keypad(True)
    if curses.COLORS < 256:
        raise RuntimeError(f'unimatrix-fade requires 256 colors; curses reports {curses.COLORS}')
    args.cycle_epoch = getattr(args, 'cycle_epoch', time.monotonic())
    record_effective_settings()
    palette = Palette()
    status = Status()
    rows, cols = screen.getmaxyx()
    columns = [Column(x, rows) for x in range(0, max(1, cols - 1), args.spacing)]
    if sync:
        sync.poll(status, columns, force=True)
    status.show(f'{args.color} | speed {args.speed} | trail {args.trail_min}-{args.trail_max} | density {args.density} | fade {args.fade_levels}')
    frame = 0
    while True:
        global GUARD_INTERRUPT
        if GUARD_INTERRUPT:
            GUARD_INTERRUPT = False
            status.show(f'Exit guard enabled — use {args.exit_guard["binding"]} to exit')
        if STOP_REQUESTED:
            if sync:
                sync.publish(status.enabled, message='Matrix all: closing', quit_requested=True)
            return
        if sync and sync.poll(status, columns):
            return
        palette.update()
        screen.bkgd(' ', palette.background_attr)
        new_rows, new_cols = screen.getmaxyx()
        if (new_rows, new_cols) != (rows, cols):
            rows, cols = new_rows, new_cols
            columns = [Column(x, rows) for x in range(0, max(1, cols - 1), args.spacing)]
            screen.erase()
        if handle_key(screen, status, columns, sync):
            return
        advanced = advance_simulation(columns, frame)
        screen.erase()
        for col in columns:
            if col.stream is None:
                continue
            for y, char in col.stream.cells.items():
                if 0 <= y < rows and 0 <= col.x < cols - 1:
                    try:
                        screen.addstr(y, col.x, char, trail_attr(col.stream, y, palette))
                    except curses.error:
                        pass
        status.draw(screen, palette)
        screen.refresh()
        delay_ms = max(1, round(1000 / args.fps_cap))
        if args.speed < 100:
            delay_ms = max(delay_ms, (100 - args.speed) * 10)
        curses.napms(delay_ms)
        if advanced:
            frame = (frame + 1) % 600000


def main():
    sync = None
    if args.sync_state:
        sync = SyncState(args.sync_state)
        args.cycle_epoch = time.monotonic()
        args.paused = False
        args.pause_started = 0.0
        args.cycle_paused_elapsed = 0.0
        args.settings_lock = False
        sync.publish(not args.status_off)
    if args.window_tag:
        sys.stdout.write(f'\033]0;{args.window_tag}\007')
        sys.stdout.flush()
    try:
        curses.wrapper(run, sync)
    except (KeyboardInterrupt, RuntimeError) as exc:
        if isinstance(exc, RuntimeError):
            print(f'ERROR: {exc}', file=sys.stderr)
        if sync:
            try:
                sync.publish(not args.status_off, message='Matrix all: closing', quit_requested=True)
            except OSError:
                pass


if __name__ == '__main__':
    main()
