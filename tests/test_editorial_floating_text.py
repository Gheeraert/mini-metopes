"""Encadres Word natifs (style ``BlockText`` -> floatingText), decision 0029."""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from mini_metopes.docx import inspect_docx_file
from mini_metopes.editorial import FloatingText, Paragraph, build_editorial_document
from mini_metopes.metadata import load_metadata_file
from mini_metopes.tei import convert_docx_to_tei
from test_docx_numbering import paragraph, runtime_docx, write_docx

FIXTURES = Path(__file__).parent / "fixtures"
METADATA = FIXTURES / "metadata" / "native-tei-conversion.metadata.json"
NS = {"tei": "http://www.tei-c.org/ns/1.0"}

STYLES = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>
  <w:style w:type="paragraph" w:styleId="BlockText"><w:name w:val="Block Text"/></w:style>
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


def test_block_text_paragraph_becomes_a_floating_text() -> None:
    body = (
        paragraph("Titre", style="Heading1")
        + paragraph("Avant l'encadre.")
        + paragraph("Contenu de l'encadre.", style="BlockText")
        + paragraph("Apres l'encadre.")
    )
    path = _runtime_docx("floating-single.docx", body)

    built = build_editorial_document(inspect_docx_file(path))

    floats = [block for block in built.document.blocks if isinstance(block, FloatingText)]
    assert len(floats) == 1
    assert len(floats[0].paragraphs) == 1
    assert floats[0].paragraphs[0].content[0].text == "Contenu de l'encadre."
    # L'encadre n'interrompt pas le reste du flux : le texte apres reste present.
    assert any(
        isinstance(block, Paragraph) and block.content and block.content[0].text == "Apres l'encadre."
        for block in built.document.blocks
    )


def test_consecutive_block_text_paragraphs_form_one_floating_text() -> None:
    body = (
        paragraph("Titre", style="Heading1")
        + paragraph("Premiere ligne d'encadre.", style="BlockText")
        + paragraph("Seconde ligne d'encadre.", style="BlockText")
        + paragraph("Corps du texte.")
    )
    path = _runtime_docx("floating-multi.docx", body)

    built = build_editorial_document(inspect_docx_file(path))

    floats = [block for block in built.document.blocks if isinstance(block, FloatingText)]
    assert len(floats) == 1
    assert [p.content[0].text for p in floats[0].paragraphs] == [
        "Premiere ligne d'encadre.",
        "Seconde ligne d'encadre.",
    ]


def test_block_text_can_appear_anywhere_without_positional_constraint() -> None:
    """Contrairement a Epigraph/Signature, aucune contrainte de position."""
    body = (
        paragraph("Corps avant.")
        + paragraph("Encadre au milieu du texte.", style="BlockText")
        + paragraph("Corps apres.")
    )
    path = _runtime_docx("floating-anywhere.docx", body)

    assert "misplaced_epigraph_not_serializable" not in _codes(path)
    assert "misplaced_signature_not_serializable" not in _codes(path)
    built = build_editorial_document(inspect_docx_file(_runtime_docx("floating-anywhere-2.docx", body)))
    assert any(isinstance(block, FloatingText) for block in built.document.blocks)


def test_block_text_inside_a_note_is_refused() -> None:
    body = paragraph("Titre", style="Heading1") + '<w:p><w:r><w:footnoteReference w:id="1"/></w:r></w:p>'
    footnotes = (
        '<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:footnote w:id="1">' + paragraph("Encadre dans une note.", style="BlockText") + "</w:footnote>"
        "</w:footnotes>"
    )
    path = _runtime_docx("floating-note.docx", body, footnotes=footnotes)

    assert "floating_text_in_note_not_serializable" in _codes(path)


def test_floating_text_serializes_as_a_nested_body() -> None:
    body = (
        paragraph("Titre de section", style="Heading1")
        + paragraph("Avant.")
        + paragraph("Premiere ligne.", style="BlockText")
        + paragraph("Seconde ligne.", style="BlockText")
        + paragraph("Apres.")
    )
    path = _runtime_docx("floating-tei.docx", body)

    result = convert_docx_to_tei(path, metadata=_metadata())

    assert result.is_successful, result.diagnostics
    tree = etree.fromstring(result.xml_bytes)
    floating = tree.xpath("//tei:body/tei:div/tei:floatingText", namespaces=NS)[0]
    inner_body = floating.xpath("tei:body", namespaces=NS)[0]
    assert [p.text for p in inner_body.xpath("tei:p", namespaces=NS)] == ["Premiere ligne.", "Seconde ligne."]
    # Le flux principal se poursuit normalement de part et d'autre.
    division_children = [etree.QName(child).localname for child in tree.xpath("//tei:body/tei:div", namespaces=NS)[0]]
    assert division_children == ["head", "p", "floatingText", "p"]


def test_empty_floating_text_paragraph_is_refused_at_serialization() -> None:
    body = paragraph("Titre", style="Heading1") + '<w:p><w:pPr><w:pStyle w:val="BlockText"/></w:pPr></w:p>'
    path = _runtime_docx("floating-empty.docx", body)

    assert "empty_floating_text_not_serializable" in _codes(path)
