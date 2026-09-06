# Contributing

Konsole Matrix Digital Rain is a Fedora/KDE-focused local utility. Changes
should preserve its inspectable, user-level, privacy-conscious design.

## Development principles

- Prefer small, reviewable changes that extend the existing architecture.
- Keep configuration data separate from executable code.
- Preserve restrictive permissions and atomic state updates.
- Do not add telemetry, analytics, hidden update checks, cloud dependencies,
  privileged services, or remote-execution paths without explicit project
  direction.
- Do not use blind remote-install patterns such as `curl | bash`.
- Do not add Matrix-film logos, stills, promotional artwork, or other
  franchise-owned visual assets.
- Keep Fedora/KDE/Wayland limitations explicit rather than claiming unsupported
  behavior.

## Safe validation

From the repository root:

    for f in bin/* scripts/*; do
        first=$(head -n 1 -- "$f" 2>/dev/null || true)
        case "$first" in
            '#!'*bash*|'#!'*sh*) bash -n -- "$f" ;;
        esac
    done
    python3 -m unittest discover -s tests -p 'test_*.py' -v

The automated suite is designed to run without a graphical Plasma session,
real locking, privileged operations, or an installed external UniMatrix copy.
ShellCheck is part of CI when available. Graphical Konsole, KWin, display
topology, cursor, and KDE lock behavior remain manual acceptance tests.

The optional upstream provenance audit is separate from the normal test suite:

    python3 tests/optional_upstream_provenance.py --path /path/to/unimatrix

It reads an externally retained file and never copies or modifies it.

## Contributions and provenance

Document behavior and security boundaries when changing them. Add or update
tests for portable behavior. Contributions to derived renderer code must
preserve the UniMatrix attribution, source URL, GPL-3.0-or-later context, and
clear modification status. New project-owned source should use the project’s
SPDX identifier.

Do not invent copyright holders, upstream relationships, or release history.
Do not add external assets without reviewing their license and recording the
required notices.
