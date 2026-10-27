# Changelog

This changelog follows a Keep-a-Changelog-inspired structure and records the
v0.9.0 source release and future work.

## [Unreleased]

### Added

- Native animated Matrix rain on the KDE lock screen: a Plasma 6 QML
  wallpaper plugin (`plasma/wallpapers/io.github.devddimitrov.matrixrain/`)
  with independent per-monitor rainfall, wall-clock-synchronized hue and
  cycling, and verified display-off suspension (simulation gates on the
  window's `frameSwapped` presentation heartbeat and measured 0.0% CPU
  during DPMS-off).
- GPU shader renderer (default `auto` render mode): a baked `.qsb` fragment
  shader (`contents/shaders/rain.frag`) composites a white glyph atlas with a
  per-cell state texture for terminal-exact discrete fades at terminal pace
  (25 steps/s at speed 96) — measured ~32% of one core across three displays.
  Canvas fallbacks remain: `quality` (discrete-fade fillText) and `low-power`
  (fade-overlay).
- `matrix-lock quality balanced|high|battery` presets that switch rendering
  bundles (render mode, FPS cap, speed, density, trails, flashes) while never
  touching the selected color, hue cycling, white heads, or glyph size.
- Custom hue-cycle editing: exclusion ranges ({id, start, end, blend,
  enabled}, wrap-capable, overlap-merged, full-cycle rejection) carve
  unwanted spectrum out of the automatic cycle; the retained endpoints are
  bridged by configurable smoothstep-eased linear-light crossfades on a
  deterministic precomputed path (terminal renderer + wallpaper
  `cyclepath.js` verified color-identical). Live: `x` marks start/end at
  the displayed hue (direction-aware, works paused), `X` clears, `u`/`U`
  session undo/redo of intentional edits (bounded, redo cleared by new
  edits), `r` session reset (undoable). CLI: `matrix-lock cycle show|reset`
  and `cycle exclude add|list|remove|enable|disable|set-blend|clear`
  (degrees map exactly onto the cycle; `--phase` for exact positions);
  every change records an undoable history revision. Presets carry
  exclusions; `matrix-lock configure --preset NAME` edits a saved preset
  live with explicit update confirmation.
- Named lock-screen presets: `matrix-lock preset save|list|show|apply|rename|
  delete` with friendly display names ("Neon Purple" ↔ `neon_purple.toml`
  under `lock-presets/`), full-fidelity visual capture (exact HEX/hue-cycle
  state, pacing, trails, heads, fades, background, render mode), read-only
  built-ins, explicit `--force` replacement, atomic 0600 writes, persistence
  independent of the bounded revision history, and apply-creates-a-revision
  so `matrix-lock undo` restores the previous appearance. Presets never
  include resource-protection settings. `matrix-lock configure` now offers
  saving a captured look as the active configuration, a named preset, or
  both.
- Adaptive resource protection for both renderers
  (`bin/matrix_resource_guard.py`, mirrored in the wallpaper's `guard.js`):
  the animation freezes its current frame while aggregate CPU or
  memory-in-use is at or above 85% for ~8 s (or memory PSI indicates stalls)
  and resumes after both metrics hold at or below 70% for 10 s. CPU comes
  from `/proc/stat` counter deltas, memory from `MemAvailable`; one shared
  5-second poller per greeter process (0.03% of one core measured) that
  pauses while displays are off. Terminal `[resource_guard]` config section;
  lock-screen `resource-guard`/`guard-*` settings via `matrix-lock set`;
  live reading in `matrix-lock doctor`. Monitoring failures fail open, and a
  manual pause or resume always wins over the guard.
- `matrix-lock` command: live configuration preview that reuses the terminal
  renderer, save/cancel semantics, exact hue capture (`capture-hue`, visual
  `h` hold, `set hue DEG`, `set color "#RRGGBB"`), hue cycling controls,
  preset import, bounded revision history with `undo`/`restore`, safe
  greeter testing (`preview --greeter`), and `enable`/`disable` with
  automatic backup/restore of the previous lock wallpaper.
- Independent lock-screen profile (`lockscreen.toml`) with low-power public
  defaults; terminal settings are never modified by lock-screen saves.
- Shared color helpers in `matrix_config.py` (`nearest_cycle_phase`,
  `parse_hex_color`, `rgb_to_hex`, `hue_degrees_rgb`, `ramp_rgb`) and new
  renderer options `--cycle-phase` and `--hue-hold` used by lock previews.
- `matrix-guide --lock` section; lock-screen checks in `matrix-doctor` and
  `matrix-lock doctor`; lock-screen test suite (`tests/test_lockscreen.py`).

### Changed

- Holding a hue with `h` now anchors and records the held phase so
  `matrix-lock capture-hue` and `matrix-preset save --from-last` capture the
  exact visually selected color.
- Installer/uninstaller manage the wallpaper plugin files under
  `$XDG_DATA_HOME/plasma/wallpapers/`.

### Fixed

- Command-list regression tests now include `matrix-help`, which was added
  in v0.9.0 without updating the pinned expectations.

- Continue KDE/Wayland acceptance testing and maintenance after v0.9.0.
- Add curated screenshots or terminal recordings only when they contain no
  private machine data or franchise-owned artwork.

## [0.9.0] - 2026-09-06

Initial public release containing:

- cinematic configurable Matrix-style terminal rendering;
- color palettes, cycling, backgrounds, presets, and live controls;
- synchronized multi-monitor Konsole mode;
- optional user-level saver controller with explicit KDE lock modes;
- safe user-level installer and manifest-based uninstaller;
- read-only diagnostics and portable regression/staging tests;
- Fedora/KDE architecture, controls, security, and provenance documentation.
