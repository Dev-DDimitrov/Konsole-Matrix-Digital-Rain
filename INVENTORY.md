# Public source manifest

This document describes the intended public source tree. It is repository-
relative and deliberately does not record installed paths, personal
configuration, workstation history, or private audit snapshots.

Initial public release: **v0.9.0**.

## Source layout

| Path | Role |
| --- | --- |
| `bin/` | Runtime launchers and Python implementations. |
| `bin/matrix_renderer.py` | Substantially modified/derived UniMatrix renderer. |
| `bin/matrix_config.py` | Configuration, palettes, presets, and secure state helpers. |
| `bin/matrix_saver.py` | Idle-aware visual and KDE lock-handoff controller. |
| `bin/matrix_cursor.py` | Reversible Plasma stock cursor-effect integration. |
| `bin/matrix_doctor.py` | Read-only environment and capability diagnostics. |
| `bin/matrix_guide*.py` | Generated command/control metadata and guide. |
| `bin/matrix_settings.py` | Atomic global settings management. |
| `bin/matrix_preset.py` | Safe visual-preset management. |
| `bin/matrix*` | User-facing launcher wrappers and display controllers. |
| `bin/unimatrix-fade*` | Local renderer entry points; not copies of the external UniMatrix executable. |
| `config/config.toml.example` | Non-destructive first-install configuration example. |
| `konsole/` | Matrix-owned Konsole profiles and color schemes. |
| `scripts/install.sh` | User-level installation with dry-run and manifest safeguards. |
| `scripts/uninstall.sh` | Manifest-based user-level removal with preservation checks. |
| `systemd/matrix-saver.service` | Optional user unit; never enabled automatically. |
| `tests/` | Portable regression, safety, and staging tests. |
| `*.md` | User, contributor, architecture, security, provenance, and release documentation. |
| `.github/workflows/` | Safe static and portable test automation. |

## Public commands

`matrix`, `matrix-konsole`, `matrix-full`, `matrix-all`, `matrix-preview`,
`matrix-saver`, `matrix-settings`, `matrix-preset`, `matrix-doctor`, and
`matrix-guide` are the public command surface. See [GUIDE.md](GUIDE.md) and
[CONTROLS.md](CONTROLS.md).

## Runtime versus source

The installer copies selected source-tree runtime files to user-level XDG and
`$HOME/.local/bin` targets. Mutable user configuration, presets, runtime state,
backup directories, and install manifests are generated outside this source
tree and are not public source files.

## Upstream provenance

`bin/matrix_renderer.py` contains substantially modified and derived work based
on [UniMatrix](https://github.com/will8211/unimatrix) by William Mannard,
released under `GPL-3.0-or-later`. UniMatrix states that it is based on CMatrix
by Chris Allegretta and Abishek V. Ashok. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the renderer header.

The external installed UniMatrix executable, retained audit checkout, upstream
fonts, screenshots, and media are not part of this repository.

## Intentional exclusions

The public repository must exclude `.agents/`, `.codex/`, Git metadata,
generated Python caches, local configuration and presets, runtime state,
development backups, private audit output, and uncurated demo captures.
