#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
"""Deterministic tests for the lock-screen profile, history, and KDE export."""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE_ROOT = Path(__file__).resolve().parents[1]
BIN = Path(os.environ.get("MATRIX_TEST_BIN", SOURCE_ROOT / "bin"))
sys.path.insert(0, str(BIN))
import matrix_config as config  # noqa: E402
import matrix_lockscreen as lock  # noqa: E402

PLUGIN_ROOT = SOURCE_ROOT / "plasma/wallpapers/io.github.devddimitrov.matrixrain"


class Isolated(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="matrix-lock-test-")
        root = Path(self._tmp.name)
        self._patches = [
            patch.object(lock, "LOCK_CONFIG_PATH", root / "lockscreen.toml"),
            patch.object(lock, "HISTORY_DIR", root / "history"),
            patch.object(lock, "WALLPAPER_BACKUP_PATH", root / "backup.json"),
            patch.object(lock, "KSCREENLOCKERRC", root / "kscreenlockerrc"),
            patch.object(lock, "PLUGIN_DIR", PLUGIN_ROOT),
        ]
        for item in self._patches:
            item.start()
        self.addCleanup(self._tmp.cleanup)
        for item in self._patches:
            self.addCleanup(item.stop)
        self.root = root


class ValidationTests(Isolated):
    def test_defaults_are_valid_and_low_power(self):
        values = lock.validate({})
        self.assertEqual(values["color"], "green")
        self.assertFalse(values["color_cycle"])
        self.assertFalse(values["flashers"])
        self.assertLessEqual(values["fps_cap"], 15)
        self.assertEqual(values["white_head_rate"], 25)

    def test_unknown_keys_and_bad_values_are_rejected(self):
        with self.assertRaises(config.ConfigError):
            lock.validate({"surprise": 1})
        with self.assertRaises(config.ConfigError):
            lock.validate({"color": "chartreuse"})
        with self.assertRaises(config.ConfigError):
            lock.validate({"color": "#12345"})
        with self.assertRaises(config.ConfigError):
            lock.validate({"cycle_direction": "sideways"})
        with self.assertRaises(config.ConfigError):
            lock.validate({"speed": "fast"})

    def test_values_clamp_and_normalize(self):
        values = lock.validate({"speed": 500, "fps_cap": 500, "white_head_rate": -5,
                                "cycle_phase": 1.75, "color": "#ABCDEF"})
        self.assertEqual(values["speed"], 100)
        self.assertEqual(values["fps_cap"], 60)
        self.assertEqual(values["white_head_rate"], 0)
        self.assertAlmostEqual(values["cycle_phase"], 0.75)
        self.assertEqual(values["color"], "#abcdef")

    def test_reduced_motion_disables_motion_features(self):
        values = lock.validate({"reduced_motion": True, "color_cycle": True,
                                "flashers": True, "mutation_rate": 5.0})
        self.assertFalse(values["color_cycle"])
        self.assertFalse(values["flashers"])
        self.assertEqual(values["mutation_rate"], 0.0)

    def test_hex_parsing_and_hue_conversion(self):
        self.assertEqual(config.parse_hex_color("#00FF88"), (0, 255, 136))
        self.assertEqual(config.parse_hex_color("#0f8"), (0, 255, 136))
        with self.assertRaises(config.ConfigError):
            config.parse_hex_color("00ff88")
        with self.assertRaises(config.ConfigError):
            config.parse_hex_color("#gg0000")
        self.assertEqual(config.rgb_to_hex((0, 255, 136)), "#00ff88")
        self.assertEqual(config.hue_degrees_rgb(0), (255, 0, 0))
        self.assertEqual(config.hue_degrees_rgb(480), config.hue_degrees_rgb(120))
        self.assertEqual(config.hue_degrees_rgb(-90), config.hue_degrees_rgb(270))
        with self.assertRaises(config.ConfigError):
            config.hue_degrees_rgb("violet")

    def test_exact_hue_setters_preserve_color_and_phase(self):
        values = lock.set_hue_degrees(dict(lock.LOCK_DEFAULTS), 270)
        self.assertEqual(values["color"], config.rgb_to_hex(config.hue_degrees_rgb(270)))
        values = lock.set_color(dict(lock.LOCK_DEFAULTS), "#8B5CF6")
        self.assertEqual(values["color"], "#8b5cf6")
        phase = values["cycle_phase"]
        self.assertTrue(0.0 <= phase < 1.0)
        # The stored phase is the nearest spectrum anchor for the exact color.
        self.assertEqual(phase, config.nearest_cycle_phase((0x8b, 0x5c, 0xf6)))

    def test_shared_ramp_matches_terminal_ramp(self):
        for color in ("green", "cyan", "magenta"):
            base = config.COLOR_RGB[color]
            ramp = config.ramp_rgb(base)
            self.assertEqual(len(ramp), 6)
            indices = config.ramp_indices(color)
            self.assertEqual(indices, [config.nearest_xterm(rgb) for rgb in ramp])


