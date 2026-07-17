"""Construction conservatoire du modele editorial depuis une inspection OOXML."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from mini_metopes.docx import (
    DocxInspection,
    ParagraphInfo,
    RelationshipInfo,
    RunInfo,
    inspect_docx_file,
)

from .convention import NATIVE_WORD_CONVENTION, WordEditorialConvention
from .model import (
    ColumnBreak,
    DrawingReference,
    EditorialBlock,
    EditorialBuildResult,
    EditorialDiagnostic,
    EditorialDocument,
    EditorialInline,
    EditorialLink,
    EditorialNote,
    DiagnosticSeverity,
    Heading,
    LineBreak,
    NoteReference,
    PageBreak,
    Paragraph,
    ProseQuote,
    ProseQuoteParagraph,
    Tab,
    TextMark,
    TextSpan,
    VerseLine,
    VerseQuote,
    VerseStanza,
)


_MARK_ORDER: tuple[TextMark, ...] = (
    "bold",
    "italic",
    "small_caps",
    "caps",
    "superscript",
    "subscript",
)


def build_editorial_document(
    inspection: DocxInspection,
    *,
    convention: WordEditorialConvention = NATIVE_WORD_CONVENTION,
    excluded_body_paragraph_indexes: frozenset[int] = frozenset(),
) -> EditorialBuildResult:
    """Construire un modele editorial immuable sans produire de TEI."""
    diagnostics: list[EditorialDiagnostic] = []
    body_relationships = {relation.relationship_id: relation for relation in inspection.relationships}
    footnote_relationships = {
        relation.relationship_id: relation for relation in inspection.footnote_relationships
    }
    endnote_relationships = {
        relation.relationship_id: relation for relation in inspection.endnote_relationships
    }
    notes_by_key: dict[tuple[str, str], EditorialNote] = {}
    notes: list[EditorialNote] = []
    referenced_notes: set[tuple[str, str]] = set()
    note_sources = (*inspection.footnotes, *inspection.endnotes)
    for note in note_sources:
        key = (note.kind, note.note_id)
        if key in notes_by_key:
            diagnostics.append(
                EditorialDiagnostic(
                    code="duplicate_note_id",
                    severity="warning",
                    message=f"identifiant de note duplique : {note.kind}:{note.note_id}",
                    note_id=note.note_id,
                )
            )
        blocks, note_references = _build_blocks(
            note.paragraphs,
            convention=convention,
            relationships=footnote_relationships if note.kind == "footnote" else endnote_relationships,
            diagnostics=diagnostics,
            note_id=note.note_id,
            detect_heading_jumps=False,
        )
        referenced_notes.update(note_references)
        editorial_note = EditorialNote(
            note_id=note.note_id,
            note_kind=note.kind,
            blocks=blocks,
        )
        notes.append(editorial_note)
        notes_by_key.setdefault(key, editorial_note)

    body_paragraphs = tuple(
        paragraph for paragraph in inspection.paragraphs if paragraph.index not in excluded_body_paragraph_indexes
    )
    blocks, body_references = _build_blocks(
        body_paragraphs,
        convention=convention,
        relationships=body_relationships,
        diagnostics=diagnostics,
        note_id=None,
        detect_heading_jumps=True,
    )
    referenced_notes.update(body_references)
    _diagnose_note_targets(notes_by_key, referenced_notes, diagnostics)

    return EditorialBuildResult(
        document=EditorialDocument(
            source_name=inspection.source.name,
            blocks=blocks,
            notes=tuple(notes),
        ),
        diagnostics=tuple(diagnostics),
    )


def build_editorial_document_from_file(
    path: Path,
    *,
    convention: WordEditorialConvention = NATIVE_WORD_CONVENTION,
) -> EditorialBuildResult:
    """Inspecter un DOCX puis construire son modele editorial sans imprimer."""
    inspection = inspect_docx_file(path)
    return build_editorial_document(inspection, convention=convention)


def _build_blocks(
    paragraphs: tuple[ParagraphInfo, ...],
    *,
    convention: WordEditorialConvention,
    relationships: dict[str, RelationshipInfo],
    diagnostics: list[EditorialDiagnostic],
    note_id: str | None,
    detect_heading_jumps: bool,
) -> tuple[tuple[EditorialBlock, ...], set[tuple[str, str]]]:
    blocks: list[EditorialBlock] = []
    referenced_notes: set[tuple[str, str]] = set()
    previous_heading_level: int | None = None
    paragraph_position = 0
    while paragraph_position < len(paragraphs):
        paragraph = paragraphs[paragraph_position]
        content, references = _build_inline_content(
            paragraph,
            convention=convention,
            relationships=relationships,
            diagnostics=diagnostics,
            note_id=note_id,
        )
        referenced_notes.update(references)
        role = convention.paragraph_role(paragraph.style_id, paragraph.outline_level)
        if role.kind == "heading":
            assert role.heading_level is not None
            heading_level = role.heading_level
            if not content:
                diagnostics.append(
                    EditorialDiagnostic(
                        code="empty_heading",
                        severity="warning",
                        message="titre de section vide",
                        paragraph_index=paragraph.index,
                        style_id=paragraph.style_id,
                        note_id=note_id,
                    )
                )
            if (
                detect_heading_jumps
                and previous_heading_level is not None
                and heading_level > previous_heading_level + 1
            ):
                diagnostics.append(
                    EditorialDiagnostic(
                        code="heading_level_jump",
                        severity="info",
                        message=f"saut de niveau de titre : {previous_heading_level} vers {heading_level}",
                        paragraph_index=paragraph.index,
                        style_id=paragraph.style_id,
                    )
                )
            previous_heading_level = heading_level
            blocks.append(
                Heading(
                    level=heading_level,
                    content=content,
                    source_paragraph_index=paragraph.index,
                    source_style_id=paragraph.style_id,
                )
            )
            paragraph_position += 1
            continue

        if role.kind == "prose_quote":
            quote_paragraphs = [
                ProseQuoteParagraph(
                    content=content,
                    source_paragraph_index=paragraph.index,
                    source_style_id=paragraph.style_id,
                )
            ]
            if not content:
                diagnostics.append(
                    _diagnostic(
                        "empty_prose_quote_paragraph",
                        "warning",
                        "paragraphe de citation en prose vide",
                        paragraph,
                        0,
                        note_id,
                    )
                )
            paragraph_position += 1
            while paragraph_position < len(paragraphs):
                next_paragraph = paragraphs[paragraph_position]
                if convention.paragraph_role(next_paragraph.style_id, next_paragraph.outline_level).kind != "prose_quote":
                    break
                next_content, next_references = _build_inline_content(
                    next_paragraph,
                    convention=convention,
                    relationships=relationships,
                    diagnostics=diagnostics,
                    note_id=note_id,
                )
                referenced_notes.update(next_references)
                quote_paragraphs.append(
                    ProseQuoteParagraph(
                        content=next_content,
                        source_paragraph_index=next_paragraph.index,
                        source_style_id=next_paragraph.style_id,
                    )
                )
                if not next_content:
                    diagnostics.append(
                        _diagnostic(
                            "empty_prose_quote_paragraph",
                            "warning",
                            "paragraphe de citation en prose vide",
                            next_paragraph,
                            0,
                            note_id,
                        )
                    )
                paragraph_position += 1
            blocks.append(ProseQuote(paragraphs=tuple(quote_paragraphs)))
            continue

        if role.kind == "verse_quote":
            stanzas = [_build_verse_stanza(paragraph, content, note_id, diagnostics)]
            paragraph_position += 1
            while paragraph_position < len(paragraphs):
                next_paragraph = paragraphs[paragraph_position]
                if convention.paragraph_role(next_paragraph.style_id, next_paragraph.outline_level).kind != "verse_quote":
                    break
                next_content, next_references = _build_inline_content(
                    next_paragraph,
                    convention=convention,
                    relationships=relationships,
                    diagnostics=diagnostics,
                    note_id=note_id,
                )
                referenced_notes.update(next_references)
                stanzas.append(_build_verse_stanza(next_paragraph, next_content, note_id, diagnostics))
                paragraph_position += 1
            blocks.append(VerseQuote(stanzas=tuple(stanzas)))
            continue

        _diagnose_paragraph_style(paragraph, convention, diagnostics, note_id)
        blocks.append(
            Paragraph(
                content=content,
                source_paragraph_index=paragraph.index,
                source_style_id=paragraph.style_id,
            )
        )
        paragraph_position += 1
    return tuple(blocks), referenced_notes


def _build_verse_stanza(
    paragraph: ParagraphInfo,
    content: tuple[EditorialInline, ...],
    note_id: str | None,
    diagnostics: list[EditorialDiagnostic],
) -> VerseStanza:
    """Decouper un paragraphe ``IntenseQuote`` en vers sur les seuls retours manuels."""
    if not content:
        diagnostics.append(
            _diagnostic(
                "empty_verse_stanza",
                "warning",
                "strophe poetique vide",
                paragraph,
                0,
                note_id,
            )
        )
        return VerseStanza(
            lines=(VerseLine(content=(), source_paragraph_index=paragraph.index, line_index=0),),
            source_paragraph_index=paragraph.index,
            source_style_id=paragraph.style_id,
        )

    lines: list[tuple[EditorialInline, ...]] = []
    current: list[EditorialInline] = []
    for item in content:
        if isinstance(item, LineBreak):
            lines.append(tuple(current))
            current = []
        else:
            current.append(item)
    lines.append(tuple(current))
    for line_index, line in enumerate(lines):
        if not line:
            diagnostics.append(
                _diagnostic(
                    "empty_verse",
                    "warning",
                    "vers poetique vide",
                    paragraph,
                    line_index,
                    note_id,
                )
            )
    return VerseStanza(
        lines=tuple(
            VerseLine(content=line, source_paragraph_index=paragraph.index, line_index=line_index)
            for line_index, line in enumerate(lines)
        ),
        source_paragraph_index=paragraph.index,
        source_style_id=paragraph.style_id,
    )


def _diagnose_paragraph_style(
    paragraph: ParagraphInfo,
    convention: WordEditorialConvention,
    diagnostics: list[EditorialDiagnostic],
    note_id: str | None,
) -> None:
    style_id = paragraph.style_id
    if style_id is None or style_id in convention.paragraph_style_ids:
        return
    if style_id in convention.deferred_paragraph_style_ids:
        diagnostics.append(
            EditorialDiagnostic(
                code="deferred_paragraph_style",
                severity="info",
                message=f"interpretation editoriale differee pour le style {style_id}",
                paragraph_index=paragraph.index,
                style_id=style_id,
                note_id=note_id,
            )
        )
        return
    diagnostics.append(
        EditorialDiagnostic(
            code="unsupported_paragraph_style",
            severity="warning",
            message=f"style de paragraphe non reconnu : {style_id}",
            paragraph_index=paragraph.index,
            style_id=style_id,
            note_id=note_id,
        )
    )


def _build_inline_content(
    paragraph: ParagraphInfo,
    *,
    convention: WordEditorialConvention,
    relationships: dict[str, RelationshipInfo],
    diagnostics: list[EditorialDiagnostic],
    note_id: str | None,
) -> tuple[tuple[EditorialInline, ...], set[tuple[str, str]]]:
    content: list[EditorialInline] = []
    references: set[tuple[str, str]] = set()
    for run_index, run in enumerate(paragraph.runs):
        marks = _marks_for_run(run, convention, paragraph, run_index, note_id, diagnostics)
        link = _link_for_run(run, relationships, paragraph, run_index, note_id, diagnostics)
        for item in run.contents:
            if item.kind == "text":
                if item.text:
                    _append_inline(content, TextSpan(text=item.text, marks=marks, link=link))
            elif item.kind == "tab":
                content.append(Tab())
                diagnostics.append(
                    _diagnostic(
                        "tab_in_editorial_content",
                        "info",
                        "tabulation conservee dans le contenu editorial",
                        paragraph,
                        run_index,
                        note_id,
                    )
                )
            elif item.kind == "break":
                _append_break(content, item.break_type, paragraph, run_index, note_id, diagnostics)
            elif item.kind == "footnote_reference" and item.reference_id is not None:
                content.append(NoteReference(note_id=item.reference_id, note_kind="footnote"))
                references.add(("footnote", item.reference_id))
            elif item.kind == "endnote_reference" and item.reference_id is not None:
                content.append(NoteReference(note_id=item.reference_id, note_kind="endnote"))
                references.add(("endnote", item.reference_id))
            elif item.kind == "drawing":
                content.append(DrawingReference(relationship_ids=item.relationship_ids))
                diagnostics.append(
                    _diagnostic(
                        "drawing_not_editorially_interpreted",
                        "info",
                        "dessin conserve sans interpretation editoriale",
                        paragraph,
                        run_index,
                        note_id,
                    )
                )
    return tuple(content), references


def _marks_for_run(
    run: RunInfo,
    convention: WordEditorialConvention,
    paragraph: ParagraphInfo,
    run_index: int,
    note_id: str | None,
    diagnostics: list[EditorialDiagnostic],
) -> tuple[TextMark, ...]:
    inherited = convention.character_marks(run.style_id)
    if inherited is None:
        diagnostics.append(
            _diagnostic(
                "unsupported_character_style",
                "warning",
                f"style de caractere non reconnu : {run.style_id}",
                paragraph,
                run_index,
                note_id,
                style_id=run.style_id,
            )
        )
        inherited = ()
    marks = set(inherited)
    for mark, direct_value in (
        ("bold", run.bold),
        ("italic", run.italic),
        ("small_caps", run.small_caps),
        ("caps", run.caps),
    ):
        if direct_value is True:
            marks.add(mark)
        elif direct_value is False:
            marks.discard(mark)
    if run.superscript:
        marks.add("superscript")
    if run.subscript:
        marks.add("subscript")
    if run.superscript and run.subscript:
        diagnostics.append(
            _diagnostic(
                "conflicting_vertical_alignment",
                "warning",
                "exposant et indice declares simultanement",
                paragraph,
                run_index,
                note_id,
            )
        )
    return tuple(mark for mark in _MARK_ORDER if mark in marks)


def _link_for_run(
    run: RunInfo,
    relationships: dict[str, RelationshipInfo],
    paragraph: ParagraphInfo,
    run_index: int,
    note_id: str | None,
    diagnostics: list[EditorialDiagnostic],
) -> EditorialLink | None:
    relationship_id = run.hyperlink_relationship_id
    anchor = run.hyperlink_anchor
    if relationship_id is not None:
        relationship = relationships.get(relationship_id)
        if relationship is None:
            diagnostics.append(
                _diagnostic(
                    "missing_hyperlink_relationship",
                    "warning",
                    f"relation d'hyperlien absente : {relationship_id}",
                    paragraph,
                    run_index,
                    note_id,
                )
            )
            return EditorialLink(
                kind="unresolved",
                relationship_id=relationship_id,
                anchor=anchor,
            )
        return EditorialLink(
            kind="external",
            target=relationship.target,
            relationship_id=relationship_id,
            anchor=anchor,
        )
    if anchor is not None:
        return EditorialLink(kind="internal", anchor=anchor)
    return None


def _append_break(
    content: list[EditorialInline],
    break_type: str | None,
    paragraph: ParagraphInfo,
    run_index: int,
    note_id: str | None,
    diagnostics: list[EditorialDiagnostic],
) -> None:
    if break_type == "line":
        content.append(LineBreak())
    elif break_type == "page":
        content.append(PageBreak())
    elif break_type == "column":
        content.append(ColumnBreak())
    else:
        diagnostics.append(
            _diagnostic(
                "unsupported_break_type",
                "warning",
                f"type de saut non pris en charge : {break_type or 'absent'}",
                paragraph,
                run_index,
                note_id,
            )
        )


def _append_inline(content: list[EditorialInline], item: EditorialInline) -> None:
    if not isinstance(item, TextSpan):
        content.append(item)
        return
    if not item.text:
        return
    if content and isinstance(content[-1], TextSpan):
        previous = content[-1]
        if previous.marks == item.marks and previous.link == item.link:
            content[-1] = replace(previous, text=previous.text + item.text)
            return
    content.append(item)


def _diagnose_note_targets(
    notes_by_key: dict[tuple[str, str], EditorialNote],
    referenced_notes: set[tuple[str, str]],
    diagnostics: list[EditorialDiagnostic],
) -> None:
    for note_kind, note_id in sorted(referenced_notes):
        if (note_kind, note_id) not in notes_by_key:
            diagnostics.append(
                EditorialDiagnostic(
                    code="missing_note_target",
                    severity="warning",
                    message=f"cible de note absente : {note_kind}:{note_id}",
                    note_id=note_id,
                )
            )
    for note_kind, note_id in notes_by_key:
        if (note_kind, note_id) not in referenced_notes:
            diagnostics.append(
                EditorialDiagnostic(
                    code="unreferenced_note",
                    severity="info",
                    message=f"note non appelee : {note_kind}:{note_id}",
                    note_id=note_id,
                )
            )


def _diagnostic(
    code: str,
    severity: DiagnosticSeverity,
    message: str,
    paragraph: ParagraphInfo,
    run_index: int,
    note_id: str | None,
    *,
    style_id: str | None = None,
) -> EditorialDiagnostic:
    return EditorialDiagnostic(
        code=code,
        severity=severity,
        message=message,
        paragraph_index=paragraph.index,
        run_index=run_index,
        style_id=style_id,
        note_id=note_id,
    )
