// Custom hue-cycle path: QML mirror of the matrix_config cycle-path engine.
// The lock profile exports merged, enabled exclusion gaps as
// "start:end:blend;..." (phases 0-1, blend seconds). Arcs traverse the
// retained spectrum at the normal rate; bridges crossfade the retained
// endpoints (smoothstep-eased, linear-light RGB). Everything is precomputed
// once per configuration change, so per-tick evaluation is a scan over a
// handful of segments. Keep semantics identical to the Python side.
.pragma library

function parseGaps(text) {
    const gaps = []
    const chunks = String(text || "").split(";")
    for (let i = 0; i < chunks.length; ++i) {
        const parts = chunks[i].trim().split(":")
        if (parts.length < 3)
            continue
        const start = Number(parts[0]), end = Number(parts[1]), blend = Number(parts[2])
        if (!isFinite(start) || !isFinite(end) || !isFinite(blend))
            continue
        gaps.push([((start % 1) + 1) % 1, ((end % 1) + 1) % 1,
                   Math.min(30.0, Math.max(0.05, blend))])
    }
    gaps.sort(function (a, b) { return a[0] - b[0] })
    return gaps
}

// -> {total, segments: [[t0, t1, isArc, a, b], ...]} or null (full spectrum).
function buildPath(gaps, period) {
    if (!gaps || gaps.length === 0)
        return null
    period = Math.max(2.0, Number(period) || 72.0)
    const segments = []
    let t = 0.0
    for (let i = 0; i < gaps.length; ++i) {
        const gap = gaps[i]
        const nxt = gaps[(i + 1) % gaps.length]
        const arcFrom = gap[1]
        let arcLen = (((nxt[0] - arcFrom) % 1) + 1) % 1
        if (gaps.length === 1)
            arcLen = (((gap[0] - gap[1]) % 1) + 1) % 1
        segments.push([t, t + arcLen * period, true, arcFrom, arcFrom + arcLen])
        t += arcLen * period
        segments.push([t, t + nxt[2], false, nxt[0] % 1, nxt[1] % 1])
        t += nxt[2]
    }
    return { total: t, segments: segments }
}

function _segmentAt(path, seconds) {
    const total = path.total
    const s = ((seconds % total) + total) % total
    const segments = path.segments
    for (let i = 0; i < segments.length; ++i) {
        if (s <= segments[i][1]) {
            const seg = segments[i]
            return [seg, (s - seg[0]) / Math.max(1e-9, seg[1] - seg[0])]
        }
    }
    return [segments[segments.length - 1], 1.0]
}

function _blendLinear(a, b, f) {
    const out = [0, 0, 0]
    for (let i = 0; i < 3; ++i) {
        const la = Math.pow(a[i] / 255.0, 2.2)
        const lb = Math.pow(b[i] / 255.0, 2.2)
        out[i] = Math.round(255.0 * Math.pow(Math.max(0, la + (lb - la) * f), 1.0 / 2.2))
    }
    return out
}

// Displayed color at a path position; cycleRgbFn maps phase -> [r,g,b].
function colorAt(path, seconds, cycleRgbFn) {
    const found = _segmentAt(path, seconds)
    const seg = found[0], f = found[1]
    if (seg[2])   // arc
        return cycleRgbFn((((seg[3] + (seg[4] - seg[3]) * f) % 1) + 1) % 1)
    const eased = f * f * (3.0 - 2.0 * f)
    return _blendLinear(cycleRgbFn(seg[3]), cycleRgbFn(seg[4]), eased)
}

// Path position (seconds) displaying a given spectrum phase; phases inside
// an excluded gap anchor at that gap's bridge start.
function anchorFor(path, phase) {
    phase = ((phase % 1) + 1) % 1
    const segments = path.segments
    for (let i = 0; i < segments.length; ++i) {
        const seg = segments[i]
        if (!seg[2])
            continue
        const offset = (((phase - (seg[3] % 1)) % 1) + 1) % 1
        const length = seg[4] - seg[3]
        if (offset <= length + 1e-9)
            return seg[0] + (seg[1] - seg[0]) * Math.min(1.0, offset / Math.max(1e-9, length))
    }
    for (let i = 0; i < segments.length; ++i) {
        const seg = segments[i]
        if (!seg[2]) {
            const inside = (((phase - seg[3]) % 1) + 1) % 1 <= (((seg[4] - seg[3]) % 1) + 1) % 1
            if (inside)
                return seg[0]
        }
    }
    return 0.0
}