class ProfilePersistenceTests(Isolated):
    def test_save_load_roundtrip_and_atomicity(self):
        values = lock.validate({"color": "#8b5cf6", "density": 44})
        saved, revision = lock.save_profile(values, note="test")
        self.assertEqual(lock.load_profile(), saved)
        self.assertTrue((self.root / "lockscreen.toml").is_file())
        stray = [p for p in self.root.iterdir() if p.name.startswith(".lockscreen")]
        self.assertEqual(stray, [], "atomic write must not leave temp files")
        self.assertTrue((self.root / "history" / f"{revision}.toml").is_file())

    def test_missing_profile_returns_defaults(self):
        self.assertEqual(lock.load_profile(), dict(lock.LOCK_DEFAULTS))

    def test_corrupt_profile_is_reported_not_crashed(self):
        (self.root / "lockscreen.toml").write_text("not = [valid", encoding="utf-8")
        with self.assertRaises(config.ConfigError):
            lock.load_profile()

    def test_history_is_bounded_and_newest_first(self):
        with patch.object(lock, "HISTORY_LIMIT", 5):
            for index in range(8):
                lock.save_profile({"speed": index + 1}, note=f"rev {index}")
            entries = lock.history_entries()
            self.assertEqual(len(entries), 5)
            speeds = [values["speed"] for _, values in entries]
            self.assertEqual(speeds, [8, 7, 6, 5, 4])

    def test_restore_and_undo_preserve_forward_history(self):
        _, first = lock.save_profile({"speed": 10}, note="first")
        lock.save_profile({"speed": 20}, note="second")
        restored = lock.load_revision(first)
        self.assertEqual(restored["speed"], 10)
        lock.save_profile(restored, note="restore")
        entries = lock.history_entries()
        speeds = [values["speed"] for _, values in entries]
        self.assertEqual(speeds[:3], [10, 20, 10])

    def test_bad_revision_ids_are_rejected(self):
        for bad in ("../../etc/passwd", "20250101-000000/../x", "evil", ""):
            with self.assertRaises(config.ConfigError):
                lock.load_revision(bad)


class TerminalInterchangeTests(Isolated):
    def test_held_hue_capture_is_exact(self):
        term = {"color_cycle": True, "hue_hold": True, "cycle_phase": 0.42}
        values = lock.from_terminal_values(term)
        self.assertEqual(values["color"], config.rgb_to_hex(config.cycle_rgb(0.42)))
        self.assertFalse(values["color_cycle"])
        self.assertAlmostEqual(values["cycle_phase"], 0.42)

    def test_cycling_capture_stays_cycling(self):
        term = {"color_cycle": True, "hue_hold": False, "cycle_phase": 0.1,
                "cycle_period": 36.0, "cycle_direction": "reverse"}
        values = lock.from_terminal_values(term)
        self.assertTrue(values["color_cycle"])
        self.assertEqual(values["cycle_period"], 36.0)
        self.assertEqual(values["cycle_direction"], "reverse")

    def test_named_color_and_background_mapping(self):
        term = {"color": "cyan", "color_cycle": False, "background": "charcoal",
                "white_head_rate": 50, "fps_cap": 240}
        values = lock.from_terminal_values(term)
        self.assertEqual(values["color"], "cyan")
        self.assertEqual(values["background"], "#303030")
        self.assertEqual(values["white_head_rate"], 50)
        self.assertEqual(values["fps_cap"], 60, "lock fps must clamp to the low-power cap")

    def test_preset_apply_only_touches_preset_keys(self):
        base = lock.validate({"glyph_size": 30, "fps_cap": 10})
        values, name = lock.apply_preset(base, "cyber")
        self.assertEqual(name, "cyber")
        self.assertEqual(values["glyph_size"], 30)
        self.assertEqual(values["fps_cap"], 10)
        self.assertTrue(values["color_cycle"])
        self.assertEqual(values["density"], 58)

    def test_preview_arguments_are_safe_and_complete(self):
        values = lock.validate({"color": "#8b5cf6"})
        arguments = lock.renderer_preview_arguments(values)
        self.assertIn("--hue-hold", arguments)
        self.assertIn("--color-cycle", arguments)
        for argument in arguments:
            self.assertTrue(re.fullmatch(r"[A-Za-z0-9#.\-]+", argument),
                            f"unsafe preview argument: {argument!r}")
        named = lock.renderer_preview_arguments(lock.validate({"color": "green"}))
        self.assertIn("--color", named)
        self.assertNotIn("--hue-hold", named)


