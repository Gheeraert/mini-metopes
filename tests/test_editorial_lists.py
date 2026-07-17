"""Tests structurels des listes editoriales construites depuis Word."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from mini_metopes.docx import inspect_docx_file
from mini_metopes.editorial import (
    EditorialList,
    Heading,
    Paragraph,
    TextSpan,
    build_editorial_document,
    editorial_build_result_to_json,
)
from test_docx_numbering import basic_numbering, numbering_xml, paragraph, runtime_docx, write_docx


FIXTURES = Path(__file__).parent / "fixtures" / "docx"


def _lists(blocks):
    return [block for block in blocks if isinstance(block, EditorialList)]


def _inspection_with_levels(levels: tuple[int, ...]):
    inspection = inspect_docx_file(FIXTURES / "native-lists-tei.docx")
    template = inspection.paragraphs[3]
    assert template.numbering is not None
    paragraphs = tuple(
        replace(
            template,
            index=index,
            numbering_level=level,
            numbering=replace(template.numbering, level=level),
        )
        for index, level in enumerate(levels)
    )
    return replace(inspection, paragraphs=paragraphs, footnotes=(), endnotes=())


@pytest.mark.parametrize(
    ("levels", "root_count", "has_jump"),
    [
        ((0, 0, 0), 1, False),
        ((0, 1, 0), 1, False),
        ((0, 1, 2, 1, 0), 1, False),
        ((1, 1), 1, False),
        ((2, 2), 1, False),
        ((1, 0), 2, False),
        ((0, 2), 2, True),
    ],
)
def test_level_sequences_have_a_deterministic_structure(
    levels: tuple[int, ...], root_count: int, has_jump: bool,
) -> None:
    result = build_editorial_document(_inspection_with_levels(levels))
    lists = _lists(result.document.blocks)
    assert len(lists) == root_count
    assert any(item.code == "list_level_jump_not_serializable" for item in result.diagnostics) is has_jump
    if levels[0] > 0:
        assert any(item.code == "list_root_level_normalized" for item in result.diagnostics)
    if levels == (0, 1, 0):
        assert len(lists[0].items[0].child_lists) == 1


def test_native_lists_build_a_frozen_nested_editorial_tree() -> None:
    result = build_editorial_document(inspect_docx_file(FIXTURES / "native-lists-tei.docx"))
    body_lists = _lists(result.document.blocks)

    assert [item.list_kind for item in body_lists] == ["ordered", "bulleted", "ordered"]
    first = body_lists[0]
    assert first.num_format == "decimal"
    assert first.start == 1
    assert [item.source_paragraph_index for item in first.items] == [3, 7]
    child = first.items[0].child_lists[0]
    assert child.list_kind == "bulleted"
    assert [item.source_paragraph_index for item in child.items] == [4, 6]
    assert child.items[0].child_lists[0].num_format == "lowerLetter"
    assert child.items[0].child_lists[0].items[0].content == (TextSpan(text="Sous-sous-item."),)

    assert body_lists[1].source_level == 1
    assert body_lists[1].source_numbering_id == "44"
    assert body_lists[2].source_numbering_id == "43"
    assert body_lists[2].start == 5
    assert any(item.code == "list_root_level_normalized" for item in result.diagnostics)
    assert any(item.code == "list_root_level_decrease_split" for item in result.diagnostics)


def test_list_items_keep_inline_content_notes_and_lists_in_notes() -> None:
    result = build_editorial_document(inspect_docx_file(FIXTURES / "native-lists-tei.docx"))
    first = _lists(result.document.blocks)[0].items[0]
    assert any(isinstance(item, TextSpan) and item.text == "Premier item " for item in first.content)
    assert any(isinstance(item, TextSpan) and item.marks == ("bold",) for item in first.content)
    assert any(getattr(item, "kind", None) == "note_reference" for item in first.content)

    footnote = next(note for note in result.document.notes if note.note_kind == "footnote")
    endnote = next(note for note in result.document.notes if note.note_kind == "endnote")
    assert isinstance(footnote.blocks[0], EditorialList)
    assert footnote.blocks[0].list_kind == "ordered"
    assert isinstance(endnote.blocks[0], EditorialList)
    assert endnote.blocks[0].list_kind == "bulleted"


def test_removed_numbering_stays_a_paragraph_and_json_is_deterministic() -> None:
    inspection = inspect_docx_file(FIXTURES / "native-lists-tei.docx")
    result = build_editorial_document(inspection)
    removed = next(block for block in result.document.blocks if isinstance(block, Paragraph) and block.source_paragraph_index == 12)
    assert removed.source_style_id == "ListParagraph"
    assert editorial_build_result_to_json(result).encode("utf-8") == editorial_build_result_to_json(result).encode("utf-8")


def test_numbered_nonparagraph_roles_and_empty_items_are_diagnosed() -> None:
    inspection = inspect_docx_file(FIXTURES / "native-lists-tei.docx")
    changed_heading = replace(inspection.paragraphs[3], style_id="Heading1")
    empty_item = replace(inspection.paragraphs[4], text="", runs=())
    following = inspection.paragraphs[5]
    assert following.numbering is not None
    unnumbered_following = replace(
        following,
        numbering=replace(following.numbering, status="removed"),
        numbering_id="0",
    )
    changed = replace(
        inspection,
        paragraphs=inspection.paragraphs[:3] + (changed_heading, empty_item, unnumbered_following) + inspection.paragraphs[6:],
    )
    result = build_editorial_document(changed)
    codes = [item.code for item in result.diagnostics]
    assert "numbered_nonparagraph_style_not_serializable" in codes
    assert "empty_list_item_not_serializable" in codes
    assert any(isinstance(block, Heading) and block.source_paragraph_index == 3 for block in result.document.blocks)


def test_level_jump_is_blocking_without_inventing_a_parent_item() -> None:
    inspection = inspect_docx_file(FIXTURES / "native-lists-tei.docx")
    current = inspection.paragraphs[4]
    assert current.numbering is not None
    jumped = replace(current, numbering=replace(current.numbering, level=2), numbering_level=2)
    changed = replace(inspection, paragraphs=inspection.paragraphs[:4] + (jumped,) + inspection.paragraphs[5:])
    result = build_editorial_document(changed)
    assert any(item.code == "list_level_jump_not_serializable" and item.severity == "error" for item in result.diagnostics)


def test_changed_signature_at_a_child_level_creates_ordered_sibling_lists() -> None:
    inspection = inspect_docx_file(FIXTURES / "native-lists-tei.docx")
    template = inspection.paragraphs[3]
    assert template.numbering is not None
    parent = replace(template, index=0, numbering=replace(template.numbering, level=0), numbering_level=0)
    bullet = replace(
        template, index=1,
        numbering=replace(template.numbering, level=1, list_kind="bulleted", num_format="bullet"),
        numbering_level=1,
    )
    ordered = replace(
        template, index=2,
        numbering=replace(template.numbering, numbering_id="43", level=1, list_kind="ordered", num_format="decimal"),
        numbering_id="43", numbering_level=1,
    )
    result = build_editorial_document(replace(inspection, paragraphs=(parent, bullet, ordered), footnotes=(), endnotes=()))
    children = _lists(result.document.blocks)[0].items[0].child_lists
    assert [(item.list_kind, item.source_numbering_id) for item in children] == [
        ("bulleted", "42"), ("ordered", "43"),
    ]


def test_only_direct_resolved_marker_lists_are_eligible() -> None:
    inspection = inspect_docx_file(FIXTURES / "native-lists-tei.docx")
    current = inspection.paragraphs[3]
    assert current.numbering is not None
    style_based = replace(current, numbering=replace(current.numbering, origin="style", status="unresolved"))
    changed = replace(inspection, paragraphs=inspection.paragraphs[:3] + (style_based,) + inspection.paragraphs[4:])
    result = build_editorial_document(changed)
    assert any(item.code == "style_based_numbering_not_serializable" for item in result.diagnostics)


def test_interrupted_same_numbering_instance_is_not_serializable() -> None:
    path = runtime_docx("interrupted-same-numid.docx")
    write_docx(
        path,
        paragraph("Premier", num_id="42", ilvl="0")
        + paragraph("Interruption")
        + paragraph("Reprise", num_id="42", ilvl="0"),
        numbering=basic_numbering(),
    )

    result = build_editorial_document(inspect_docx_file(path))

    diagnostic = next(item for item in result.diagnostics if item.code == "interrupted_list_continuation_not_serializable")
    assert diagnostic.paragraph_index == 2
    assert "numId=42" in diagnostic.message
    assert "interruptions=1" in diagnostic.message


def test_distinct_numbering_instance_after_interruption_stays_serializable() -> None:
    path = runtime_docx("interrupted-distinct-numid.docx")
    numbering = numbering_xml(
        '<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"><w:numFmt w:val="decimal"/></w:lvl></w:abstractNum>'
        '<w:num w:numId="42"><w:abstractNumId w:val="1"/></w:num>'
        '<w:num w:numId="44"><w:abstractNumId w:val="1"/></w:num>'
    )
    write_docx(
        path,
        paragraph("Premier", num_id="42", ilvl="0")
        + paragraph("Interruption")
        + paragraph("Nouvelle instance", num_id="44", ilvl="0"),
        numbering=numbering,
    )

    result = build_editorial_document(inspect_docx_file(path))

    assert [item.source_numbering_id for item in _lists(result.document.blocks)] == ["42", "44"]
    assert "interrupted_list_continuation_not_serializable" not in [item.code for item in result.diagnostics]


def test_interrupted_list_continuation_is_scoped_to_each_part() -> None:
    numbering = basic_numbering()
    footnotes = """<?xml version="1.0" encoding="UTF-8"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:footnote w:id="1">
    <w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="42"/></w:numPr></w:pPr><w:r><w:t>Note un</w:t></w:r></w:p>
    <w:p><w:r><w:t>Interruption note</w:t></w:r></w:p>
    <w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="42"/></w:numPr></w:pPr><w:r><w:t>Note reprise</w:t></w:r></w:p>
  </w:footnote>
