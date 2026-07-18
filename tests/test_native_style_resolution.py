"""Resolution multilingue deterministe des styles Word natifs."""

from __future__ import annotations

from pathlib import Path

from mini_metopes.docx import StyleInfo, inspect_docx_file
from mini_metopes.editorial import build_editorial_document
from mini_metopes.editorial.convention import (
    NATIVE_WORD_CONVENTION,
    native_style_alias_map,
    resolve_convention_for_styles,
)
from mini_metopes.editorial.model import Heading, Paragraph, ProseQuote, VerseQuote
from mini_metopes.tei import prepare_tei_conversion

from test_docx_numbering import runtime_docx, write_docx


def _style(
    style_id: str,
    name: str | None,
    *,
    style_type: str = "paragraph",
    is_custom: bool | None = None,
    based_on: str | None = None,
) -> StyleInfo:
    return StyleInfo(
        style_id=style_id,
        name=name,
        style_type=style_type,
        based_on=based_on,
        linked_style=None,
        is_default=False,
        is_custom=is_custom,
        outline_level=None,
        quick_format=None,
        ui_priority=None,
    )


FRENCH_WORD_STYLES = (
    # Word francais : styleId localise, w:name canonique anglais.
    _style("Titre1", "heading 1"),
    _style("Titre2", "heading 2"),
    _style("Corpsdetexte", "Body Text"),
    _style("Citationintense", "Intense Quote"),
    _style("Paragraphedeliste", "List Paragraph"),
    _style("Notedebasdepage", "footnote text"),
    _style("Appelnotedebasdep", "footnote reference", style_type="character"),
    _style("Lienhypertexte", "Hyperlink", style_type="character"),
)


def test_french_word_style_ids_resolve_through_canonical_names() -> None:
    aliases = native_style_alias_map(FRENCH_WORD_STYLES)
    assert aliases == {
        "Titre1": "Heading1",
        "Titre2": "Heading2",
        "Corpsdetexte": "BodyText",
        "Citationintense": "IntenseQuote",
        "Paragraphedeliste": "ListParagraph",
        "Notedebasdepage": "FootnoteText",
        "Appelnotedebasdep": "FootnoteReference",
        "Lienhypertexte": "Hyperlink",
    }


def test_localized_display_names_resolve_with_case_space_and_accent_folding() -> None:
    aliases = native_style_alias_map(
        (
            _style("S1", "TITRE  1"),
            _style("S2", "Citation intense"),
            _style("S3", "Légende"),
            _style("S4", "Elevé", style_type="character"),
            _style("S5", "accentuation", style_type="character"),
        )
    )
    assert aliases == {
        "S1": "Heading1",
        "S2": "IntenseQuote",
        "S3": "Caption",
        "S4": "Strong",
        "S5": "Emphasis",
    }


def test_custom_styles_never_resolve_even_with_native_names() -> None:
    aliases = native_style_alias_map(
        (
            _style("MaCitation", "Citation", is_custom=True),
            _style("TEIquote", "TEI_quote", is_custom=True),
            _style("FauxTitre", "heading 1", is_custom=True),
        )
    )
    assert aliases == {}


def test_canonical_identifiers_are_never_resignified_by_name() -> None:
    aliases = native_style_alias_map((_style("Quote", "heading 1"),))
    assert aliases == {}


def test_based_on_does_not_transmit_native_identity() -> None:
    aliases = native_style_alias_map(
        (
            _style("Normal", "Normal"),
            _style("StyleMaison", "Style maison", based_on="Normal"),
        )
    )
    assert "StyleMaison" not in aliases


def test_character_and_paragraph_name_tables_are_type_separated() -> None:
    aliases = native_style_alias_map(
        (
            # Un style de caractere nomme comme un style de paragraphe natif
            # ne doit pas etre reconnu, et inversement.
            _style("C1", "Citation", style_type="character"),
            _style("P1", "Emphasis", style_type="paragraph"),
        )
    )
    assert aliases == {}


