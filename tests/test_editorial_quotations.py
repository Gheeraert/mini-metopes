"""Tests de la convention native Word pour les citations prose et poetiques."""

from __future__ import annotations

from pathlib import Path

import pytest

from mini_metopes.docx import inspect_docx_file
from mini_metopes.editorial import (
    LineBreak,
    NATIVE_WORD_CONVENTION,
    NoteReference,
    PageBreak,
    ProseQuote,
    TextSpan,
    VerseQuote,
    build_editorial_document,
    editorial_build_result_to_json,
)


FIXTURES = Path(__file__).parent / "fixtures" / "docx"


@pytest.fixture()
def quotation_result():
    return build_editorial_document(inspect_docx_file(FIXTURES / "native-quotations.docx"))


def test_quote_roles_use_stable_identifiers_and_override_outline_levels() -> None:
    assert NATIVE_WORD_CONVENTION.paragraph_role("Quote", 0).kind == "prose_quote"
    assert NATIVE_WORD_CONVENTION.paragraph_role("IntenseQuote", 1).kind == "verse_quote"
    assert NATIVE_WORD_CONVENTION.paragraph_role("Title", 0).kind == "deferred"
    assert NATIVE_WORD_CONVENTION.paragraph_role("Subtitle", 1).kind == "deferred"


def test_consecutive_prose_quote_paragraphs_are_grouped_without_losing_boundaries(quotation_result) -> None:
    prose_quotes = [block for block in quotation_result.document.blocks if isinstance(block, ProseQuote)]
    assert [len(quote.paragraphs) for quote in prose_quotes] == [2, 2]
    first = prose_quotes[0].paragraphs[0]
    assert first.source_paragraph_index == 0
    assert isinstance(first.content[0], TextSpan)
    assert first.content[0].marks == ("bold",)
    assert any(isinstance(item, LineBreak) for item in first.content)
    assert any(isinstance(item, NoteReference) and item.note_id == "30" for item in first.content)
    link = next(item for item in first.content if isinstance(item, TextSpan) and item.text == " lien")
    assert link.link is not None and link.link.target == "https://example.test/quote-body"
    assert prose_quotes[1].paragraphs[-1].content == ()
    assert prose_quotes[0].paragraphs[1].content[0] == TextSpan(text="Second paragraphe.")
    assert "empty_prose_quote_paragraph" in [item.code for item in quotation_result.diagnostics]


def test_verse_quotes_preserve_stanzas_lines_and_inline_order(quotation_result) -> None:
    verse_quotes = [block for block in quotation_result.document.blocks if isinstance(block, VerseQuote)]
    assert [len(quote.stanzas) for quote in verse_quotes] == [4, 1]
    first_stanza = verse_quotes[0].stanzas[0]
    assert [line.line_index for line in first_stanza.lines] == [0, 1, 2, 3]
    assert first_stanza.lines[0].content == (TextSpan(text="Vers un"),)
    assert first_stanza.lines[2].content == ()
    second_line = first_stanza.lines[1]
    assert any(isinstance(item, NoteReference) and item.note_id == "30" for item in second_line.content)
    final_line = first_stanza.lines[3]
    assert any(isinstance(item, PageBreak) for item in final_line.content)
    assert any(isinstance(item, TextSpan) and item.link is not None for item in final_line.content)
    assert any(item.code == "empty_verse" for item in quotation_result.diagnostics)
    assert any(item.code == "empty_verse_stanza" for item in quotation_result.diagnostics)
    assert [line.line_index for line in verse_quotes[1].stanzas[0].lines] == [0, 1, 2]


def test_notes_apply_the_same_quote_convention_and_their_own_relationship_scope(quotation_result) -> None:
    footnote = next(note for note in quotation_result.document.notes if note.note_id == "30")
    assert isinstance(footnote.blocks[0], ProseQuote)
    assert isinstance(footnote.blocks[1], VerseQuote)
    note_line = footnote.blocks[1].stanzas[0].lines[-1]
    link = next(item for item in note_line.content if isinstance(item, TextSpan) and item.text == " lien-note")
    assert link.link is not None
    assert link.link.target == "https://example.test/quote-footnote"
    endnote = next(note for note in quotation_result.document.notes if note.note_id == "40")
    assert isinstance(endnote.blocks[0], VerseQuote)


def test_quote_json_is_deterministic_and_explicit(quotation_result) -> None:
    first = editorial_build_result_to_json(quotation_result).encode("utf-8")
    second = editorial_build_result_to_json(quotation_result).encode("utf-8")
    assert first == second
    assert b'"prose_quote"' in first
    assert b'"verse_stanza"' in first
    assert b'"verse_line"' in first
