#!/usr/bin/env python3
"""Adaptive resource protection for the Matrix renderers.

Suspends animation while the whole system is overloaded and resumes when it
recovers. CPU utilization is derived from /proc/stat counter differences
(never load average), memory from MemAvailable (so reclaimable cache is not
mistaken for used memory) with /proc/pressure/memory PSI as a stall signal.

The decision logic lives in pure functions (`step_state`) so thresholds and
hysteresis are unit-testable with synthetic inputs; `ResourceGuard` wraps
them with real /proc sampling on a conservative interval. The QML wallpaper
mirrors this exact state machine in contents/ui/guard.js.
"""

import time
from pathlib import Path

# Defaults shared by the terminal renderer and the lock-screen profile.
GUARD_DEFAULTS = {
    "resource_guard": True,
    "guard_cpu_pause": 85,     # % aggregate CPU that triggers protection
    "guard_mem_pause": 85,     # % memory in use (MemTotal - MemAvailable)
    "guard_cpu_resume": 70,    # recovery requires both metrics at or below
    "guard_mem_resume": 70,    # their resume thresholds...
    "guard_pause_secs": 8,     # ...sustained overload before pausing
    "guard_resume_secs": 10,   # ...and stable calm before resuming
}

SAMPLE_INTERVAL = 5.0          # seconds between /proc samples
PSI_PAUSE = 20.0               # memory PSI some avg10 that forces protection
PSI_RESUME = 5.0               # PSI must fall below this to count as calm
MAX_FAILURES = 3               # consecutive unreadable samples -> fail open


def validate_guard(values):
    """Clamp guard settings in place (values is any dict holding the keys)."""
    values["resource_guard"] = bool(values.get(
        "resource_guard", GUARD_DEFAULTS["resource_guard"]))
    for key in ("guard_cpu_pause", "guard_mem_pause"):
        values[key] = int(min(100, max(50, int(values.get(key, GUARD_DEFAULTS[key])))))
    for key, pause_key in (("guard_cpu_resume", "guard_cpu_pause"),
                           ("guard_mem_resume", "guard_mem_pause")):
        resume = int(min(100, max(10, int(values.get(key, GUARD_DEFAULTS[key])))))
        values[key] = min(resume, values[pause_key] - 5)  # keep hysteresis
    values["guard_pause_secs"] = float(min(120.0, max(2.0, float(
        values.get("guard_pause_secs", GUARD_DEFAULTS["guard_pause_secs"])))))
    values["guard_resume_secs"] = float(min(600.0, max(2.0, float(
        values.get("guard_resume_secs", GUARD_DEFAULTS["guard_resume_secs"])))))
    return values


def initial_state():
    return {"held": False, "overload_s": 0.0, "calm_s": 0.0,
            "failures": 0, "snoozed": False}


def step_state(state, sample, cfg, interval_s):
    """Advance the hysteresis state machine by one sample (pure).

    sample: {"ok": bool, "cpu": float|None, "mem": float|None, "psi": float|None}
    cfg: a dict containing the guard_* keys. Returns a new state dict.
    """
    out = dict(state)
    if not sample.get("ok"):
        out["failures"] += 1
        out["overload_s"] = 0.0
        out["calm_s"] = 0.0
        if out["failures"] >= MAX_FAILURES:
            out["held"] = False      # fail open: never freeze on broken metrics
        return out
    out["failures"] = 0
    cpu, mem = sample.get("cpu"), sample.get("mem")
    psi = sample.get("psi") or 0.0
    overload = ((cpu is not None and cpu >= cfg["guard_cpu_pause"])
                or (mem is not None and mem >= cfg["guard_mem_pause"])
                or psi >= PSI_PAUSE)
    calm = ((cpu is not None and cpu <= cfg["guard_cpu_resume"])
            and (mem is not None and mem <= cfg["guard_mem_resume"])
            and psi <= PSI_RESUME)
    if out["snoozed"]:
        # The user manually resumed during overload: stay out of the way
        # until the system has actually calmed down once.
        if not overload:
            out["snoozed"] = False
        out["held"] = False
        out["overload_s"] = 0.0
        out["calm_s"] = 0.0
        return out
    if not out["held"]:
        out["overload_s"] = out["overload_s"] + interval_s if overload else 0.0
        out["calm_s"] = 0.0
        if out["overload_s"] >= cfg["guard_pause_secs"]:
            out["held"] = True
            out["calm_s"] = 0.0
    else:
        out["calm_s"] = out["calm_s"] + interval_s if calm else 0.0
        if out["calm_s"] >= cfg["guard_resume_secs"]:
            out["held"] = False
            out["overload_s"] = 0.0
    return out


