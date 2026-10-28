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
            "matrix-saver", "matrix-settings", "matrix-preset", "matrix-lock",
            "matrix-doctor", "matrix-guide", "matrix-help",
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

    def test_resource_guard_engages_and_releases_via_pause_bookkeeping(self):
        r = renderer()
        held_flag = {"value": True}
        guard = Mock()
        guard.poll = lambda: held_flag["value"]
        guard.held = True
        r.RESOURCE_GUARD = guard
        r.args.paused = False
        r.args.auto_held = False
        status = Mock()
        r.poll_resource_guard(status, None)
        self.assertTrue(r.args.auto_held)
        self.assertTrue(r.args.paused)        # engaged through pause bookkeeping
        held_flag["value"] = False
        r.poll_resource_guard(status, None)
        self.assertFalse(r.args.auto_held)
        self.assertFalse(r.args.paused)       # released automatically

    def test_resource_guard_never_overrides_manual_pause(self):
        r = renderer()
        guard = Mock()
        held = {"value": True}
        guard.poll = lambda: held["value"]
        r.RESOURCE_GUARD = guard
        r.args.paused = True                  # user paused first
        r.args.auto_held = False
        r.args.pause_started = 1.0
        status = Mock()
        r.poll_resource_guard(status, None)   # overload while user paused
        self.assertFalse(r.args.auto_held)
        held["value"] = False
        r.poll_resource_guard(status, None)   # recovery
        self.assertTrue(r.args.paused)        # user pause preserved

    def test_session_undo_redo_and_invalidation(self):
        r = renderer()
        r.args.paused = False
        r.UNDO_STACK.clear(); r.REDO_STACK.clear()
        with patch.object(r, "record_effective_settings"):
            r.handle_key(Keys(ord("2")), Mock(), [], None)   # color -> red
            self.assertEqual(r.args.color, "red")
            self.assertEqual(len(r.UNDO_STACK), 1)
            r.handle_key(Keys(ord("D")), Mock(), [], None)   # density +5
            density = r.args.density
            self.assertEqual(len(r.UNDO_STACK), 2)
            r.handle_key(Keys(ord("u")), Mock(), [], None)   # undo density
            self.assertEqual(r.args.density, density - 5)
            r.handle_key(Keys(ord("u")), Mock(), [], None)   # undo color
            self.assertEqual(r.args.color, "green")
            self.assertEqual(len(r.REDO_STACK), 2)
            r.handle_key(Keys(ord("U")), Mock(), [], None)   # redo color
            self.assertEqual(r.args.color, "red")
            # A new edit clears the remaining redo branch.
            r.handle_key(Keys(ord("3")), Mock(), [], None)
            self.assertEqual(r.REDO_STACK, [])
            # Pause is not an edit: no undo entry.
            depth = len(r.UNDO_STACK)
            r.handle_key(Keys(ord("p")), Mock(), [], None)
            self.assertEqual(len(r.UNDO_STACK), depth)
            r.handle_key(Keys(ord("p")), Mock(), [], None)

    def test_exclusion_marking_clear_and_undo(self):
        r = renderer()
        r.args.paused = False
        r.UNDO_STACK.clear(); r.REDO_STACK.clear()
        r.args.cycle_exclusions = []
        with patch.object(r, "record_effective_settings"):
            status = Mock()
            # Marking needs cycling on.
            r.args.color_cycle = False
            r.handle_key(Keys(ord("x")), status, [], None)
            self.assertEqual(r.args.cycle_exclusions, [])
            # Hold the hue to make the marked phases deterministic.
            r.args.color_cycle = True
            r.args.hue_hold = True
            r.args.hue_hold_phase = 0.20
            r.handle_key(Keys(ord("x")), status, [], None)   # mark start
            self.assertEqual(r.args.exclusion_mark, 0.20)
            self.assertEqual(len(r.UNDO_STACK), 0)           # mark alone: no edit
            r.args.hue_hold_phase = 0.45
            r.handle_key(Keys(ord("x")), status, [], None)   # mark end
            self.assertEqual(len(r.args.cycle_exclusions), 1)
            self.assertAlmostEqual(r.args.cycle_exclusions[0]["start"], 0.20)
            self.assertAlmostEqual(r.args.cycle_exclusions[0]["end"], 0.45)
            self.assertEqual(len(r.UNDO_STACK), 1)
            r.handle_key(Keys(ord("X")), status, [], None)   # clear all
            self.assertEqual(r.args.cycle_exclusions, [])
            r.handle_key(Keys(ord("u")), status, [], None)   # undo clear
            self.assertEqual(len(r.args.cycle_exclusions), 1)
            r.handle_key(Keys(ord("u")), status, [], None)   # undo creation
            self.assertEqual(r.args.cycle_exclusions, [])

    def test_reverse_cycling_swaps_marked_interval(self):
        r = renderer()
        r.args.paused = False
        r.args.cycle_exclusions = []
        r.args.color_cycle = True
        r.args.hue_hold = True
        r.args.cycle_direction = "reverse"
        with patch.object(r, "record_effective_settings"):
            r.args.hue_hold_phase = 0.45
            r.handle_key(Keys(ord("x")), Mock(), [], None)
            r.args.hue_hold_phase = 0.20
            r.handle_key(Keys(ord("x")), Mock(), [], None)
        # Traveling backwards from 0.45 to 0.20 excludes the forward arc 0.20->0.45.
        self.assertAlmostEqual(r.args.cycle_exclusions[0]["start"], 0.20)
        self.assertAlmostEqual(r.args.cycle_exclusions[0]["end"], 0.45)
        r.args.cycle_direction = "forward"

    def test_session_reset_is_undoable(self):
        r = renderer()
        r.args.paused = False
        r.UNDO_STACK.clear(); r.REDO_STACK.clear()
        with patch.object(r, "record_effective_settings"):
            r.handle_key(Keys(ord("2")), Mock(), [], None)
            r.handle_key(Keys(ord("r")), Mock(), [], None)   # session reset
            self.assertEqual(r.args.color, r.STARTUP_SETTINGS["color"])
            r.handle_key(Keys(ord("u")), Mock(), [], None)   # undo the reset
            self.assertEqual(r.args.color, "red")

    def test_manual_resume_during_hold_snoozes_guard(self):
        r = renderer()
        guard = Mock()
        guard.held = True
        r.RESOURCE_GUARD = guard
        r.args.auto_held = True
        r.args.paused = True
        r.args.pause_started = 1.0
        r.handle_key(Keys(ord("p")), Mock(), [], None)
        self.assertFalse(r.args.paused)       # user resumed
        self.assertFalse(r.args.auto_held)
        guard.snooze.assert_called_once()     # guard stands down until calm


if __name__ == "__main__":
    unittest.main()
