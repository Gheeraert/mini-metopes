"""Tests de la CLI de validation."""

from __future__ import annotations

import os
import locale
from pathlib import Path
import subprocess
import sys
import json

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "xml"
DOCX_FIXTURES = ROOT / "tests" / "fixtures" / "docx"


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


def run_cli_bytes(*arguments: str) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    source_root = str(ROOT / "src")
    environment["PYTHONPATH"] = source_root + os.pathsep + environment.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "mini_metopes", *arguments],
        capture_output=True,
        check=False,
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


def test_inspect_docx_human_output() -> None:
    completed = run_cli("inspect-docx", str(DOCX_FIXTURES / "basic-inspection.docx"))
    assert completed.returncode == 0
    assert "DOCX" in completed.stdout
    assert "Paragraphes : 3" in completed.stdout
    assert "Styles de paragraphe employés" in completed.stdout
    assert "Médias : 1" in completed.stdout


def test_inspect_docx_json_is_utf8_and_deterministic() -> None:
    first = run_cli_bytes("inspect-docx", str(DOCX_FIXTURES / "basic-inspection.docx"), "--json")
    second = run_cli_bytes("inspect-docx", str(DOCX_FIXTURES / "basic-inspection.docx"), "--json")
    assert first.returncode == 0
    assert first.stdout == second.stdout
    result = json.loads(first.stdout.decode("utf-8"))
    assert result["paragraphs"][1]["footnote_reference_ids"] == ["7"]
    assert result["media"][0]["content_type"] == "image/png"


@pytest.mark.parametrize(
    "path",
    [
        DOCX_FIXTURES / "missing.docx",
        DOCX_FIXTURES / "not-a-zip.docx",
        DOCX_FIXTURES / "without-document.docx",
        DOCX_FIXTURES / "malformed-document.docx",
    ],
)
def test_inspect_docx_errors_use_exit_code_two(path: Path) -> None:
    completed = run_cli("inspect-docx", str(path))
    assert completed.returncode == 2
    assert "ERREUR" in completed.stdout


@pytest.mark.parametrize("arguments", [("inspect-docx", "--help"), ("validate", "--help")])
def test_subcommand_help_is_available(arguments: tuple[str, ...]) -> None:
    completed = run_cli(*arguments)
    assert completed.returncode == 0
    assert "usage:" in completed.stdout
