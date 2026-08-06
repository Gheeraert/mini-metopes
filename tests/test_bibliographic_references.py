"""References bibliographiques Word controlees et bibliographie finale."""

from __future__ import annotations

from pathlib import Path
from lxml import etree

from mini_metopes.cli import main
from mini_metopes.editorial import (
    BibliographicReference,
    BibliographicReferenceInline,
    EditorialBibliography,
    EditorialDocument,
    NATIVE_WORD_CONVENTION,
    Paragraph,
    TextSpan,
    build_editorial_document,
    editorial_build_result_to_json,
)
from mini_metopes.docx import inspect_docx_file
from mini_metopes.metadata import load_metadata_file
from mini_metopes.tei import convert_docx_to_tei
from mini_metopes.tei.serializer import serialize_editorial_document_to_tei
from mini_metopes.validation import validate_xml_bytes
from test_docx_numbering import basic_numbering, runtime_docx, write_docx


ROOT = Path(__file__).parent / "fixtures"
DOCX = ROOT / "docx" / "native-bibliographic-references.docx"
METADATA = ROOT / "metadata" / "native-bibliographic-references.metadata.json"
NS = {"tei": "http://www.tei-c.org/ns/1.0"}


STYLES = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Citation"/></w:style>
  <w:style w:type="paragraph" w:styleId="IntenseQuote"><w:name w:val="Citation intense"/></w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="Paragraphe de liste"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="Titre 1"/></w:style>
  <w:style w:type="paragraph" w:customStyle="1" w:styleId="TEIbiblstart"><w:name w:val="TEI_bibl_start"/></w:style>
  <w:style w:type="paragraph" w:customStyle="1" w:styleId="TEIbiblreference"><w:name w:val="TEI_bibl_reference"/></w:style>
  <w:style w:type="character" w:customStyle="1" w:styleId="TEIbiblreference-inline"><w:name w:val="TEI_bibl_reference-inline"/></w:style>
