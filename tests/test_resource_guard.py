#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
"""Synthetic-input tests for adaptive resource protection (no real load)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]
BIN = Path(os.environ.get("MATRIX_TEST_BIN", SOURCE_ROOT / "bin"))
sys.path.insert(0, str(BIN))
import matrix_resource_guard as guard  # noqa: E402

CFG = guard.validate_guard(dict(guard.GUARD_DEFAULTS))
INTERVAL = 5.0


def run_sequence(samples, cfg=CFG, state=None):
    """Feed samples through the state machine; return list of held flags."""
    state = state or guard.initial_state()
    held = []
    for sample in samples:
        state = guard.step_state(state, sample, cfg, INTERVAL)
        held.append(state["held"])
    return state, held


def s(cpu=None, mem=40.0, psi=0.0, ok=True):
    return {"ok": ok, "cpu": cpu, "mem": mem, "psi": psi}


class StateMachine(unittest.TestCase):
    def test_normal_operation_below_thresholds(self):
        _, held = run_sequence([s(cpu=30), s(cpu=55), s(cpu=10)] * 4)
        self.assertFalse(any(held))

    def test_sustained_cpu_overload_triggers(self):
        _, held = run_sequence([s(cpu=30), s(cpu=95), s(cpu=92), s(cpu=97)])
        self.assertEqual(held, [False, False, True, True])

    def test_sustained_memory_overload_triggers(self):
        _, held = run_sequence([s(cpu=20, mem=90), s(cpu=20, mem=91)])
        self.assertEqual(held, [False, True])

    def test_memory_psi_triggers_even_at_moderate_percent(self):
        _, held = run_sequence([s(cpu=20, mem=60, psi=35), s(cpu=20, mem=60, psi=30)])
        self.assertEqual(held, [False, True])

    def test_transient_spike_does_not_trigger(self):
        # One hot sample between calm samples never reaches pause_secs=8.
        _, held = run_sequence([s(cpu=20), s(cpu=96), s(cpu=25), s(cpu=97), s(cpu=30)])
        self.assertFalse(any(held))

    def test_recovery_requires_stable_calm_period(self):
        state, held = run_sequence([s(cpu=95), s(cpu=95)])
        self.assertTrue(held[-1])
        # One calm sample is not enough (resume_secs=10 needs two).
        state, held = run_sequence([s(cpu=50)], state=state)
        self.assertTrue(held[-1])
        state, held = run_sequence([s(cpu=40)], state=state)
        self.assertFalse(held[-1])

    def test_hysteresis_band_keeps_current_state(self):
        # 75% is above resume (70) and below pause (85): held stays held,
        # normal stays normal.
        state, _ = run_sequence([s(cpu=95), s(cpu=95)])
        state, held = run_sequence([s(cpu=75)] * 6, state=state)
        self.assertTrue(all(held))
        _, held = run_sequence([s(cpu=75)] * 6)
        self.assertFalse(any(held))

    def test_calm_interrupted_restarts_recovery_clock(self):
        state, _ = run_sequence([s(cpu=95), s(cpu=95)])
        state, held = run_sequence([s(cpu=40), s(cpu=90), s(cpu=40)], state=state)
        self.assertTrue(held[-1])  # single calm after interruption: still held
        _, held = run_sequence([s(cpu=40)], state=state)
        self.assertFalse(held[-1])

    def test_unknown_cpu_first_sample_never_counts_calm_or_overload(self):
        state, held = run_sequence([s(cpu=None, mem=40)])
        self.assertFalse(held[-1])
        self.assertEqual(state["overload_s"], 0.0)
        self.assertEqual(state["calm_s"], 0.0)

    def test_monitoring_failure_fails_open(self):
        state, _ = run_sequence([s(cpu=95), s(cpu=95)])
        self.assertTrue(state["held"])
        bad = {"ok": False, "cpu": None, "mem": None, "psi": None}
        state, held = run_sequence([bad, bad, bad], state=state)
        self.assertEqual(held, [True, True, False])

    def test_snooze_respects_user_resume_until_calm(self):
        state, _ = run_sequence([s(cpu=95), s(cpu=95)])
        state = dict(state, held=False, snoozed=True, overload_s=0.0, calm_s=0.0)
        # Still overloaded: guard must not re-engage while snoozed.
        state, held = run_sequence([s(cpu=95)] * 4, state=state)
        self.assertFalse(any(held))
        self.assertTrue(state["snoozed"])
        # Calm clears the snooze; a later overload can trigger again.
        state, held = run_sequence([s(cpu=30)], state=state)
        self.assertFalse(state["snoozed"])
        _, held = run_sequence([s(cpu=95), s(cpu=95)], state=state)
        self.assertTrue(held[-1])


class Validation(unittest.TestCase):
    def test_defaults_are_sane(self):
        cfg = guard.validate_guard(dict(guard.GUARD_DEFAULTS))
        self.assertTrue(cfg["resource_guard"])
        self.assertEqual(cfg["guard_cpu_pause"], 85)
        self.assertEqual(cfg["guard_cpu_resume"], 70)

    def test_resume_clamped_below_pause_for_hysteresis(self):
        cfg = guard.validate_guard({"guard_cpu_pause": 80, "guard_cpu_resume": 95})
        self.assertLessEqual(cfg["guard_cpu_resume"], 75)

    def test_threshold_bounds(self):
        cfg = guard.validate_guard({"guard_cpu_pause": 10, "guard_mem_pause": 400,
                                    "guard_pause_secs": 0, "guard_resume_secs": 9999})
        self.assertEqual(cfg["guard_cpu_pause"], 50)
        self.assertEqual(cfg["guard_mem_pause"], 100)
        self.assertEqual(cfg["guard_pause_secs"], 2.0)
        self.assertEqual(cfg["guard_resume_secs"], 600.0)


class ProcParsing(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="matrix-guard-test-")
        self.root = Path(self._tmp.name)
        (self.root / "pressure").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, content):
        (self.root / name).write_text(content, encoding="ascii")

    def test_cpu_percent_from_counter_deltas(self):
        self.write("stat", "cpu  100 0 100 800 0 0 0 0 0 0\n")
        first = guard.read_cpu_counters(self.root)
        self.assertEqual(first, (200, 1000))
        self.write("stat", "cpu  500 0 300 900 100 0 0 0 0 0\n")
        sample, counters = guard.sample_metrics(first, self.root)
        # busy delta 600, total delta 800 -> 75%
        self.assertAlmostEqual(sample["cpu"], 75.0)
        self.assertEqual(counters, (800, 1800))

    def test_mem_percent_uses_memavailable(self):
        self.write("meminfo", "MemTotal: 1000 kB\nMemFree: 50 kB\nMemAvailable: 400 kB\n")
        self.assertAlmostEqual(guard.read_mem_percent(self.root), 60.0)

    def test_psi_parsed_and_optional(self):
        self.write("pressure/memory",
                   "some avg10=12.34 avg60=1.00 avg300=0.10 total=1\n"
                   "full avg10=0.00 avg60=0.00 avg300=0.00 total=0\n")
        self.assertAlmostEqual(guard.read_memory_psi(self.root), 12.34)
        (self.root / "pressure" / "memory").unlink()
        self.assertIsNone(guard.read_memory_psi(self.root))

    def test_missing_proc_yields_not_ok_sample(self):
        sample, counters = guard.sample_metrics(None, self.root / "missing")
        self.assertFalse(sample["ok"])
        self.assertIsNone(counters)

    def test_first_sample_has_no_cpu_percent(self):
        self.write("stat", "cpu  100 0 100 800 0 0 0 0 0 0\n")
        self.write("meminfo", "MemTotal: 1000 kB\nMemAvailable: 900 kB\n")
        sample, _ = guard.sample_metrics(None, self.root)
        self.assertTrue(sample["ok"])
        self.assertIsNone(sample["cpu"])
        self.assertAlmostEqual(sample["mem"], 10.0)


class GuardWrapper(unittest.TestCase):
    def test_poll_respects_interval_and_disabled(self):
        g = guard.ResourceGuard(cfg={"resource_guard": False})
        self.assertFalse(g.poll(now=0.0))
        g = guard.ResourceGuard(proc_root="/nonexistent")
        g.poll(now=0.0)
        due = g._next_due
        g.poll(now=1.0)  # not due: state unchanged, no sampling
        self.assertEqual(g._next_due, due)

    def test_snooze_marks_state(self):
        g = guard.ResourceGuard()
        g.state = dict(g.state, held=True)
        g.snooze()
        self.assertFalse(g.held)
        self.assertTrue(g.state["snoozed"])


if __name__ == "__main__":
    unittest.main()
