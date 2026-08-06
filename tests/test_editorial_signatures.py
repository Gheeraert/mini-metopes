"""Signature d'auteur Word native (style ``Signature``), decision 0028."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from lxml import etree

from mini_metopes.docx import inspect_docx_file
from mini_metopes.editorial import Paragraph, build_editorial_document
from mini_metopes.metadata import (
    Contributor,
    extract_metadata_suggestions,
    load_metadata_file,
    metadata_consistency_issues,
)
from mini_metopes.tei import convert_docx_to_tei
from test_docx_numbering import paragraph, runtime_docx, write_docx

FIXTURES = Path(__file__).parent / "fixtures"
METADATA = FIXTURES / "metadata" / "native-tei-conversion.metadata.json"
NS = {"tei": "http://www.tei-c.org/ns/1.0"}

STYLES = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>
  <w:style w:type="paragraph" w:styleId="Signature"><w:name w:val="Signature"/></w:style>
</w:styles>
"""


def _metadata():
    loaded = load_metadata_file(METADATA)
    assert loaded.metadata is not None
    return loaded.metadata


def _runtime_docx(name: str, body: str, *, footnotes: str | None = None) -> Path:
    path = runtime_docx(name)
    write_docx(path, body, styles=STYLES, footnotes=footnotes)
    return path


def _codes(path: Path) -> list[str]:
    return [diagnostic.code for diagnostic in convert_docx_to_tei(path, metadata=_metadata()).diagnostics]


def test_single_terminal_signature_line_becomes_a_plain_paragraph() -> None:
    body = paragraph("Titre", style="Heading1") + paragraph("Corps du texte.") + paragraph("Claire Dubuisson", style="Signature")
    path = _runtime_docx("signature-single.docx", body)

    built = build_editorial_document(inspect_docx_file(path))

    last = built.document.blocks[-1]
    assert isinstance(last, Paragraph)
    assert last.content[0].text == "Claire Dubuisson"
    assert last.rendition is None
    assert "misplaced_signature_not_serializable" not in [d.code for d in built.diagnostics]


def test_two_terminal_signature_lines_become_two_paragraphs_in_order() -> None:
    body = (
        paragraph("Titre", style="Heading1")
        + paragraph("Corps du texte.")
        + paragraph("Claire Dubuisson", style="Signature")
        + paragraph("Universite de Rouen", style="Signature")
    )
    path = _runtime_docx("signature-double.docx", body)

    built = build_editorial_document(inspect_docx_file(path))

    last_two = built.document.blocks[-2:]
    assert all(isinstance(block, Paragraph) for block in last_two)
    assert [block.content[0].text for block in last_two] == ["Claire Dubuisson", "Universite de Rouen"]


def test_trailing_empty_signature_paragraph_does_not_count_toward_the_limit() -> None:
    """Artefact Word reel : le "style suivant" de Signature est lui-meme, une
    simple touche Entree laisse un paragraphe Signature vide en fin de bloc."""
    body = (
        paragraph("Titre", style="Heading1")
        + paragraph("Corps du texte.")
        + paragraph("Claire Dubuisson", style="Signature")
        + paragraph("Universite de Rouen", style="Signature")
        + '<w:p><w:pPr><w:pStyle w:val="Signature"/></w:pPr></w:p>'
    )
    path = _runtime_docx("signature-trailing-empty.docx", body)

    built = build_editorial_document(inspect_docx_file(path))

    assert "misplaced_signature_not_serializable" not in [d.code for d in built.diagnostics]
    last_two = built.document.blocks[-2:]
    assert [block.content[0].text for block in last_two] == ["Claire Dubuisson", "Universite de Rouen"]


def test_signature_not_at_the_end_is_refused() -> None:
    body = (
        paragraph("Titre", style="Heading1")
        + paragraph("Claire Dubuisson", style="Signature")
        + paragraph("Corps du texte apres la signature.")
    )
    path = _runtime_docx("signature-misplaced.docx", body)

    assert "misplaced_signature_not_serializable" in _codes(path)


