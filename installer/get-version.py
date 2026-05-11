"""Print the project version from pyproject.toml.

Used by installer/build.bat to inject the version into setup.iss and the
PyInstaller specs without hardcoding it.

Usage:
    python installer/get-version.py
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"

if not PYPROJECT.is_file():
    sys.exit(f"pyproject.toml not found at {PYPROJECT}")

with open(PYPROJECT, "rb") as fh:
    data = tomllib.load(fh)

try:
    print(data["project"]["version"])
except KeyError:
    sys.exit("pyproject.toml is missing [project].version")
