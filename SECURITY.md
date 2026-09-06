# Security policy

## Status

The initial public release target is **v0.9.0**. Until the first public
repository and release process exist, no security contact address or private
reporting endpoint is configured.

When the public repository is created, private GitHub vulnerability reporting
or another private reporting mechanism should be enabled before public release
announcements. Do not place exploitable vulnerability details in a public issue
or discussion.

## What to report

Please report issues that could cause, for example:

- unintended privilege escalation or privileged execution;
- unsafe deletion or modification outside managed user targets;
- unintended access to credentials, private files, or unrelated processes;
- arbitrary command execution through configuration, presets, or installer
  inputs;
- failure to restore temporary KDE/KWin state safely;
- release artifacts containing secrets or private machine data.

Please include the affected version or source revision, environment details
that are safe to share, reproduction steps, and the smallest useful proof.
Request coordination before publishing details that would enable exploitation.

## Security boundaries

This is a user-level Fedora/KDE utility. It does not implement authentication;
KDE/kscreenlocker is the authoritative security boundary. The optional
`exit_guard` protects selected Matrix-window inputs but is not authentication,
authorization, or a secure lock.

The project has no runtime telemetry, analytics, updater, network service,
cloud dependency, hidden remote-execution mechanism, or password handling. It
does not use `/dev/input` scraping, privileged input grabs, or an intended
privileged daemon/service.

See [SECURITY-MODEL.md](SECURITY-MODEL.md) for the detailed threat boundary,
process lifecycle, state handling, and known limitations.
