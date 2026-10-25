/*
    SPDX-License-Identifier: GPL-3.0-or-later
    Part of Konsole Matrix Digital Rain.

    Matrix Digital Rain wallpaper for Plasma 6 (lock screen and desktop).

    This is a QML/Canvas port of the project's terminal renderer simulation
    (bin/matrix_renderer.py). Every screen runs its own independent rainfall
    instance; the hue is a pure function of wall-clock time and the exported
    CyclePhase/CycleEpoch anchor, so all screens stay color-synchronized
    without any IPC or daemon.

    Power behavior: the simulation is driven by a timer paced exactly like the
    terminal renderer (max(1000/fpsCap, (100-speed)*10) ms). If the compositor
    stops delivering frames (display off / fully occluded), paint callbacks
    stop; after a few missed paints the simulation suspends and only a cheap
    5-second probe remains until painting resumes.
*/

import QtQuick
import QtQuick.Window
import org.kde.plasma.plasmoid

WallpaperItem {
    id: root

    // ---- configuration -----------------------------------------------------
    readonly property string fixedColor: root.configuration.FixedColor
    readonly property string backgroundColor: root.configuration.BackgroundColor
    readonly property bool reducedMotion: root.configuration.ReducedMotion
    readonly property bool colorCycle: root.configuration.ColorCycle && !reducedMotion
    readonly property real cyclePhase: root.configuration.CyclePhase
    readonly property real cyclePeriod: Math.max(2.0, root.configuration.CyclePeriod)
    readonly property bool cycleReverse: root.configuration.CycleDirectionReverse
    readonly property real cycleEpoch: root.configuration.CycleEpoch
    readonly property int speed: Math.max(1, Math.min(100, root.configuration.Speed))
    readonly property int density: Math.max(1, Math.min(100, root.configuration.Density))
    readonly property int trailMin: Math.max(4, root.configuration.TrailMin)
    readonly property int trailMax: Math.max(trailMin, root.configuration.TrailMax)
    readonly property int fadeLevels: Math.max(3, Math.min(6, root.configuration.FadeLevels))
    readonly property int whiteHeadRate: Math.max(0, Math.min(100, root.configuration.WhiteHeadRate))
    readonly property real mutationRate: reducedMotion ? 0 : Math.max(0, Math.min(100, root.configuration.MutationRate))
    readonly property bool flashers: root.configuration.Flashers && !reducedMotion
    readonly property bool asynchronous: root.configuration.Asynchronous
    readonly property int fpsCap: Math.max(1, Math.min(60, root.configuration.FpsCap))
    readonly property int glyphSize: Math.max(10, Math.min(72, root.configuration.GlyphSize))
    // The canvas rasters at a reduced internal resolution and the scene graph
    // scales the texture up; this is the main CPU lever of the renderer.
    readonly property real renderScale: Math.max(0.25, Math.min(1.0, root.configuration.RenderScale || 0.5))

    readonly property int stepInterval: Math.max(Math.round(1000 / fpsCap), (100 - speed) * 10)

    // ---- simulation + palette state (plain JS, owned by this instance) -----
    property var columns: []
    property int frame: 0
    property int rows: 0
    property int cols: 0
    property int paintSerial: 0
    property int requestSerial: 0
    property bool suspended: false
    property var trailColors: []
    property string trailKey: ""

    // Weighted selection string (same weighting as the terminal renderer)
    // and its unique alphabet used as glyph-atlas columns.
    readonly property string glyphs: "ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ"
        + "12345678901234567890" + "-=*_+|:<\">-=*_+|:<\">-=*_+|:<\">-=*_+|:<\">"
    readonly property var glyphTable: {
        const unique = []
        const seen = ({})
        const map = []
        for (let i = 0; i < glyphs.length; ++i) {
            const ch = glyphs.charAt(i)
            if (seen[ch] === undefined) {
                seen[ch] = unique.length
                unique.push(ch)
            }
            map.push(seen[ch])
        }
        return { unique: unique, map: map }
    }

    readonly property int fontPx: Math.max(5, Math.round(glyphSize * renderScale))
    // "low-power" renders only newly advanced heads plus one fade overlay per
    // step (constant cost); "quality" repaints every cell with exact discrete
    // fade levels like the terminal renderer, at a higher CPU cost.
    readonly property bool qualityMode: String(root.configuration.RenderMode) === "quality"

    // Spectrum waypoints identical to matrix_config.CYCLE_WAYPOINTS.
    readonly property var cycleWaypoints: [
        [0.000, 120], [0.025, 130], [0.055, 145], [0.085, 155],
        [0.115, 165], [0.145, 175], [0.170, 180], [0.195, 188],
        [0.220, 200],
        [0.245, 210], [0.270, 218], [0.295, 225], [0.320, 235],
        [0.345, 245], [0.370, 255], [0.400, 265],
        [0.430, 275], [0.460, 285], [0.490, 295], [0.525, 310],
        [0.560, 325], [0.585, 337], [0.605, 345], [0.620, 350],
        [0.640, 355], [0.660, 360], [0.700, 375], [0.740, 390],
        [0.770, 405], [0.800, 420],
        [0.835, 435], [0.870, 450], [0.905, 465], [0.940, 475],
        [1.000, 480]
    ]

    function hsvToRgb(h, s, v) {
        h = ((h % 360) + 360) % 360 / 60.0
        const i = Math.floor(h)
        const f = h - i
        const p = v * (1 - s)
        const q = v * (1 - s * f)
        const t = v * (1 - s * (1 - f))
        let r, g, b
        switch (i % 6) {
        case 0: r = v; g = t; b = p; break
        case 1: r = q; g = v; b = p; break
        case 2: r = p; g = v; b = t; break
        case 3: r = p; g = q; b = v; break
        case 4: r = t; g = p; b = v; break
        default: r = v; g = p; b = q; break
        }
        return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)]
    }

    function rgbToHsv(r, g, b) {
        r /= 255; g /= 255; b /= 255
        const mx = Math.max(r, g, b), mn = Math.min(r, g, b)
        const d = mx - mn
        let h = 0
        if (d > 0) {
            if (mx === r) h = 60 * (((g - b) / d) % 6)
            else if (mx === g) h = 60 * ((b - r) / d + 2)
            else h = 60 * ((r - g) / d + 4)
        }
        return [((h % 360) + 360) % 360, mx === 0 ? 0 : d / mx, mx]
    }

    function cycleRgb(phase) {
        const position = ((phase % 1) + 1) % 1
        const points = cycleWaypoints
        for (let i = 0; i < points.length - 1; ++i) {
            const [startPhase, startHue] = points[i]
            const [endPhase, endHue] = points[i + 1]
            if (position <= endPhase) {
                const amount = (position - startPhase) / Math.max(1e-9, endPhase - startPhase)
                return hsvToRgb(startHue + (endHue - startHue) * amount, 1, 1)
            }
        }
        return hsvToRgb(points[points.length - 1][1], 1, 1)
    }

    function parseHex(text) {
        const match = /^#([0-9a-f]{6})$/i.exec(String(text).trim())
        if (!match) return [0, 255, 0]
        const value = parseInt(match[1], 16)
        return [(value >> 16) & 255, (value >> 8) & 255, value & 255]
    }

    function cssRgb(rgb) {
        return "rgb(" + rgb[0] + "," + rgb[1] + "," + rgb[2] + ")"
    }

    // Identical shaping to matrix_config.ramp_rgb (bright -> dark).
    function rampRgb(baseRgb, levels) {
        const hsv = rgbToHsv(baseRgb[0], baseRgb[1], baseRgb[2])
        const brightness = [1.0, 0.82, 0.63, 0.46, 0.30, 0.16]
        const full = brightness.map(level =>
            hsvToRgb(hsv[0], Math.max(0.72, hsv[1]), Math.min(1.0, hsv[2] * level)))
        if (levels >= full.length) return full
        const last = full.length - 1
        const result = []
        for (let i = 0; i < levels; ++i)
            result.push(full[Math.round(i * last / (levels - 1))])
        return result
    }

    function currentPhase() {
        const sign = cycleReverse ? -1.0 : 1.0
        const elapsed = (Date.now() / 1000.0) - cycleEpoch
        const phase = cyclePhase + sign * (elapsed / cyclePeriod)
        return ((phase % 1) + 1) % 1
    }

    function updateTrailColors() {
        let base, key
        if (colorCycle) {
            const phase = currentPhase()
            key = "cycle:" + Math.floor(phase * 720) + ":" + fadeLevels
            if (key === trailKey) return
            base = cycleRgb(phase)
        } else {
            key = "fixed:" + fixedColor + ":" + fadeLevels
            if (key === trailKey) return
            base = parseHex(fixedColor)
        }
        trailColors = rampRgb(base, fadeLevels).map(cssRgb)
        trailKey = key
    }

    // ---- simulation (port of Stream/Column in matrix_renderer.py) ----------
    function newStream() {
        const length = trailMin + Math.floor(Math.random() * (trailMax - trailMin + 1))
        return {
            length: length,
            head: -Math.floor(Math.random() * Math.max(1, Math.floor(length / 2)) + 1),
            stepEvery: asynchronous ? 1 + Math.floor(Math.random() * 3) : 1,
            whiteHead: Math.random() * 100 < whiteHeadRate,
            cells: [],      // ring of {y, glyph}
            done: false
        }
    }

    function newCooldown(initial) {
        const maxGap = Math.max(2, Math.floor(rows * (110 - density) / 100))
        if (initial) return Math.floor(Math.random() * (maxGap + 1))
        return Math.max(1, Math.floor(maxGap / 5)) + Math.floor(Math.random() * Math.max(1, maxGap - maxGap / 5))
    }

    property bool needsFullClear: true

    function rebuild() {
        const pitchX = Math.round(glyphSize * 1.35)
        const pitchY = Math.round(glyphSize * 1.15)
        cols = Math.max(1, Math.floor(width / pitchX))
        rows = Math.max(1, Math.ceil(height / pitchY))
        const next = []
        for (let x = 0; x < cols; ++x)
            next.push({ x: x, stream: null, cooldown: newCooldown(true), paintedStream: null, paintedHead: 0 })
        columns = next
        frame = 0
        needsFullClear = true
    }

    function randomGlyph() {
        // Weighted pick mapped to its unique atlas column.
        return glyphTable.map[Math.floor(Math.random() * glyphs.length)]
    }

    function advanceStream(stream) {
        stream.head += 1
        if (stream.head >= 0 && stream.head < rows)
            stream.cells.push({ y: stream.head, glyph: randomGlyph() })
        const oldest = stream.head - stream.length
        while (stream.cells.length > 0 && stream.cells[0].y < oldest)
            stream.cells.shift()
        if (stream.head - stream.length >= rows)
            stream.done = true
    }

    function tickColumn(column) {
        if (column.stream === null) {
            if (column.cooldown <= 0)
                column.stream = newStream()
            else
                column.cooldown -= 1
            return
        }
        const stream = column.stream
        if (frame % stream.stepEvery === 0)
            advanceStream(stream)
        if (flashers && mutationRate > 0 && qualityMode) {
            for (let i = 0; i < stream.cells.length; ++i)
                if (Math.random() < mutationRate / 100.0)
                    stream.cells[i].glyph = randomGlyph()
        }
        if (stream.done) {
            column.stream = null
            column.cooldown = newCooldown(false)
        }
    }

    function tick() {
        // Display-off suspension: when the compositor stops scheduling
        // frames (output off), requested paints never complete; back off
        // once several requests are outstanding and let the probe resume us.
        if (requestSerial - paintSerial > 5) {
            suspended = true
            return
        }
        for (let i = 0; i < columns.length; ++i)
            tickColumn(columns[i])
        frame = (frame + 1) % 600000
        requestSerial += 1
        canvas.requestPaint()
    }

    onWidthChanged: rebuild()
    onHeightChanged: rebuild()
    onGlyphSizeChanged: rebuild()
    onDensityChanged: rebuild()
    onRenderScaleChanged: rebuild()
    Component.onCompleted: rebuild()

    function headColorCss() {
        const bg = parseHex(backgroundColor)
        return (bg[0] + bg[1] + bg[2]) > 600 ? "#000000" : "#ffffff"
    }

    Rectangle {
        anchors.fill: parent
        color: root.backgroundColor
    }

    Canvas {
        id: canvas
        width: Math.max(1, Math.round(root.width * root.renderScale))
        height: Math.max(1, Math.round(root.height * root.renderScale))
        transformOrigin: Item.TopLeft
        scale: root.width / Math.max(1, width)
        smooth: true
        // Threaded is the one strategy whose requestPaint() reliably repaints
        // on Qt 6.11 (Immediate paints only once; verified on this stack).
        // The onPaint handler records 2D commands on the GUI thread, so the
        // suspension bookkeeping below is safe; rasterization happens on the
        // canvas worker thread.
        renderStrategy: Canvas.Threaded

        onPaint: {
            root.paintSerial = root.requestSerial
            if (root.suspended)
                root.suspended = false
            const ctx = getContext("2d")
            root.updateTrailColors()
            const colors = root.trailColors
            if (colors.length === 0)
                return
            const factor = root.renderScale
            const pitchX = Math.round(root.glyphSize * 1.35) * factor
            const pitchY = Math.round(root.glyphSize * 1.15) * factor
            const unique = root.glyphTable.unique
            const columnList = root.columns
            ctx.font = root.fontPx + "px monospace"
            ctx.textBaseline = "top"
            if (root.needsFullClear || root.qualityMode) {
                ctx.clearRect(0, 0, width, height)
                root.needsFullClear = false
            }

            if (root.qualityMode) {
                // Exact terminal look: every visible cell is repainted with
                // its discrete fade level, bucketed to minimize state changes.
                const buckets = []
                for (let level = 0; level <= colors.length; ++level)
                    buckets.push([])
                for (let i = 0; i < columnList.length; ++i) {
                    const stream = columnList[i].stream
                    if (stream === null)
                        continue
                    const px = columnList[i].x * pitchX
                    for (let c = 0; c < stream.cells.length; ++c) {
                        const cell = stream.cells[c]
                        if (cell.y < 0 || cell.y >= root.rows)
                            continue
                        const distance = Math.max(0, stream.head - cell.y)
                        let level
                        if (distance === 0 && stream.whiteHead)
                            level = colors.length
                        else {
                            const ratio = Math.min(1.0, distance / Math.max(1, stream.length - 1))
                            level = Math.min(colors.length - 1, Math.floor(ratio * colors.length))
                        }
                        buckets[level].push(cell.glyph, px, cell.y * pitchY)
                    }
                }
                for (let level = 0; level <= colors.length; ++level) {
                    const bucket = buckets[level]
                    if (bucket.length === 0)
                        continue
                    ctx.fillStyle = level === colors.length ? root.headColorCss() : colors[level]
                    for (let b = 0; b < bucket.length; b += 3)
                        ctx.fillText(unique[bucket[b]], bucket[b + 1], bucket[b + 2])
                }
                return
            }

            // Low-power mode: one fade overlay plus only the glyphs whose
            // stream advanced since the previous paint. Trails fade
            // continuously toward the background instead of in discrete
            // steps; the simulation (and so the rain pattern) is identical.
            const trailSteps = Math.max(4, (root.trailMin + root.trailMax) / 2)
            const fadeAlpha = Math.min(0.5, 1.0 - Math.pow(0.08, 1.0 / trailSteps))
            ctx.globalCompositeOperation = "destination-out"
            ctx.fillStyle = "rgba(0,0,0," + fadeAlpha.toFixed(4) + ")"
            ctx.fillRect(0, 0, width, height)
            ctx.globalCompositeOperation = "source-over"
            const bright = colors[0]
            const headCss = root.headColorCss()
            for (let i = 0; i < columnList.length; ++i) {
                const column = columnList[i]
                const stream = column.stream
                if (stream === null) {
                    column.paintedStream = null
                    continue
                }
                const from = column.paintedStream === stream
                    ? column.paintedHead + 1 : Math.max(0, stream.head)
                const px = column.x * pitchX
                const base = stream.head - (stream.cells.length - 1)
                for (let y = Math.max(0, from); y <= stream.head && y < root.rows; ++y) {
                    const cell = stream.cells[y - base]
                    if (cell === undefined)
                        continue
                    if (y === stream.head && stream.whiteHead) {
                        ctx.fillStyle = headCss
                        ctx.fillText(unique[cell.glyph], px, y * pitchY)
                        const previous = stream.cells[y - base - 1]
                        if (previous !== undefined && previous.y >= 0) {
                            ctx.fillStyle = bright
                            ctx.fillText(unique[previous.glyph], px, previous.y * pitchY)
                        }
                    } else {
                        ctx.fillStyle = bright
                        ctx.fillText(unique[cell.glyph], px, y * pitchY)
                    }
                }
                column.paintedStream = stream
                column.paintedHead = stream.head
            }
        }
    }

    // The window-visibility gate stops all simulation work when the
    // compositor hides or unmaps this surface. The outstanding-paint gate is
    // a safety net for render loops that stop completing paints. Measured
    // limitation: in greeter --testing mode with DPMS off, Qt falls back to
    // timer-driven rendering and paints keep completing, so neither gate
    // fires there; behavior under a real session lock depends on KWin
    // unmapping the lock surfaces.
    readonly property bool windowVisible: {
        const visibility = root.Window.visibility
        return visibility !== Window.Hidden && visibility !== Window.Minimized
    }

    Timer {
        id: stepTimer
        interval: root.stepInterval
        repeat: true
        running: root.visible && root.windowVisible && !root.suspended
        onTriggered: root.tick()
    }

    Timer {
        id: probeTimer
        interval: 5000
        repeat: true
        running: root.suspended
        onTriggered: canvas.requestPaint()
    }
}
