#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
"""Deterministic tests for custom hue-cycle exclusions and the blended path."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]
BIN = Path(os.environ.get("MATRIX_TEST_BIN", SOURCE_ROOT / "bin"))
sys.path.insert(0, str(BIN))
import matrix_config as config  # noqa: E402

PERIOD = 72.0


def ex(start, end, blend=1.0, enabled=True, ident=None):
    item = {"start": start, "end": end, "blend": blend, "enabled": enabled}
    if ident is not None:
        item["id"] = ident
    return item


class DegreesMapping(unittest.TestCase):
    def test_phase_hue_round_trip_is_exact(self):
        for degrees in (0, 45, 105, 120, 180, 200, 270, 300, 359.5):
            phase = config.phase_from_hue(degrees)
            self.assertAlmostEqual(config.hue_from_phase(phase) % 360,
                                   degrees % 360, places=2)

    def test_green_is_phase_zero(self):
        self.assertAlmostEqual(config.phase_from_hue(120), 0.0)

    def test_invalid_degrees_rejected(self):
        with self.assertRaises(config.ConfigError):
            config.phase_from_hue("not-a-number")


class Normalization(unittest.TestCase):
    def test_empty_and_none(self):
        self.assertEqual(config.normalize_cycle_exclusions(None), [])
        self.assertEqual(config.normalize_cycle_exclusions([]), [])

    def test_single_exclusion_gets_stable_id(self):
        result = config.normalize_cycle_exclusions([ex(0.2, 0.4)])
        self.assertEqual(result[0]["id"], 1)
        result = config.normalize_cycle_exclusions([ex(0.2, 0.4, ident=7), ex(0.5, 0.6)])
        self.assertEqual([item["id"] for item in result], [7, 8])

    def test_invalid_inputs_rejected(self):
        for bad in ("text", [{"start": 0.1}], [{"start": "x", "end": 0.2}],
                    [ex(0.3, 0.3)], [42]):
            with self.assertRaises(config.ConfigError):
                config.normalize_cycle_exclusions(bad)

    def test_blend_clamped(self):
        result = config.normalize_cycle_exclusions([ex(0.1, 0.2, blend=999)])
        self.assertEqual(result[0]["blend"], config.CYCLE_BLEND_MAX)
        result = config.normalize_cycle_exclusions([ex(0.1, 0.2, blend=0)])
        self.assertEqual(result[0]["blend"], config.CYCLE_BLEND_MIN)

    def test_full_cycle_exclusion_rejected(self):
        with self.assertRaisesRegex(config.ConfigError, "must remain"):
            config.normalize_cycle_exclusions([ex(0.0, 0.97)])
        with self.assertRaisesRegex(config.ConfigError, "must remain"):
            config.normalize_cycle_exclusions([ex(0.0, 0.5), ex(0.45, 0.99)])

    def test_disabled_exclusions_do_not_count(self):
        result = config.normalize_cycle_exclusions([ex(0.0, 0.97, enabled=False)])
        self.assertFalse(result[0]["enabled"])
        self.assertEqual(config.enabled_cycle_gaps(result), [])


class GapMerging(unittest.TestCase):
    def test_overlapping_gaps_merge_with_longest_blend(self):
        gaps = config.enabled_cycle_gaps(config.normalize_cycle_exclusions(
            [ex(0.1, 0.3, blend=1.0), ex(0.25, 0.4, blend=2.5)]))
        self.assertEqual(len(gaps), 1)
        self.assertAlmostEqual(gaps[0][0], 0.1)
        self.assertAlmostEqual(gaps[0][1], 0.4)
        self.assertAlmostEqual(gaps[0][2], 2.5)

    def test_boundary_wrapping_gap(self):
        gaps = config.enabled_cycle_gaps(config.normalize_cycle_exclusions(
            [ex(0.9, 0.1)]))
        self.assertEqual(len(gaps), 1)
        self.assertAlmostEqual(gaps[0][0], 0.9)
        self.assertAlmostEqual(gaps[0][1], 0.1)

    def test_two_pieces_merge_across_wrap(self):
        gaps = config.enabled_cycle_gaps(config.normalize_cycle_exclusions(
            [ex(0.85, 0.999999), ex(0.0, 0.15)]))
        self.assertEqual(len(gaps), 1)
        self.assertAlmostEqual(gaps[0][0], 0.85, places=4)
        self.assertAlmostEqual(gaps[0][1], 0.15, places=4)

    def test_disjoint_gaps_stay_separate(self):
        gaps = config.enabled_cycle_gaps(config.normalize_cycle_exclusions(
            [ex(0.1, 0.2), ex(0.5, 0.6)]))
        self.assertEqual(len(gaps), 2)


class PathBuilding(unittest.TestCase):
    def test_no_exclusions_means_no_path(self):
        self.assertIsNone(config.build_cycle_path([], PERIOD))

    def test_total_duration_is_arcs_plus_blends(self):
        exclusions = config.normalize_cycle_exclusions(
            [ex(0.2, 0.3, blend=2.0), ex(0.6, 0.7, blend=1.5)])
        path = config.build_cycle_path(exclusions, PERIOD)
        self.assertAlmostEqual(path["total"], 0.8 * PERIOD + 3.5, places=6)
        kinds = [seg[2] for seg in path["segments"]]
        self.assertEqual(kinds, ["arc", "bridge", "arc", "bridge"])

    def test_bridge_endpoints_are_continuous_with_arcs(self):
        exclusions = config.normalize_cycle_exclusions([ex(0.2, 0.5, blend=1.0)])
        path = config.build_cycle_path(exclusions, PERIOD)
        for t0, t1, kind, a, b in path["segments"]:
            if kind != "bridge":
                continue
            before = config.cycle_path_rgb(path, t0 - 1e-6)
            at_start = config.cycle_path_rgb(path, t0 + 1e-9)
            after = config.cycle_path_rgb(path, t1 + 1e-6)
            at_end = config.cycle_path_rgb(path, t1 - 1e-9)
            for x, y in zip(before, at_start):
                self.assertLessEqual(abs(x - y), 2)
            for x, y in zip(after, at_end):
                self.assertLessEqual(abs(x - y), 2)

    def test_excluded_phases_never_shown_on_arcs(self):
        exclusions = config.normalize_cycle_exclusions([ex(0.25, 0.45)])
        path = config.build_cycle_path(exclusions, PERIOD)
        steps = 4000
        for index in range(steps):
            seconds = path["total"] * index / steps
            kind, a, b, fraction = config._path_segment(path, seconds)
            if kind == "arc":
                phase = (a + (b - a) * fraction) % 1.0
                inside = (phase - 0.25) % 1.0 < (0.45 - 0.25) - 1e-6
                self.assertFalse(inside and 1e-6 < (phase - 0.25) % 1.0,
                                 f"excluded phase {phase} shown at {seconds}")

    def test_reverse_traversal_is_time_mirror(self):
        exclusions = config.normalize_cycle_exclusions([ex(0.2, 0.5, blend=2.0)])
        path = config.build_cycle_path(exclusions, PERIOD)
        for seconds in (0.0, 3.3, 20.0, 41.7, path["total"] - 0.1):
            forward = config.cycle_path_rgb(path, seconds)
            # Negative time must wrap identically to total-offset time.
            mirrored = config.cycle_path_rgb(path, seconds - path["total"])
            self.assertEqual(forward, mirrored)

    def test_wrapping_gap_path(self):
        exclusions = config.normalize_cycle_exclusions([ex(0.9, 0.1, blend=1.0)])
        path = config.build_cycle_path(exclusions, PERIOD)
        self.assertAlmostEqual(path["total"], 0.8 * PERIOD + 1.0, places=6)
        # Path starts at the gap end (0.1) and the single arc runs to 0.9.
        t0, t1, kind, a, b = path["segments"][0]
        self.assertEqual(kind, "arc")
        self.assertAlmostEqual(a % 1.0, 0.1)
        self.assertAlmostEqual(b - a, 0.8)

    def test_timing_is_deterministic_and_rate_preserving(self):
        exclusions = config.normalize_cycle_exclusions([ex(0.2, 0.5, blend=1.0)])
        path_a = config.build_cycle_path(exclusions, PERIOD)
        path_b = config.build_cycle_path(exclusions, PERIOD)
        self.assertEqual(path_a, path_b)
        # An arc of 10% of the spectrum takes 10% of the period.
        for t0, t1, kind, a, b in path_a["segments"]:
            if kind == "arc":
                self.assertAlmostEqual((t1 - t0) / PERIOD, (b - a), places=6)


class AnchorsAndPhases(unittest.TestCase):
    def setUp(self):
        self.exclusions = config.normalize_cycle_exclusions([ex(0.2, 0.5, blend=1.0)])
        self.path = config.build_cycle_path(self.exclusions, PERIOD)

    def test_anchor_round_trip_on_allowed_phase(self):
        for phase in (0.0, 0.1, 0.19, 0.55, 0.7, 0.99):
            seconds = config.cycle_path_anchor(self.path, phase)
            self.assertAlmostEqual(config.cycle_path_phase(self.path, seconds),
                                   phase, places=5)

    def test_anchor_inside_gap_snaps_to_bridge_start(self):
        seconds = config.cycle_path_anchor(self.path, 0.3)
        kind, a, b, fraction = config._path_segment(self.path, seconds + 1e-6)
        self.assertEqual(kind, "bridge")

    def test_bridge_phase_snaps_to_nearer_endpoint(self):
        for t0, t1, kind, a, b in self.path["segments"]:
            if kind != "bridge":
                continue
            self.assertAlmostEqual(config.cycle_path_phase(self.path, t0 + 0.1), a)
            self.assertAlmostEqual(config.cycle_path_phase(self.path, t1 - 0.1), b)

    def test_exact_hue_hold_reproducible(self):
        seconds = config.cycle_path_anchor(self.path, 0.7)
        phase = config.cycle_path_phase(self.path, seconds)
        self.assertEqual(config.cycle_rgb(phase), config.cycle_rgb(0.7))


class CompactFormat(unittest.TestCase):
    def test_round_trip_preserves_values_and_enabled(self):
        exclusions = config.normalize_cycle_exclusions(
            [ex(0.123456, 0.654321, blend=1.75),
             ex(0.9, 0.05, blend=0.5, enabled=False)])
        text = config.format_cycle_exclusions(exclusions)
        parsed = config.parse_cycle_exclusions(text)
        self.assertEqual(len(parsed), 2)
        self.assertAlmostEqual(parsed[0]["start"], 0.123456)
        self.assertAlmostEqual(parsed[0]["end"], 0.654321)
        self.assertAlmostEqual(parsed[0]["blend"], 1.75)
        self.assertFalse(parsed[1]["enabled"])

    def test_gaps_format_contains_only_enabled(self):
        exclusions = config.normalize_cycle_exclusions(
            [ex(0.2, 0.3), ex(0.5, 0.6, enabled=False)])
        text = config.format_cycle_gaps(exclusions)
        self.assertEqual(text.count(";"), 0)
        self.assertIn("0.200000:0.300000", text)

    def test_parse_rejects_garbage(self):
        for bad in ("0.1:0.2:x", "0.1;0.2", "::"):
            with self.assertRaises(config.ConfigError):
                config.parse_cycle_exclusions(bad)
        self.assertEqual(config.parse_cycle_exclusions(""), [])

    def test_toml_literal_renders_exclusion_lists(self):
        exclusions = config.normalize_cycle_exclusions([ex(0.2, 0.3)])
        literal = config._toml_literal(exclusions)
        self.assertIn("start = 0.2", literal)
        self.assertIn("enabled = true", literal)


if __name__ == "__main__":
    unittest.main()