</w:styles>
"""

TABLE_XML = (
    "<w:tbl><w:tblGrid><w:gridCol/></w:tblGrid>"
    "<w:tr><w:tc><w:p><w:r><w:t>Cellule.</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
)


def _metadata():
    loaded = load_metadata_file(METADATA)
    assert loaded.metadata is not None
    return loaded.metadata


def _paragraph(text: str, style: str = "Normal") -> str:
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>'


def _bibl_inline_run(text: str) -> str:
    return f'<w:r><w:rPr><w:rStyle w:val="TEIbiblreference-inline"/></w:rPr><w:t>{text}</w:t></w:r>'


def _bibl_reference(text: str = "Reference.", *, inline: bool = False, numbered: bool = False) -> str:
    numbering = '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="42"/></w:numPr>' if numbered else ""
    content = _bibl_inline_run(text) if inline else f"<w:r><w:t>{text}</w:t></w:r>"
    return f'<w:p><w:pPr><w:pStyle w:val="TEIbiblreference"/>{numbering}</w:pPr>{content}</w:p>'


def _runtime_docx(name: str, body: str, *, styles: str = STYLES, numbering: str | None = None) -> Path:
    path = runtime_docx(name)
    write_docx(path, body, styles=styles, numbering=numbering)
    return path


def _codes(path: Path) -> list[str]:
    return [diagnostic.code for diagnostic in convert_docx_to_tei(path, metadata=_metadata()).diagnostics]


def _assert_cli_refuses_atomically(path: Path, destination: Path, code: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("<old/>", encoding="utf-8")
    before = {item.name for item in destination.parent.iterdir()}

    assert code in _codes(path)
    assert main(["convert-docx", str(path), str(destination), "--metadata", str(METADATA)]) == 1

    assert destination.read_text(encoding="utf-8") == "<old/>"
    assert {item.name for item in destination.parent.iterdir()} == before
    media = destination.parent / "media"
    assert not media.exists() or not any(media.iterdir())


def test_controlled_bibliographic_styles_are_strict() -> None:
    convention = NATIVE_WORD_CONVENTION
    assert convention.is_bibliography_start_style("TEIbiblstart", "TEI_bibl_start", True, "paragraph")
    assert convention.is_bibliographic_reference_style("TEIbiblreference", "TEI_bibl_reference", True, "paragraph")
    assert convention.is_bibliographic_reference_inline_style(
        "TEIbiblreference-inline", "TEI_bibl_reference-inline", True, "character"
    )
    assert not convention.is_bibliographic_reference_style("TEIbiblreference", "TEI_bibl_reference", False, "paragraph")
    assert not convention.is_bibliographic_reference_style("TEIbiblreference", "wrong", True, "paragraph")
    assert not convention.is_bibliographic_reference_inline_style(
        "TEIbiblreference-inline", "TEI_bibl_reference-inline", True, "paragraph"
    )
    assert convention.bibliography_start_style_status("TEIbiblstart", "wrong", True, "paragraph") == "invalid"
    assert convention.bibliographic_reference_style_status("Local", "TEI_bibl_reference", True, "paragraph") == "invalid"
    assert convention.bibliographic_reference_inline_style_status(
        "TEIbiblreference-inline", "TEI_bibl_reference-inline", None, "character"
    ) == "invalid"


def test_fixture_builds_sources_inline_references_and_final_bibliography() -> None:
    built = build_editorial_document(inspect_docx_file(DOCX))
    document = built.document
    assert document.bibliography is not None
    assert len(document.bibliography.entries) == 3
    assert sum(block.kind == "bibliographic_reference" for block in document.blocks) == 1
    assert sum(getattr(block, "source", None) is not None for block in document.blocks) == 2
    assert "bibliographic_reference_inline" in editorial_build_result_to_json(built)


def test_fixture_serializes_bibliographic_structures_and_validates() -> None:
    result = convert_docx_to_tei(DOCX, metadata=_metadata())
    assert result.is_successful
    assert result.xml_bytes is not None
    assert validate_xml_bytes(result.xml_bytes).valid
    tree = etree.fromstring(result.xml_bytes)
    assert tree.xpath("count(/tei:TEI/tei:text/tei:body//tei:p[starts-with(string(), 'Voir')]/tei:bibl)", namespaces=NS) == 1.0
    assert tree.xpath("count(/tei:TEI/tei:text/tei:body//tei:item/tei:p/tei:bibl)", namespaces=NS) == 2.0
    assert tree.xpath("count(/tei:TEI/tei:text/tei:body//tei:table//tei:bibl)", namespaces=NS) == 1.0
    assert tree.xpath("count(/tei:TEI/tei:text/tei:body//tei:note//tei:bibl)", namespaces=NS) == 1.0
    assert tree.xpath("count(/tei:TEI/tei:text/tei:body//tei:figure/tei:p[@rend='caption']/tei:bibl)", namespaces=NS) == 1.0
    assert len(tree.xpath("/tei:TEI/tei:text/tei:body//tei:cit/tei:bibl", namespaces=NS)) == 2
    assert len(tree.xpath("/tei:TEI/tei:text/tei:back/tei:div[@type='bibliography']/tei:listBibl/tei:bibl", namespaces=NS)) == 3
    assert tree.xpath("string(/tei:TEI/tei:text/tei:back/tei:div[@type='bibliography']/tei:head)", namespaces=NS) == "Bibliographie"
    assert tree.xpath("count(/tei:TEI/tei:text/tei:body//tei:bibl/tei:bibl)", namespaces=NS) == 0.0
    first_inline = tree.xpath("/tei:TEI/tei:text/tei:body//tei:p[starts-with(string(), 'Voir')]/tei:bibl", namespaces=NS)[0]
    assert first_inline.xpath("count(./tei:hi[@rend='bold italic small-caps sup'])", namespaces=NS) == 1.0
    assert first_inline.xpath("string(./tei:ref/@target)", namespaces=NS) == "https://example.test/bibl"


def test_model_docx_counts_inline_references_recursively(capsys) -> None:
    assert main(["model-docx", str(DOCX)]) == 0
    captured = capsys.readouterr()

    assert "References bibliographiques inline : 6" in captured.out
    assert "Citations avec source : 2" in captured.out


def test_manual_bibliography_and_inline_reference_are_defensive() -> None:
    inline = BibliographicReferenceInline((TextSpan("Dupont, 2024"),))
    entry = BibliographicReference((TextSpan("Dupont, 2024."),), 1, "TEIbiblreference")
    document = EditorialDocument(
        "manual.docx", (Paragraph((TextSpan("Voir "), inline), 0, "Normal"),), (),
        bibliography=EditorialBibliography((TextSpan("Bibliographie"),), 2, "TEIbiblstart", (entry,)),
    )
    result = serialize_editorial_document_to_tei(document)
    assert result.is_successful
    assert result.xml_bytes is not None
    tree = etree.fromstring(result.xml_bytes)
    assert tree.xpath("string(//tei:p/tei:bibl)", namespaces=NS) == "Dupont, 2024"


def test_empty_bibliography_is_refused() -> None:
    document = EditorialDocument(
        "manual.docx", (), (), bibliography=EditorialBibliography((TextSpan("Bibliographie"),), 1, "TEIbiblstart", ())
    )
    result = serialize_editorial_document_to_tei(document)
    assert result.xml_bytes is None
    assert {diagnostic.code for diagnostic in result.diagnostics} >= {"bibliography_without_entries_not_serializable"}


def test_nested_bibliographic_inline_is_refused_in_all_bibl_contexts() -> None:
    cases = {
        "standalone": _bibl_reference("Nested.", inline=True),
        "source": _paragraph("Citation.", "Quote") + _bibl_reference("Nested source.", inline=True),
        "entry": _paragraph("Bibliographie", "TEIbiblstart") + _bibl_reference("Nested entry.", inline=True),
        "title": '<w:p><w:pPr><w:pStyle w:val="TEIbiblstart"/></w:pPr>' + _bibl_inline_run("Nested title.") + "</w:p>" + _bibl_reference(),
    }
    for name, body in cases.items():
        path = _runtime_docx(f"bibl-nested-{name}.docx", body)
        assert "nested_bibliographic_reference_not_serializable" in _codes(path)


def test_manual_nested_bibliographic_inline_is_rejected_by_serializer() -> None:
    inline = BibliographicReferenceInline((TextSpan("interne"),))
    cases = [
        EditorialDocument("manual.docx", (BibliographicReference((inline,), 1, "TEIbiblreference"),), ()),
        EditorialDocument(
            "manual.docx",
            (),
            (),
            bibliography=EditorialBibliography((inline,), 1, "TEIbiblstart", (BibliographicReference((TextSpan("Entree"),), 2, "TEIbiblreference"),)),
        ),
    ]
    for document in cases:
        result = serialize_editorial_document_to_tei(document)
        assert result.xml_bytes is None
        assert "nested_bibliographic_reference_not_serializable" in [diagnostic.code for diagnostic in result.diagnostics]


def test_invalid_controlled_bibliographic_styles_use_dedicated_codes() -> None:
    style_cases = [
        ("start-wrong-name", STYLES.replace("TEI_bibl_start", "wrong"), _paragraph("Bibliographie", "TEIbiblstart"), "invalid_bibliography_start_style"),
        ("start-wrong-id", STYLES.replace('w:styleId="TEIbiblstart"', 'w:styleId="LocalBiblStart"'), _paragraph("Bibliographie", "LocalBiblStart"), "invalid_bibliography_start_style"),
        ("start-not-custom", STYLES.replace(' w:customStyle="1" w:styleId="TEIbiblstart"', ' w:styleId="TEIbiblstart"'), _paragraph("Bibliographie", "TEIbiblstart"), "invalid_bibliography_start_style"),
        ("start-wrong-type", STYLES.replace('w:type="paragraph" w:customStyle="1" w:styleId="TEIbiblstart"', 'w:type="character" w:customStyle="1" w:styleId="TEIbiblstart"'), _paragraph("Bibliographie", "TEIbiblstart"), "invalid_bibliography_start_style"),
        ("start-missing-definition", STYLES.replace('<w:style w:type="paragraph" w:customStyle="1" w:styleId="TEIbiblstart"><w:name w:val="TEI_bibl_start"/></w:style>', ""), _paragraph("Bibliographie", "TEIbiblstart"), "invalid_bibliography_start_style"),
        ("reference-wrong-name", STYLES.replace("TEI_bibl_reference", "wrong"), _bibl_reference(), "invalid_bibliographic_reference_style"),
        ("reference-wrong-id", STYLES.replace('w:styleId="TEIbiblreference"', 'w:styleId="LocalBiblReference"'), _paragraph("Reference.", "LocalBiblReference"), "invalid_bibliographic_reference_style"),
        ("reference-not-custom", STYLES.replace(' w:customStyle="1" w:styleId="TEIbiblreference"', ' w:styleId="TEIbiblreference"'), _bibl_reference(), "invalid_bibliographic_reference_style"),
        ("reference-wrong-type", STYLES.replace('w:type="paragraph" w:customStyle="1" w:styleId="TEIbiblreference"', 'w:type="character" w:customStyle="1" w:styleId="TEIbiblreference"'), _bibl_reference(), "invalid_bibliographic_reference_style"),
        ("reference-missing-definition", STYLES.replace('<w:style w:type="paragraph" w:customStyle="1" w:styleId="TEIbiblreference"><w:name w:val="TEI_bibl_reference"/></w:style>', ""), _bibl_reference(), "invalid_bibliographic_reference_style"),
    ]
    for name, styles, body, code in style_cases:
        path = _runtime_docx(f"bibl-invalid-{name}.docx", body, styles=styles)
        codes = _codes(path)
        assert code in codes
        assert "unsupported_paragraph_style" not in codes

    inline_cases = [
        ("wrong-name", STYLES.replace("TEI_bibl_reference-inline", "wrong")),
        ("wrong-id", STYLES.replace('w:styleId="TEIbiblreference-inline"', 'w:styleId="LocalBiblInline"').replace('w:val="TEIbiblreference-inline"', 'w:val="LocalBiblInline"')),
        ("not-custom", STYLES.replace(' w:customStyle="1" w:styleId="TEIbiblreference-inline"', ' w:styleId="TEIbiblreference-inline"')),
        ("wrong-type", STYLES.replace('w:type="character" w:customStyle="1" w:styleId="TEIbiblreference-inline"', 'w:type="paragraph" w:customStyle="1" w:styleId="TEIbiblreference-inline"')),
        ("missing-definition", STYLES.replace('<w:style w:type="character" w:customStyle="1" w:styleId="TEIbiblreference-inline"><w:name w:val="TEI_bibl_reference-inline"/></w:style>', "")),
    ]
    for name, styles in inline_cases:
        path = _runtime_docx(f"bibl-inline-invalid-{name}.docx", '<w:p><w:r><w:rPr><w:rStyle w:val="TEIbiblreference-inline"/></w:rPr><w:t>Inline</w:t></w:r></w:p>', styles=styles)
        codes = _codes(path)
        assert "invalid_bibliographic_reference_inline_style" in codes
        assert "unsupported_character_style" not in codes


def test_multiple_bibliography_starts_are_diagnosed_once_per_faulty_paragraph() -> None:
    path = _runtime_docx(
        "bibl-multiple-starts.docx",
        _paragraph("Bibliographie", "TEIbiblstart") + _bibl_reference("Un.") + _paragraph("Bis", "TEIbiblstart") + _bibl_reference("Deux."),
    )
    result = build_editorial_document(inspect_docx_file(path))
    diagnostics = [item for item in result.diagnostics if item.code == "multiple_bibliographies_not_serializable"]

    assert len(diagnostics) == 1
    assert diagnostics[0].paragraph_index == 2


def test_bibliographic_transitions_are_preserved() -> None:
    path = _runtime_docx(
        "bibl-transitions.docx",
        _paragraph("Citation.", "Quote")
        + _bibl_reference("Source.")
        + TABLE_XML
        + _paragraph("Apres.")
        + _paragraph("Citation 2.", "Quote")
        + TABLE_XML
        + _bibl_reference("Autonome.")
        + _paragraph("Bibliographie", "TEIbiblstart")
        + _bibl_reference("Entree."),
    )
    result = convert_docx_to_tei(path, metadata=_metadata())
    assert result.xml_bytes is not None
    root = etree.fromstring(result.xml_bytes)
    body_tags = [etree.QName(child).localname for child in root.xpath("/tei:TEI/tei:text/tei:body/*", namespaces=NS)]

    assert body_tags[:6] == ["cit", "table", "p", "quote", "table", "bibl"]
    assert root.xpath("count(/tei:TEI/tei:text/tei:body/tei:cit/tei:bibl)", namespaces=NS) == 1.0


def test_bibliographic_refusals_cover_blocks_inline_and_bibliography() -> None:
    cases = {
        "empty-reference": (_bibl_reference(""), "empty_bibliographic_reference_not_serializable", None),
        "numbered-reference": (_bibl_reference("Numbered.", numbered=True), "numbered_bibliographic_reference_not_serializable", basic_numbering()),
        "two-sources": (_paragraph("Citation.", "Quote") + _bibl_reference("Source 1.") + _bibl_reference("Source 2."), "multiple_bibliographic_sources_not_serializable", None),
        "empty-title": (_paragraph("", "TEIbiblstart") + _bibl_reference("Entree."), "empty_bibliography_title_not_serializable", None),
        "no-entry": (_paragraph("Bibliographie", "TEIbiblstart"), "bibliography_without_entries_not_serializable", None),
        "nonterminal-normal": (_paragraph("Bibliographie", "TEIbiblstart") + _bibl_reference("Entree.") + _paragraph("Apres."), "nonterminal_bibliography_not_serializable", None),
        "title-after-start": (_paragraph("Bibliographie", "TEIbiblstart") + _bibl_reference("Entree.") + _paragraph("Titre", "Heading1"), "nonterminal_bibliography_not_serializable", None),
        "table-after-start": (_paragraph("Bibliographie", "TEIbiblstart") + _bibl_reference("Entree.") + TABLE_XML, "nonterminal_bibliography_not_serializable", None),
        "empty-inline": ('<w:p><w:r><w:rPr><w:rStyle w:val="TEIbiblreference-inline"/></w:rPr></w:r></w:p>', "empty_bibliographic_reference_inline_not_serializable", None),
        "bibl-start-note": (_paragraph("Corps."), "bibliography_in_note_not_serializable", None),
    }
    for name, (body, code, numbering) in cases.items():
        if name == "bibl-start-note":
            path = runtime_docx("bibl-start-note.docx")
            footnotes = '<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:footnote w:id="1">' + _paragraph("Bibliographie", "TEIbiblstart") + "</w:footnote></w:footnotes>"
            write_docx(path, body, styles=STYLES, footnotes=footnotes)
        else:
            path = _runtime_docx(f"bibl-refusal-{name}.docx", body, numbering=numbering)
        assert code in _codes(path)


def test_cli_refusals_are_atomic_for_bibliographic_errors(tmp_path: Path) -> None:
    cases = {
        "nonterminal": (
            _paragraph("Bibliographie", "TEIbiblstart") + _bibl_reference("Entree.") + _paragraph("Apres."),
            "nonterminal_bibliography_not_serializable",
            None,
        ),
        "numbered": (_bibl_reference("Numbered.", numbered=True), "numbered_bibliographic_reference_not_serializable", basic_numbering()),
        "nested": (_bibl_reference("Nested.", inline=True), "nested_bibliographic_reference_not_serializable", None),
    }
    for name, (body, code, numbering) in cases.items():
        path = _runtime_docx(f"bibl-cli-{name}.docx", body, numbering=numbering)
        _assert_cli_refuses_atomically(path, tmp_path / name / "book.xml", code)


NATIVE_BIBLIOGRAPHY_STYLES = STYLES.replace(
    "</w:styles>",
    '  <w:style w:type="paragraph" w:styleId="Bibliography"><w:name w:val="Bibliography"/></w:style>\n</w:styles>',
)


CUSTOM_FLAGGED_BIBLIOGRAPHY_STYLES = STYLES.replace(
    "</w:styles>",
    '  <w:style w:type="paragraph" w:customStyle="1" w:styleId="Bibliography"><w:name w:val="Bibliography"/></w:style>\n</w:styles>',
)


def _native_bibl_entry(text: str) -> str:
    return _paragraph(text, "Bibliography")


def test_native_bibliography_style_is_recognized_even_when_word_marks_it_custom() -> None:
    """Corpus reel : Word peut ecrire w:customStyle="1" sur Bibliography meme
    applique tel quel depuis la galerie, sans passer par le gestionnaire de
    citations. Exiger l'absence de customStyle rejetait ce document reel."""
    body = _paragraph("Corps du texte.") + _native_bibl_entry("Premiere reference.") + _native_bibl_entry("Seconde reference.")
    path = _runtime_docx("native-bibliography-custom-flag.docx", body, styles=CUSTOM_FLAGGED_BIBLIOGRAPHY_STYLES)

    built = build_editorial_document(inspect_docx_file(path))

    assert built.document.bibliography is not None
    assert len(built.document.bibliography.entries) == 2
    assert "unsupported_paragraph_style" not in [d.code for d in built.diagnostics]


