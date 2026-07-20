"""Normalisation des paragraphes Word reellement vides et des vers vides.

Un paragraphe Word visuellement vide est generalement un artefact de mise en
page : il ne doit ni produire ``<p/>``/``<l/>``, ni bloquer la generation de
la TEI. Ces tests couvrent la detection centralisee
(``is_semantically_empty_paragraph``), le traitement des paragraphes de prose
et les differents cas de vers vides (debut/fin de bloc, frontiere de strophe,
suites de lignes vides, contexte ambigu).
"""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from mini_metopes.docx import inspect_docx_file
from mini_metopes.editorial import (
    Paragraph,
    TextSpan,
    VerseQuote,
    build_editorial_document_from_file,
    is_semantically_empty_paragraph,
)
from mini_metopes.metadata import load_metadata_file
from mini_metopes.tei import convert_docx_to_tei
from mini_metopes.validation import validate_xml_bytes
from test_docx_numbering import runtime_docx, write_docx


FIXTURES = Path(__file__).parent / "fixtures"
REAL_DOCX = FIXTURES / "docx" / "conclusion_racine_queer_styles_natifs_minimetopes.docx"
REAL_METADATA = FIXTURES / "metadata" / "conclusion_racine_queer_styles_natifs_minimetopes.metadata.json"
NS = {"tei": "http://www.tei-c.org/ns/1.0"}

STYLES = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="IntenseQuote"><w:name w:val="Intense Quote"/></w:style>
</w:styles>
"""


def _write(name: str, body: str, **kwargs) -> Path:
    path = runtime_docx(name)
    write_docx(path, body, styles=STYLES, **kwargs)
    return path


def _p(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def _empty_p() -> str:
    return "<w:p/>"


def _verse_p(*segments: str) -> str:
    """Paragraphe ``IntenseQuote`` dont les segments sont separes par des ``<w:br/>``."""
    runs = "<w:br/>".join(f"<w:t xml:space=\"preserve\">{segment}</w:t>" for segment in segments)
    return f'<w:p><w:pPr><w:pStyle w:val="IntenseQuote"/></w:pPr><w:r>{runs}</w:r></w:p>'


# ---------------------------------------------------------------------------
# Fonction centralisee de detection
# ---------------------------------------------------------------------------


def test_is_semantically_empty_paragraph_flags_only_content_free_paragraphs() -> None:
    path = _write(
        "detection.docx",
        _p("Texte.") + _empty_p(),
    )
    paragraphs = inspect_docx_file(path).paragraphs
    assert is_semantically_empty_paragraph(paragraphs[0]) is False
    assert is_semantically_empty_paragraph(paragraphs[1]) is True


def test_is_semantically_empty_paragraph_rejects_paragraph_with_only_a_footnote() -> None:
    footnotes = """<?xml version="1.0" encoding="UTF-8"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:footnote w:id="1"><w:p><w:r><w:t>Note</w:t></w:r></w:p></w:footnote>
