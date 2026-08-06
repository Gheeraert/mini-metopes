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

STYLES_WITH_BIBLIOGRAPHY = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>
  <w:style w:type="paragraph" w:styleId="Signature"><w:name w:val="Signature"/></w:style>
  <w:style w:type="paragraph" w:styleId="Bibliography"><w:name w:val="Bibliography"/></w:style>
</w:styles>
"""

STYLES_MULTI_LEVEL = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading4"><w:name w:val="heading 4"/></w:style>
  <w:style w:type="paragraph" w:styleId="Signature"><w:name w:val="Signature"/></w:style>
</w:styles>
"""


def _multi_level_docx(name: str, body: str) -> Path:
    path = runtime_docx(name)
    write_docx(path, body, styles=STYLES_MULTI_LEVEL)
    return path


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


def test_signature_followed_by_a_titre2_pivot_heading_is_accepted() -> None:
    """Livre a plusieurs contributions (decision 0037) : la signature d'une
    contribution peut preceder le Titre2 (pivot chapitre/contribution) de
    la contribution suivante."""
    body = (
        paragraph("Contribution un", style="Heading2")
        + paragraph("Corps du texte.")
        + paragraph("Claire Dubuisson", style="Signature")
        + paragraph("Universite de Rouen", style="Signature")
        + paragraph("Contribution deux", style="Heading2")
        + paragraph("Corps du texte.")
        + paragraph("Autre Auteur", style="Signature")
    )
    path = _multi_level_docx("signature-titre2-next.docx", body)

    built = build_editorial_document(inspect_docx_file(path))

    assert "misplaced_signature_not_serializable" not in [d.code for d in built.diagnostics]
    signature_texts = [
        block.content[0].text
        for block in built.document.blocks
        if isinstance(block, Paragraph) and block.content and block.content[0].text in {"Claire Dubuisson", "Autre Auteur"}
    ]
    assert signature_texts == ["Claire Dubuisson", "Autre Auteur"]


def test_signature_followed_by_a_titre1_part_heading_is_accepted() -> None:
    body = (
        paragraph("Chapitre", style="Heading2")
        + paragraph("Corps du texte.")
        + paragraph("Claire Dubuisson", style="Signature")
        + paragraph("Partie suivante", style="Heading1")
        + paragraph("Chapitre suivant", style="Heading2")
        + paragraph("Corps du texte.")
    )
    path = _multi_level_docx("signature-titre1-next.docx", body)

    built = build_editorial_document(inspect_docx_file(path))

    assert "misplaced_signature_not_serializable" not in [d.code for d in built.diagnostics]


def test_signature_followed_by_a_titre3_section_heading_is_refused() -> None:
    """Titre3 est desormais une section interne a la contribution, plus une
    frontiere : la signature ne peut pas le preceder (decision 0037)."""
    body = (
        paragraph("Contribution", style="Heading2")
        + paragraph("Corps du texte.")
        + paragraph("Claire Dubuisson", style="Signature")
        + paragraph("Section", style="Heading3")
    )
    path = _multi_level_docx("signature-titre3-next.docx", body)

    built = build_editorial_document(inspect_docx_file(path))

    assert "misplaced_signature_not_serializable" in [d.code for d in built.diagnostics]


def test_signature_followed_by_a_titre4_subsection_heading_is_refused() -> None:
    body = (
        paragraph("Contribution", style="Heading2")
        + paragraph("Corps du texte.")
        + paragraph("Claire Dubuisson", style="Signature")
        + paragraph("Sous-section", style="Heading4")
    )
    path = _multi_level_docx("signature-titre4-next.docx", body)

    built = build_editorial_document(inspect_docx_file(path))

    assert "misplaced_signature_not_serializable" in [d.code for d in built.diagnostics]


def test_signature_inside_a_note_is_refused() -> None:
    body = paragraph("Titre", style="Heading1") + '<w:p><w:r><w:footnoteReference w:id="1"/></w:r></w:p>'
    footnotes = (
        '<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:footnote w:id="1">' + paragraph("Signature dans une note.", style="Signature") + "</w:footnote>"
        "</w:footnotes>"
    )
    path = _runtime_docx("signature-note.docx", body, footnotes=footnotes)

    assert "misplaced_signature_not_serializable" in _codes(path)


def test_signature_followed_by_a_native_bibliography_heading_is_accepted() -> None:
    """Corpus reel : la bibliographie generale du livre (Titre1) suit la
    signature de la contribution. Le titre precedent la bibliographie
    native en devient le <head> (decision 0031), rendant la signature
    a nouveau terminale par rapport au corps de la contribution."""
    body = (
        paragraph("Titre", style="Heading1")
        + paragraph("Corps du texte.")
        + paragraph("Claire Dubuisson", style="Signature")
        + paragraph("Universite de Rouen", style="Signature")
        + paragraph("Bibliographie", style="Heading1")
        + paragraph("Reference un.", style="Bibliography")
        + paragraph("Reference deux.", style="Bibliography")
    )
    path = runtime_docx("signature-then-bibliography.docx")
    write_docx(path, body, styles=STYLES_WITH_BIBLIOGRAPHY)

    built = build_editorial_document(inspect_docx_file(path))

    assert "misplaced_signature_not_serializable" not in [d.code for d in built.diagnostics]
    assert built.document.bibliography is not None
    assert built.document.bibliography.title[0].text == "Bibliographie"
    assert len(built.document.bibliography.entries) == 2
    last_two = built.document.blocks[-2:]
    assert [block.content[0].text for block in last_two] == ["Claire Dubuisson", "Universite de Rouen"]


