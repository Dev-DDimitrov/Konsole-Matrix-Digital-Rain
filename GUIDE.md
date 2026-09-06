# User guide

This guide describes the public command surface. The executable `matrix-guide`
is the generated live reference; [CONTROLS.md](CONTROLS.md) contains the
compact control table.

The authoritative live reference is the executable `matrix-guide`. It is
generated from `bin/matrix_guide_data.py`, so command and control metadata has
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