</w:footnotes>
"""
    endnotes = """<?xml version="1.0" encoding="UTF-8"?>
<w:endnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:endnote w:id="2">
    <w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="42"/></w:numPr></w:pPr><w:r><w:t>Fin un</w:t></w:r></w:p>
    <w:p><w:r><w:t>Interruption fin</w:t></w:r></w:p>
    <w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="42"/></w:numPr></w:pPr><w:r><w:t>Fin reprise</w:t></w:r></w:p>
  </w:endnote>
</w:endnotes>
"""
    path = runtime_docx("interrupted-notes.docx")
    write_docx(
        path,
        paragraph("Corps", num_id="42", ilvl="0"),
        numbering=numbering,
        footnotes=footnotes,
        endnotes=endnotes,
    )

    result = build_editorial_document(inspect_docx_file(path))
    diagnostics = [item for item in result.diagnostics if item.code == "interrupted_list_continuation_not_serializable"]

    assert [(item.note_id, item.paragraph_index) for item in diagnostics] == [("1", 2), ("2", 2)]


def test_explicit_lvlrestart_values_are_blocking() -> None:
    for value in ("0", "1", "2"):
        path = runtime_docx(f"explicit-lvlrestart-{value}.docx")
        write_docx(
            path,
            paragraph("Restart", num_id="42", ilvl="0"),
            numbering=basic_numbering(f'<w:numFmt w:val="decimal"/><w:lvlRestart w:val="{value}"/>'),
        )

        result = build_editorial_document(inspect_docx_file(path))

        assert any(
            item.code == "explicit_list_restart_not_serializable" and item.severity == "error"
            for item in result.diagnostics
        )
        assert "list_restart_semantics_normalized" not in [item.code for item in result.diagnostics]
