// System resource monitor for adaptive protection. Loaded through a Loader
// so a missing plasma5support module degrades to "no protection" instead of
// breaking the wallpaper.
//
// The executable dataengine is shared per process and keyed by the command
// string, so the single greeter process runs one cat(1) per interval no
// matter how many screens show the wallpaper. Reading /proc directly keeps
// CPU% counter-delta based and includes memory PSI, with no extra daemon.
import QtQuick
import org.kde.plasma.plasma5support as P5Support
import "guard.js" as Guard

Item {
    id: mon
    visible: false

    // cfg: {cpuPause, memPause, cpuResume, memResume, pauseSecs, resumeSecs}
    property var cfg: ({ cpuPause: 85, memPause: 85, cpuResume: 70,
                         memResume: 70, pauseSecs: 8, resumeSecs: 10 })
    // The parent turns this off while displays are off so monitoring cannot
    // defeat the near-zero idle state; reconnecting samples immediately.
    property bool monitoringActive: true
    property bool held: false

    property var guardState: Guard.initialState()
    property var prevCpu: null
    readonly property string command:
        "cat /proc/stat /proc/meminfo /proc/pressure/memory 2>/dev/null"
    readonly property real intervalS: 5.0

    P5Support.DataSource {
        engine: "executable"
        connectedSources: mon.monitoringActive ? [mon.command] : []
        interval: mon.intervalS * 1000
        onNewData: function (sourceName, data) {
            const parsed = Guard.parseMetrics(String(data.stdout || ""), mon.prevCpu)
            mon.prevCpu = parsed.cpuCounters
            mon.guardState = Guard.step(mon.guardState, parsed.sample,
                                        mon.cfg, mon.intervalS)
            if (mon.guardState.held !== mon.held) {
                mon.held = mon.guardState.held
                console.warn("matrixrain: resource protection "
                             + (mon.held ? "engaged" : "released")
                             + " (cpu=" + parsed.sample.cpu
                             + " mem=" + parsed.sample.mem
                             + " psi=" + parsed.sample.psi + ")")
            }
        }
    }
}
