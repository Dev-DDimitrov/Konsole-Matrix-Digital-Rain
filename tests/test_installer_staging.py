#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
"""Portable installer and uninstaller checks using an isolated temporary home."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = SOURCE_ROOT / "scripts/install.sh"
UNINSTALLER = SOURCE_ROOT / "scripts/uninstall.sh"


class InstallerStagingTests(unittest.TestCase):
    def run_script(self, script: Path, *args: str, env: dict[str, str]) -> str:
        result = subprocess.run(
            [str(script), *args],
            cwd=SOURCE_ROOT,
            env=env,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        return result.stdout

    def test_install_dry_run_and_manifest_uninstall_preserve_modified_files(self):
        with tempfile.TemporaryDirectory(prefix="matrix-staging-") as root:
            root_path = Path(root)
            config_home = root_path / "config"
            data_home = root_path / "data"
            runtime_home = root_path / "runtime"
            runtime_home.mkdir(mode=0o700)
            env = {
                **os.environ,
                "HOME": str(root_path),
                "XDG_CONFIG_HOME": str(config_home),
                "XDG_DATA_HOME": str(data_home),
                "XDG_RUNTIME_DIR": str(runtime_home),
            }

            dry_run = self.run_script(INSTALLER, "--dry-run", env=env)
            self.assertIn("dry-run: no files or manifest written", dry_run)
            self.assertFalse((root_path / ".local/bin/matrix").exists())

            installed = self.run_script(INSTALLER, env=env)
            self.assertIn("Matrix installation complete", installed)
            manifest = data_home / "konsole-matrix-digital-rain/install-manifest.tsv"
            self.assertTrue(manifest.is_file())
            self.assertTrue((root_path / ".local/bin/matrix").is_file())
            self.assertTrue(
                (config_home / "konsole-matrix-digital-rain/config.toml").is_file()
            )

            preview = self.run_script(UNINSTALLER, "--dry-run", env=env)
            self.assertIn("would remove:", preview)
            self.assertTrue((root_path / ".local/bin/matrix").is_file())

            modified = root_path / ".local/bin/matrix"
            modified.write_text(
                modified.read_text(encoding="utf-8") + "\n# local change\n",
                encoding="utf-8",
            )
            removed = self.run_script(UNINSTALLER, env=env)
            self.assertIn("preserved modified file", removed)
            self.assertTrue(modified.is_file())
            self.assertFalse(manifest.exists())
            self.assertTrue(
                (config_home / "konsole-matrix-digital-rain/config.toml").is_file()
            )


if __name__ == "__main__":
    unittest.main()
