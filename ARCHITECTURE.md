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

## Installation state

The installer records only the files it installed, with SHA-256 values, in a
private manifest under `$XDG_DATA_HOME/konsole-matrix-digital-rain/`. Upgrade
replacements are backed up there. Uninstall removes only unchanged files from
that manifest and preserves modified files, user config, and presets by
default.