</w:footnotes>
"""
    path = _write(
        "detection-footnote.docx",
        '<w:p><w:r><w:footnoteReference w:id="1"/></w:r></w:p>',
        footnotes=footnotes,
    )
    paragraph = inspect_docx_file(path).paragraphs[0]
    assert paragraph.footnote_reference_ids == ("1",)
    assert is_semantically_empty_paragraph(paragraph) is False


# ---------------------------------------------------------------------------
# Paragraphes ordinaires vides (section 3)
# ---------------------------------------------------------------------------


def test_ordinary_empty_paragraph_between_two_prose_paragraphs_is_dropped() -> None:
    path = _write(
        "ordinary-single-empty.docx",
        _p("Premier paragraphe.") + _empty_p() + _p("Second paragraphe."),
    )
    result = build_editorial_document_from_file(path)

    paragraphs = [block for block in result.document.blocks if isinstance(block, Paragraph)]
    assert [block.content for block in paragraphs] == [
        (TextSpan(text="Premier paragraphe."),),
        (TextSpan(text="Second paragraphe."),),
    ]
    assert [code for code in (d.code for d in result.diagnostics) if code == "empty_paragraph_ignored"] == [
        "empty_paragraph_ignored"
    ]
    assert "empty_paragraph_not_serializable" not in [d.code for d in result.diagnostics]


def test_several_consecutive_empty_paragraphs_are_dropped_without_artificial_structure() -> None:
    path = _write(
        "ordinary-multiple-empty.docx",
        _p("A.") + _empty_p() + _empty_p() + _empty_p() + _p("B."),
    )
    result = build_editorial_document_from_file(path)

    paragraphs = [block for block in result.document.blocks if isinstance(block, Paragraph)]
    assert [block.content for block in paragraphs] == [
        (TextSpan(text="A."),),
        (TextSpan(text="B."),),
    ]
    ignored = [d for d in result.diagnostics if d.code == "empty_paragraph_ignored"]
    assert len(ignored) == 3


def test_empty_paragraphs_at_start_and_end_of_document_are_dropped() -> None:
    path = _write(
        "ordinary-edges-empty.docx",
        _empty_p() + _p("Milieu.") + _empty_p(),
    )
    result = build_editorial_document_from_file(path)

    paragraphs = [block for block in result.document.blocks if isinstance(block, Paragraph)]
    assert len(paragraphs) == 1
    assert paragraphs[0].content == (TextSpan(text="Milieu."),)
    assert len([d for d in result.diagnostics if d.code == "empty_paragraph_ignored"]) == 2


def test_paragraph_with_significant_content_but_no_visible_text_is_preserved() -> None:
    footnotes = """<?xml version="1.0" encoding="UTF-8"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:footnote w:id="1"><w:p><w:r><w:t>Note</w:t></w:r></w:p></w:footnote>
