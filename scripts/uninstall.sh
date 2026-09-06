#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
set -Eeuo pipefail
umask 077

USER_HOME="${HOME:?HOME is required}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$USER_HOME/.config}"
DATA_HOME="${XDG_DATA_HOME:-$USER_HOME/.local/share}"
BIN_TARGET="$USER_HOME/.local/bin"
KONSOLE_TARGET="$DATA_HOME/konsole"
PROJECT_DATA_TARGET="$DATA_HOME/konsole-matrix-digital-rain"
CONFIG_TARGET="$CONFIG_HOME/konsole-matrix-digital-rain"
SYSTEMD_TARGET="$CONFIG_HOME/systemd/user"
MANIFEST="$PROJECT_DATA_TARGET/install-manifest.tsv"
DRY_RUN=0
PURGE=0
CONFIRMED=0

usage() {
    printf '%s\n' \
        "Usage: scripts/uninstall.sh [--dry-run] [--purge-user-data --yes]" \
        "Removes only files recorded by the Matrix installation manifest." \
        "User config and presets are preserved unless purge is explicitly confirmed."
}

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --purge-user-data) PURGE=1 ;;
        --yes) CONFIRMED=1 ;;
        -h|--help) usage; exit 0 ;;
        *) printf 'ERROR: unknown option: %s\n' "$arg" >&2; exit 2 ;;
    esac
done

if (( PURGE && !CONFIRMED )); then
    printf '%s\n' '--purge-user-data requires --yes' >&2
    exit 2
fi
if [[ ! -f "$MANIFEST" ]]; then
    printf 'No Matrix install manifest found: %s\n' "$MANIFEST" >&2
    exit 1
fi

path_is_allowed() {
    case "$1" in
        "$BIN_TARGET"/*|"$KONSOLE_TARGET"/*|"$SYSTEMD_TARGET"/*) return 0 ;;
        *) return 1 ;;
    esac
}

removed=0
preserved=0
while IFS=$'\t' read -r path expected || [[ -n "$path" ]]; do
    [[ -n "$path" && -n "$expected" ]] || continue
    if ! path_is_allowed "$path"; then
        printf 'WARN: preserving manifest path outside managed targets: %s\n' "$path" >&2
        preserved=$((preserved + 1))
        continue
    fi
    if [[ ! -e "$path" ]]; then
        printf 'absent: %s\n' "$path"
        continue
    fi
    if [[ -L "$path" ]]; then
        printf 'preserved symlink: %s\n' "$path"
        preserved=$((preserved + 1))
        continue
    fi
    actual="$(sha256sum -- "$path" | awk '{print $1}')"
    if [[ "$actual" != "$expected" ]]; then
        printf 'preserved modified file: %s\n' "$path"
        preserved=$((preserved + 1))
        continue
    fi
    if (( DRY_RUN )); then
        printf 'would remove: %s\n' "$path"
    else
        rm -f -- "$path"
        printf 'removed: %s\n' "$path"
    fi
    removed=$((removed + 1))
done < "$MANIFEST"

if (( ! DRY_RUN )); then
    rm -f -- "$MANIFEST"
    rmdir -- "$PROJECT_DATA_TARGET" 2>/dev/null || true
    for directory in "$BIN_TARGET" "$KONSOLE_TARGET" "$SYSTEMD_TARGET"; do
        rmdir -- "$directory" 2>/dev/null || true
    done
    if command -v systemctl >/dev/null 2>&1; then
        systemctl --user daemon-reload >/dev/null 2>&1 || true
    fi
    if (( PURGE )); then
        case "$CONFIG_TARGET" in "$USER_HOME"/*) ;; *) printf '%s\n' 'ERROR: unsafe config purge target' >&2; exit 1 ;; esac
        case "$PROJECT_DATA_TARGET" in "$USER_HOME"/*) ;; *) printf '%s\n' 'ERROR: unsafe data purge target' >&2; exit 1 ;; esac
        rm -rf -- "$CONFIG_TARGET" "$PROJECT_DATA_TARGET"
        printf 'purged user Matrix config/presets/data: %s and %s\n' "$CONFIG_TARGET" "$PROJECT_DATA_TARGET"
    fi
fi

printf 'Matrix uninstall complete: removed=%s preserved=%s\n' "$removed" "$preserved"
