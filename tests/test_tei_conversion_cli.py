"""Tests de la commande convert-docx."""

from __future__ import annotations

from pathlib import Path

from mini_metopes.cli import main
from mini_metopes.validation import validate_xml_file


FIXTURES = Path(__file__).parent / "fixtures" / "docx"


def test_convert_docx_writes_valid_tei(tmp_path: Path, capsys) -> None:
    output = tmp_path / "converted.xml"
    code = main(["convert-docx", str(FIXTURES / "native-tei-conversion.docx"), str(output)])
    captured = capsys.readouterr()
    assert code == 0
    assert "Validation Commons Publishing" in captured.out
    assert output.exists()
    assert validate_xml_file(output).valid


def test_convert_docx_failure_does_not_write_output(tmp_path: Path, capsys) -> None:
    output = tmp_path / "failed.xml"
    code = main(["convert-docx", str(FIXTURES / "native-quotations.docx"), str(output)])
    captured = capsys.readouterr()
    assert code == 1
    assert "empty_verse" in captured.out
    assert not output.exists()


def test_convert_docx_precontrol_failure_prints_diagnostics_and_preserves_output(tmp_path: Path, capsys) -> None:
    output = tmp_path / "preserved.xml"
    output.write_text("ancienne sortie", encoding="utf-8")

    code = main(["convert-docx", str(FIXTURES / "native-editorial.docx"), str(output)])
    captured = capsys.readouterr()

    assert code == 1
    assert "deferred_paragraph_style" in captured.out
    assert "unsupported_character_style" in captured.out
    assert output.read_text(encoding="utf-8") == "ancienne sortie"