class ExportTests(Isolated):
    def test_export_covers_every_plugin_config_entry(self):
        xml = (PLUGIN_ROOT / "contents/config/main.xml").read_text(encoding="utf-8")
        entries = set(re.findall(r'<entry name="([A-Za-z]+)"', xml))
        exported = set(lock.export_assignments(lock.validate({}), epoch=0.0))
        self.assertEqual(entries, exported)

    def test_export_writes_and_preserves_unrelated_config(self):
        rc = self.root / "kscreenlockerrc"
        rc.write_text("[Daemon]\nLockGrace=30\n\n[Greeter][Wallpaper][org.kde.image][General]\n"
                      "Image=file:///art.png\n", encoding="utf-8")
        lock.export_to_lockscreen(lock.validate({"color": "#00ff88"}), rc_path=rc, epoch=5.0)
        content = rc.read_text(encoding="utf-8")
        self.assertIn("LockGrace=30", content)
        self.assertIn("Image=file:///art.png", content)
        self.assertIn("[Greeter][Wallpaper][io.github.devddimitrov.matrixrain][General]", content)
        self.assertIn("FixedColor=#00ff88", content)
        self.assertIn("CycleEpoch=5", content)
        # A second export must update in place, not duplicate.
        lock.export_to_lockscreen(lock.validate({"color": "#ff0000"}), rc_path=rc, epoch=6.0)
        content = rc.read_text(encoding="utf-8")
        self.assertEqual(content.count("FixedColor="), 1)
        self.assertIn("FixedColor=#ff0000", content)

    def test_enable_backs_up_and_disable_restores(self):
        rc = self.root / "kscreenlockerrc"
        rc.write_text("[Greeter]\nWallpaperPlugin=org.kde.image\n", encoding="utf-8")
        previous = lock.enable(rc_path=rc)
        self.assertEqual(previous, "org.kde.image")
        self.assertEqual(lock.current_wallpaper_plugin(rc), lock.PLUGIN_ID)
        backup = json.loads((self.root / "backup.json").read_text(encoding="utf-8"))
        self.assertEqual(backup["wallpaper_plugin"], "org.kde.image")
        # Re-enabling must not overwrite the original backup.
        lock.enable(rc_path=rc)
        backup = json.loads((self.root / "backup.json").read_text(encoding="utf-8"))
        self.assertEqual(backup["wallpaper_plugin"], "org.kde.image")
        restored = lock.disable(rc_path=rc)
        self.assertEqual(restored, "org.kde.image")
        self.assertEqual(lock.current_wallpaper_plugin(rc), "org.kde.image")
        self.assertFalse((self.root / "backup.json").exists())

    def test_enable_requires_installed_plugin(self):
        with patch.object(lock, "PLUGIN_DIR", self.root / "missing"):
            with self.assertRaises(config.ConfigError):
                lock.enable(rc_path=self.root / "kscreenlockerrc")


class QmlParityTests(unittest.TestCase):
    def test_qml_waypoints_match_python_spectrum(self):
        qml = (PLUGIN_ROOT / "contents/ui/main.qml").read_text(encoding="utf-8")
        pairs = re.findall(r"\[(\d+\.\d+), (\d+)\]", qml)
        qml_waypoints = tuple((float(a), int(b)) for a, b in pairs)
        self.assertEqual(qml_waypoints, config.CYCLE_WAYPOINTS)

    def test_qml_brightness_ramp_matches_python(self):
        qml = (PLUGIN_ROOT / "contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertIn("[1.0, 0.82, 0.63, 0.46, 0.30, 0.16]", qml)
        self.assertIn("Math.max(0.72, hsv[1])", qml)

    def test_qml_uses_terminal_pacing_formula(self):
        qml = (PLUGIN_ROOT / "contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertIn("Math.max(Math.round(1000 / fpsCap), (100 - speed) * 10)", qml)

    def test_plugin_package_is_complete(self):
        for relative in ("metadata.json", "contents/ui/main.qml",
                         "contents/ui/config.qml", "contents/config/main.xml"):
            self.assertTrue((PLUGIN_ROOT / relative).is_file(), relative)
        metadata = json.loads((PLUGIN_ROOT / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["KPlugin"]["Id"], lock.PLUGIN_ID)
        self.assertEqual(metadata["KPackageStructure"], "Plasma/Wallpaper")


class CliTests(Isolated):
    def test_cli_set_show_history_undo(self):
        sys.path.insert(0, str(BIN))
        import matrix_lock as cli
        with patch.object(sys, "argv", ["matrix-lock", "set", "hue", "270"]):
            self.assertEqual(cli.main(), 0)
        with patch.object(sys, "argv", ["matrix-lock", "set", "color-cycle", "on"]):
            self.assertEqual(cli.main(), 0)
        values = lock.load_profile()
        self.assertTrue(values["color_cycle"])
        self.assertEqual(values["color"], config.rgb_to_hex(config.hue_degrees_rgb(270)))
        with patch.object(sys, "argv", ["matrix-lock", "undo"]):
            self.assertEqual(cli.main(), 0)
        self.assertFalse(lock.load_profile()["color_cycle"])

    def test_cli_rejects_bad_hue_and_color(self):
        import matrix_lock as cli
        for arguments in (["set", "hue", "violet"], ["set", "color", "notacolor"],
                          ["set", "fps-cap", "NaNistan"]):
            with patch.object(sys, "argv", ["matrix-lock", *arguments]):
                with self.assertRaises(SystemExit) as caught:
                    cli.main()
                self.assertNotEqual(caught.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
