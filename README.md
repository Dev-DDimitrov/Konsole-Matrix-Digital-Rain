# Konsole Matrix Digital Rain

[![CI](https://github.com/Dev-DDimitrov/Konsole-Matrix-Digital-Rain/actions/workflows/ci.yml/badge.svg)](https://github.com/Dev-DDimitrov/Konsole-Matrix-Digital-Rain/actions/workflows/ci.yml)

Konsole Matrix Digital Rain is an independent Fedora/KDE utility for a
polished digital-rain experience in Konsole, with configurable palettes,
synchronized multi-monitor windows, and an optional idle-aware saver
controller.

The repository is public. The initial public release is **v0.9.0**, and this
source snapshot represents that release.

Konsole Matrix Digital Rain is an independent open-source project and is not
affiliated with, sponsored by, or endorsed by the creators or rights holders
of *The Matrix*. “The Matrix” and related marks belong to their respective
owners.

## Why this exists

I want to share this project out of love for Linux, the Matrix, and all things
in between. It brings the visual experience, KDE integration, and safety
controls together in a small local utility that remains inspectable and
controllable.

## Features

- Cinematic green defaults: speed 96, trails 16–38, density 52, six fade
  levels, 75% white heads, and 0.8% glyph mutation.
- Seven direct colors plus a balanced green/cyan, blue, purple/pink,
  red/orange, and yellow/lime cycle.
- Profile, black, charcoal, white, and translucent backgrounds.
- Presets: `cinematic`, `classic`, `ambient`, `dense`, `minimal`, and `cyber`.
- Live controls for color, cycling, speed, hue hold, pause, white heads,
  backgrounds, settings lock, and safe exit handling.
- Independent terminal rain or synchronized multi-monitor rainfall.
- Optional Plasma stock Hide Cursor integration with stale-state recovery.
- Optional user-level systemd saver service that is installed but never enabled
  automatically.
- Explicit `visual-only`, `immediate`, and secure `after` saver modes.
- Atomic private configuration, runtime state, presets, and install manifests.

## Screenshots and demo

Curated project screenshots and terminal recordings may be added later. No
upstream UniMatrix screenshots, Matrix-film artwork, logos, or other franchise
media are redistributed by this repository.

## Supported environment and requirements

The supported target is Fedora Linux with KDE Plasma, Konsole, Python 3.11 or
newer, Bash, and a 256-color terminal. The optional integrations use
`kscreen-doctor`, `gdbus`, `loginctl`, and user-level systemd. The ordinary
renderer uses only the Python standard library.

The saver and multi-monitor modes require a live KDE session for their real
behavior. Static checks and automated tests do not require a graphical session
or a running service.

## Installation

Inspect the public source repository first:

    git clone https://github.com/Dev-DDimitrov/Konsole-Matrix-Digital-Rain.git
    cd Konsole-Matrix-Digital-Rain
    scripts/install.sh --dry-run
    scripts/install.sh

The dry run validates the source tree and shows intended user-level targets.
The installer copies managed launchers, Python modules, Konsole assets, and
the optional user unit. It preserves an existing user configuration, creates
private backups for replaced managed files, and never enables the saver
service.

## Commands

| Command | Purpose |
| --- | --- |
| `matrix` | Run rain in the current terminal. |
| `matrix-konsole` | Open a dedicated Matrix Konsole window. |
| `matrix-full` | Open one UI-free fullscreen display. |
| `matrix-all` | Open synchronized fullscreen windows across enabled displays. |
| `matrix-preview` | Preview a palette or preset in a normal Konsole window. |
| `matrix-saver` | Run the idle-aware visual and secure saver controller. |
| `matrix-settings` | Inspect and manage global visual defaults. |
| `matrix-preset` | Save and manage local visual presets. |
| `matrix-doctor` | Run read-only Fedora/KDE/Matrix diagnostics. |
| `matrix-guide` | Show the generated command and control reference. |

See [CONTROLS.md](CONTROLS.md), [GUIDE.md](GUIDE.md), and the executable
`matrix-guide` for the complete current control surface.

## Rainfall, palettes, and presets

Ordinary `matrix` uses the current terminal profile background by default.
Dedicated Matrix Konsole launchers use an opaque black background unless
`--background translucent` is selected. The translucent profile is a
Matrix-owned Konsole asset with 70% opacity.

Use `--preset cinematic`, `--preset classic`, or another built-in preset to
select a visual starting point. User presets are visual-only TOML files under
`\${XDG_CONFIG_HOME:-\$HOME/.config}/konsole-matrix-digital-rain/presets/`. They never save global
animation pause state.

The ordinary renderer advances each rainfall stream independently. `matrix-all`
shares visual settings, controls, hue state, pause state, and exit state across
its windows while each display continues its own rain simulation.

## Saver and KDE security behavior

The concise modes are:

    matrix-saver visual-only
    matrix-saver immediate
    matrix-saver after

`visual-only` returns to the unlocked desktop. `immediate` hands off to
`loginctl lock-session` without launching a visual child. `after` shows Matrix
first, then performs the real KDE lock handoff after the configured delay or
when the visual session exits early. Use `--dry-run` to inspect the policy
without starting windows or locking.

KDE/kscreenlocker remains the authentication boundary. Ordinary Konsole
windows are not represented as a lock-screen-native visual and do not remain
above a secure lock screen after locking.

## Settings and uninstall

Configuration precedence is CLI option, selected preset, user configuration,
then built-in defaults. `matrix-settings show|get|set|reset|path` manages
global defaults with atomic updates.

Preview removal with:

    scripts/uninstall.sh --dry-run

Uninstall removes only unchanged files recorded in the private install
manifest. Modified managed files, user configuration, and presets are
preserved by default. Purging user data is a separate explicitly confirmed
operation: `--purge-user-data --yes`.

## Privacy and security

The utility is user-level only. It has no runtime network requirement,
telemetry, analytics, updater, cloud dependency, password handling, or hidden
remote-execution mechanism. Configuration is data rather than shell code.
Runtime state and mutable settings use restrictive permissions and atomic
updates. See [SECURITY-MODEL.md](SECURITY-MODEL.md) and
[SECURITY.md](SECURITY.md).

Known limitations include the lack of a reliable cross-session idle-inhibitor
enumeration API in the target KDE environment, best-effort cursor hiding from
the stock Plasma effect, and the requirement for a real KDE session for live
window and lock behavior.

## Development and documentation

The public source tree is organized as follows:

- `bin/` — runtime launchers and Python implementations.
- `config/` — non-destructive example configuration.
- `konsole/` — Matrix-owned Konsole profiles and color schemes.
- `scripts/` — user-level install and uninstall scripts.
- `systemd/` — optional user service unit.
- `tests/` — portable regression and safety tests.

See [ARCHITECTURE.md](ARCHITECTURE.md), [CONTROLS.md](CONTROLS.md),
[GUIDE.md](GUIDE.md), [INVENTORY.md](INVENTORY.md),
[CONTRIBUTING.md](CONTRIBUTING.md), and [CHANGELOG.md](CHANGELOG.md).

## Validation

Automated and CI-safe checks require no graphical Plasma session, real screen
locking, service enablement, privileged operations, or external UniMatrix copy:

    for f in bin/* scripts/*; do
        first=$(head -n 1 -- "$f" 2>/dev/null || true)
        case "$first" in '#!'*bash*|'#!'*sh*) bash -n -- "$f" ;; esac
    done
    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v

The staging test exercises dry-run installation, isolated installation, and
manifest-based uninstall behavior in a temporary home. ShellCheck runs in CI
when the Fedora runner installs it. Live Konsole, display-topology, cursor,
and KDE lock behavior remain manual graphical acceptance tests. The optional
upstream provenance check is documented in [CONTRIBUTING.md](CONTRIBUTING.md)
and is not part of the default suite.

## Upstream attribution and license

The renderer in `bin/matrix_renderer.py` contains substantially modified and
derived work based on [UniMatrix](https://github.com/will8211/unimatrix) by
William Mannard. UniMatrix is released under the GNU General Public License,
version 3 or any later version. UniMatrix also states that it is based on
CMatrix by Chris Allegretta and Abishek V. Ashok; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the project’s provenance
details.

This project is released under [GPL-3.0-or-later](LICENSE). The external
installed UniMatrix executable is not bundled, copied, modified, or managed by
this repository. Upstream fonts, screenshots, and media are not redistributed.

Contributions must preserve applicable upstream attribution and license
notices. See [CONTRIBUTING.md](CONTRIBUTING.md).
