# Third-party notices and provenance

This document records known upstream relationships for the source tree. It is
not a claim that every visual concept or system integration is third-party
code.

## UniMatrix

The renderer in `bin/matrix_renderer.py` contains substantially modified and
derived work based on:

- Project: UniMatrix
- Repository: <https://github.com/will8211/unimatrix>
- Author identified by upstream: William Mannard
- Original source date: 2018-01-19
- License: GNU General Public License version 3, or any later version
- SPDX expression: `GPL-3.0-or-later`

The current renderer is not a verbatim copy. It adds extensive local work,
including configurable trails and palettes, synchronized state, color-cycle
behavior, saved settings, pause and guard controls, and KDE/Konsole
integration. Those additions are not authored by William Mannard. The detailed
provenance header in `bin/matrix_renderer.py` identifies the relationship at
the source-file level.

UniMatrix’s own README and source state that it is based on CMatrix by Chris
Allegretta and Abishek V. Ashok. This repository does not contain a copied
CMatrix source tree. The statement is retained as part of the upstream
provenance context.

## Local project components

The remaining components are local project work or integration assets,
including the configuration library, saver controller, Plasma cursor
integration, diagnostics, settings and preset tools, shell launchers,
installer/uninstaller, systemd unit, Konsole profiles, color schemes, tests,
and documentation. They do not carry UniMatrix source code merely because
they use Matrix-style terminology or invoke the local renderer.

## Not redistributed

The following remain outside this repository:

- the installed external `~/.local/bin/unimatrix` executable;
- the retained upstream audit checkout;
- UniMatrix’s bundled fonts;
- UniMatrix screenshots and other media;
- Matrix-film logos, artwork, stills, characters, or promotional assets.

The canonical tree does not copy, modify, or manage the external installed
UniMatrix executable.

## License and independent-project notice

This project uses [GNU GPL-3.0-or-later](LICENSE). Contributions that modify
derived renderer code must preserve the UniMatrix attribution and license
context and must identify substantial modifications.

Konsole Matrix Digital Rain is an independent open-source project and is not
affiliated with, sponsored by, or endorsed by the creators or rights holders
of *The Matrix*. “The Matrix” and related marks belong to their respective
owners. This notice does not itself provide trademark clearance.

The project also does not claim sponsorship, endorsement, or authorization by
the UniMatrix, CMatrix, KDE, or Fedora projects.
