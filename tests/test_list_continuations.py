"""Continuations explicites d'items de liste par le style ListParagraph."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from lxml import etree

from mini_metopes.cli import main
from mini_metopes.docx import inspect_docx_file
from mini_metopes.editorial import (
    EditorialDocument,
    EditorialList,
    EditorialListItem,
    NATIVE_WORD_CONVENTION,
    Paragraph,
    TextSpan,
    build_editorial_document,
    editorial_build_result_to_json,
)
from mini_metopes.metadata import load_metadata_file
from mini_metopes.tei import convert_docx_to_tei, serialize_editorial_document_to_tei
from mini_metopes.validation import validate_xml_bytes
from test_docx_numbering import paragraph, runtime_docx, write_docx


FIXTURES = Path(__file__).parent / "fixtures"
DOCX = FIXTURES / "docx" / "native-list-continuations.docx"
METADATA = FIXTURES / "metadata" / "native-list-continuations.metadata.json"
TEI = {"tei": "http://www.tei-c.org/ns/1.0"}


NUMBERING = """<?xml version="1.0" encoding="UTF-8"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="1">
    <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/></w:lvl>
    <w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="bullet"/></w:lvl>
  </w:abstractNum>
  <w:num w:numId="42"><w:abstractNumId w:val="1"/></w:num>
  <w:num w:numId="44"><w:abstractNumId w:val="1"/></w:num>
</w:numbering>
"""

STYLES = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="Paragraphe de liste"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="Titre 1"/></w:style>
</w:styles>
"""

CUSTOM_LIST_STYLES = STYLES.replace(
    '<w:style w:type="paragraph" w:styleId="ListParagraph">',
    '<w:style w:type="paragraph" w:customStyle="1" w:styleId="ListParagraph">',
)


def _metadata():
    loaded = load_metadata_file(METADATA)
    assert loaded.metadata is not None
    return loaded.metadata


def _lists(blocks: tuple[object, ...]) -> list[EditorialList]:
    result: list[EditorialList] = []
    for block in blocks:
        if isinstance(block, EditorialList):
            result.append(block)
            for item in block.items:
                result.extend(_lists(item.child_lists))
    return result


def _items(editorial_list: EditorialList) -> list[EditorialListItem]:
    result: list[EditorialListItem] = []
    for item in editorial_list.items:
        result.append(item)
        for child in item.child_lists:
            result.extend(_items(child))
    return result


def _runtime_sequence(name: str, body: str, *, styles: str = STYLES) -> Path:
    path = runtime_docx(name)
    write_docx(path, body, styles=styles, numbering=NUMBERING)
    return path


def _conversion_codes(path: Path) -> list[str]:
    return [diagnostic.code for diagnostic in convert_docx_to_tei(path, metadata=_metadata()).diagnostics]


def test_convention_accepts_only_integrated_listparagraph_as_continuation_style() -> None:
    convention = NATIVE_WORD_CONVENTION

    assert convention.is_list_continuation_style("ListParagraph", False)
    assert convention.is_list_continuation_style("ListParagraph", None)
    assert not convention.is_list_continuation_style("ListParagraph", True)
    assert not convention.is_list_continuation_style("ParagrapheDeListe", False)