def test_native_bibliography_style_needs_no_controlled_start_style() -> None:
    """Le style natif Word Bibliography suffit seul : pas de TEIbiblstart."""
    body = _paragraph("Corps du texte.") + _native_bibl_entry("Premiere reference.") + _native_bibl_entry("Seconde reference.")
    path = _runtime_docx("native-bibliography.docx", body, styles=NATIVE_BIBLIOGRAPHY_STYLES)

    built = build_editorial_document(inspect_docx_file(path))

    assert built.document.bibliography is not None
    assert built.document.bibliography.title == ()
    assert len(built.document.bibliography.entries) == 2


def test_native_bibliography_style_serializes_without_a_head() -> None:
    body = _paragraph("Corps du texte.") + _native_bibl_entry("Premiere reference.") + _native_bibl_entry("Seconde reference.")
    path = _runtime_docx("native-bibliography-tei.docx", body, styles=NATIVE_BIBLIOGRAPHY_STYLES)

    result = convert_docx_to_tei(path, metadata=_metadata())

    assert result.is_successful, result.diagnostics
    tree = etree.fromstring(result.xml_bytes)
    list_bibl = tree.xpath("//tei:back/tei:div[@type='bibliography']/tei:listBibl", namespaces=NS)[0]
    assert list_bibl.xpath("tei:head", namespaces=NS) == []
    assert len(list_bibl.xpath("tei:bibl", namespaces=NS)) == 2


def test_native_bibliography_style_still_refuses_content_after_it() -> None:
    """Meme regle "unique et terminale" que TEIbiblstart, sans style de debut dedie."""
    body = _native_bibl_entry("Reference.") + _paragraph("Apres.")
    path = _runtime_docx("native-bibliography-nonterminal.docx", body, styles=NATIVE_BIBLIOGRAPHY_STYLES)

    assert "nonterminal_bibliography_not_serializable" in _codes(path)
