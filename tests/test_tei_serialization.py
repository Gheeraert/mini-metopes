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
    ProseQuote,
    TextSpan,
    VerseLine,
    VerseQuote,
    VerseStanza,
    build_editorial_document,
    build_editorial_document_from_file,
)
from mini_metopes.docx import InspectionIssue, RunContentInfo, inspect_docx_file
from mini_metopes.metadata import extract_metadata_suggestions, load_metadata_file
from mini_metopes.tei import (
    convert_docx_to_tei,
    prepare_tei_conversion,
    serialize_editorial_document_to_tei,
    write_tei_conversion_result,
)
from mini_metopes.validation import ValidationIssue, ValidationResult, validate_xml_bytes
import mini_metopes.tei.serializer as serializer


FIXTURES = Path(__file__).parent / "fixtures" / "docx"
METADATA = Path(__file__).parent / "fixtures" / "metadata" / "native-tei-conversion.metadata.json"
NS = {"tei": "http://www.tei-c.org/ns/1.0"}


@pytest.fixture()
def document() -> EditorialDocument:
    inspection = inspect_docx_file(FIXTURES / "native-tei-conversion.docx")
    consumed = extract_metadata_suggestions(inspection).consumed_paragraph_indexes
    return build_editorial_document(inspection, excluded_body_paragraph_indexes=frozenset(consumed)).document


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


def test_native_word_note_marks_do_not_pollute_tei_notes(result) -> None:
    tree = _tree(result)

    assert tree.xpath("count(//tei:note[@place='foot'])", namespaces=NS) == 2.0
    assert tree.xpath("count(//tei:note[@place='end'])", namespaces=NS) == 1.0
    assert tree.xpath("count(//tei:note//tei:note)", namespaces=NS) == 0.0
    assert tree.xpath("count(//tei:note//tei:hi)", namespaces=NS) == 0.0
    assert "1Note de bas de page" not in tree.xpath("string((//tei:note[@place='foot'])[1])", namespaces=NS)
    assert "2Note de fin" not in tree.xpath("string(//tei:note[@place='end'])", namespaces=NS)


def test_positive_native_conversion_has_no_unknown_style_diagnostics() -> None:
    metadata = load_metadata_file(METADATA).metadata
    assert metadata is not None
    result = convert_docx_to_tei(FIXTURES / "native-tei-conversion.docx", metadata=metadata)

    assert result.is_successful
    assert "unsupported_paragraph_style" not in [diagnostic.code for diagnostic in result.diagnostics]
    assert "unsupported_character_style" not in [diagnostic.code for diagnostic in result.diagnostics]


def test_run_with_declared_foreign_language_is_wrapped_in_hi_with_xml_lang() -> None:
    """Un run Word tague dans une autre langue que le document (metadata.language
    = fr) doit porter xml:lang, sans que ce soit une exception au principe
    "pas de dialecte TEI local" (hi accepte xml:lang, voir docs/architecture/0019)."""
    metadata = load_metadata_file(METADATA).metadata
    assert metadata is not None
    assert metadata.language == "fr"
    inspection = inspect_docx_file(FIXTURES / "native-tei-conversion.docx")
    paragraph = inspection.paragraphs[2]
    assert paragraph.text == "Avant le premier titre."
    foreign_run = replace(paragraph.runs[0], language="en-US")
    modified_paragraph = replace(paragraph, runs=(foreign_run,))
    inspection = replace(
        inspection,
        paragraphs=inspection.paragraphs[:2] + (modified_paragraph,) + inspection.paragraphs[3:],
    )
    consumed = extract_metadata_suggestions(inspection).consumed_paragraph_indexes
    editorial = build_editorial_document(inspection, excluded_body_paragraph_indexes=frozenset(consumed))

    result = serialize_editorial_document_to_tei(editorial.document, metadata=metadata)

    assert result.is_successful
    tree = _tree(result)
    hi_elements = tree.xpath(
        "//tei:hi[@xml:lang='en-US']",
        namespaces={**NS, "xml": "http://www.w3.org/XML/1998/namespace"},
    )
    assert len(hi_elements) == 1
    assert hi_elements[0].text == "Avant le premier titre."


