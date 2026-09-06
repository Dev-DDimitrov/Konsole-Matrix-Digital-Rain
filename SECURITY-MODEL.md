# Security model

This document describes the intended security boundaries of the local utility;
it is not a guarantee that every deployment or desktop integration behaves
identically.

## Scope and authority

- The utility is user-level only and requires no root privileges.
- KDE/kscreenlocker remains the authentication and secure-lock boundary.
- `matrix-saver visual-only` is visual lifecycle management, not security.
- `matrix-saver immediate` and `after` hand off to KDE through `loginctl`.
- The optional user service is never enabled automatically by the installer.
- The UI `exit_guard` is an input guard, not authentication or authorization.

## State and configuration

- Runtime state is stored under the user runtime directory with private
  directory and file permissions.
- Configuration is data, not shell code, and does not provide arbitrary
  command execution.
- User settings, presets, and install manifests use atomic or restrictive
  updates where appropriate.
- Synchronized renderer state is required to remain inside the private runtime
  directory and is validated for ownership and permissions.
- Preset names are normalized and rejected when they attempt filesystem
  traversal.

## Process and desktop integration

- `matrix-saver` launches only the project’s own renderer entry point and
  verifies ownership before terminating its process group.
- `matrix-all` identifies its own windows through a private session token and
  restores temporary KWin/cursor state during normal and stale-marker cleanup.
- Cursor hiding uses only Plasma’s stock Hide Cursor effect; no privileged input
  grab, X11-only cursor hack, third-party cursor utility, or `/dev/input`
  scraping is used.
- Konsole and KWin integration is best-effort and depends on the current KDE
  session.

## Privacy and network boundary

- No password is read, stored, or handled.
- No runtime telemetry, analytics, updater, cloud dependency, or network service
  is implemented.
- No hidden remote-execution mechanism is part of configuration or normal
  operation.
- The project does not intentionally access unrelated user credentials,
  browser data, shell history, monitor identifiers, or external project data.

## Known limitations

- Reliable global activity and idle-inhibitor information is session- and KDE-
  dependent.
- Visual-only mode can fall back to explicit Matrix-window exit when global
  activity monitoring is unavailable.
- Ordinary Konsole windows are behind the secure lock screen after a real KDE
  lock; keeping them visible while locked would require lock-screen-native
  integration that this project does not fake.
- This project does not implement authentication. Security-sensitive users
  must rely on KDE’s lock-screen policy and inspect the optional service before
  enabling it.

## Related documents

See [SECURITY.md](SECURITY.md), [ARCHITECTURE.md](ARCHITECTURE.md), and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
