"""Tests structurels de la premiere serialisation TEI Commons Publishing."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from lxml import etree

from mini_metopes.editorial import (
    DrawingReference,
    EditorialDocument,
    EditorialLink,
    EditorialNote,
    Heading,
    NoteReference,
    Paragraph,
    TextSpan,
    VerseLine,
    VerseQuote,
    VerseStanza,
    build_editorial_document_from_file,
)
from mini_metopes.tei import serialize_editorial_document_to_tei, write_tei_conversion_result
from mini_metopes.validation import ValidationIssue, ValidationResult, validate_xml_bytes
import mini_metopes.tei.serializer as serializer


FIXTURES = Path(__file__).parent / "fixtures" / "docx"
NS = {"tei": "http://www.tei-c.org/ns/1.0"}


@pytest.fixture()
def document() -> EditorialDocument:
    return build_editorial_document_from_file(FIXTURES / "native-tei-conversion.docx").document


@pytest.fixture()
def result(document):
    return serialize_editorial_document_to_tei(document)


def _tree(result) -> etree._Element:
    assert result.xml_bytes is not None
    return etree.fromstring(result.xml_bytes)


def test_valid_conversion_has_deterministic_minimal_envelope(result, document) -> None:
    assert result.is_successful
    assert validate_xml_bytes(result.xml_bytes or b"").valid
    tree = _tree(result)
    assert tree.tag == "{http://www.tei-c.org/ns/1.0}TEI"
    assert tree.xpath("string(tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:title)", namespaces=NS) == document.source_name
    assert tree.xpath("count(tei:text/tei:body)", namespaces=NS) == 1.0
    again = serialize_editorial_document_to_tei(document)
    assert result.xml_bytes == again.xml_bytes


def test_sections_paragraphs_and_inline_content_are_serialized(result) -> None:
    tree = _tree(result)
    assert tree.xpath("tei:text/tei:body/tei:p[1]/text()", namespaces=NS) == ["Avant le premier titre."]
    assert tree.xpath("tei:text/tei:body/tei:div/tei:head/text()", namespaces=NS) == ["Premiere section"]
    assert tree.xpath("tei:text/tei:body/tei:div/tei:div/tei:head/text()", namespaces=NS) == ["Sous-section"]
    assert tree.xpath("tei:text/tei:body/tei:div/tei:div/tei:div/tei:head/text()", namespaces=NS) == ["Niveau trois"]
    assert tree.xpath("//tei:hi/@rend", namespaces=NS) == ["bold", "italic", "small-caps", "uppercase", "sup", "sub", "italic", "italic", "italic"]
    assert tree.xpath("//tei:ref/@target", namespaces=NS) == ["https://example.test/body"]
    assert tree.xpath("count(//tei:lb)", namespaces=NS) == 1.0


def test_quotes_verse_and_notes_keep_their_structure_and_position(result) -> None:
    tree = _tree(result)
    assert tree.xpath("count(tei:text/tei:body/tei:div/tei:quote)", namespaces=NS) == 2.0
    assert tree.xpath("count(tei:text/tei:body/tei:div/tei:quote[1]/tei:p)", namespaces=NS) == 2.0
    assert tree.xpath("count(tei:text/tei:body/tei:div/tei:quote[2]/tei:lg)", namespaces=NS) == 2.0
    assert tree.xpath("count(tei:text/tei:body/tei:div/tei:quote[2]/tei:lg/tei:l)", namespaces=NS) == 4.0
    assert tree.xpath("count(//tei:note[@place='foot'])", namespaces=NS) == 2.0
    assert tree.xpath("count(//tei:note[@place='end'])", namespaces=NS) == 1.0
    assert tree.xpath("count(//tei:note//tei:quote)", namespaces=NS) == 4.0


@pytest.mark.parametrize(
    ("document_factory", "code"),
    [
        (lambda document: replace(document, blocks=(replace(document.blocks[1], content=()),)), "empty_heading_not_serializable"),
        (lambda document: replace(document, notes=()), "missing_note_target_not_serializable"),
    ],
)
def test_blocking_diagnostics_prevent_xml(document, document_factory, code: str) -> None:
    result = serialize_editorial_document_to_tei(document_factory(document))
    assert result.xml_bytes is None
    assert code in [diagnostic.code for diagnostic in result.diagnostics]


def test_inline_and_verse_failures_are_explicit(document) -> None:
    paragraph = Paragraph(
        content=(
            TextSpan("A", link=EditorialLink(kind="internal", anchor="x")),
            TextSpan("B", link=EditorialLink(kind="unresolved", relationship_id="rIdMissing")),
            DrawingReference(()),
        ),
        source_paragraph_index=0,
        source_style_id="Normal",
    )
    verse = VerseQuote(
        stanzas=(VerseStanza((VerseLine((TextSpan("plein"),), 1, 0), VerseLine((), 1, 1)), 1, "IntenseQuote"),),
    )
    result = serialize_editorial_document_to_tei(replace(document, blocks=(paragraph, verse), notes=()))
    codes = [diagnostic.code for diagnostic in result.diagnostics]
    assert "internal_link_target_not_materialized" in codes
    assert "unresolved_link_not_serializable" in codes
    assert "drawing_reference_not_serializable" in codes
    assert "empty_verse_not_serializable" in codes

    empty_stanza = VerseQuote(stanzas=(VerseStanza((VerseLine((), 2, 0),), 2, "IntenseQuote"),))
    result = serialize_editorial_document_to_tei(replace(document, blocks=(empty_stanza,), notes=()))
    assert "empty_verse_stanza_not_serializable" in [diagnostic.code for diagnostic in result.diagnostics]


def test_duplicate_and_cyclic_notes_are_rejected(document) -> None:
    duplicate = replace(document, notes=(document.notes[0], document.notes[0]))
    assert "duplicate_note_target_not_serializable" in [
        diagnostic.code for diagnostic in serialize_editorial_document_to_tei(duplicate).diagnostics
    ]
    cyclic_note = EditorialNote(
        note_id="1",
        note_kind="footnote",
        blocks=(Paragraph((NoteReference("1", "footnote"),), 0, "Normal"),),
    )
    cyclic_document = EditorialDocument(
        source_name="cycle.docx",
        blocks=(Paragraph((NoteReference("1", "footnote"),), 0, "Normal"),),
        notes=(cyclic_note,),
    )
    assert "cyclic_note_reference" in [
        diagnostic.code for diagnostic in serialize_editorial_document_to_tei(cyclic_document).diagnostics
    ]


def test_failed_normative_validation_is_reported(monkeypatch: pytest.MonkeyPatch, document) -> None:
    monkeypatch.setattr(
        serializer,
        "validate_xml_tree",
        lambda tree: ValidationResult(False, (ValidationIssue("schema test"),)),
    )
    result = serializer.serialize_editorial_document_to_tei(document)
    assert result.xml_bytes is None
    assert result.validation_issues
    assert "tei_validation_failed" in [diagnostic.code for diagnostic in result.diagnostics]


def test_atomic_writer_preserves_existing_file_on_failed_result(tmp_path: Path, result) -> None:
    destination = tmp_path / "output.xml"
    destination.write_text("conserve", encoding="utf-8")
    failed = replace(result, xml_bytes=None)
    with pytest.raises(ValueError):
        write_tei_conversion_result(failed, destination)
    assert destination.read_text(encoding="utf-8") == "conserve"
    write_tei_conversion_result(result, destination)
    assert validate_xml_bytes(destination.read_bytes()).valid