def test_trailing_page_break_only_signature_paragraph_does_not_count() -> None:
    """Corpus reel : un saut de page force avant la section suivante peut
    atterrir sur un paragraphe Signature vide (le "style suivant" de
    Signature est lui-meme)."""
    body = (
        paragraph("Titre", style="Heading1")
        + paragraph("Corps du texte.")
        + paragraph("Claire Dubuisson", style="Signature")
        + paragraph("Universite de Rouen", style="Signature")
        + '<w:p><w:pPr><w:pStyle w:val="Signature"/></w:pPr><w:r><w:br w:type="page"/></w:r></w:p>'
    )
    path = _runtime_docx("signature-trailing-page-break.docx", body)

    built = build_editorial_document(inspect_docx_file(path))

    assert "misplaced_signature_not_serializable" not in [d.code for d in built.diagnostics]
    last_two = built.document.blocks[-2:]
    assert [block.content[0].text for block in last_two] == ["Claire Dubuisson", "Universite de Rouen"]


def test_trailing_page_break_on_a_normal_paragraph_after_signature_is_accepted() -> None:
    """Corpus reel : le saut de page manuel qui suit une signature atterrit
    parfois sur un paragraphe qui ne porte plus le style Signature (le
    style suivant a ete change, ou l'auteur a valide le style suivant
    propose par Word). Decision 0035."""
    body = (
        paragraph("Titre", style="Heading1")
        + paragraph("Corps du texte.")
        + paragraph("Claire Dubuisson", style="Signature")
        + paragraph("Universite de Rouen", style="Signature")
        + '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
    )
    path = _runtime_docx("signature-trailing-normal-page-break.docx", body)

    built = build_editorial_document(inspect_docx_file(path))

    assert "misplaced_signature_not_serializable" not in [d.code for d in built.diagnostics]
    assert "empty_paragraph_ignored" in [d.code for d in built.diagnostics]
    last_two = built.document.blocks[-2:]
    assert [block.content[0].text for block in last_two] == ["Claire Dubuisson", "Universite de Rouen"]


def test_page_break_after_signature_no_longer_blocks_tei_generation() -> None:
    """Reproduction directe du bug signale : un saut de page apres une
    signature bloquait la generation TEI (``break_not_serializable``),
    meme quand la signature elle-meme etait valide (decision 0035)."""
    body = (
        paragraph("Titre", style="Heading1")
        + paragraph("Corps du texte.")
        + paragraph("Claire Dubuisson", style="Signature")
        + paragraph("Universite de Rouen", style="Signature")
        + '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
    )
    path = _runtime_docx("signature-page-break-tei.docx", body)

    result = convert_docx_to_tei(path, metadata=_metadata())

    assert result.is_successful, result.diagnostics
    assert "break_not_serializable" not in [d.code for d in result.diagnostics]
    tree = etree.fromstring(result.xml_bytes)
    paragraphs = tree.xpath("//tei:body//tei:p", namespaces=NS)
    assert [p.text for p in paragraphs[-2:]] == ["Claire Dubuisson", "Universite de Rouen"]


def test_page_break_on_a_normal_paragraph_before_the_next_contribution_is_accepted() -> None:
    """Le meme saut de page, cette fois entre deux contributions d'un
    livre (decision 0037) : la signature reste terminale par rapport a la
    contribution qui precede."""
    body = (
        paragraph("Contribution un", style="Heading2")
        + paragraph("Corps du texte.")
        + paragraph("Claire Dubuisson", style="Signature")
        + '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
        + paragraph("Contribution deux", style="Heading2")
        + paragraph("Corps du texte.")
        + paragraph("Autre Auteur", style="Signature")
    )
    path = _multi_level_docx("signature-page-break-next-contribution.docx", body)

    built = build_editorial_document(inspect_docx_file(path))

    assert "misplaced_signature_not_serializable" not in [d.code for d in built.diagnostics]


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

    assert len(suggestions.signatures) == 1
    assert suggestions.signatures[0].name == "Claire Dubuisson"
    assert suggestions.signatures[0].affiliation == "Universite de Rouen"
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

    assert suggestions.signatures == ()


def test_extraction_reads_one_signature_per_contribution() -> None:
    body = (
        paragraph("Contribution un", style="Heading3")
        + paragraph("Corps du texte.")
        + paragraph("Claire Dubuisson", style="Signature")
        + paragraph("Universite de Rouen", style="Signature")
        + paragraph("Contribution deux", style="Heading3")
        + paragraph("Corps du texte.")
        + paragraph("Autre Auteur", style="Signature")
    )
    path = _multi_level_docx("signature-suggestion-multi.docx", body)

    suggestions = extract_metadata_suggestions(inspect_docx_file(path))

    assert [(s.name, s.affiliation) for s in suggestions.signatures] == [
        ("Claire Dubuisson", "Universite de Rouen"),
        ("Autre Auteur", None),
    ]


def test_consistency_check_warns_per_unmatched_signature_with_distinct_paths() -> None:
    body = (
        paragraph("Contribution un", style="Heading3")
        + paragraph("Corps.")
        + paragraph("Claire Dubuisson", style="Signature")
        + paragraph("Contribution deux", style="Heading3")
        + paragraph("Corps.")
        + paragraph("Auteur Inconnu", style="Signature")
    )
    path = _multi_level_docx("signature-mismatch-multi.docx", body)
    suggestions = extract_metadata_suggestions(inspect_docx_file(path))
    metadata = replace(_metadata(), contributors=(Contributor("p1", "author", given_name="Claire", family_name="Dubuisson"),))

    issues = metadata_consistency_issues(metadata, path, suggestions)

    mismatch_issues = [issue for issue in issues if issue.code == "signature_contributor_not_in_metadata"]
    assert len(mismatch_issues) == 1
    assert mismatch_issues[0].path == "signatures[1]"


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
