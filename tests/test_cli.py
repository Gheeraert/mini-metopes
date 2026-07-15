"""Tests de la CLI de validation."""

from __future__ import annotations

import os
import locale
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "xml"


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    source_root = str(ROOT / "src")
    environment["PYTHONPATH"] = source_root + os.pathsep + environment.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "mini_metopes", *arguments],
        capture_output=True,
        check=False,
        encoding=locale.getencoding(),
        text=True,
        env=environment,
    )


@pytest.mark.parametrize(
    ("arguments", "returncode", "expected"),
    [
        (("validate", str(FIXTURES / "valid" / "minimal.xml")), 0, "VALIDE"),
        (("validate", str(FIXTURES / "invalid" / "poetic-citation-with-empty-lg.xml")), 1, "INVALIDE"),
        (("validate", str(FIXTURES / "invalid" / "malformed.xml")), 1, "INVALIDE"),
        (("validate", str(FIXTURES / "missing.xml")), 2, "ERREUR"),
        (("--help",), 0, "usage:"),
        (("validate", "--help"), 0, "usage:"),
    ],
)
def test_cli(arguments: tuple[str, ...], returncode: int, expected: str) -> None:
    completed = run_cli(*arguments)
    assert completed.returncode == returncode
    assert expected in completed.stdout
