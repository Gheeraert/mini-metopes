"""Epigraphes Word natives (style ``Salutation``), decision 0027."""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from mini_metopes.docx import inspect_docx_file
from mini_metopes.editorial import Epigraph, Heading, build_editorial_document
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
  <w:style w:type="paragraph" w:styleId="Salutation"><w:name w:val="Salutation"/></w:style>
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


def test_salutation_after_heading_becomes_a_single_paragraph_epigraph() -> None:
    body = paragraph("Habiter la marge", style="Heading1") + paragraph("Vivre, c'est resister.", style="Salutation") + paragraph("Corps du texte.")
    path = _runtime_docx("epigraph-single.docx", body)

    built = build_editorial_document(inspect_docx_file(path))

    epigraphs = [block for block in built.document.blocks if isinstance(block, Epigraph)]
    assert len(epigraphs) == 1
    assert len(epigraphs[0].paragraphs) == 1
    assert epigraphs[0].paragraphs[0].content[0].text == "Vivre, c'est resister."
    assert "misplaced_epigraph_not_serializable" not in [d.code for d in built.diagnostics]


def test_consecutive_salutation_paragraphs_form_one_epigraph() -> None:
    body = (
        paragraph("Titre", style="Heading1")
        + paragraph("Premiere ligne.", style="Salutation")
        + paragraph("Seconde ligne (attribution).", style="Salutation")
        + paragraph("Corps du texte.")
    )
    path = _runtime_docx("epigraph-multi.docx", body)

    built = build_editorial_document(inspect_docx_file(path))

    epigraphs = [block for block in built.document.blocks if isinstance(block, Epigraph)]
    assert len(epigraphs) == 1
    assert [p.content[0].text for p in epigraphs[0].paragraphs] == [
        "Premiere ligne.",
        "Seconde ligne (attribution).",
    ]


def test_salutation_at_document_start_without_a_heading_is_accepted() -> None:
    """Le tout debut du document (aucun bloc precedent) compte comme tete de section."""
    body = paragraph("Epigraphe liminaire.", style="Salutation") + paragraph("Corps du texte.")
    path = _runtime_docx("epigraph-start.docx", body)

    built = build_editorial_document(inspect_docx_file(path))

    epigraphs = [block for block in built.document.blocks if isinstance(block, Epigraph)]
    assert len(epigraphs) == 1


def test_salutation_not_after_a_heading_is_refused() -> None:
    body = (
        paragraph("Titre", style="Heading1")
        + paragraph("Un paragraphe ordinaire.")
        + paragraph("Epigraphe mal placee.", style="Salutation")
    )
    path = _runtime_docx("epigraph-misplaced.docx", body)

    assert "misplaced_epigraph_not_serializable" in _codes(path)


def test_salutation_inside_a_note_is_refused() -> None:
    body = paragraph("Titre", style="Heading1") + '<w:p><w:r><w:footnoteReference w:id="1"/></w:r></w:p>'
    footnotes = (
        '<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:footnote w:id="1">' + paragraph("Epigraphe dans une note.", style="Salutation") + "</w:footnote>"
        "</w:footnotes>"
    )
    path = _runtime_docx("epigraph-note.docx", body, footnotes=footnotes)

    assert "misplaced_epigraph_not_serializable" in _codes(path)


def test_epigraph_serializes_between_head_and_body_content() -> None:
    body = (
        paragraph("Titre de section", style="Heading1")
        + paragraph("Premiere ligne.", style="Salutation")
        + paragraph("Seconde ligne.", style="Salutation")
        + paragraph("Corps du texte.")
    )
    path = _runtime_docx("epigraph-tei.docx", body)

    result = convert_docx_to_tei(path, metadata=_metadata())

    assert result.is_successful, result.diagnostics
    tree = etree.fromstring(result.xml_bytes)
    division = tree.xpath("//tei:body/tei:div", namespaces=NS)[0]
    children = [etree.QName(child).localname for child in division]
    assert children[0] == "head"
    assert children[1] == "epigraph"
    epigraph = division.xpath("tei:epigraph", namespaces=NS)[0]
    assert [p.text for p in epigraph.xpath("tei:p", namespaces=NS)] == ["Premiere ligne.", "Seconde ligne."]


def test_empty_epigraph_paragraph_is_refused_at_serialization() -> None:
    body = paragraph("Titre", style="Heading1") + '<w:p><w:pPr><w:pStyle w:val="Salutation"/></w:pPr></w:p>'
    path = _runtime_docx("epigraph-empty.docx", body)

    assert "empty_epigraph_paragraph_not_serializable" in _codes(path)