def test_resolved_convention_extends_all_native_sets() -> None:
    convention = resolve_convention_for_styles(NATIVE_WORD_CONVENTION, FRENCH_WORD_STYLES)
    assert convention.paragraph_role("Titre1", None).heading_level == 1
    assert convention.paragraph_role("Titre2", None).heading_level == 2
    role = convention.paragraph_role("Corpsdetexte", None)
    assert role.kind == "paragraph" and role.paragraph_rendition == "consecutive"
    assert convention.paragraph_role("Citationintense", None).kind == "verse_quote"
    assert convention.paragraph_role("Paragraphedeliste", None).kind == "paragraph"
    assert convention.paragraph_role("Notedebasdepage", None).kind == "paragraph"
    assert convention.is_list_continuation_style("Paragraphedeliste", None)
    assert convention.character_marks("Lienhypertexte") == ()
    assert convention.character_marks("Appelnotedebasdep") == ()


def test_resolution_without_aliases_returns_convention_unchanged() -> None:
    assert resolve_convention_for_styles(NATIVE_WORD_CONVENTION, ()) is NATIVE_WORD_CONVENTION


FRENCH_STYLES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Titre1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Titre2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="1"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Citation"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Citationintense"><w:name w:val="Intense Quote"/><w:basedOn w:val="Citation"/></w:style>
  <w:style w:type="paragraph" w:styleId="Corpsdetexte"><w:name w:val="Body Text"/><w:basedOn w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:customStyle="1" w:styleId="TEIquote"><w:name w:val="TEI_quote"/><w:basedOn w:val="Normal"/></w:style>
</w:styles>
"""


def _french_document_body() -> str:
    return (
        '<w:p><w:pPr><w:pStyle w:val="Titre1"/></w:pPr><w:r><w:t>Section</w:t></w:r></w:p>'
        '<w:p><w:pPr><w:pStyle w:val="Titre2"/></w:pPr><w:r><w:t>Sous-section</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>Paragraphe normal.</w:t></w:r></w:p>'
        '<w:p><w:pPr><w:pStyle w:val="Corpsdetexte"/></w:pPr><w:r><w:t>Paragraphe de suite.</w:t></w:r></w:p>'
        '<w:p><w:pPr><w:pStyle w:val="Citation"/></w:pPr><w:r><w:t>Citation en prose.</w:t></w:r></w:p>'
        '<w:p><w:pPr><w:pStyle w:val="Citationintense"/></w:pPr><w:r><w:t>Un vers</w:t><w:br/><w:t>Un autre vers</w:t></w:r></w:p>'
    )


def test_french_word_document_builds_the_same_editorial_model() -> None:
    source = runtime_docx("french-native-styles.docx")
    write_docx(source, _french_document_body(), styles=FRENCH_STYLES_XML)

    result = build_editorial_document(inspect_docx_file(source))

    blocks = result.document.blocks
    assert isinstance(blocks[0], Heading) and blocks[0].level == 1
    assert isinstance(blocks[1], Heading) and blocks[1].level == 2
    assert isinstance(blocks[2], Paragraph) and blocks[2].rendition is None
    assert isinstance(blocks[3], Paragraph) and blocks[3].rendition == "consecutive"
    assert isinstance(blocks[4], ProseQuote)
    assert isinstance(blocks[5], VerseQuote)
    assert not [d for d in result.diagnostics if d.severity == "error"]


def test_tei_quote_custom_style_is_rejected_as_unsupported() -> None:
    """Perimetre voulu : les styles Metopes ``TEI_*`` ne sont pas des entrees.

    Ce test documente l'absence deliberee de compatibilite avec les styles
    personnalises de la chaine Metopes et empeche une reintroduction
    accidentelle d'un mapping ``TEI_quote`` en entree.
    """
    source = runtime_docx("tei-quote-rejected.docx")
    write_docx(
        source,
        '<w:p><w:pPr><w:pStyle w:val="TEIquote"/></w:pPr><w:r><w:t>Citation Metopes.</w:t></w:r></w:p>',
        styles=FRENCH_STYLES_XML,
    )

    inspection = inspect_docx_file(source)
    result = build_editorial_document(inspection)

    rejected = [
        diagnostic
        for diagnostic in result.diagnostics
        if diagnostic.code == "unsupported_paragraph_style" and diagnostic.style_id == "TEIquote"
    ]
    assert rejected
    assert not [
        block
        for block in result.document.blocks
        if isinstance(block, (ProseQuote, VerseQuote))
    ]

    conversion_diagnostics = prepare_tei_conversion(inspection, result)
    assert any(
        diagnostic.code == "unsupported_paragraph_style"
        and diagnostic.severity == "error"
        and diagnostic.style_id == "TEIquote"
        for diagnostic in conversion_diagnostics
    )