</w:footnotes>
"""
    path = _write(
        "ordinary-significant-empty.docx",
        _p("Avant.") + '<w:p><w:r><w:footnoteReference w:id="1"/></w:r></w:p>' + _p("Apres."),
        footnotes=footnotes,
    )
    result = build_editorial_document_from_file(path)

    paragraphs = [block for block in result.document.blocks if isinstance(block, Paragraph)]
    assert len(paragraphs) == 3
    assert paragraphs[1].content != ()
    assert "empty_paragraph_ignored" not in [d.code for d in result.diagnostics]


# ---------------------------------------------------------------------------
# Vers vides (section 4)
# ---------------------------------------------------------------------------


def test_blank_verse_line_between_two_verses_creates_two_stanzas() -> None:
    path = _write(
        "verse-interior-blank.docx",
        _verse_p("Premier vers", "Second vers", "", "Troisieme vers"),
    )
    result = build_editorial_document_from_file(path)

    verse_quotes = [block for block in result.document.blocks if isinstance(block, VerseQuote)]
    assert len(verse_quotes) == 1
    assert len(verse_quotes[0].stanzas) == 2
    assert [line.content for line in verse_quotes[0].stanzas[0].lines] == [
        (TextSpan(text="Premier vers"),),
        (TextSpan(text="Second vers"),),
    ]
    assert [line.content for line in verse_quotes[0].stanzas[1].lines] == [
        (TextSpan(text="Troisieme vers"),),
    ]
    assert "verse_stanza_break_from_blank_line" in [d.code for d in result.diagnostics]
    assert "empty_verse_not_serializable" not in [d.code for d in result.diagnostics]


def test_several_blank_verse_lines_collapse_to_a_single_stanza_boundary() -> None:
    path = _write(
        "verse-multiple-interior-blank.docx",
        _verse_p("Premier vers", "", "", "", "Second vers"),
    )
    result = build_editorial_document_from_file(path)

    verse_quotes = [block for block in result.document.blocks if isinstance(block, VerseQuote)]
    assert len(verse_quotes[0].stanzas) == 2
    boundary_diagnostics = [d for d in result.diagnostics if d.code == "verse_stanza_break_from_blank_line"]
    assert len(boundary_diagnostics) == 1


def test_blank_verse_lines_at_start_and_end_of_block_are_ignored() -> None:
    path = _write(
        "verse-edges-blank.docx",
        _verse_p("", "Seul vers reel", ""),
    )
    result = build_editorial_document_from_file(path)

    verse_quotes = [block for block in result.document.blocks if isinstance(block, VerseQuote)]
    assert len(verse_quotes) == 1
    assert len(verse_quotes[0].stanzas) == 1
    assert [line.content for line in verse_quotes[0].stanzas[0].lines] == [(TextSpan(text="Seul vers reel"),)]
    assert "verse_stanza_break_from_blank_line" not in [d.code for d in result.diagnostics]


def test_wholly_empty_verse_paragraph_between_two_verse_paragraphs_is_ignored() -> None:
    path = _write(
        "verse-empty-paragraph-between.docx",
        _verse_p("Premiere strophe") + '<w:p><w:pPr><w:pStyle w:val="IntenseQuote"/></w:pPr></w:p>' + _verse_p("Seconde strophe"),
    )
    result = build_editorial_document_from_file(path)

    verse_quotes = [block for block in result.document.blocks if isinstance(block, VerseQuote)]
    assert len(verse_quotes) == 1
    assert [len(stanza.lines) for stanza in verse_quotes[0].stanzas] == [1, 1]
    assert [line.content for stanza in verse_quotes[0].stanzas for line in stanza.lines] == [
        (TextSpan(text="Premiere strophe"),),
        (TextSpan(text="Seconde strophe"),),
    ]
    assert "empty_verse_paragraph_ignored" in [d.code for d in result.diagnostics]
    assert "empty_verse_not_serializable" not in [d.code for d in result.diagnostics]
    assert "empty_verse_stanza_not_serializable" not in [d.code for d in result.diagnostics]


def test_ambiguous_wholly_empty_verse_block_is_reported_and_skipped() -> None:
    path = _write(
        "verse-ambiguous-empty-block.docx",
        _p("Avant.") + '<w:p><w:pPr><w:pStyle w:val="IntenseQuote"/></w:pPr></w:p>' + _p("Apres."),
    )
    result = build_editorial_document_from_file(path)

    assert not any(isinstance(block, VerseQuote) for block in result.document.blocks)
    assert "ambiguous_empty_verse_block" in [d.code for d in result.diagnostics]
    assert "empty_verse_quote_not_serializable" not in [d.code for d in result.diagnostics]


# ---------------------------------------------------------------------------
# Verification bout en bout : absence de <p/>/<l/> et de diagnostics bloquants
# ---------------------------------------------------------------------------


def _metadata():
    loaded = load_metadata_file(REAL_METADATA)
    assert loaded.metadata is not None
    return loaded.metadata


def test_synthetic_document_produces_no_empty_p_or_l_and_no_blocking_diagnostics() -> None:
    path = _write(
        "combined-empty-cases.docx",
        _p("A.")
        + _empty_p()
        + _empty_p()
        + _p("B.")
        + _verse_p("Premier vers", "Second vers", "", "Troisieme vers")
        + '<w:p><w:pPr><w:pStyle w:val="IntenseQuote"/></w:pPr></w:p>'
        + _verse_p("Vers isole"),
    )
    result = convert_docx_to_tei(path, metadata=_metadata())

    assert result.is_successful
    assert result.xml_bytes is not None
    codes = [d.code for d in result.diagnostics]
    assert "empty_paragraph_not_serializable" not in codes
    assert "empty_verse_not_serializable" not in codes

    tree = etree.fromstring(result.xml_bytes)
    assert tree.xpath("count(//tei:p[not(node())])", namespaces=NS) == 0.0
    assert tree.xpath("count(//tei:l[not(node())])", namespaces=NS) == 0.0


def test_real_docx_reproduction_converts_without_blocking_diagnostics() -> None:
    """Reproduction du DOCX reel ayant declenche les quatre diagnostics bloquants."""
    result = convert_docx_to_tei(REAL_DOCX, metadata=_metadata())

    assert result.is_successful
    assert result.xml_bytes is not None
    codes = [d.code for d in result.diagnostics]
    assert "empty_paragraph_not_serializable" not in codes
    assert "empty_verse_not_serializable" not in codes
    assert codes.count("empty_paragraph_ignored") == 3
    assert codes.count("verse_stanza_break_from_blank_line") == 1


def test_real_docx_produces_no_empty_p_or_l_and_validates() -> None:
    result = convert_docx_to_tei(REAL_DOCX, metadata=_metadata())
    assert result.xml_bytes is not None

    tree = etree.fromstring(result.xml_bytes)
    assert tree.xpath("count(//tei:p[not(node())])", namespaces=NS) == 0.0
    assert tree.xpath("count(//tei:l[not(node())])", namespaces=NS) == 0.0

    validation = validate_xml_bytes(result.xml_bytes)
    assert validation.valid
