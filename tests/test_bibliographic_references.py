"""References bibliographiques Word controlees et bibliographie finale."""

from __future__ import annotations

from pathlib import Path

from lxml import etree

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


ROOT = Path(__file__).parent / "fixtures"
DOCX = ROOT / "docx" / "native-bibliographic-references.docx"
METADATA = ROOT / "metadata" / "native-bibliographic-references.metadata.json"
NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def _metadata():
    loaded = load_metadata_file(METADATA)
    assert loaded.metadata is not None
    return loaded.metadata


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
    tree = etree.fromstring(result.xml_bytes)
    assert len(tree.xpath("/tei:TEI/tei:text/tei:body//tei:p/tei:bibl", namespaces=NS)) == 1
    assert len(tree.xpath("/tei:TEI/tei:text/tei:body//tei:cit/tei:bibl", namespaces=NS)) == 2
    assert len(tree.xpath("/tei:TEI/tei:text/tei:back/tei:div[@type='bibliography']/tei:listBibl/tei:bibl", namespaces=NS)) == 3
    assert tree.xpath("string(/tei:TEI/tei:text/tei:back/tei:div[@type='bibliography']/tei:head)", namespaces=NS) == "Bibliographie"


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
