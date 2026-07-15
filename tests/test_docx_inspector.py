"""Tests de l'inspection structurée des petites fixtures DOCX synthétiques."""

from __future__ import annotations

from pathlib import Path

import pytest

from mini_metopes.docx import DocxInspectionError, inspect_docx_file


FIXTURES = Path(__file__).parent / "fixtures" / "docx"


@pytest.fixture()
def basic_inspection():
    """Retourner l'inspection de la fixture générale."""
    return inspect_docx_file(FIXTURES / "basic-inspection.docx")


def test_package_inventory_and_optional_parts(basic_inspection) -> None:
    assert "word/document.xml" in basic_inspection.parts
    assert "word/styles.xml" in basic_inspection.parts
    assert "word/media/image1.png" in basic_inspection.parts
    assert basic_inspection.issues == ()
    assert basic_inspection.media[0].path == "word/media/image1.png"
    assert basic_inspection.media[0].content_type == "image/png"
    assert basic_inspection.media[0].uncompressed_size > 0


def test_styles_keep_identifier_and_display_name_separate(basic_inspection) -> None:
    styles = {style.style_id: style for style in basic_inspection.styles}
    heading = styles["Heading1"]
    assert heading.name == "Titre 1"
    assert heading.style_type == "paragraph"
    assert heading.based_on == "Normal"
    assert heading.linked_style == "Heading1Char"
    assert heading.is_custom is True
    assert heading.quick_format is True
    assert heading.ui_priority == 9
    assert heading.outline_level == 0
    assert styles["Normal"].is_default is True


def test_paragraphs_and_runs_preserve_inline_observations(basic_inspection) -> None:
    assert [paragraph.index for paragraph in basic_inspection.paragraphs] == [0, 1, 2]
    title, paragraph, numbered = basic_inspection.paragraphs
    assert title.style_id == "Heading1"
    assert title.style_name == "Titre 1"
    assert title.outline_level == 0
    assert paragraph.style_id == "Normal"
    assert paragraph.text.startswith("Texte gras non gras italique")
    assert "\taprès tabulation\naprès saut" in paragraph.text
    assert "[footnote:7]" in paragraph.text
    assert "[endnote:9]" in paragraph.text
    assert paragraph.manual_breaks == 1
    assert paragraph.footnote_reference_ids == ("7",)
    assert paragraph.endnote_reference_ids == ("9",)
    assert paragraph.hyperlink_count == 1
    assert paragraph.hyperlink_relationship_ids == ("rIdHyper",)
    assert paragraph.bookmark_start_ids == ("12",)
    assert paragraph.drawing_count == 1
    assert paragraph.drawing_relationship_ids == ("rIdImage",)
    assert numbered.numbering_id == "42"
    assert numbered.numbering_level == 1

    runs = {run.text: run for run in paragraph.runs}
    assert runs["gras"].bold is True
    assert runs[" non gras"].bold is False
    assert runs[" italique"].italic is True
    assert runs[" petites capitales"].small_caps is True
    assert runs["2"].superscript is True
    assert runs["i"].subscript is True
    assert runs["lien"].style_id == "EmphasisChar"
    assert runs["\taprès tabulation\naprès saut"].tabs == 1
    assert runs["\taprès tabulation\naprès saut"].break_types == ("line",)


def test_notes_and_document_relationships_are_recovered(basic_inspection) -> None:
    assert [(note.note_id, note.text) for note in basic_inspection.footnotes] == [
        ("7", "Note de bas de page synthétique."),
        ("3", "Note dans le vers synthétique."),
    ]
    assert [(note.note_id, note.text) for note in basic_inspection.endnotes] == [
        ("9", "Note de fin synthétique."),
    ]
    relationships = {relation.relationship_id: relation for relation in basic_inspection.relationships}
    assert relationships["rIdHyper"].target == "https://example.test/notice"
    assert relationships["rIdHyper"].target_mode == "External"
    assert relationships["rIdImage"].target == "media/image1.png"


def test_poetry_keeps_paragraphs_distinct_from_manual_breaks() -> None:
    inspection = inspect_docx_file(FIXTURES / "poetry-inspection.docx")
    assert len(inspection.paragraphs) == 2
    first, second = inspection.paragraphs
    assert first.style_id == "TEIverse"
    assert first.manual_breaks == 2
    assert second.manual_breaks == 1
    assert first.footnote_reference_ids == ("3",)
    assert "[footnote:3]" in first.text
    assert any(run.italic is True and "italique" in run.text for run in first.runs)


@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("not-a-zip.docx", "not_zip"),
        ("without-document.docx", "missing_document_part"),
        ("malformed-document.docx", "malformed_xml_part"),
    ],
)
def test_invalid_packages_raise_a_typed_error(name: str, code: str) -> None:
    with pytest.raises(DocxInspectionError) as raised:
        inspect_docx_file(FIXTURES / name)
    assert raised.value.code == code


def test_missing_file_raises_a_typed_error() -> None:
    with pytest.raises(DocxInspectionError) as raised:
        inspect_docx_file(FIXTURES / "missing.docx")
    assert raised.value.code == "missing_file"


def test_optional_parts_can_be_absent() -> None:
    inspection = inspect_docx_file(FIXTURES / "optional-parts-absent.docx")
    assert [paragraph.text for paragraph in inspection.paragraphs] == ["Minimal"]
    assert inspection.styles == ()
    assert inspection.footnotes == ()
    assert inspection.media == ()


def test_xml_part_size_limit_is_enforced() -> None:
    with pytest.raises(DocxInspectionError) as raised:
        inspect_docx_file(FIXTURES / "basic-inspection.docx", max_xml_part_bytes=32)
    assert raised.value.code == "xml_part_too_large"
