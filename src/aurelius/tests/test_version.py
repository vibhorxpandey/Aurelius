"""Guard against `__version__` drifting behind pyproject.toml.

This has bitten the project twice (0.2.0 fixed it once; it drifted again from
0.3.0 to 0.6.0). Keep it dependency-free and 3.10-safe: parse the version with a
regex rather than tomllib (stdlib only from 3.11).
"""
from __future__ import annotations

import re
from pathlib import Path

import aurelius


def _pyproject_version() -> str:
    root = Path(__file__).resolve().parents[3]
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    assert match, "no version field found in pyproject.toml"
    return match.group(1)


def test_version_matches_pyproject():
    assert aurelius.__version__ == _pyproject_version()