def test_run_with_matching_primary_language_subtag_is_not_wrapped() -> None:
    """`fr-FR` (courant sous Word) ne doit pas etre traite comme etranger
    dans un document declare `fr` : seule la sous-etiquette primaire compte."""
    metadata = load_metadata_file(METADATA).metadata
    assert metadata is not None
    inspection = inspect_docx_file(FIXTURES / "native-tei-conversion.docx")
    paragraph = inspection.paragraphs[2]
    same_language_run = replace(paragraph.runs[0], language="fr-FR")
    modified_paragraph = replace(paragraph, runs=(same_language_run,))
    inspection = replace(
        inspection,
        paragraphs=inspection.paragraphs[:2] + (modified_paragraph,) + inspection.paragraphs[3:],
    )
    consumed = extract_metadata_suggestions(inspection).consumed_paragraph_indexes
    editorial = build_editorial_document(inspection, excluded_body_paragraph_indexes=frozenset(consumed))

    result = serialize_editorial_document_to_tei(editorial.document, metadata=metadata)

    assert result.is_successful
    tree = _tree(result)
    hi_with_lang = tree.xpath(
        "//tei:hi[@xml:lang]",
        namespaces={**NS, "xml": "http://www.w3.org/XML/1998/namespace"},
    )
    assert hi_with_lang == []


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


def test_docx_conversion_propagates_inspection_and_editorial_diagnostics() -> None:
    inspection = inspect_docx_file(FIXTURES / "native-editorial.docx")
    result = convert_docx_to_tei_from_inspection_for_test(inspection)
    codes = [diagnostic.code for diagnostic in result.diagnostics]

    assert result.xml_bytes is None
    assert "deferred_paragraph_style" in codes
    assert "unsupported_character_style" in codes
    assert "tab_in_editorial_content" in codes
    assert "drawing_not_editorially_interpreted" in codes
    assert [diagnostic.origin for diagnostic in result.diagnostics].index("editorial") >= 0


def test_precontrol_keeps_deterministic_order_for_inspection_then_editorial() -> None:
    inspection = inspect_docx_file(FIXTURES / "native-tei-conversion.docx")
    inspection = replace(
        inspection,
        issues=(
            InspectionIssue("comments_not_inspected", "commentaire", "info", "word/comments.xml"),
        ),
    )
    consumed = extract_metadata_suggestions(inspection).consumed_paragraph_indexes
    editorial = build_editorial_document(inspection, excluded_body_paragraph_indexes=frozenset(consumed))

    diagnostics = prepare_tei_conversion(inspection, editorial)

    assert [diagnostic.origin for diagnostic in diagnostics[:1]] == ["inspection"]
    assert [diagnostic.code for diagnostic in diagnostics] == ["comments_not_inspected"]


def test_precontrol_blocks_numbered_paragraphs_in_body_and_notes() -> None:
    inspection = inspect_docx_file(FIXTURES / "native-tei-conversion.docx")
    body_paragraph = replace(inspection.paragraphs[0], numbering_id="42", numbering_level=1)
    note = inspection.footnotes[0]
    note_paragraph = replace(note.paragraphs[0], numbering_id="43", numbering_level=0)
    inspection = replace(
        inspection,
        paragraphs=(body_paragraph,) + inspection.paragraphs[1:],
        footnotes=(replace(note, paragraphs=(note_paragraph,) + note.paragraphs[1:]),) + inspection.footnotes[1:],
    )

    result = convert_docx_to_tei_from_inspection_for_test(inspection)
    numbered = [diagnostic for diagnostic in result.diagnostics if diagnostic.code == "numbered_paragraph_not_serializable"]

    assert result.xml_bytes is None
    assert [(diagnostic.source_part, diagnostic.note_id) for diagnostic in numbered] == [
        ("word/document.xml", None),
        ("word/footnotes.xml", "1"),
    ]


def test_precontrol_blocks_unknown_break_types() -> None:
    inspection = inspect_docx_file(FIXTURES / "native-tei-conversion.docx")
    run = inspection.paragraphs[2].runs[0]
    changed_run = replace(
        run,
        contents=run.contents + (RunContentInfo(kind="break", break_type="section"),),
    )
    changed_paragraph = replace(
        inspection.paragraphs[2],
        runs=(changed_run,) + inspection.paragraphs[2].runs[1:],
    )
    inspection = replace(
        inspection,
        paragraphs=inspection.paragraphs[:2] + (changed_paragraph,) + inspection.paragraphs[3:],
    )

    result = convert_docx_to_tei_from_inspection_for_test(inspection)

    assert result.xml_bytes is None
    assert "unsupported_break_type" in [diagnostic.code for diagnostic in result.diagnostics]


