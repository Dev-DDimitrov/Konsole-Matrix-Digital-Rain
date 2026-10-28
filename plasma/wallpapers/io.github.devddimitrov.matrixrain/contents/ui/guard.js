// Adaptive resource protection: QML mirror of bin/matrix_resource_guard.py.
// Keep the two state machines semantically identical; both are covered by
// synthetic-input tests (tests/test_resource_guard.py and the QML harness).
.pragma library

var PSI_PAUSE = 20.0
var PSI_RESUME = 5.0
var MAX_FAILURES = 3

function initialState() {
    return { held: false, overloadS: 0.0, calmS: 0.0, failures: 0 }
}

// Parse the concatenated output of:
//   cat /proc/stat /proc/meminfo /proc/pressure/memory
// Returns { sample: {ok, cpu, mem, psi}, cpuCounters: [busy, total]|null }.
// cpu is null on the first call (no previous counters to diff against).
function parseMetrics(text, prevCpu) {
    var counters = null
    var cpuMatch = text.match(/^cpu +([0-9][0-9 ]*)$/m)
    if (cpuMatch) {
        var fields = cpuMatch[1].trim().split(/ +/).map(Number)
        if (fields.length >= 5 && fields.every(isFinite)) {
            var total = fields.reduce(function (a, b) { return a + b }, 0)
            var idle = fields[3] + fields[4]
            counters = [total - idle, total]
        }
    }
    var cpu = null
    if (counters !== null && prevCpu) {
        var dtotal = counters[1] - prevCpu[1]
        if (dtotal > 0)
            cpu = Math.max(0, Math.min(100, 100.0 * (counters[0] - prevCpu[0]) / dtotal))
    }
    var mem = null
    var totalMatch = text.match(/^MemTotal:\s+(\d+)/m)
    var availMatch = text.match(/^MemAvailable:\s+(\d+)/m)
    if (totalMatch && availMatch && Number(totalMatch[1]) > 0)
        mem = Math.max(0, Math.min(100,
            100.0 * (1.0 - Number(availMatch[1]) / Number(totalMatch[1]))))
    var psi = null
    var psiMatch = text.match(/^some avg10=([0-9.]+)/m)
    if (psiMatch)
        psi = Number(psiMatch[1])
    return {
        sample: { ok: counters !== null || mem !== null, cpu: cpu, mem: mem, psi: psi },
        cpuCounters: counters
    }
}

// Advance the hysteresis state machine by one sample (pure).
// cfg keys: cpuPause, memPause, cpuResume, memResume, pauseSecs, resumeSecs.
function step(state, sample, cfg, intervalS) {
    var out = {
        held: state.held, overloadS: state.overloadS,
        calmS: state.calmS, failures: state.failures
    }
    if (!sample.ok) {
        out.failures += 1
        out.overloadS = 0.0
        out.calmS = 0.0
        if (out.failures >= MAX_FAILURES)
            out.held = false            // fail open on broken metrics
        return out
    }
    out.failures = 0
    var psi = sample.psi === null || sample.psi === undefined ? 0.0 : sample.psi
    var overload = (sample.cpu !== null && sample.cpu >= cfg.cpuPause)
        || (sample.mem !== null && sample.mem >= cfg.memPause)
        || psi >= PSI_PAUSE
    var calm = (sample.cpu !== null && sample.cpu <= cfg.cpuResume)
        && (sample.mem !== null && sample.mem <= cfg.memResume)
        && psi <= PSI_RESUME
    if (!out.held) {
        out.overloadS = overload ? out.overloadS + intervalS : 0.0
        out.calmS = 0.0
        if (out.overloadS >= cfg.pauseSecs) {
            out.held = true
            out.calmS = 0.0
        }
    } else {
        out.calmS = calm ? out.calmS + intervalS : 0.0
        if (out.calmS >= cfg.resumeSecs) {
            out.held = false
            out.overloadS = 0.0
        }
    }
    return out
}