def test_positive_fixture_builds_continuations_at_the_right_levels() -> None:
    result = build_editorial_document(inspect_docx_file(DOCX))
    body_lists = _lists(result.document.blocks)
    first = body_lists[0]
    bullet_root = next(item for item in body_lists if item.source_numbering_id == "44")
    footnote = next(note for note in result.document.notes if note.note_kind == "footnote")
    endnote = next(note for note in result.document.notes if note.note_kind == "endnote")

    assert len(body_lists) == 3
    assert [len(item.continuation_paragraphs) for item in first.items] == [2, 0, 0, 0]
    assert [item.source_paragraph_index for item in first.items[0].continuation_paragraphs] == [4, 5]
    child = first.items[2].child_lists[0]
    assert child.source_level == 1
    assert [item.source_paragraph_index for item in child.items[0].continuation_paragraphs] == [9]
    assert [item.source_paragraph_index for item in bullet_root.items[0].continuation_paragraphs] == [14]
    assert any(isinstance(inline, TextSpan) and inline.marks == ("bold", "italic") for inline in first.items[0].continuation_paragraphs[0].content)
    assert any(isinstance(inline, TextSpan) and inline.link is not None for inline in first.items[0].continuation_paragraphs[0].content)
    assert any(getattr(inline, "kind", None) == "note_reference" for inline in first.items[0].continuation_paragraphs[0].content)
    assert all(paragraph.rendition is None for item in _items(first) for paragraph in item.continuation_paragraphs)
    assert isinstance(footnote.blocks[0], EditorialList)
    assert len(footnote.blocks[0].items[0].continuation_paragraphs) == 1
    assert isinstance(endnote.blocks[0], EditorialList)
    assert len(endnote.blocks[0].items[0].continuation_paragraphs) == 1


def test_list_continuations_json_is_deterministic_and_explicit() -> None:
    result = build_editorial_document(inspect_docx_file(DOCX))
    first = editorial_build_result_to_json(result)
    second = editorial_build_result_to_json(result)
    data = json.loads(first)
    first_item = data["document"]["blocks"][3]["items"][0]

    assert first == second
    assert "continuation_paragraphs" in first_item
    assert [paragraph["source_paragraph_index"] for paragraph in first_item["continuation_paragraphs"]] == [4, 5]
    assert first_item["continuation_paragraphs"][0]["source_style_id"] == "ListParagraph"
    assert first_item["continuation_paragraphs"][0]["rendition"] is None


def test_positive_fixture_serializes_multiparagraph_items_to_valid_tei() -> None:
    result = convert_docx_to_tei(DOCX, metadata=_metadata())
    assert result.is_successful
    assert result.xml_bytes is not None and validate_xml_bytes(result.xml_bytes).valid
    root = etree.fromstring(result.xml_bytes)

    first_item_paragraphs = root.xpath("./tei:text/tei:body/tei:list[1]/tei:item[1]/tei:p", namespaces=TEI)
    paragraph_texts = [paragraph.xpath("string()", namespaces=TEI) for paragraph in first_item_paragraphs]
    assert paragraph_texts[0] == "Premier item."
    assert paragraph_texts[1].startswith("Continuation avec marques lienapres retour")
    assert paragraph_texts[2] == "Seconde continuation."
    assert root.xpath("count(./tei:text/tei:body/tei:list[1]/tei:item[2]/tei:p)", namespaces=TEI) == 0.0
    assert root.xpath("count(.//tei:item/tei:p[@rend='consecutive'])", namespaces=TEI) == 0.0
    assert root.xpath("string(.//tei:item/tei:p/tei:ref/@target)", namespaces=TEI) == "https://example.test/body"
    assert root.xpath("count(.//tei:item/tei:p/tei:note[@place='foot'])", namespaces=TEI) == 1.0
    assert root.xpath("count(.//tei:item/tei:p/tei:note[@place='end'])", namespaces=TEI) == 1.0
    assert root.xpath("count(.//tei:note[@place='foot']//tei:item/tei:p)", namespaces=TEI) == 2.0
    assert root.xpath("count(.//tei:note[@place='end']//tei:item/tei:p)", namespaces=TEI) == 2.0


