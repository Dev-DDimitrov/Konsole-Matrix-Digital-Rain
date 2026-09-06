#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
"""Non-destructive regression tests for the saver lifecycle and pause state."""

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

import matrix_config  # noqa: E402
import matrix_guide_data  # noqa: E402
import matrix_saver  # noqa: E402


def load_renderer():
    old_argv = sys.argv
    sys.argv = [str(BIN / "matrix_renderer.py")]
    try:
        with patch.object(matrix_config, "CONFIG_PATH", SOURCE_ROOT / "config/config.toml.example"):
            spec = importlib.util.spec_from_file_location(
                "matrix_renderer_test_module", BIN / "matrix_renderer.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    finally:
        sys.argv = old_argv


def guide_output(*arguments):
    with tempfile.TemporaryDirectory(prefix="matrix-test-config-") as config_home:
        env = {**os.environ, "XDG_CONFIG_HOME": config_home}
        return subprocess.check_output(
            [str(BIN / "matrix-guide"), *arguments], env=env, text=True
        )


class FakeProc:
    def __init__(self, polls):
        self.polls = iter(polls)
        self.pid = 424242

    def poll(self):
        try:
            return next(self.polls)
        except StopIteration:
            return None


class CorrectivePassTests(unittest.TestCase):
    def test_cycle_defaults_precedence_and_blue_continuity(self):
        self.assertEqual(matrix_config.DEFAULTS["cycle_period"], 72.0)
        self.assertEqual(
            matrix_config.CYCLE_SPEEDS,
            {"very-slow": 144.0, "slow": 108.0, "normal": 72.0, "fast": 36.0},
        )
        with patch.object(matrix_config, "load_config", return_value=({}, None)):
            namespace = SimpleNamespace(
                preset=None, cycle_period=55.0, cycle_speed="fast",
                reduced_motion=False,
            )
            resolved = matrix_config.resolve(namespace)
        self.assertEqual(resolved["cycle_period"], 55.0)
        self.assertEqual(resolved["cycle_speed"], "fast")

        samples = [matrix_config.cycle_rgb(i / 20.0) for i in range(7, 14)]
        for before, after in zip(samples, samples[1:]):
            self.assertLess(sum((a - b) ** 2 for a, b in zip(before, after)), 50000)

    def test_immediate_is_lock_only_and_does_not_select_idle_monitor(self):
        with patch.object(matrix_saver, "select_idle_monitor", side_effect=AssertionError), \
             patch.object(matrix_saver, "lock_command") as lock:
            result = matrix_saver.run_once({}, "immediate")
        self.assertTrue(result["success"])
        self.assertFalse(result["activated"])
        lock.assert_called_once_with()

    def test_visual_only_never_locks_and_cleans_child(self):
        proc = FakeProc([0])
        with patch.object(matrix_saver, "activate_now", return_value=(proc, [])), \
             patch.object(matrix_saver, "deactivate") as deactivate, \
             patch.object(matrix_saver, "lock_command") as lock:
            result = matrix_saver.run_once({}, "visual-only")
        self.assertFalse(result["locked"])
        deactivate.assert_called_once_with(proc)
        lock.assert_not_called()

    def test_after_early_visual_exit_hands_off_to_lock(self):
        proc = FakeProc([0, 0])
        settings = {"saver": {"lock_delay_seconds": 30}}
        with patch.object(matrix_saver, "activate_now", return_value=(proc, [])), \
             patch.object(matrix_saver, "deactivate"), \
             patch.object(matrix_saver, "lock_command") as lock:
            result = matrix_saver.run_once(settings, "after")
        self.assertTrue(result["locked"])
        lock.assert_called_once_with()

    def test_after_interruption_hands_off_to_lock(self):
        proc = FakeProc([None, None])
        old_stop = matrix_saver.STOP
        matrix_saver.STOP = True
        try:
            with patch.object(matrix_saver, "activate_now", return_value=(proc, [])), \
                 patch.object(matrix_saver, "deactivate"), \
                 patch.object(matrix_saver, "lock_command") as lock:
                result = matrix_saver.run_once({"saver": {"lock_delay_seconds": 30}}, "after")
        finally:
            matrix_saver.STOP = old_stop
        self.assertTrue(result["locked"])
        lock.assert_called_once_with()

    def test_after_locks_after_delay_and_cleans_visual_child(self):
        proc = FakeProc([None, None, None])
        settings = {"saver": {"lock_delay_seconds": 1}}
        with patch.object(matrix_saver, "activate_now", return_value=(proc, [])), \
             patch.object(matrix_saver, "deactivate") as deactivate, \
             patch.object(matrix_saver, "lock_command") as lock, \
             patch.object(matrix_saver.time, "monotonic", side_effect=[0.0, 2.0]), \
             patch.object(matrix_saver.time, "sleep"):
            result = matrix_saver.run_once(settings, "after")
        self.assertTrue(result["locked"])
        lock.assert_called_once_with()
        deactivate.assert_called_once_with(proc)

    def test_deactivate_targets_only_owned_process_group(self):
        proc = Mock()
        proc.pid = 515151
        proc.poll.return_value = None
        proc.wait.return_value = 0
        with patch.object(matrix_saver, "renderer_process_group_is_owned", return_value=True), \
             patch.object(matrix_saver.os, "killpg") as killpg:
            matrix_saver.deactivate(proc)
        killpg.assert_called_once_with(proc.pid, matrix_saver.signal.SIGTERM)
        proc.wait.assert_called_once_with(timeout=5)

    def test_expected_broken_pipe_is_handled(self):
        source = (BIN / "matrix_saver.py").read_text(encoding="utf-8")
        self.assertIn("except BrokenPipeError", source)

    def test_pause_freezes_simulation_and_effective_cycle_time(self):
        renderer = load_renderer()
        renderer.args.paused = False
        renderer.args.pause_started = 0.0
        renderer.args.cycle_paused_elapsed = 0.0
        renderer.args.cycle_epoch = 0.0
        status = Mock()
        sync = Mock()
        column = Mock()
        with patch.object(renderer.time, "monotonic", side_effect=[100.0, 160.0, 200.0]):
            renderer.toggle_pause(status, sync)
            self.assertTrue(renderer.args.paused)
            self.assertEqual(renderer.effective_animation_time(), 100.0)
            self.assertFalse(renderer.advance_simulation([column], 1))
            column.tick.assert_not_called()
            renderer.toggle_pause(status, sync)
            self.assertFalse(renderer.args.paused)
            self.assertEqual(renderer.args.cycle_paused_elapsed, 60.0)
            self.assertEqual(renderer.effective_animation_time(), 140.0)

    def test_pause_keeps_exit_control_available(self):
        renderer = load_renderer()
        renderer.args.paused = True
        renderer.args.exit_guard = {"enabled": False, "binding": "Ctrl+Y"}
        screen = Mock()
        screen.getch.return_value = ord("q")
        self.assertTrue(renderer.handle_key(screen, Mock(), [], None))

    def test_dry_run_describes_secure_after_exit_policy(self):
        result = matrix_saver.run_once({}, "after", dry_run=True)
        self.assertEqual(result["exit_action"], "lock-on-timeout-or-exit")
        self.assertTrue(result["activation_performed"])

    def test_guide_metadata_and_output_cover_public_surface(self):
        command_names = {name for name, _ in matrix_guide_data.COMMANDS}
        self.assertEqual(
            command_names,
            {"matrix", "matrix-konsole", "matrix-full", "matrix-all",
             "matrix-preview", "matrix-saver", "matrix-settings", "matrix-preset",
             "matrix-doctor", "matrix-guide"},
        )
        control_keys = {key for key, _ in matrix_guide_data.CONTROLS}
        for key in ("0", "1", "2", "3", "4", "5", "6", "7", "c", "C", "h / H", "v", "V", "p / P", "w", "S", "q / Escape / Space / Ctrl+C"):
            self.assertIn(key, control_keys)
        self.assertEqual({name for name, _ in matrix_guide_data.SAVER_MODES}, {"visual-only", "immediate", "after"})
        output = guide_output("--full")
        for name, _ in matrix_guide_data.COMMANDS:
            self.assertIn(name, output)
        for key, _ in matrix_guide_data.CONTROLS:
            self.assertIn(key, output)
        for preset in matrix_config.PRESETS:
            self.assertIn(preset, output)
        for color in matrix_config.COLORS:
            self.assertIn(color, output)

    def test_cycle_has_rich_non_blue_regions_and_normalized_spans(self):
        self.assertEqual(matrix_config.CYCLE_FAMILY_SPANS["green-cyan"], (0.00, 0.22))
        self.assertEqual(matrix_config.CYCLE_FAMILY_SPANS["blue"], (0.22, 0.40))
        self.assertEqual(matrix_config.CYCLE_FAMILY_SPANS["purple-pink"], (0.40, 0.62))
        self.assertEqual(matrix_config.CYCLE_FAMILY_SPANS["red-orange"], (0.62, 0.80))
        self.assertEqual(matrix_config.CYCLE_FAMILY_SPANS["yellow-lime"], (0.80, 1.00))
        for start, end in matrix_config.CYCLE_FAMILY_SPANS.values():
            samples = [matrix_config.cycle_rgb(start + (end - start) * i / 8) for i in range(9)]
            self.assertGreaterEqual(len(set(samples)), 5)


if __name__ == "__main__":
    unittest.main()