def test_more_than_two_terminal_signature_lines_are_refused() -> None:
    body = (
        paragraph("Titre", style="Heading1")
        + paragraph("Corps du texte.")
        + paragraph("Claire Dubuisson", style="Signature")
        + paragraph("Universite de Rouen", style="Signature")
        + paragraph("Ligne surnumeraire.", style="Signature")
    )
    path = _runtime_docx("signature-toolong.docx", body)

    assert "misplaced_signature_not_serializable" in _codes(path)


def test_signature_inside_a_note_is_refused() -> None:
    body = paragraph("Titre", style="Heading1") + '<w:p><w:r><w:footnoteReference w:id="1"/></w:r></w:p>'
    footnotes = (
        '<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:footnote w:id="1">' + paragraph("Signature dans une note.", style="Signature") + "</w:footnote>"
        "</w:footnotes>"
    )
    path = _runtime_docx("signature-note.docx", body, footnotes=footnotes)

    assert "misplaced_signature_not_serializable" in _codes(path)


def test_signature_serializes_as_a_plain_paragraph_without_rend() -> None:
    body = (
        paragraph("Titre de section", style="Heading1")
        + paragraph("Corps du texte.")
        + paragraph("Claire Dubuisson", style="Signature")
        + paragraph("Universite de Rouen", style="Signature")
    )
    path = _runtime_docx("signature-tei.docx", body)

    result = convert_docx_to_tei(path, metadata=_metadata())

    assert result.is_successful, result.diagnostics
    tree = etree.fromstring(result.xml_bytes)
    paragraphs = tree.xpath("//tei:body/tei:div/tei:p", namespaces=NS)
    assert [p.text for p in paragraphs[-2:]] == ["Claire Dubuisson", "Universite de Rouen"]
    assert all(p.get("rend") is None for p in paragraphs[-2:])


def test_extraction_reads_terminal_signature_without_consuming_it() -> None:
    body = (
        paragraph("Titre", style="Heading1")
        + paragraph("Corps du texte.")
        + paragraph("Claire Dubuisson", style="Signature")
        + paragraph("Universite de Rouen", style="Signature")
    )
    path = _runtime_docx("signature-suggestion.docx", body)

    suggestions = extract_metadata_suggestions(inspect_docx_file(path))

    assert suggestions.signature_name == "Claire Dubuisson"
    assert suggestions.signature_affiliation == "Universite de Rouen"
    assert suggestions.consumed_paragraph_indexes == ()


def test_extraction_ignores_more_than_two_terminal_signature_lines() -> None:
    body = (
        paragraph("Titre", style="Heading1")
        + paragraph("Claire Dubuisson", style="Signature")
        + paragraph("Universite de Rouen", style="Signature")
        + paragraph("Surplus.", style="Signature")
    )
    path = _runtime_docx("signature-suggestion-toolong.docx", body)

    suggestions = extract_metadata_suggestions(inspect_docx_file(path))

    assert suggestions.signature_name is None
    assert suggestions.signature_affiliation is None


def test_consistency_check_warns_when_signature_has_no_matching_contributor() -> None:
    body = paragraph("Titre", style="Heading1") + paragraph("Corps.") + paragraph("Auteur Inconnu", style="Signature")
    path = _runtime_docx("signature-mismatch.docx", body)
    suggestions = extract_metadata_suggestions(inspect_docx_file(path))
    metadata = replace(_metadata(), contributors=(Contributor("p1", "author", given_name="Autre", family_name="Personne"),))

    issues = metadata_consistency_issues(metadata, path, suggestions)

    assert "signature_contributor_not_in_metadata" in [issue.code for issue in issues]


def test_consistency_check_is_silent_when_signature_matches_a_contributor() -> None:
    body = paragraph("Titre", style="Heading1") + paragraph("Corps.") + paragraph("Claire Dubuisson", style="Signature")
    path = _runtime_docx("signature-match.docx", body)
    suggestions = extract_metadata_suggestions(inspect_docx_file(path))
    metadata = replace(_metadata(), contributors=(Contributor("p1", "author", given_name="Claire", family_name="Dubuisson"),))

    issues = metadata_consistency_issues(metadata, path, suggestions)

    assert "signature_contributor_not_in_metadata" not in [issue.code for issue in issues]