def test_manual_item_serializes_paragraphs_before_child_lists_and_validates() -> None:
    child = EditorialList(
        list_kind="bulleted",
        num_format="bullet",
        start=1,
        source_numbering_id="44",
        source_level=1,
        level_text=None,
        suffix=None,
        restart_after_level=None,
        items=(EditorialListItem((TextSpan("enfant"),), (), 2, "Normal"),),
    )
    parent = EditorialList(
        list_kind="ordered",
        num_format="decimal",
        start=1,
        source_numbering_id="42",
        source_level=0,
        level_text=None,
        suffix=None,
        restart_after_level=None,
        items=(
            EditorialListItem(
                content=(TextSpan("initial"),),
                child_lists=(child,),
                source_paragraph_index=0,
                source_style_id="Normal",
                continuation_paragraphs=(
                    Paragraph((TextSpan("suite un"),), 1, "ListParagraph"),
                    Paragraph((TextSpan("suite deux"),), 2, "ListParagraph"),
                ),
            ),
            EditorialListItem((TextSpan("second"),), (), 3, "Normal"),
        ),
    )

    result = serialize_editorial_document_to_tei(
        EditorialDocument(source_name="manual.docx", blocks=(parent,), notes=())
    )

    assert result.xml_bytes is not None
    assert validate_xml_bytes(result.xml_bytes).valid
    root = etree.fromstring(result.xml_bytes)
    assert [etree.QName(child).localname for child in root.xpath(".//tei:list[1]/tei:item[1]/*", namespaces=TEI)] == ["p", "p", "p", "list"]
    assert root.xpath("count(.//tei:list[1]/tei:item[2]/tei:p)", namespaces=TEI) == 0.0


def test_manual_invalid_list_continuations_are_rejected_defensively() -> None:
    base = EditorialListItem(
        content=(TextSpan("initial"),),
        child_lists=(),
        source_paragraph_index=0,
        source_style_id="Normal",
        continuation_paragraphs=(Paragraph((TextSpan("suite"),), 1, "ListParagraph"),),
    )
    cases = [
        (replace(base, continuation_paragraphs=(Paragraph((), 1, "ListParagraph"),)), "empty_list_continuation_not_serializable"),
        (replace(base, continuation_paragraphs=(Paragraph((TextSpan("suite"),), 1, "ListParagraph", rendition="bad"),)), "unsupported_paragraph_rendition"),  # type: ignore[arg-type]
        (replace(base, content=()), "empty_list_item_not_serializable"),
        (replace(base, content=(), continuation_paragraphs=()), "empty_list_item_not_serializable"),
    ]
    for item, code in cases:
        editorial_list = EditorialList(
            list_kind="ordered",
            num_format="decimal",
            start=1,
            source_numbering_id="42",
            source_level=0,
            level_text=None,
            suffix=None,
            restart_after_level=None,
            items=(item,),
        )
        result = serialize_editorial_document_to_tei(
            EditorialDocument(source_name="manual.docx", blocks=(editorial_list,), notes=())
        )
        assert result.xml_bytes is None
        assert code in [diagnostic.code for diagnostic in result.diagnostics]


def test_model_docx_reports_recursive_continuation_counts(capsys) -> None:
    assert main(["model-docx", str(DOCX)]) == 0
    captured = capsys.readouterr()

    assert "Paragraphes de continuation de liste du corps : 5" in captured.out
    assert "Paragraphes de continuation de liste dans les notes : 2" in captured.out
    assert "Paragraphes de continuation de liste totaux : 7" in captured.out
    assert "Items de liste multiparagraphe : 6" in captured.out


def test_listparagraph_outside_list_context_stays_an_ordinary_paragraph() -> None:
    path = _runtime_sequence("list-continuation-outside.docx", paragraph("Hors liste", style="ListParagraph"))
    result = build_editorial_document(inspect_docx_file(path))

    assert isinstance(result.document.blocks[0], Paragraph)
    assert result.document.blocks[0].source_style_id == "ListParagraph"


def test_normal_between_identical_items_remains_an_interruption() -> None:
    path = _runtime_sequence(
        "list-continuation-normal-interruption.docx",
        paragraph("Premier", num_id="42", ilvl="0")
        + paragraph("Normal")
        + paragraph("Reprise", num_id="42", ilvl="0"),
    )
    assert "interrupted_list_continuation_not_serializable" in _conversion_codes(path)


