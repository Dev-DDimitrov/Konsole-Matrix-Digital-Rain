#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
"""Deterministic checks for settings, hue state, presets, guard, and safe cursor wiring."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

SOURCE_ROOT = Path(__file__).resolve().parents[1]
BIN = Path(os.environ.get("MATRIX_TEST_BIN", SOURCE_ROOT / "bin"))
sys.path.insert(0, str(BIN))
import matrix_config as config  # noqa: E402
import matrix_cursor  # noqa: E402
import matrix_guide_data  # noqa: E402


def renderer():
    old = sys.argv
    sys.argv = [str(BIN / "matrix_renderer.py")]
    try:
        with patch.object(config, "CONFIG_PATH", SOURCE_ROOT / "config/config.toml.example"):
            spec = importlib.util.spec_from_file_location("matrix_renderer_ux", BIN / "matrix_renderer.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    finally:
        sys.argv = old


class Screen:
    def __init__(self, key): self.key = key
    def getch(self): return self.key


def guide_output(*arguments):
    with tempfile.TemporaryDirectory(prefix="matrix-test-config-") as config_home:
        env = {**os.environ, "XDG_CONFIG_HOME": config_home}
        return subprocess.check_output(
            [str(BIN / "matrix-guide"), *arguments], env=env, text=True
        )


class UXConfigurationTests(unittest.TestCase):
    def test_public_guard_defaults_and_binding(self):
        self.assertFalse(config.EXIT_GUARD_DEFAULTS["enabled"])
        self.assertEqual(config.EXIT_GUARD_DEFAULTS["binding"], "Ctrl+Y")
        self.assertEqual(config.normalize_binding("ctrl+y"), "Ctrl+Y")
        self.assertEqual(config.normalize_binding("SHIFT+y"), "Shift+Y")
        for bad in ("Space", "Ctrl+C", "../../bad", "Ctrl+1"):
            with self.assertRaises(config.ConfigError): config.normalize_binding(bad)

    def test_user_default_precedence_and_atomic_update(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.toml"
            path.write_text("# retained comment\n[rain]\nspeed = 95\n")
            config._update_toml_key(path, "rain", "speed", 97)
            self.assertIn("# retained comment", path.read_text())
            self.assertIn("speed = 97", path.read_text())
        values = {"speed": 97, "exit_guard": dict(config.EXIT_GUARD_DEFAULTS), "matrix_all": dict(config.MATRIX_ALL_DEFAULTS)}
        with patch.object(config, "load_config", return_value=(values, None)), patch.object(config, "load_user_presets", return_value={}):
            self.assertEqual(config.resolve(SimpleNamespace(preset=None))["speed"], 97)
            self.assertEqual(config.resolve(SimpleNamespace(preset=["ambient"]))["speed"], 62)
            self.assertEqual(config.resolve(SimpleNamespace(preset=None, speed=84))["speed"], 84)

    def test_preset_normalization_and_safe_user_storage(self):
        for name in ("Night Blue", "Night_Blue", "Night-Blue", "night blue", "night_blue", "night-blue"):
            self.assertEqual(config.normalize_preset_name(name), "night_blue")
        with tempfile.TemporaryDirectory() as temp, patch.object(config, "PRESET_DIR", Path(temp)):
            config.save_user_preset("Night Blue", {"speed": 77, "hue_hold": True})
            self.assertEqual(config.load_user_presets()["night_blue"]["speed"], 77)
            with self.assertRaises(config.ConfigError): config.save_user_preset("night_blue", {"speed": 1})
            with self.assertRaises(config.ConfigError): config.user_preset_path("../escape")
            with self.assertRaises(config.ConfigError): config.save_user_preset("ambient", {"speed": 1})

    def test_reverse_and_hold_preserve_exact_phase(self):
        r = renderer()
        r.args.color_cycle = True; r.args.cycle_direction = "forward"; r.args.cycle_period = 72.0
        r.args.cycle_phase = 0.0; r.args.cycle_epoch = 100.0; r.args.hue_hold = False; r.args.paused = False; r.args.cycle_paused_elapsed = 0.0
        with patch.object(r.time, "monotonic", return_value=146.8):
            before = r.current_phase(); r.reverse_cycle_direction(); after = r.current_phase()
            self.assertAlmostEqual(before, after)
            self.assertEqual(r.args.cycle_direction, "reverse")
            status = Mock(); r.toggle_hue_hold(status, None); held = r.current_phase()
        with patch.object(r.time, "monotonic", return_value=99999.0):
            self.assertAlmostEqual(r.current_phase(), held)
            r.reverse_cycle_direction(); self.assertAlmostEqual(r.current_phase(), held)
            r.toggle_hue_hold(Mock(), None); self.assertAlmostEqual(r.current_phase(), held)

    def test_green_reset_preserves_non_hue_settings_and_hold(self):
        r = renderer()
        r.args.color_cycle = True; r.args.hue_hold = True; r.args.hue_hold_phase = .42
        r.args.cycle_phase = .42; r.args.cycle_direction = "reverse"; r.args.cycle_period = 36.0; r.args.speed = 97
        r.args.paused = False; r.args.cycle_paused_elapsed = 0.0
        with patch.object(r.time, "monotonic", return_value=100): r.reset_cycle_green()
        self.assertEqual(r.current_phase(), 0.0); self.assertTrue(r.args.hue_hold)
        self.assertEqual(r.args.cycle_direction, "reverse"); self.assertEqual(r.args.cycle_period, 36.0); self.assertEqual(r.args.speed, 97)

    def test_h_upper_lower_and_white_heads_remap(self):
        r = renderer(); r.args.color_cycle = True; r.args.hue_hold = False; r.args.paused = False; r.args.cycle_epoch = 0; r.args.cycle_phase = 0; r.args.cycle_paused_elapsed = 0
        with patch.object(r.time, "monotonic", return_value=10):
            r.handle_key(Screen(ord("h")), Mock(), [], None); self.assertTrue(r.args.hue_hold)
            r.handle_key(Screen(ord("H")), Mock(), [], None); self.assertFalse(r.args.hue_hold)
        heads = r.args.white_head_rate
        r.handle_key(Screen(ord("w")), Mock(), [], None); self.assertNotEqual(r.args.white_head_rate, heads)

    def test_guard_blocks_normal_exit_and_ctrl_y_exits(self):
        r = renderer(); r.args.exit_guard = {"enabled": True, "binding": "Ctrl+Y"}; r.args.paused = False
        for key in (ord("q"), 27, ord(" ")):
            self.assertFalse(r.handle_key(Screen(key), Mock(), [], None))
        self.assertTrue(r.handle_key(Screen(25), Mock(), [], None))
        r.args.exit_guard = {"enabled": True, "binding": "Shift+Y"}
        self.assertTrue(r.handle_key(Screen(ord("Y")), Mock(), [], None))

    def test_guarded_sigint_does_not_stop_but_sigterm_does(self):
        r = renderer(); r.args.exit_guard = {"enabled": True, "binding": "Ctrl+Y"}
        r.STOP_REQUESTED = False; r.GUARD_INTERRUPT = False
        r._request_stop(r.signal.SIGINT, None)
        self.assertTrue(r.GUARD_INTERRUPT); self.assertFalse(r.STOP_REQUESTED)
        r._request_stop(r.signal.SIGTERM, None)
        self.assertTrue(r.STOP_REQUESTED)

    def test_sync_payload_carries_held_phase_and_direction(self):
        r = renderer()
        with tempfile.TemporaryDirectory() as temp, patch.dict(r.os.environ, {"XDG_RUNTIME_DIR": temp}):
            Path(temp).chmod(0o700)
            state = Path(temp) / "state.json"
            r.args.cycle_phase = .42; r.args.hue_hold = True; r.args.hue_hold_phase = .42
            r.args.cycle_direction = "reverse"; r.args.paused = False; r.args.cycle_epoch = 100.0
            sync = r.SyncState(state); sync.publish(True, message="Hue held")
            payload = json.loads(state.read_text())
            self.assertTrue(payload["hue_hold"]); self.assertEqual(payload["hue_hold_phase"], .42)
            self.assertEqual(payload["cycle_phase"], .42); self.assertEqual(payload["settings"]["cycle_direction"], "reverse")

    def test_cursor_uses_stock_kde_only_and_has_stale_marker(self):
        source = (BIN / "matrix_cursor.py").read_text()
        self.assertIn("hidecursor", source)
        self.assertNotIn("xdotool", source); self.assertNotIn("unclutter", source); self.assertNotIn("X11", source)
        self.assertIn("restore_stale", source)

    def test_cursor_marker_restores_prior_state(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(matrix_cursor, "MARKER", Path(temp) / "cursor.json"), \
             patch.object(matrix_cursor, "available", return_value=True), \
             patch.object(matrix_cursor, "_setting", return_value="false"), \
             patch.object(matrix_cursor, "_effect_loaded", return_value=False), \
             patch.object(matrix_cursor, "_set_setting") as set_setting, \
             patch.object(matrix_cursor, "_run"):
            self.assertTrue(matrix_cursor.activate())
            self.assertTrue(matrix_cursor.status()["stale_override"])
            self.assertTrue(matrix_cursor.restore())
            set_setting.assert_any_call("false")
            self.assertFalse(matrix_cursor.status()["stale_override"])

    def test_saver_shortcuts_and_guide(self):
        for mode in ("visual-only", "immediate", "after"):
            with tempfile.TemporaryDirectory(prefix="matrix-test-config-") as config_home:
                env = {**os.environ, "XDG_CONFIG_HOME": config_home}
                output = subprocess.check_output(
                    [str(BIN / "matrix-saver"), mode, "--dry-run"], env=env, text=True
                )
            self.assertIn(f'"mode": "{mode}"', output)
        control_names = {key for key, _ in matrix_guide_data.CONTROLS}
        self.assertTrue({"0", "h / H", "w", "S", "p / P"}.issubset(control_names))
        guide = guide_output("--settings")
        self.assertIn("exit_guard", guide); self.assertIn("Ctrl+Y", guide)

if __name__ == "__main__":
    unittest.main()
