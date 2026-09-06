"""Focused, non-destructive checks for the final Matrix interaction pass."""

# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
from __future__ import annotations

import importlib.util
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
import matrix_guide_data  # noqa: E402


def renderer():
    old = sys.argv
    sys.argv = [str(BIN / "matrix_renderer.py")]
    try:
        with patch.object(config, "CONFIG_PATH", SOURCE_ROOT / "config/config.toml.example"):
            spec = importlib.util.spec_from_file_location("matrix_renderer_final_controls", BIN / "matrix_renderer.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    finally:
        sys.argv = old


class Keys:
    def __init__(self, *keys):
        self.keys = list(keys)

    def getch(self):
        return self.keys.pop(0) if self.keys else -1


def guide_output(*arguments):
    with tempfile.TemporaryDirectory(prefix="matrix-test-config-") as config_home:
        env = {**os.environ, "XDG_CONFIG_HOME": config_home}
        return subprocess.check_output(
            [str(BIN / "matrix-guide"), *arguments], env=env, text=True
        )


class FinalInteractionTests(unittest.TestCase):
    def test_speed_is_96_in_defaults_config_and_resolution(self):
        self.assertEqual(config.DEFAULTS["speed"], 96)
        example_path = SOURCE_ROOT / "config/config.toml.example"
        values, _ = config.load_config(example_path)
        with tempfile.TemporaryDirectory(prefix="matrix-test-presets-") as preset_dir:
            with patch.object(config, "load_config", return_value=(values, None)), patch.object(
                config, "PRESET_DIR", Path(preset_dir)
            ):
                self.assertEqual(values["speed"], 96)
                self.assertEqual(config.resolve(SimpleNamespace(preset=None))["speed"], 96)
                self.assertEqual(config.resolve(SimpleNamespace(preset=None, speed=84))["speed"], 84)
        self.assertNotIn(
            "speed = 97",
            (SOURCE_ROOT / "config/config.toml.example").read_text(encoding="utf-8"),
        )
        self.assertNotIn('set speed 97', (BIN / "matrix_guide.py").read_text(encoding="utf-8"))

    def test_background_cycle_is_small_and_preserves_visual_state(self):
        r = renderer()
        r.args.background = "profile"
        r.args.black_background = False
        r.args.cycle_phase = 0.37
        r.args.speed = 96
        r.args.trail_min = 16
        r.args.trail_max = 38
        r.args.density = 52
        r.args.paused = False
        with patch.object(r, "save_last_effective"), patch.object(r, "record_effective_settings"):
            seen = []
            for _ in range(5):
                r.cycle_background(Mock(), None)
                seen.append(r.args.background)
        self.assertEqual(seen, ["black", "charcoal", "white", "translucent", "profile"])
        self.assertEqual(r.args.cycle_phase, 0.37)
        self.assertEqual(r.args.speed, 96)
        self.assertEqual((r.args.trail_min, r.args.trail_max, r.args.density), (16, 38, 52))
        self.assertEqual(config.BACKGROUND_MODES, ("profile", "black", "charcoal", "white", "translucent"))
        self.assertIn("0.70", (SOURCE_ROOT / "konsole/Matrix-Translucent.colorscheme").read_text())

    def test_white_heads_cycle_is_75_50_25_0(self):
        r = renderer()
        r.args.white_head_rate = 75
        with patch.object(r, "record_effective_settings"):
            seen = []
            for _ in range(4):
                r.cycle_white_heads(Mock(), None)
                seen.append(r.args.white_head_rate)
        self.assertEqual(seen, [50, 25, 0, 75])

    def test_alt_arrows_nudge_and_hold_without_using_shift_arrow(self):
        r = renderer()
        r.args.color_cycle = True
        r.args.hue_hold = False
        r.args.cycle_phase = 0.4
        r.args.cycle_epoch = 0.0
        r.args.cycle_period = 72.0
        r.args.cycle_paused_elapsed = 0.0
        r.args.paused = False
        r.args.settings_lock = False
        with patch.object(r.time, "monotonic", return_value=0.0), patch.object(r, "save_last_effective"):
            self.assertFalse(r.handle_key(Keys(27, 91, 67), Mock(), [], None))
            self.assertTrue(r.args.hue_hold)
            phase = r.args.hue_hold_phase
            self.assertAlmostEqual(phase, 0.4 + r.args.manual_hue_step)
            self.assertFalse(r.handle_key(Keys(27, 91, 68), Mock(), [], None))
            self.assertAlmostEqual(r.args.hue_hold_phase, 0.4)
        source = (BIN / "matrix_renderer.py").read_text(encoding="utf-8")
        self.assertNotIn("Shift+Left", source)
        self.assertNotIn("Shift+Right", source)
        self.assertNotIn("Shift+Space", source)

    def test_settings_lock_blocks_preferences_but_allows_pause_and_unlock(self):
        r = renderer()
        r.args.settings_lock = False
        r.args.paused = False
        r.args.exit_guard = {"enabled": False, "binding": "Ctrl+Y"}
        r.args.color = "green"
        r.args.white_head_rate = 75
        with patch.object(r, "save_last_effective"):
            r.handle_key(Keys(12), Mock(), [], None)
            self.assertTrue(r.args.settings_lock)
            r.handle_key(Keys(ord("1")), Mock(), [], None)
            self.assertEqual(r.args.color, "green")
            r.handle_key(Keys(ord("w")), Mock(), [], None)
            self.assertEqual(r.args.white_head_rate, 75)
            r.handle_key(Keys(ord("p")), Mock(), [], None)
            self.assertTrue(r.args.paused)
            r.handle_key(Keys(ord("p")), Mock(), [], None)
            self.assertFalse(r.args.paused)
            r.handle_key(Keys(12), Mock(), [], None)
            self.assertFalse(r.args.settings_lock)

    def test_public_metadata_and_guide_cover_new_controls(self):
        controls = {key for key, _ in matrix_guide_data.CONTROLS}
        self.assertTrue({"b", "w", "Alt+Left / Alt+Right", "Ctrl+L", "p / P"}.issubset(controls))
        self.assertEqual([name for name, _ in matrix_guide_data.COMMANDS], [
            "matrix", "matrix-konsole", "matrix-full", "matrix-all", "matrix-preview",
            "matrix-saver", "matrix-settings", "matrix-preset", "matrix-doctor", "matrix-guide",
        ])
        guide = guide_output("--full")
        for text in ("background", "75% -> 50% -> 25% -> 0%", "Alt+Left / Alt+Right", "Ctrl+L", "speed 96"):
            self.assertIn(text, guide)

    def test_cursor_and_plugin_limits_are_reported_without_unsafe_hacks(self):
        cursor = (BIN / "matrix_cursor.py").read_text(encoding="utf-8")
        all_source = (BIN / "matrix-all").read_text(encoding="utf-8")
        doctor = (BIN / "matrix_doctor.py").read_text(encoding="utf-8")
        for forbidden in ("xdotool", "unclutter", "/dev/input", "XOpenDisplay"):
            self.assertNotIn(forbidden, cursor + all_source + doctor)
        self.assertIn("stock Plasma auto-hide only", doctor)
        self.assertIn('"--show-cursor"', all_source)
        self.assertIn("matrix_cursor.restore()", all_source)
        self.assertIn('BACKGROUND_MODE="$BACKGROUND_MODE"', all_source)
        self.assertIn("Plugin panel suppression", doctor)
        self.assertIn("Live translucency", doctor)
        self.assertNotIn("sshmanager", all_source.lower())
        self.assertNotIn("quick commands", all_source.lower())

    def test_profile_scope(self):
        profile = (SOURCE_ROOT / "konsole/Matrix.profile").read_text(encoding="utf-8")
        self.assertEqual(next(line for line in profile.splitlines() if line.startswith("Command=")), "Command=matrix")
        self.assertNotIn("Opacity", profile)
        translucent = (SOURCE_ROOT / "konsole/Matrix-Translucent.profile").read_text(encoding="utf-8")
        self.assertIn("Matrix-Translucent", translucent)


if __name__ == "__main__":
    unittest.main()
