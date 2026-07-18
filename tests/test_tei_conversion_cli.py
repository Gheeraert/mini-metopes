"""Tests de la commande convert-docx."""

from __future__ import annotations

from pathlib import Path

from mini_metopes.cli import main
from mini_metopes.validation import validate_xml_file
from test_docx_numbering import basic_numbering, paragraph, runtime_docx, write_docx


FIXTURES = Path(__file__).parent / "fixtures" / "docx"
METADATA = Path(__file__).parent / "fixtures" / "metadata" / "native-tei-conversion.metadata.json"
LIST_METADATA = Path(__file__).parent / "fixtures" / "metadata" / "native-lists-tei.metadata.json"


def test_convert_docx_writes_valid_tei(tmp_path: Path, capsys) -> None:
    output = tmp_path / "converted.xml"
    code = main(["convert-docx", str(FIXTURES / "native-tei-conversion.docx"), str(output), "--metadata", str(METADATA)])
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
    assert "missing_metadata" in captured.out
    assert not output.exists()


def test_convert_docx_writes_a_resolved_native_list(tmp_path: Path, capsys) -> None:
    output = tmp_path / "lists.xml"
    code = main([
        "convert-docx", str(FIXTURES / "native-lists-tei.docx"), str(output),
        "--metadata", str(LIST_METADATA),
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "list_root_level_normalized" in captured.out
    assert output.exists()
    assert validate_xml_file(output).valid


def test_convert_docx_refuses_interrupted_list_continuation_and_preserves_output(
    tmp_path: Path,
    capsys,
) -> None:
    source = runtime_docx("cli-interrupted-list.docx")
    write_docx(
        source,
        paragraph("Premier", num_id="42", ilvl="0")
        + paragraph("Interruption")
        + paragraph("Reprise", num_id="42", ilvl="0"),
        numbering=basic_numbering(),
    )
    output = tmp_path / "preserved.xml"
    output.write_text("ancienne sortie", encoding="utf-8")

    code = main(["convert-docx", str(source), str(output), "--metadata", str(LIST_METADATA)])
    captured = capsys.readouterr()

    assert code == 1
    assert "interrupted_list_continuation_not_serializable" in captured.out
    assert output.read_text(encoding="utf-8") == "ancienne sortie"


def test_convert_docx_refuses_explicit_lvlrestart_values_and_preserves_output(
    tmp_path: Path,
    capsys,
) -> None:
    for value in ("0", "1"):
        source = runtime_docx(f"cli-explicit-lvlrestart-{value}.docx")
        write_docx(
            source,
            paragraph("Restart", num_id="42", ilvl="0"),
            numbering=basic_numbering(f'<w:numFmt w:val="decimal"/><w:lvlRestart w:val="{value}"/>'),
        )
        output = tmp_path / f"preserved-{value}.xml"
        output.write_text("ancienne sortie", encoding="utf-8")

        code = main(["convert-docx", str(source), str(output), "--metadata", str(LIST_METADATA)])
        captured = capsys.readouterr()

        assert code == 1
        assert "explicit_list_restart_not_serializable" in captured.out
        assert output.read_text(encoding="utf-8") == "ancienne sortie"


def test_convert_docx_precontrol_failure_prints_diagnostics_and_preserves_output(tmp_path: Path, capsys) -> None:
    output = tmp_path / "preserved.xml"
    output.write_text("ancienne sortie", encoding="utf-8")

    code = main(["convert-docx", str(FIXTURES / "native-editorial.docx"), str(output)])
    captured = capsys.readouterr()

    assert code == 1
    assert "missing_metadata" in captured.out
    assert output.read_text(encoding="utf-8") == "ancienne sortie"
