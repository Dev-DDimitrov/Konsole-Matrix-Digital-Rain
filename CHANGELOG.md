# Changelog

This changelog follows a Keep-a-Changelog-inspired structure and records the
v0.9.0 source release and future work.

## [Unreleased]

### Added

- Native animated Matrix rain on the KDE lock screen: a Plasma 6 QML
  wallpaper plugin (`plasma/wallpapers/io.github.devddimitrov.matrixrain/`)
  with independent per-monitor rainfall, wall-clock-synchronized hue and
  cycling, a low-power fade-overlay render mode (default) plus an exact
  discrete-fade `quality` mode, and display-off suspension.
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
