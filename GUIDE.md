# User guide

This guide describes the public command surface. The executable `matrix-guide`
is the generated live reference; [CONTROLS.md](CONTROLS.md) contains the
compact control table.

The authoritative live reference is the executable `matrix-guide`, also
available as `matrix-help` with the same options. It is generated from `bin/matrix_guide_data.py`, so command and control metadata has
one maintained source.

## Commands

`matrix` runs the cinematic renderer in the current terminal. `matrix-konsole`
opens a clean Matrix Konsole window, `matrix-full` fills one display, and
`matrix-all` fills every currently enabled display with synchronized controls
and independent rain simulations. `matrix-preview` is the normal-window
preview entry point.

`matrix-saver` is the idle-aware controller. Its visual-only mode is not a
security boundary; immediate and after modes hand off to KDE's real lock
mechanism. `matrix-doctor` is read-only. `matrix-settings` manages defaults,
and `matrix-preset` manages local visual presets.

`matrix-lock` manages the animated KDE lock-screen wallpaper with an
independent profile: `configure` opens a live preview with the
normal Matrix controls and offers to save on exit, `set hue`/`set color`
select exact colors, `capture-hue` imports a hue held with `h`,
`quality balanced|high|battery` switches rendering bundles without touching
colors, `preset save|list|show|apply|rename|delete` manages named user
presets ("Neon Purple" keeps its friendly name; built-ins are read-only and
applying never touches resource protection), and `history`/`undo`/`restore`
provide reversible configuration rollback. The automatic hue cycle is
customizable: press `x` twice in `matrix-lock configure` to exclude the
traversed hue range (u/U undo/redo live edits, X clears), or use
`matrix-lock cycle exclude add 45 105` numerically; excluded ranges are
bridged by short smooth crossfades, presets carry them, and
`matrix-lock configure --preset NAME` edits a saved preset live. Adaptive resource protection (on by default, `[resource_guard]` in
config.toml for the terminal, `matrix-lock set resource-guard`/`guard-*` for
the lock screen) freezes the animation while overall system CPU or memory
use is excessive and resumes it automatically; it never overrides a manual
pause.
`enable` backs up the previous lock wallpaper before activating;
`disable` restores it. See `matrix-guide --lock` for the complete workflow
and the README's "Animated KDE lock screen" section for details.

## Defaults and configuration

The intended cinematic defaults include speed 96, green, trail 16–38,
density 52, six fade levels, 75% white heads, mutation 0.8%, profile/current
background for ordinary `matrix`, and color cycling disabled. Dedicated
Matrix launchers retain their explicit black appearance unless configured
otherwise.

Precedence is CLI, selected preset, user configuration, then built-in
defaults. The shipped example is `config/config.toml.example`; an installer
does not overwrite an existing user config. See [README.md](README.md) for
installation and [CONTRIBUTING.md](CONTRIBUTING.md) for safe validation.

## Saver security

`visual-only` returns to the unlocked desktop. `immediate` locks immediately.
`after` shows Matrix first and invokes the real KDE lock on timeout or early
exit. KDE/kscreenlocker is the authentication boundary; this utility never
handles passwords and never pretends ordinary Konsole windows remain above a
secure lock screen.

The project is licensed under [GPL-3.0-or-later](LICENSE). The renderer’s
UniMatrix provenance is documented in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