def read_cpu_counters(proc_root="/proc"):
    """(busy, total) jiffies from the aggregate cpu line, or None."""
    try:
        with open(Path(proc_root) / "stat", encoding="ascii", errors="replace") as handle:
            first = handle.readline().split()
    except OSError:
        return None
    if len(first) < 8 or first[0] != "cpu":
        return None
    try:
        fields = [int(part) for part in first[1:]]
    except ValueError:
        return None
    total = sum(fields)
    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)  # idle + iowait
    return (total - idle, total)


def read_mem_percent(proc_root="/proc"):
    """Memory utilization % based on MemAvailable, or None."""
    total = available = None
    try:
        with open(Path(proc_root) / "meminfo", encoding="ascii", errors="replace") as handle:
            for line in handle:
                if line.startswith("MemTotal:"):
                    total = float(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    available = float(line.split()[1])
                if total is not None and available is not None:
                    break
    except OSError:
        return None
    if not total or available is None:
        return None
    return max(0.0, min(100.0, 100.0 * (1.0 - available / total)))


def read_memory_psi(proc_root="/proc"):
    """memory pressure 'some avg10' %, or None when PSI is unavailable."""
    try:
        with open(Path(proc_root) / "pressure" / "memory",
                  encoding="ascii", errors="replace") as handle:
            for line in handle:
                if line.startswith("some"):
                    for token in line.split():
                        if token.startswith("avg10="):
                            return float(token[6:])
    except (OSError, ValueError):
        return None
    return None


def sample_metrics(prev_cpu, proc_root="/proc"):
    """One metrics sample. Returns (sample, cpu_counters_for_next_call)."""
    counters = read_cpu_counters(proc_root)
    cpu = None
    if counters and prev_cpu:
        dtotal = counters[1] - prev_cpu[1]
        if dtotal > 0:
            cpu = max(0.0, min(100.0, 100.0 * (counters[0] - prev_cpu[0]) / dtotal))
    mem = read_mem_percent(proc_root)
    psi = read_memory_psi(proc_root)
    ok = counters is not None or mem is not None
    return ({"ok": ok, "cpu": cpu, "mem": mem, "psi": psi}, counters)


class ResourceGuard:
    """Samples /proc on a fixed interval and tracks the protection state."""

    def __init__(self, cfg=None, proc_root="/proc", interval_s=SAMPLE_INTERVAL):
        merged = dict(GUARD_DEFAULTS)
        if cfg:
            merged.update({key: cfg[key] for key in GUARD_DEFAULTS if key in cfg})
        self.cfg = validate_guard(merged)
        self.enabled = self.cfg["resource_guard"]
        self.proc_root = proc_root
        self.interval_s = interval_s
        self.state = initial_state()
        self._prev_cpu = None
        self._next_due = 0.0
        self.last_sample = None

    @property
    def held(self):
        return self.enabled and self.state["held"]

    def poll(self, now=None):
        """Sample if due; cheap no-op otherwise. Returns current held flag."""
        if not self.enabled:
            return False
        now = time.monotonic() if now is None else now
        if now >= self._next_due:
            self._next_due = now + self.interval_s
            sample, self._prev_cpu = sample_metrics(self._prev_cpu, self.proc_root)
            self.last_sample = sample
            self.state = step_state(self.state, sample, self.cfg, self.interval_s)
        return self.held

    def snooze(self):
        """User manually resumed while held: stand down until calm returns."""
        self.state = dict(self.state, held=False, snoozed=True,
                          overload_s=0.0, calm_s=0.0)

    def describe(self):
        sample = self.last_sample or {}
        def fmt(value, suffix="%"):
            return "n/a" if value is None else f"{value:.0f}{suffix}"
        return (f"cpu {fmt(sample.get('cpu'))} mem {fmt(sample.get('mem'))} "
                f"psi {fmt(sample.get('psi'))} -> "
                f"{'HOLD' if self.held else 'normal'}")
