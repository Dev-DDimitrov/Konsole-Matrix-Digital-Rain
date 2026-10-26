#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
"""Portable installer and uninstaller checks using an isolated temporary home."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = SOURCE_ROOT / "scripts/install.sh"
UNINSTALLER = SOURCE_ROOT / "scripts/uninstall.sh"


def installer_runtime_files() -> set[str]:
    """Parse the RUNTIME_FILES=() array out of scripts/install.sh."""
    text = INSTALLER.read_text(encoding="utf-8")
    match = re.search(r"RUNTIME_FILES=\((.*?)\)", text, re.DOTALL)
    assert match, "RUNTIME_FILES array not found in install.sh"
    return set(match.group(1).split())


def installer_wallpaper_files() -> set[str]:
    text = INSTALLER.read_text(encoding="utf-8")
    match = re.search(r"WALLPAPER_FILES=\((.*?)\)", text, re.DOTALL)
    assert match, "WALLPAPER_FILES array not found in install.sh"
    return set(match.group(1).split())


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


class DependencyAuditTests(unittest.TestCase):
    """Source-level guard against the missing-runtime-module class of bug:
    every local matrix_* module imported by any shipped file must itself be
    in the installer's RUNTIME_FILES list, and every wallpaper source file
    must be in WALLPAPER_FILES."""

    def test_every_imported_python_module_is_installed(self):
        runtime = installer_runtime_files()
        import_re = re.compile(r"^\s*(?:import|from)\s+(matrix_[a-z_0-9]+)", re.MULTILINE)
        for name in sorted(runtime):
            source = SOURCE_ROOT / "bin" / name
            self.assertTrue(source.is_file(), f"RUNTIME_FILES names missing file: {name}")
            for module in import_re.findall(source.read_text(encoding="utf-8")):
                self.assertIn(
                    f"{module}.py", runtime,
                    f"{name} imports {module} but {module}.py is not in "
                    f"install.sh RUNTIME_FILES — installed runtime would break",
                )

    def test_every_wallpaper_runtime_file_is_installed(self):
        wallpaper = installer_wallpaper_files()
        plugin = SOURCE_ROOT / "plasma/wallpapers/io.github.devddimitrov.matrixrain"
        expected = {"metadata.json"}
        for sub in ("contents/ui", "contents/config"):
            for path in (plugin / sub).iterdir():
                expected.add(f"{sub}/{path.name}")
        expected.add("contents/shaders/rain.frag.qsb")  # baked artifact ships
        expected.discard("contents/shaders/rain.frag")  # GLSL source does not
        for name in sorted(expected):
            self.assertIn(name, wallpaper,
                          f"wallpaper file {name} missing from WALLPAPER_FILES")
        for name in sorted(wallpaper):
            self.assertTrue((plugin / name).is_file(),
                            f"WALLPAPER_FILES names missing file: {name}")


class InstalledCliRegressionTests(unittest.TestCase):
    """Install into an isolated home and exercise the INSTALLED CLI, so a
    module missing from the installed runtime fails here, not on the user."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="matrix-installed-cli-")
        root = Path(cls._tmp.name)
        cls.config_home = root / "config"
        cls.data_home = root / "data"
        runtime_home = root / "runtime"
        runtime_home.mkdir(mode=0o700)
        cls.env = {
            **{k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
            "HOME": str(root),
            "XDG_CONFIG_HOME": str(cls.config_home),
            "XDG_DATA_HOME": str(cls.data_home),
            "XDG_RUNTIME_DIR": str(runtime_home),
            "PATH": f"{root}/.local/bin:{os.environ['PATH']}",
        }
        # Pre-existing user state the installer must preserve.
        lock_dir = cls.config_home / "konsole-matrix-digital-rain"
        lock_dir.mkdir(parents=True)
        (lock_dir / "config.toml").write_text("speed = 77\n", encoding="utf-8")
        (lock_dir / "lockscreen.toml").write_text(
            "[lockscreen]\ncolor = \"#8b5cf6\"\n", encoding="utf-8")
        history = lock_dir / "lockscreen-history"
        history.mkdir()
        (history / "20260101-000000.toml").write_text("[lockscreen]\n", encoding="utf-8")
        backup_dir = cls.data_home / "konsole-matrix-digital-rain"
        backup_dir.mkdir(parents=True)
        (backup_dir / "lockscreen-wallpaper-backup.json").write_text("{}", encoding="utf-8")
        subprocess.run([str(INSTALLER)], cwd=SOURCE_ROOT, env=cls.env, check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        cls.root = root

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def cli(self, *args, expect_ok=True):
        result = subprocess.run(
            list(args), cwd=str(self.root), env=self.env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
        if expect_ok:
            self.assertEqual(
                result.returncode, 0,
                f"{' '.join(args)} failed:\n{result.stdout}")
        return result.stdout

    def test_installed_modules_cover_dependencies(self):
        bin_dir = self.root / ".local/bin"
        for name in installer_runtime_files():
            self.assertTrue((bin_dir / name).is_file(), f"not installed: {name}")
        # Import every installed python module against the installed dir only.
        for module in sorted(p.stem for p in bin_dir.glob("matrix_*.py")):
            if module == "matrix_renderer":
                continue  # parses CLI args at import; covered via unimatrix-fade below
            out = subprocess.run(
                ["python3", "-c", f"import sys; sys.path.insert(0, '{bin_dir}'); "
                                  f"import {module}"],
                cwd=str(self.root), env=self.env, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(out.returncode, 0,
                             f"installed module {module} failed to import:\n{out.stdout}")

    def test_matrix_lock_cli_works_from_install(self):
        self.cli("matrix-lock", "--help")
        self.cli("matrix-lock", "configure", "--help")
        out = self.cli("matrix-lock", "show")
        self.assertIn("resource_guard", out)
        self.assertIn("#8b5cf6", out)              # pre-existing profile kept
        self.cli("matrix-lock", "quality")
        out = self.cli("matrix-lock", "set", "color-cycle", "on")
        self.assertIn("saved lock-screen profile", out)
        out = self.cli("matrix-lock", "show")
        self.assertIn("color_cycle = True", out)
        self.cli("matrix-lock", "set", "color-cycle", "off")

    def test_other_entry_points_start_from_install(self):
        self.cli("matrix-settings", "--help")
        self.cli("matrix-preset", "--help")
        self.cli("unimatrix-fade", "--help")
        out = self.cli("matrix-guide", "--lock")
        self.assertIn("resource", out.lower())

    def test_install_preserved_existing_user_state(self):
        lock_dir = self.config_home / "konsole-matrix-digital-rain"
        self.assertEqual((lock_dir / "config.toml").read_text(encoding="utf-8"),
                         "speed = 77\n")
        self.assertTrue((lock_dir / "lockscreen-history/20260101-000000.toml").is_file())
        backup = self.data_home / "konsole-matrix-digital-rain/lockscreen-wallpaper-backup.json"
        self.assertEqual(backup.read_text(encoding="utf-8"), "{}")


if __name__ == "__main__":
    unittest.main()
