"""Tests de l'inspection structurée des petites fixtures DOCX synthétiques."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest

from mini_metopes.docx import DocxInspectionError, RunContentInfo, inspect_docx_file


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
    assert "Texte litteral [footnote:7]" in paragraph.text
    assert "avant tabulation\tapres tabulation\napres saut" in paragraph.text
    assert "[footnote:7]" in paragraph.text
    assert "[endnote:9]" in paragraph.text
    assert paragraph.manual_breaks == 1
    assert paragraph.footnote_reference_ids == ("7",)
    assert paragraph.endnote_reference_ids == ("9",)
    assert paragraph.hyperlink_count == 2
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
    structured_run = next(run for run in paragraph.runs if run.footnote_reference_ids == ("7",))
    assert structured_run.tabs == 1
    assert structured_run.break_types == ("line",)


def test_runs_expose_an_ordered_inline_content_stream(basic_inspection) -> None:
    paragraph = basic_inspection.paragraphs[1]
    run = next(run for run in paragraph.runs if run.footnote_reference_ids == ("7",))

    assert run.contents == (
        RunContentInfo(kind="text", text="avant tabulation"),
        RunContentInfo(kind="tab"),
        RunContentInfo(kind="text", text="apres tabulation"),
        RunContentInfo(kind="break", break_type="line"),
        RunContentInfo(kind="text", text="apres saut"),
        RunContentInfo(kind="footnote_reference", reference_id="7"),
        RunContentInfo(kind="drawing", relationship_ids=("rIdImage",)),
    )
    assert run.text == "avant tabulation\tapres tabulation\napres saut[footnote:7][drawing]"
    assert run.manual_breaks == 1
    assert run.tabs == 1
    assert run.drawing_count == 1


def test_break_types_keep_line_page_and_column_distinct(basic_inspection) -> None:
    paragraph = basic_inspection.paragraphs[1]
    page_and_column_run = next(run for run in paragraph.runs if run.break_types == ("page", "column"))

    assert page_and_column_run.text == "avant pageapres pageapres colonne"
    assert page_and_column_run.manual_breaks == 0
    assert tuple(
        content.break_type for content in page_and_column_run.contents if content.kind == "break"
    ) == ("page", "column")


def test_literal_note_marker_and_note_reference_are_unambiguous(basic_inspection) -> None:
    paragraph = basic_inspection.paragraphs[1]
    literal_run = next(run for run in paragraph.runs if run.text == "Texte litteral [footnote:7]")
    reference_run = next(run for run in paragraph.runs if run.footnote_reference_ids == ("7",))

    assert literal_run.contents == (
        RunContentInfo(kind="text", text="Texte litteral [footnote:7]"),
    )
    assert any(content.kind == "footnote_reference" for content in reference_run.contents)


def test_runs_keep_external_and_internal_hyperlink_context(basic_inspection) -> None:
    paragraph = basic_inspection.paragraphs[1]
    external_run = next(run for run in paragraph.runs if run.text == "lien")
    internal_run = next(run for run in paragraph.runs if run.text == "lien interne")
    ordinary_run = basic_inspection.paragraphs[0].runs[0]

    assert external_run.hyperlink_relationship_id == "rIdHyper"
    assert external_run.hyperlink_anchor is None
    assert internal_run.hyperlink_relationship_id is None
    assert internal_run.hyperlink_anchor == "repere_synthetique"
    assert ordinary_run.hyperlink_relationship_id is None
    assert ordinary_run.hyperlink_anchor is None


def test_notes_and_document_relationships_are_recovered(basic_inspection) -> None:
    assert [(note.note_id, note.text) for note in basic_inspection.footnotes] == [
        ("7", "Note de bas de page italique\navec saut.\nSecond paragraphe de note."),
        ("3", "Note dans le vers synthétique."),
    ]
    assert [(note.note_id, note.text) for note in basic_inspection.endnotes] == [
        ("9", "Note de fin synthétique."),
    ]
    relationships = {relation.relationship_id: relation for relation in basic_inspection.relationships}
    assert relationships["rIdHyper"].target == "https://example.test/notice"
    assert relationships["rIdHyper"].target_mode == "External"
    assert relationships["rIdImage"].target == "media/image1.png"
    assert basic_inspection.footnote_relationships == ()
    assert basic_inspection.endnote_relationships == ()


def test_relationships_are_scoped_by_ooxml_part() -> None:
    inspection = inspect_docx_file(FIXTURES / "native-editorial.docx")

    assert [(relation.relationship_id, relation.target) for relation in inspection.relationships] == [
        ("rIdHyper", "https://example.test/body"),
        ("rIdImage", "media/image1.png"),
    ]
    assert [(relation.relationship_id, relation.target) for relation in inspection.footnote_relationships] == [
        ("rIdHyper", "https://example.test/footnote"),
    ]
    assert [(relation.relationship_id, relation.target) for relation in inspection.endnote_relationships] == [
        ("rIdHyper", "https://example.test/endnote"),
    ]


def test_notes_keep_structured_paragraphs_and_runs(basic_inspection) -> None:
    note = basic_inspection.footnotes[0]

    assert note.note_id == "7"
    assert [paragraph.index for paragraph in note.paragraphs] == [0, 1]
    assert [paragraph.text for paragraph in note.paragraphs] == [
        "Note de bas de page italique\navec saut.",
        "Second paragraphe de note.",
    ]
    assert len(note.paragraphs[0].runs) == 2
    assert note.paragraphs[0].runs[1].italic is True
    assert note.paragraphs[0].runs[1].manual_breaks == 1


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


def test_textbox_paragraph_is_not_folded_into_main_sequence() -> None:
    inspection = inspect_docx_file(FIXTURES / "textbox-inspection.docx")
    assert len(inspection.paragraphs) == 1
    paragraph = inspection.paragraphs[0]
    assert paragraph.text == "Texte exterieur[drawing]"
    assert "Texte de la zone" not in paragraph.text
    assert all("Texte de la zone" not in run.text for run in paragraph.runs)
    assert paragraph.drawing_count == 1
    assert any(issue.code == "textboxes_not_inspected" for issue in inspection.issues)


def test_tables_and_textboxes_in_notes_are_reported(tmp_path: Path) -> None:
    path = tmp_path / "notes-with-unsupported-structures.docx"
    files = {
        "word/document.xml": """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Corps</w:t></w:r></w:p></w:body></w:document>""",
        "word/footnotes.xml": """<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:footnote w:id="1"><w:p><w:r><w:t>Note</w:t></w:r></w:p><w:tbl/></w:footnote></w:footnotes>""",
        "word/endnotes.xml": """<w:endnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:endnote w:id="2"><w:p><w:r><w:drawing><w:txbxContent><w:p><w:r><w:t>Zone</w:t></w:r></w:p></w:txbxContent></w:drawing></w:r></w:p></w:endnote></w:endnotes>""",
    }
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in files.items():
            info = ZipInfo(name, date_time=(2024, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, content)

    inspection = inspect_docx_file(path)

    assert any(
        issue.code == "table_not_modeled" and issue.part == "word/footnotes.xml"
        for issue in inspection.issues
    )
    assert any(
        issue.code == "textboxes_not_inspected" and issue.part == "word/endnotes.xml"
        for issue in inspection.issues
    )


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


def test_zip_runtime_error_while_reading_part_is_typed(monkeypatch: pytest.MonkeyPatch) -> None:
    original_read = ZipFile.read

    def raising_read(self: ZipFile, name: str, pwd: bytes | None = None) -> bytes:
        if name == "word/document.xml":
            raise RuntimeError("synthetic encrypted entry")
        return original_read(self, name, pwd)

    monkeypatch.setattr(ZipFile, "read", raising_read)

    with pytest.raises(DocxInspectionError) as raised:
        inspect_docx_file(FIXTURES / "basic-inspection.docx")

    assert raised.value.code == "unreadable_part"
    assert isinstance(raised.value.__cause__, RuntimeError)
