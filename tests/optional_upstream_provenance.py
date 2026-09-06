#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Part of Konsole Matrix Digital Rain.
"""Optional local check for the retained external UniMatrix executable."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path


EXPECTED_SHA256 = "0bd73f1fc3625aa50402df84c3efd76f5c6929630e00fc6a90c163b645812546"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Optionally verify an external retained UniMatrix file."
    )
    parser.add_argument(
        "--path",
        default=os.environ.get("MATRIX_ORIGINAL_UNIMATRIX"),
        help="external UniMatrix path; omitted means skip cleanly",
    )
    args = parser.parse_args()
    if not args.path:
        print("SKIP: no external UniMatrix path supplied")
        return 0

    path = Path(args.path).expanduser()
    if not path.is_file():
        print(f"SKIP: external UniMatrix file not found: {path}")
        return 0

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        print(f"FAIL: unexpected UniMatrix SHA-256 for {path}: {digest}")
        return 1
    print(f"PASS: retained external UniMatrix matches expected SHA-256: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