def test_ambiguous_continuation_to_another_instance_level_or_end_is_blocking(tmp_path: Path) -> None:
    cases = [
        (
            "list-continuation-other-instance.docx",
            paragraph("Premier", num_id="42", ilvl="0")
            + paragraph("Suite", style="ListParagraph")
            + paragraph("Autre", num_id="44", ilvl="0"),
            "autre instance",
        ),
        (
            "list-continuation-other-level.docx",
            paragraph("Premier", num_id="42", ilvl="0")
            + paragraph("Suite", style="ListParagraph")
            + paragraph("Enfant", num_id="42", ilvl="1"),
            "autre niveau",
        ),
        (
            "list-continuation-child-to-parent.docx",
            paragraph("Parent", num_id="42", ilvl="0")
            + paragraph("Enfant", num_id="42", ilvl="1")
            + paragraph("Suite", style="ListParagraph")
            + paragraph("Retour", num_id="42", ilvl="0"),
            "reprise apres sous-liste",
        ),
        (
            "list-continuation-end.docx",
            paragraph("Premier", num_id="42", ilvl="0") + paragraph("Suite", style="ListParagraph"),
            "fin de sequence",
        ),
        (
            "list-continuation-heading.docx",
            paragraph("Premier", num_id="42", ilvl="0")
            + paragraph("Suite", style="ListParagraph")
            + paragraph("Titre", style="Heading1"),
            "fin de sequence",
        ),
    ]
    for name, body, reason in cases:
        path = _runtime_sequence(name, body)
        destination = tmp_path / f"{name}.xml"
        destination.write_text("ancienne sortie", encoding="utf-8")

        result = convert_docx_to_tei(path, metadata=_metadata())
        code = main(["convert-docx", str(path), str(destination), "--metadata", str(METADATA)])

        diagnostic = next(item for item in result.diagnostics if item.code == "ambiguous_list_continuation_not_serializable")
        assert diagnostic.source_paragraph_index in {1, 2}
        assert reason in diagnostic.message
        assert code == 1
        assert destination.read_text(encoding="utf-8") == "ancienne sortie"


def test_custom_or_empty_listparagraph_continuations_are_blocking() -> None:
    custom = _runtime_sequence(
        "list-continuation-custom.docx",
        paragraph("Premier", num_id="42", ilvl="0")
        + paragraph("Suite", style="ListParagraph")
        + paragraph("Reprise", num_id="42", ilvl="0"),
        styles=CUSTOM_LIST_STYLES,
    )
    empty = _runtime_sequence(
        "list-continuation-empty.docx",
        paragraph("Premier", num_id="42", ilvl="0")
        + paragraph("", style="ListParagraph")
        + paragraph("Reprise", num_id="42", ilvl="0"),
    )

    custom_codes = _conversion_codes(custom)
    empty_codes = _conversion_codes(empty)

    assert "ambiguous_list_continuation_not_serializable" in custom_codes
    assert "empty_list_continuation_not_serializable" in empty_codes


def test_listparagraph_with_removed_or_active_numbering_is_not_misread_as_continuation() -> None:
    removed = _runtime_sequence(
        "list-continuation-removed-numbering.docx",
        paragraph("Premier", num_id="42", ilvl="0")
        + paragraph("Suite", style="ListParagraph", num_id="0")
        + paragraph("Reprise", num_id="42", ilvl="0"),
    )
    active = _runtime_sequence(
        "list-continuation-active-numbering.docx",
        paragraph("Premier", num_id="42", ilvl="0")
        + paragraph("Item", style="ListParagraph", num_id="42", ilvl="0"),
    )

    removed_result = build_editorial_document(inspect_docx_file(removed))
    active_result = build_editorial_document(inspect_docx_file(active))

    assert isinstance(removed_result.document.blocks[1], Paragraph)
    assert removed_result.document.blocks[1].source_style_id == "ListParagraph"
    assert len(_lists(active_result.document.blocks)[0].items) == 2
    assert not _lists(active_result.document.blocks)[0].items[0].continuation_paragraphs
