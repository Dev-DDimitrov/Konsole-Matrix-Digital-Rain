# Architecture

This document describes the repository-relative design of the v0.9.0 public
release. See [INVENTORY.md](INVENTORY.md) for the source manifest and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for provenance.

## Runtime layout

All runtime files are kept together in `bin/` because the launchers and
Python modules intentionally discover one another relative to their installed
directory. The installer copies that directory as a managed set to
`$HOME/.local/bin/`.

Konsole profiles and color schemes are separate installation assets. The
translucent profile is Matrix-owned and launch-time only; it does not alter a
normal Konsole profile. The user unit is installed under the XDG user systemd
location but is never enabled automatically.

## State flow

Renderer settings come from built-in defaults, user config, presets, and CLI
options. `matrix-all` creates a private atomic state file under
`$XDG_RUNTIME_DIR` and each renderer independently advances rainfall while
sharing controls, hue state, pause state, and exit state.

`matrix-saver` has separate activation and idle-monitoring paths. `--once`
activates immediately. Automatic mode requires the available standards-based
session idle source. Immediate and after modes call `loginctl lock-session`;
the secure KDE lock screen is authoritative.

## Lock-screen wallpaper

The animated lock screen is a Plasma 6 QML wallpaper plugin installed to the
user wallpaper location. Each screen's instance simulates its own rainfall
while hue is a pure function of wall-clock time and the exported phase anchor,
so screens stay synchronized without IPC. The `matrix-lock` CLI owns the
canonical profile (`lockscreen.toml`), a bounded revision history, and the
one-way export that compiles the profile into the plugin's KConfig group in
`kscreenlockerrc`. No project process runs while the screen is locked; the
stock KDE greeter reads the exported configuration.

The default `auto` render mode draws through a GPU fragment shader: a Canvas
rasterizes a one-row white glyph atlas once, a second tiny Canvas encodes
per-cell state (R = glyph index, G = fade level) as 2x2 pixel blocks via
fillRect draw ops (putImageData does not reach a threaded Canvas texture on
Qt 6.11), and the baked `.qsb` shader composites atlas and state with the
exported color ramp, so hue cycling never rebuilds the atlas. Canvas
fallbacks (`quality` discrete-fade fillText, `low-power` fade overlay) remain
selectable and are used automatically if shader compilation fails. Simulation
gates on the window's frameSwapped presentation heartbeat: when the
compositor stops completing frames (displays off), stepping stops within
~1.5 s at 0.0% measured CPU and resumes on the first presented frame.

Adaptive resource protection shares one hysteresis state machine between
`bin/matrix_resource_guard.py` (terminal renderer, `matrix-lock doctor`) and
`contents/ui/guard.js` (wallpaper): overload at >=85% CPU (from /proc/stat
counter deltas) or memory-in-use (MemAvailable based) sustained ~8 s, or
memory PSI stalls; recovery when both hold <=70% for 10 s; unreadable
metrics fail open. The wallpaper samples through one plasma5support
executable dataengine source shared by every screen in the greeter process
and disconnects it while displays are off; the terminal renderer reads
/proc directly on the same 5 s cadence and reuses its pause bookkeeping so
a user pause is never overridden. On release, the wallpaper slews the hue
back onto the shared wall-clock schedule (at most half a cycle in ~15 s) so
monitors stay synchronized without a visible hue jump.

## Installation state

The installer records only the files it installed, with SHA-256 values, in a
private manifest under `$XDG_DATA_HOME/konsole-matrix-digital-rain/`. Upgrade
replacements are backed up there. Uninstall removes only unchanged files from
that manifest and preserves modified files, user config, and presets by
default.
