"""Tests de la convention Word native et du premier modele editorial."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from mini_metopes.docx import RunContentInfo, inspect_docx_file
from mini_metopes.editorial import (
    ColumnBreak,
    DrawingReference,
    Heading,
    LineBreak,
    NATIVE_WORD_CONVENTION,
    NoteReference,
    PageBreak,
    Paragraph,
    Tab,
    TextSpan,
    build_editorial_document,
    build_editorial_document_from_file,
    editorial_build_result_to_json,
)


FIXTURES = Path(__file__).parent / "fixtures" / "docx"


@pytest.fixture()
def editorial_inspection():
    return inspect_docx_file(FIXTURES / "native-editorial.docx")


@pytest.fixture()
def editorial_result(editorial_inspection):
    return build_editorial_document(editorial_inspection)


def _diagnostic_codes(result) -> list[str]:
    return [diagnostic.code for diagnostic in result.diagnostics]


def _block(result, source_index: int):
    return next(block for block in result.document.blocks if block.source_paragraph_index == source_index)


def _replace_run(inspection, expected_text: str, replacement):
    paragraphs = []
    for paragraph in inspection.paragraphs:
        runs = tuple(replacement if run.text == expected_text else run for run in paragraph.runs)
        paragraphs.append(replace(paragraph, runs=runs))
    return replace(inspection, paragraphs=tuple(paragraphs))


def test_native_headings_are_recognized_by_identifier_not_display_name(editorial_result) -> None:
    first, second = editorial_result.document.blocks[:2]
    assert isinstance(first, Heading)
    assert first.level == 1
    assert first.source_style_id == "Heading1"
    assert first.content == (TextSpan(text="Bonjour"),)
    assert isinstance(second, Heading)
    assert second.level == 2
    assert second.source_style_id == "Heading2"


def test_paragraph_styles_are_conservative_and_deferred(editorial_result) -> None:
    assert isinstance(_block(editorial_result, 2), Paragraph)
    assert isinstance(_block(editorial_result, 3), Paragraph)
    assert _block(editorial_result, 3).source_style_id is None
    assert isinstance(_block(editorial_result, 4), Heading)
    assert _block(editorial_result, 4).source_style_id == "UnknownParagraph"
    assert isinstance(_block(editorial_result, 5), Paragraph)
    assert isinstance(_block(editorial_result, 7), Paragraph)
    assert {diagnostic.style_id for diagnostic in editorial_result.diagnostics if diagnostic.code == "deferred_paragraph_style"} == {
        "Title",
        "Subtitle",
        "Quote",
        "IntenseQuote",
    }


def test_style_classification_priority_handles_outline_fallbacks(editorial_inspection) -> None:
    result = build_editorial_document(editorial_inspection)

    assert isinstance(_block(result, 0), Heading)
    assert _block(result, 0).level == 1
    assert isinstance(_block(result, 2), Paragraph)
    assert isinstance(_block(result, 4), Heading)
    assert _block(result, 4).level == 3
    assert isinstance(_block(result, 5), Paragraph)
    assert isinstance(_block(result, 7), Paragraph)
    assert {
        diagnostic.style_id
        for diagnostic in result.diagnostics
        if diagnostic.code == "deferred_paragraph_style"
    } >= {"Title", "Quote"}

    paragraph = editorial_inspection.paragraphs[3]
    replacement = replace(paragraph, outline_level=2)
    inspection = replace(
        editorial_inspection,
        paragraphs=editorial_inspection.paragraphs[:3] + (replacement,) + editorial_inspection.paragraphs[4:],
    )

    result = build_editorial_document(inspection)
    block = _block(result, 3)
    assert isinstance(block, Heading)
    assert block.level == 3


def test_marks_apply_character_styles_then_direct_properties(editorial_result) -> None:
    paragraph = _block(editorial_result, 2)
    assert isinstance(paragraph, Paragraph)
    spans = {item.text: item for item in paragraph.content if isinstance(item, TextSpan)}
    assert spans["gras"].marks == ("bold",)
    assert spans[" italique"].marks == ("italic",)
    assert spans[" petites"].marks == ("small_caps",)
    assert spans[" capitales"].marks == ("caps",)
    assert spans["2"].marks == ("superscript",)
    assert spans["i"].marks == ("subscript",)
    assert spans[" emphase"].marks == ("italic",)
    assert spans[" pas-fort localA"].marks == ()
    assert "unsupported_character_style" in _diagnostic_codes(editorial_result)


def test_direct_marks_have_a_canonical_order_and_report_vertical_conflicts(editorial_inspection) -> None:
    run = next(run for run in editorial_inspection.paragraphs[2].runs if run.text == "gras")
    replacement = replace(
        run,
        bold=True,
        italic=True,
        small_caps=True,
        caps=True,
        superscript=True,
        subscript=True,
    )
    result = build_editorial_document(_replace_run(editorial_inspection, "gras", replacement))
    paragraph = _block(result, 2)
    assert isinstance(paragraph, Paragraph)
    span = next(item for item in paragraph.content if isinstance(item, TextSpan) and item.text == "gras")
    assert span.marks == ("bold", "italic", "small_caps", "caps", "superscript", "subscript")
    assert "conflicting_vertical_alignment" in _diagnostic_codes(result)


def test_text_spans_merge_only_when_adjacent_marks_and_links_match(editorial_result) -> None:
    heading = _block(editorial_result, 0)
    paragraph = _block(editorial_result, 2)
    assert isinstance(heading, Heading)
    assert heading.content == (TextSpan(text="Bonjour"),)
    assert isinstance(paragraph, Paragraph)
    content = paragraph.content
    tab_index = content.index(Tab())
    assert content[tab_index - 1] == TextSpan(text=" pas-fort localA")
    assert content[tab_index + 1] == TextSpan(text="B")
    assert isinstance(content[tab_index + 2], LineBreak)
    assert isinstance(content[tab_index + 4], PageBreak)
    assert isinstance(content[tab_index + 6], ColumnBreak)


def test_links_notes_breaks_and_drawings_keep_their_order(editorial_result) -> None:
    paragraph = _block(editorial_result, 2)
    assert isinstance(paragraph, Paragraph)
    content = paragraph.content
    external = next(item for item in content if isinstance(item, TextSpan) and item.text == "externe")
    internal = next(item for item in content if isinstance(item, TextSpan) and item.text == "interne")
    assert external.link is not None
    assert external.link.kind == "external"
    assert external.link.target == "https://example.test/body"
    assert external.link.relationship_id == "rIdHyper"
    assert internal.link is not None
    assert internal.link.kind == "internal"
    assert internal.link.anchor == "repere"
    external_index = content.index(external)
    assert content[external_index - 1] == TextSpan(text="E")
    note_index = next(
        index
        for index, item in enumerate(content)
        if isinstance(item, NoteReference) and item.note_kind == "footnote"
    )
    assert content[note_index - 1] == TextSpan(text="avant-note")
    assert content[note_index + 1] == TextSpan(text="apres-note")
    assert content[note_index : note_index + 4] == (
        NoteReference(note_id="10", note_kind="footnote"),
        TextSpan(text="apres-note"),
        NoteReference(note_id="20", note_kind="endnote"),
        DrawingReference(relationship_ids=("rIdImage",)),
    )
    assert "tab_in_editorial_content" in _diagnostic_codes(editorial_result)
    assert "drawing_not_editorially_interpreted" in _diagnostic_codes(editorial_result)


def test_notes_keep_blocks_and_report_unreferenced_notes(editorial_result) -> None:
    notes = {(note.note_kind, note.note_id): note for note in editorial_result.document.notes}
    footnote = notes[("footnote", "10")]
    endnote = notes[("endnote", "20")]
    assert len(footnote.blocks) == 1
    assert isinstance(footnote.blocks[0], Paragraph)
    assert footnote.blocks[0].content[0] == TextSpan(text="Note italique", marks=("italic",))
    assert isinstance(footnote.blocks[0].content[1], LineBreak)
    footnote_link = next(
        item for item in footnote.blocks[0].content if isinstance(item, TextSpan) and item.text == "lien note"
    )
    endnote_link = next(
        item for item in endnote.blocks[0].content if isinstance(item, TextSpan) and item.text == "lien fin"
    )
    assert footnote_link.link is not None
    assert footnote_link.link.target == "https://example.test/footnote"
    assert endnote_link.link is not None
    assert endnote_link.link.target == "https://example.test/endnote"
    assert "unreferenced_note" in _diagnostic_codes(editorial_result)


def test_missing_references_and_duplicate_notes_are_diagnosed(editorial_inspection) -> None:
    external = next(run for run in editorial_inspection.paragraphs[2].runs if run.text == "externe")
    changed_external = replace(external, hyperlink_relationship_id="rIdMissing")
    with_missing_relationship = _replace_run(editorial_inspection, "externe", changed_external)
    changed_run = next(run for run in with_missing_relationship.paragraphs[2].runs if run.text == "Texte ")
    changed_run = replace(
        changed_run,
        contents=changed_run.contents + (RunContentInfo(kind="footnote_reference", reference_id="404"),),
    )
    inspection = _replace_run(with_missing_relationship, "Texte ", changed_run)
    inspection = replace(inspection, footnotes=inspection.footnotes + (inspection.footnotes[0],))

    result = build_editorial_document(inspection)
    codes = _diagnostic_codes(result)
    assert "missing_hyperlink_relationship" in codes
    assert "missing_note_target" in codes
    assert "duplicate_note_id" in codes


def test_note_hyperlinks_use_their_own_relationship_scope(editorial_inspection) -> None:
    result = build_editorial_document(replace(editorial_inspection, footnote_relationships=()))
    footnote = next(
        note for note in result.document.notes if note.note_kind == "footnote" and note.note_id == "10"
    )
    note_link = next(
        item for item in footnote.blocks[0].content if isinstance(item, TextSpan) and item.text == "lien note"
    )

    assert note_link.link is not None
    assert note_link.link.kind == "unresolved"
    assert note_link.link.relationship_id == "rIdHyper"
    assert any(
        diagnostic.code == "missing_hyperlink_relationship" and diagnostic.note_id == "10"
        for diagnostic in result.diagnostics
    )


def test_unknown_break_types_are_not_converted_to_line_breaks(editorial_inspection) -> None:
    run = next(run for run in editorial_inspection.paragraphs[2].runs if run.text == "Texte ")
    replacement = replace(run, contents=run.contents + (RunContentInfo(kind="break", break_type="section"),))
    result = build_editorial_document(_replace_run(editorial_inspection, "Texte ", replacement))
    assert "unsupported_break_type" in _diagnostic_codes(result)


def test_empty_headings_and_level_jumps_are_preserved_and_diagnosed(editorial_result) -> None:
    heading = _block(editorial_result, 9)
    assert isinstance(heading, Heading)
    assert heading.level == 4
    assert heading.content == ()
    assert "empty_heading" in _diagnostic_codes(editorial_result)


def test_building_and_json_serialization_are_deterministic(editorial_inspection) -> None:
    first = build_editorial_document(editorial_inspection)
    second = build_editorial_document(editorial_inspection)
    assert first == second
    assert editorial_build_result_to_json(first).encode("utf-8") == editorial_build_result_to_json(second).encode("utf-8")
    assert str(FIXTURES.parent.parent) not in editorial_build_result_to_json(first)


def test_build_from_file_is_a_non_printing_convenience_api(editorial_result) -> None:
    result = build_editorial_document_from_file(FIXTURES / "native-editorial.docx")
    assert result == editorial_result
