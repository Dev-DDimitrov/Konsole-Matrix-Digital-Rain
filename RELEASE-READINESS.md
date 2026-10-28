# Release readiness — v0.10.0 candidate

This document records the verified state of the `feature/lockscreen-rain`
release candidate so the remaining gates are explicit. It is updated as gates
close; it never claims verification that has not actually happened.

Candidate version: **v0.10.0** (additive, backward compatible with v0.9.0).
Audit baseline commit: `63e002d` on `feature/lockscreen-rain`.

## Release audit (2026-10-26): CONDITIONAL PASS

A full evidence-based audit of the release candidate covered code and
architecture, lock-screen security boundaries, performance, configuration and
data integrity, installation/upgrade/uninstall from the public v0.9.0 release,
the CLI surface, documentation accuracy, privacy and licensing, and git state.

Verified evidence, summarized:

- **Security.** No KScreenLocker/PAM/SDDM/authentication modification
  anywhere; the resource monitor executes one fixed, hard-coded read-only
  command with no configuration data ever interpolated; all `kscreenlockerrc`
  writes are validated literals; installers refuse symlinked sources,
  restrict targets to an allowlist, and write atomically with restrictive
  permissions. One hardening fix landed during the audit: `matrix-lock
  disable` validates the wallpaper-plugin id read from the rollback backup
  before writing it to `kscreenlockerrc` (regression-tested).
- **Automated tests.** 144/144 unit tests pass, including installer staging,
  installed-CLI regression tests in an isolated home, dependency audit of
  installer file lists, synthetic resource-guard scenarios, and 489/489
  Python-to-QML cycle-path parity vectors.
- **Installed CLI.** 34/34 smoke checks of the documented command surface on
  a real installation, including an interactive `configure` session in a PTY.
- **Upgrade path.** Public v0.9.0 installed into an isolated home, then
  upgraded to the candidate: user configuration and presets preserved,
  manifest grows 27 to 39 entries, uninstall removes only managed files, the
  lock wallpaper is never auto-enabled, and the sequence is repeatable.
- **Integrity.** Corrupted profile, preset, and backup inputs fail cleanly
  (exit 2, no tracebacks); `cycle reset` provably leaves unrelated settings
  untouched; configuration history undo round-trips.
- **Performance** (measured as % of one CPU core, three displays):
  balanced 31.6-40% at a verified 25.0 steps/s, high 53.5% at 50.0 steps/s,
  battery 7.5%; displays off 0.0% with monitoring silenced; resource-hold
  freeze 0.4%; shared metrics poller 0.03% in isolation.
- **Reproducibility.** The committed `rain.frag.qsb` is byte-identical to a
  fresh rebuild via `scripts/build-shaders.sh`.
- **Privacy/licensing.** No secrets, personal paths, or private data in
  tracked files; GPL-3.0-or-later with UniMatrix/CMatrix attribution intact.

The verdict was CONDITIONAL only because physical acceptance on real hardware
was still outstanding at audit time.

## Physical acceptance (2026-10-27): PASSED

Performed personally by the maintainer on the target Fedora/KDE Plasma 6
Wayland workstation (three displays, one at fractional scale):

1. Real KDE lock and unlock using Meta+L — **passed**.
2. Three-monitor Matrix visual presentation — **passed**.
3. Locked-session display sleep and wake — **passed**.
4. External-monitor hot-plug while locked — **passed**.

These were the audit's only blocking conditions.

## GitHub Actions CI (2026-10-27): PASSED

The branch was pushed and proposed as a pull request against `main`
(2026-10-27, with maintainer authorization). Both the push-triggered and the
pull-request CI runs passed in full on the Fedora container, including the
ShellCheck step — the one check that cannot run locally — alongside shell
syntax validation, Python AST validation, all 144 portable tests, and the
provenance check.

## Remaining release gates

1. **Explicit maintainer authorization** to merge, tag, and publish. Nothing
   is merged, tagged, or published before that authorization.

## Known-good but not manually re-checked

The following passed automated or instrumented verification only; they have
not been individually checked off by hand and are not release blockers:

- Resource-guard pause/resume under a genuine sustained overload on the
  locked workstation (verified with synthetic inputs, a real-metric trigger,
  and frozen-frame screenshot comparison in greeter testing mode).
- Long-duration (multi-hour) locked-session soak.
- Behavior on distributions other than Fedora/KDE Plasma 6 (unsupported).

## Release steps once authorized (instructions, not yet executed)

1. Merge `feature/lockscreen-rain` into `main` with `--no-ff`; no squash, no
   force-push.
2. Push `main` and confirm GitHub Actions CI is green, including ShellCheck.
3. Move the CHANGELOG `[Unreleased]` section to `[0.10.0]` with the release
   date, commit, tag `v0.10.0`, push the tag.
4. Create the GitHub release from the tag using the CHANGELOG section as the
   release notes.