def test_hyperlink_character_styles_are_recognized_without_extra_marks() -> None:
    inspection = inspect_docx_file(FIXTURES / "native-tei-conversion.docx")
    paragraph = inspection.paragraphs[4]
    link_run = next(run for run in paragraph.runs if run.hyperlink_relationship_id == "rIdHyper")
    followed_run = replace(link_run, text=" lien suivi", style_id="FollowedHyperlink")
    hyperlink_run = replace(link_run, style_id="Hyperlink")
    paragraph = replace(
        paragraph,
        runs=tuple(hyperlink_run if run is link_run else run for run in paragraph.runs) + (followed_run,),
    )
    inspection = replace(
        inspection,
        paragraphs=inspection.paragraphs[:2] + (paragraph,) + inspection.paragraphs[3:],
    )
    editorial = build_editorial_document(inspection)

    assert "unsupported_character_style" not in [diagnostic.code for diagnostic in editorial.diagnostics]


def test_non_blocking_inspection_diagnostics_are_preserved_on_success() -> None:
    inspection = inspect_docx_file(FIXTURES / "native-tei-conversion.docx")
    inspection = replace(
        inspection,
        issues=(
            InspectionIssue("comments_not_inspected", "commentaires presents", "info", "word/comments.xml"),
            InspectionIssue("headers_footers_not_inspected", "en-tetes presents", "info", None),
        ),
    )

    result = convert_docx_to_tei_from_inspection_for_test(inspection)

    assert result.is_successful
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "comments_not_inspected",
        "headers_footers_not_inspected",
    ]


def test_header_footer_static_text_blocks_conversion() -> None:
    """Un en-tete/pied de page porteur de texte redige ne doit pas disparaitre
    silencieusement de la TEI (contrairement a un champ automatique)."""
    inspection = inspect_docx_file(FIXTURES / "native-tei-conversion.docx")
    inspection = replace(
        inspection,
        issues=(
            InspectionIssue(
                "header_footer_text_not_serializable",
                "titre courant redige",
                "warning",
                "word/header1.xml",
            ),
        ),
    )

    result = convert_docx_to_tei_from_inspection_for_test(inspection)

    assert result.xml_bytes is None
    assert "header_footer_text_not_serializable" in [diagnostic.code for diagnostic in result.diagnostics]


def test_blocking_inspection_diagnostics_prevent_serialization() -> None:
    inspection = inspect_docx_file(FIXTURES / "native-tei-conversion.docx")
    for code in ("textboxes_not_inspected", "table_in_note_not_serializable"):
        changed = replace(
            inspection,
            issues=(InspectionIssue(code, f"{code} present", "info", "word/document.xml"),),
        )
        result = convert_docx_to_tei_from_inspection_for_test(changed)
        assert result.xml_bytes is None
        assert [diagnostic.code for diagnostic in result.diagnostics] == [code]


def test_heading_in_note_is_reported_without_type_error() -> None:
    document = EditorialDocument(
        source_name="heading-note.docx",
        blocks=(Paragraph((NoteReference("1", "footnote"),), 0, "Normal"),),
        notes=(
            EditorialNote(
                note_id="1",
                note_kind="footnote",
                blocks=(Heading(1, (TextSpan("Titre dans note"),), 0, "Heading1"),),
            ),
        ),
    )

    result = serialize_editorial_document_to_tei(document)

    assert result.xml_bytes is None
    assert "heading_in_note_not_serializable" in [diagnostic.code for diagnostic in result.diagnostics]


def test_empty_quote_containers_are_explicitly_rejected(document) -> None:
    result = serialize_editorial_document_to_tei(
        replace(document, blocks=(ProseQuote(paragraphs=()), VerseQuote(stanzas=())), notes=())
    )

    assert result.xml_bytes is None
    assert "empty_prose_quote_not_serializable" in [diagnostic.code for diagnostic in result.diagnostics]
    assert "empty_verse_quote_not_serializable" in [diagnostic.code for diagnostic in result.diagnostics]


def convert_docx_to_tei_from_inspection_for_test(inspection):
    consumed = extract_metadata_suggestions(inspection).consumed_paragraph_indexes
    editorial = build_editorial_document(inspection, excluded_body_paragraph_indexes=frozenset(consumed))
    diagnostics = prepare_tei_conversion(inspection, editorial)
    if any(diagnostic.severity == "error" for diagnostic in diagnostics):
        from mini_metopes.tei import TeiConversionResult

        return TeiConversionResult(None, diagnostics, ())
    return serialize_editorial_document_to_tei(editorial.document, initial_diagnostics=diagnostics)
