#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
set -Eeuo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
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

RUNTIME_FILES=(
    matrix matrix-all matrix-doctor matrix-full matrix-guide matrix-konsole
    matrix-preset matrix-preview matrix-saver matrix-settings
    unimatrix-fade unimatrix-fade-sync
    matrix_config.py matrix_cursor.py matrix_doctor.py matrix_guide.py
    matrix_guide_data.py matrix_preset.py matrix_renderer.py matrix_saver.py
    matrix_settings.py
)
KONSOLE_FILES=(Matrix.profile Matrix.colorscheme Matrix-Translucent.profile Matrix-Translucent.colorscheme)
UNIT_FILE="matrix-saver.service"

usage() {
    printf '%s\n' \
        "Usage: scripts/install.sh [--dry-run]" \
        "Install the frozen Matrix utility for the current user." \
        "Existing user config and presets are preserved. The saver service is never enabled automatically."
}

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        -h|--help) usage; exit 0 ;;
        *) printf 'ERROR: unknown option: %s\n' "$arg" >&2; exit 2 ;;
    esac
done

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
note() { printf '%s\n' "$*"; }

command -v python3 >/dev/null 2>&1 || die "python3 is required"
for optional in konsole kscreen-doctor gdbus loginctl systemctl; do
    if ! command -v "$optional" >/dev/null 2>&1; then
        note "WARN: optional runtime command not found: $optional"
    fi
done

[[ -d "$PROJECT_ROOT/bin" && -d "$PROJECT_ROOT/konsole" && -d "$PROJECT_ROOT/systemd" ]] || die "source tree is incomplete: $PROJECT_ROOT"
for name in "${RUNTIME_FILES[@]}"; do
    [[ -f "$PROJECT_ROOT/bin/$name" && ! -L "$PROJECT_ROOT/bin/$name" ]] || die "missing or symlinked source file: bin/$name"
done
for name in "${KONSOLE_FILES[@]}"; do
    [[ -f "$PROJECT_ROOT/konsole/$name" && ! -L "$PROJECT_ROOT/konsole/$name" ]] || die "missing or symlinked source file: konsole/$name"
done
[[ -f "$PROJECT_ROOT/config/config.toml.example" ]] || die "missing config/config.toml.example"
[[ -f "$PROJECT_ROOT/systemd/$UNIT_FILE" ]] || die "missing systemd/$UNIT_FILE"

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$PROJECT_DATA_TARGET/install-backups/$STAMP"
INSTALLED_PATHS=()

target_is_safe() {
    local path="$1"
    case "$path" in
        "$BIN_TARGET"/*|"$KONSOLE_TARGET"/*|"$SYSTEMD_TARGET"/*) return 0 ;;
        *) return 1 ;;
    esac
}

backup_and_install() {
    local source="$1" target="$2" mode="$3"
    target_is_safe "$target" || die "refusing unsafe target: $target"
    [[ ! -L "$target" ]] || die "refusing to replace symlink: $target"
    if [[ -e "$target" && ! -f "$target" && ! -L "$target" ]]; then
        die "target is not a regular file: $target"
    fi
    if [[ -f "$target" ]] && cmp -s "$source" "$target"; then
        note "unchanged: $target"
    elif (( DRY_RUN )); then
        note "would install: $target"
    else
        mkdir -p -- "$(dirname -- "$target")"
        if [[ -f "$target" ]]; then
            mkdir -p -- "$BACKUP_DIR"
            cp -p -- "$target" "$BACKUP_DIR/$(basename -- "$target")"
            note "backup: $BACKUP_DIR/$(basename -- "$target")"
        fi
        install -m "$mode" -- "$source" "$target"
        note "installed: $target"
    fi
    INSTALLED_PATHS+=("$target")
}

for name in "${RUNTIME_FILES[@]}"; do
    backup_and_install "$PROJECT_ROOT/bin/$name" "$BIN_TARGET/$name" 755
done
for name in "${KONSOLE_FILES[@]}"; do
    backup_and_install "$PROJECT_ROOT/konsole/$name" "$KONSOLE_TARGET/$name" 644
done
backup_and_install "$PROJECT_ROOT/systemd/$UNIT_FILE" "$SYSTEMD_TARGET/$UNIT_FILE" 644

if [[ -e "$CONFIG_TARGET/config.toml" ]]; then
    [[ -f "$CONFIG_TARGET/config.toml" && ! -L "$CONFIG_TARGET/config.toml" ]] || die "user config is not a regular file"
    note "preserved existing user config: $CONFIG_TARGET/config.toml"
elif (( DRY_RUN )); then
    note "would create first-install user config: $CONFIG_TARGET/config.toml"
else
    mkdir -p -- "$CONFIG_TARGET"
    install -m 600 -- "$PROJECT_ROOT/config/config.toml.example" "$CONFIG_TARGET/config.toml"
    note "created first-install user config: $CONFIG_TARGET/config.toml"
fi

if (( ! DRY_RUN )); then
    mkdir -p -- "$PROJECT_DATA_TARGET"
    temporary="$MANIFEST.tmp.$$"
    : > "$temporary"
    chmod 600 "$temporary"
    for path in "${INSTALLED_PATHS[@]}"; do
        printf '%s\t%s\n' "$path" "$(sha256sum -- "$path" | awk '{print $1}')" >> "$temporary"
    done
    mv -f -- "$temporary" "$MANIFEST"
    chmod 600 "$MANIFEST"
    if command -v systemctl >/dev/null 2>&1; then
        systemctl --user daemon-reload >/dev/null 2>&1 || note "WARN: user systemd daemon-reload unavailable"
    fi
else
    note "dry-run: no files or manifest written"
fi

note "Matrix installation complete. matrix-saver.service was not enabled."
