#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
# Regenerate the baked Qt shader (.qsb) for the lock-screen wallpaper plugin.
# The .qsb artifact is committed so users and installs never need qsb.
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SHADER_DIR="$SCRIPT_DIR/../plasma/wallpapers/io.github.devddimitrov.matrixrain/contents/shaders"

QSB=""
for candidate in qsb /usr/lib64/qt6/bin/qsb /usr/lib/qt6/bin/qsb; do
    if command -v "$candidate" >/dev/null 2>&1; then
        QSB="$candidate"
        break
    fi
done
[[ -n "$QSB" ]] || { echo "ERROR: qsb not found (install qt6-qtshadertools)" >&2; exit 1; }

"$QSB" --qt6 -o "$SHADER_DIR/rain.frag.qsb" "$SHADER_DIR/rain.frag"
echo "built: $SHADER_DIR/rain.frag.qsb"
