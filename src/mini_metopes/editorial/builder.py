"""Construction conservatoire du modele editorial depuis une inspection OOXML."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
import posixpath

from mini_metopes.docx import (
    DocxInspection,
    DrawingInfo,
    MediaInfo,
    ParagraphInfo,
    RelationshipInfo,
    RunInfo,
    TableInfo,
    inspect_docx_file,
)

from .convention import (
    NATIVE_WORD_CONVENTION,
    ParagraphRole,
    WordEditorialConvention,
    resolve_convention_for_styles,
)
from .model import (
    BibliographicReference,
    BibliographicReferenceInline,
    ColumnBreak,
    DrawingReference,
    EditorialBlock,
    EditorialBuildResult,
    EditorialBibliography,
    EditorialDiagnostic,
    EditorialDocument,
    Epigraph,
    EpigraphParagraph,
    FloatingText,
    FloatingTextParagraph,
    EditorialFigure,
    EditorialGraphic,
    EditorialInline,
    EditorialList,
    EditorialListItem,
    EditorialLink,
    EditorialNote,
    EditorialTable,
    EditorialTableCell,
    EditorialTableRow,
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


DOCUMENT_PART = "word/document.xml"
FOOTNOTES_PART = "word/footnotes.xml"
ENDNOTES_PART = "word/endnotes.xml"
IMAGE_RELATIONSHIP_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"


_MARK_ORDER: tuple[TextMark, ...] = (
    "bold",
    "italic",
    "small_caps",
    "caps",
    "superscript",
    "subscript",
)


_NumberingInterruptions = dict[str, int]
_ClosedNumberingLevel = tuple[str, int]


@dataclass
class _ListItemBuilder:
    """Noeud mutable prive, fige seulement a la sortie du constructeur."""

    content: tuple[EditorialInline, ...]
    source_paragraph_index: int
    source_style_id: str | None
    continuation_paragraphs: list[Paragraph] = field(default_factory=list)
    child_lists: list["_ListBuilder"] = field(default_factory=list)


@dataclass
class _ListBuilder:
    """Representation transitoire d'une liste a un niveau OOXML donne."""

    list_kind: str
    num_format: str
    start: int | None
    numbering_id: str
    level: int
    level_text: str | None
    suffix: str | None
    restart_after_level: int | None
    items: list[_ListItemBuilder] = field(default_factory=list)

    @property
    def signature(self) -> tuple[str, int, str, str, int | None, int | None]:
        return (
            self.numbering_id,
            self.level,
            self.list_kind,
            self.num_format,
            self.start,
            self.restart_after_level,
        )


@dataclass(frozen=True)
class _BuiltFigure:
    figure: EditorialFigure
    next_position: int
    references: set[tuple[str, str]]


@dataclass(frozen=True)
class _RelationshipIndex:
    unique: dict[str, RelationshipInfo]
    duplicates: frozenset[str]


def build_editorial_document(
    inspection: DocxInspection,
    *,
    convention: WordEditorialConvention = NATIVE_WORD_CONVENTION,
    excluded_body_paragraph_indexes: frozenset[int] = frozenset(),
) -> EditorialBuildResult:
    """Construire un modele editorial immuable sans produire de TEI."""
    convention = resolve_convention_for_styles(convention, inspection.styles)
    diagnostics: list[EditorialDiagnostic] = []
    body_relationship_index = _relationship_index(inspection.relationships)
    footnote_relationship_index = _relationship_index(inspection.footnote_relationships)
    endnote_relationship_index = _relationship_index(inspection.endnote_relationships)
    media_by_path = {media.path: media for media in inspection.media}
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
            relationships=(
                footnote_relationship_index.unique
                if note.kind == "footnote"
                else endnote_relationship_index.unique
            ),
            figure_relationships=(
                footnote_relationship_index
                if note.kind == "footnote"
                else endnote_relationship_index
            ),
            media_by_path=media_by_path,
            source_part=FOOTNOTES_PART if note.kind == "footnote" else ENDNOTES_PART,
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

    observed_body_paragraphs = tuple(
        block for block in inspection.body_blocks if isinstance(block, ParagraphInfo)
    )
    source_body_blocks: tuple[ParagraphInfo | TableInfo, ...] = (
        inspection.body_blocks
        if inspection.body_blocks and observed_body_paragraphs == inspection.paragraphs
        else inspection.paragraphs
    )
    body_blocks = tuple(
        block
        for block in source_body_blocks
        if not isinstance(block, ParagraphInfo) or block.index not in excluded_body_paragraph_indexes
    )
    body_blocks, bibliography, bibliography_references = _extract_final_bibliography(
        body_blocks,
        convention=convention,
        relationships=body_relationship_index.unique,
        diagnostics=diagnostics,
    )
    blocks, body_references = _build_blocks(
        body_blocks,
        convention=convention,
        relationships=body_relationship_index.unique,
        figure_relationships=body_relationship_index,
        media_by_path=media_by_path,
        source_part=DOCUMENT_PART,
        diagnostics=diagnostics,
        note_id=None,
        detect_heading_jumps=True,
    )
    referenced_notes.update(body_references)
    referenced_notes.update(bibliography_references)
    _diagnose_note_targets(notes_by_key, referenced_notes, diagnostics)

    return EditorialBuildResult(
        document=EditorialDocument(
            source_name=inspection.source.name,
            blocks=blocks,
            notes=tuple(notes),
            bibliography=bibliography,
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


def _extract_final_bibliography(
    blocks: tuple[ParagraphInfo | TableInfo, ...],
    *,
    convention: WordEditorialConvention,
    relationships: dict[str, RelationshipInfo],
    diagnostics: list[EditorialDiagnostic],
) -> tuple[tuple[ParagraphInfo | TableInfo, ...], EditorialBibliography | None, set[tuple[str, str]]]:
    """Extraire l'unique bibliographie terminale du seul flux principal.

    Deux declencheurs, mutuellement exclusifs : le style controle
    ``TEIbiblstart`` (titre explicite, prioritaire s'il est present), ou a
    defaut le premier paragraphe du style natif ``Bibliography`` (pas de
    titre : Word n'a pas de style de debut de bibliographie separe).
    """
    starts = [
        index for index, block in enumerate(blocks)
        if isinstance(block, ParagraphInfo) and convention.is_bibliography_start_style(
            block.style_id, block.style_name, block.style_is_custom, block.style_type
        )
    ]
    if starts:
        reported_multiple_starts: set[int] = set()
        if len(starts) > 1:
            for index in starts[1:]:
                block = blocks[index]
                assert isinstance(block, ParagraphInfo)
                diagnostics.append(_bibliographic_diagnostic(
                    "multiple_bibliographies_not_serializable", "plusieurs debuts de bibliographie", block, None
                ))
                reported_multiple_starts.add(block.index)
        start_index = starts[0]
        start = blocks[start_index]
        assert isinstance(start, ParagraphInfo)
        title, references = _build_inline_content(
            start, convention=convention, relationships=relationships, diagnostics=diagnostics, note_id=None
        )
        if _contains_bibliographic_inline(title):
            diagnostics.append(_bibliographic_diagnostic(
                "nested_bibliographic_reference_not_serializable",
                "reference bibliographique inline dans un titre de bibliographie",
                start,
                None,
            ))
        if not title:
            diagnostics.append(_bibliographic_diagnostic(
                "empty_bibliography_title_not_serializable", "titre de bibliographie vide", start, None
            ))
        entry_position = start_index + 1
        title_required = True
    else:
        native_starts = [
            index for index, block in enumerate(blocks)
            if isinstance(block, ParagraphInfo) and convention.is_native_bibliography_reference_style(
                block.style_id, block.style_is_custom
            )
        ]
        if not native_starts:
            return blocks, None, set()
        reported_multiple_starts = set()
        start_index = native_starts[0]
        start = blocks[start_index]
        assert isinstance(start, ParagraphInfo)
        entry_position = start_index
        title_required = False
        heading_index = _preceding_heading_index(blocks, start_index, convention)
        if heading_index is not None:
            heading = blocks[heading_index]
            assert isinstance(heading, ParagraphInfo)
            title, references = _build_inline_content(
                heading, convention=convention, relationships=relationships, diagnostics=diagnostics, note_id=None
            )
            start_index = heading_index
        else:
            title = ()
            references = set()
    entries, entry_position = _collect_bibliography_entries(
        blocks, entry_position,
        convention=convention, relationships=relationships, diagnostics=diagnostics,
        references=references, reported_multiple_starts=reported_multiple_starts,
    )
    if not entries:
        diagnostics.append(_bibliographic_diagnostic(
            "bibliography_without_entries_not_serializable", "bibliographie sans entree", start, None
        ))
    return blocks[:start_index], EditorialBibliography(
        title=title, source_paragraph_index=start.index, source_style_id=start.style_id, entries=tuple(entries),
        title_required=title_required,
    ), references


def _preceding_heading_index(
    blocks: tuple[ParagraphInfo | TableInfo, ...], before_index: int, convention: WordEditorialConvention
) -> int | None:
    """Chercher un titre immediatement avant ``before_index``, blancs ignores.

    Utilise pour rattacher un titre de section (ex. "Bibliographie") a une
    bibliographie declenchee par le seul style natif ``Bibliography`` (sans
    ``TEIbiblstart``) : Word n'a pas de style de titre de bibliographie
    dedie, le titre de section qui la precede en tient lieu (voir decision
    0031). Ne rattache rien si un autre contenu s'intercale.
    """
    index = before_index - 1
    while index >= 0:
        block = blocks[index]
        if isinstance(block, ParagraphInfo) and is_semantically_empty_paragraph(block):
            index -= 1
            continue
        if isinstance(block, ParagraphInfo) and _paragraph_role(block, convention).kind == "heading":
            return index
        return None
    return None


def _collect_bibliography_entries(
    blocks: tuple[ParagraphInfo | TableInfo, ...],
    position: int,
    *,
    convention: WordEditorialConvention,
    relationships: dict[str, RelationshipInfo],
    diagnostics: list[EditorialDiagnostic],
    references: set[tuple[str, str]],
    reported_multiple_starts: set[int],
) -> tuple[list[BibliographicReference], int]:
    """Consommer les entrees jusqu'a la fin du flux, en refusant tout intrus."""
    entries: list[BibliographicReference] = []
    while position < len(blocks):
        block = blocks[position]
        if isinstance(block, ParagraphInfo) and convention.is_bibliographic_reference_style(
            block.style_id, block.style_name, block.style_is_custom, block.style_type
        ):
            reference, entry_references = _build_bibliographic_reference(
                block, convention=convention, relationships=relationships, diagnostics=diagnostics, note_id=None
            )
            references.update(entry_references)
            if reference is not None:
                entries.append(reference)
            position += 1
            continue
        invalid_bibliographic_style_code = (
            _invalid_bibliography_style_code(block, convention)
            if isinstance(block, ParagraphInfo)
            else None
        )
        if invalid_bibliographic_style_code is not None:
            diagnostics.append(_bibliographic_diagnostic(
                invalid_bibliographic_style_code,
                "style bibliographique controle invalide",
                block,
                None,
            ))
            position += 1
            continue
        if isinstance(block, ParagraphInfo) and not block.text.strip() and not block.runs:
            diagnostics.append(_bibliographic_diagnostic(
                "empty_bibliography_separator_ignored", "separateur vide dans la bibliographie ignore", block, None, severity="info"
            ))
            position += 1
            continue
        if isinstance(block, ParagraphInfo) and convention.is_bibliography_start_style(
            block.style_id, block.style_name, block.style_is_custom, block.style_type
        ):
            if block.index not in reported_multiple_starts:
                diagnostics.append(_bibliographic_diagnostic(
                    "multiple_bibliographies_not_serializable", "second debut de bibliographie", block, None
                ))
        else:
            diagnostics.append(EditorialDiagnostic(
                code="nonterminal_bibliography_not_serializable", severity="error",
                message="bloc non admis apres le debut de la bibliographie", paragraph_index=(block.index if isinstance(block, ParagraphInfo) else None),
                style_id=(block.style_id if isinstance(block, ParagraphInfo) else None),
            ))
        position += 1
    return entries, position


def _build_blocks(
    paragraphs: tuple[ParagraphInfo | TableInfo, ...],
    *,
    convention: WordEditorialConvention,
    relationships: dict[str, RelationshipInfo],
    figure_relationships: _RelationshipIndex,
    media_by_path: dict[str, MediaInfo],
    source_part: str,
    diagnostics: list[EditorialDiagnostic],
    note_id: str | None,
    detect_heading_jumps: bool,
) -> tuple[tuple[EditorialBlock, ...], set[tuple[str, str]]]:
    blocks: list[EditorialBlock] = []
    referenced_notes: set[tuple[str, str]] = set()
    previous_heading_level: int | None = None
    closed_numbering_ids: set[str] = set()
    interrupted_numbering_ids: _NumberingInterruptions = {}
    paragraph_position = 0
    while paragraph_position < len(paragraphs):
        paragraph = paragraphs[paragraph_position]
        if isinstance(paragraph, TableInfo):
            if closed_numbering_ids:
                for numbering_id in closed_numbering_ids:
                    interrupted_numbering_ids[numbering_id] = interrupted_numbering_ids.get(numbering_id, 0) + 1
                closed_numbering_ids = set()
            table, table_references = _build_editorial_table(
                paragraph,
                convention=convention,
                relationships=relationships,
                diagnostics=diagnostics,
                note_id=note_id,
            )
            if table is not None:
                blocks.append(table)
            referenced_notes.update(table_references)
            paragraph_position += 1
            continue
        role = _paragraph_role(paragraph, convention)

        invalid_bibliographic_style_code = _invalid_bibliography_style_code(paragraph, convention)
        if invalid_bibliographic_style_code is not None:
            diagnostics.append(_bibliographic_diagnostic(
                invalid_bibliographic_style_code,
                "style bibliographique controle invalide",
                paragraph,
                note_id,
            ))
            paragraph_position += 1
            continue

        if note_id is not None and convention.is_bibliography_start_style(
            paragraph.style_id, paragraph.style_name, paragraph.style_is_custom, paragraph.style_type
        ):
            diagnostics.append(_bibliographic_diagnostic(
                "bibliography_in_note_not_serializable", "debut de bibliographie dans une note", paragraph, note_id
            ))

        if convention.is_bibliographic_reference_style(
            paragraph.style_id, paragraph.style_name, paragraph.style_is_custom, paragraph.style_type
        ):
            reference, references = _build_bibliographic_reference(
                paragraph, convention=convention, relationships=relationships, diagnostics=diagnostics, note_id=note_id
            )
            referenced_notes.update(references)
            if reference is not None:
                blocks.append(reference)
            paragraph_position += 1
            continue

        if convention.is_figure_title_style(
            paragraph.style_id, paragraph.style_name, paragraph.style_is_custom
        ):
            title, title_references = _build_figure_text_paragraph(
                paragraph,
                rendition="figure-title",
                role_name="title",
                convention=convention,
                relationships=relationships,
                diagnostics=diagnostics,
                note_id=note_id,
            )
            referenced_notes.update(title_references)
            next_paragraph = (
                paragraphs[paragraph_position + 1]
                if paragraph_position + 1 < len(paragraphs)
                else None
            )
            if isinstance(next_paragraph, ParagraphInfo) and next_paragraph.drawing_count:
                figure = _build_figure_if_supported(
                    paragraphs,
                    paragraph_position + 1,
                    title=title,
                    convention=convention,
                    relationships=relationships,
                    figure_relationships=figure_relationships,
                    media_by_path=media_by_path,
                    source_part=source_part,
                    diagnostics=diagnostics,
                    note_id=note_id,
                )
                if figure is not None:
                    blocks.append(figure.figure)
                    referenced_notes.update(figure.references)
                    paragraph_position = figure.next_position
                    continue
            diagnostics.append(_figure_text_diagnostic(
                "orphan_figure_title_not_serializable", "titre de figure sans image immediate suivante",
                paragraph, note_id,
            ))

        if paragraph.drawing_count:
            figure = _build_figure_if_supported(
                paragraphs,
                paragraph_position,
                convention=convention,
                relationships=relationships,
                figure_relationships=figure_relationships,
                media_by_path=media_by_path,
                source_part=source_part,
                diagnostics=diagnostics,
                note_id=note_id,
            )
            if figure is not None:
                blocks.append(figure.figure)
                referenced_notes.update(figure.references)
                paragraph_position = figure.next_position
                continue

        if (
            convention.is_figure_caption_style(paragraph.style_id, paragraph.style_is_custom)
            or convention.is_controlled_figure_caption_style(paragraph.style_id, paragraph.style_name, paragraph.style_is_custom)
        ):
            diagnostics.append(
                EditorialDiagnostic(
                    code="orphan_figure_caption_not_serializable",
                    severity="error",
                    message="legende de figure sans figure immediate precedente",
                    paragraph_index=paragraph.index,
                    style_id=paragraph.style_id,
                    note_id=note_id,
                )
            )
        if convention.is_figure_credits_style(paragraph.style_id, paragraph.style_name, paragraph.style_is_custom):
            diagnostics.append(_figure_text_diagnostic(
                "orphan_figure_credits_not_serializable", "credits de figure sans figure immediate precedente",
                paragraph, note_id,
            ))

        if _is_serializable_list_paragraph(paragraph, role.kind):
            list_blocks, next_position, list_references, sequence_numbering_ids = _build_list_sequence(
                paragraphs,
                paragraph_position,
                convention=convention,
                relationships=relationships,
                media_by_path=media_by_path,
                source_part=source_part,
                diagnostics=diagnostics,
                note_id=note_id,
                interrupted_numbering_ids=interrupted_numbering_ids,
            )
            blocks.extend(list_blocks)
            referenced_notes.update(list_references)
            closed_numbering_ids = sequence_numbering_ids
            paragraph_position = next_position
            continue

        if closed_numbering_ids:
            for numbering_id in closed_numbering_ids:
                interrupted_numbering_ids[numbering_id] = interrupted_numbering_ids.get(numbering_id, 0) + 1
            closed_numbering_ids = set()
        else:
            for numbering_id in tuple(interrupted_numbering_ids):
                interrupted_numbering_ids[numbering_id] += 1

        content, references = _build_inline_content(
            paragraph,
            convention=convention,
            relationships=relationships,
            diagnostics=diagnostics,
            note_id=note_id,
        )
        referenced_notes.update(references)
        if _has_active_numbering(paragraph):
            _diagnose_nonserializable_numbering(paragraph, role.kind, diagnostics, note_id)
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
                if not isinstance(next_paragraph, ParagraphInfo):
                    break
                if _paragraph_role(next_paragraph, convention).kind != "prose_quote":
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
            source, source_references, next_position = _citation_source_if_immediate(
                paragraphs, paragraph_position, convention=convention, relationships=relationships,
                diagnostics=diagnostics, note_id=note_id
            )
            referenced_notes.update(source_references)
            blocks.append(ProseQuote(paragraphs=tuple(quote_paragraphs), source=source))
            paragraph_position = next_position
            continue

        if role.kind == "verse_quote":
            stanzas = list(_build_verse_stanzas(paragraph, content, note_id, diagnostics))
            paragraph_position += 1
            while paragraph_position < len(paragraphs):
                next_paragraph = paragraphs[paragraph_position]
                if not isinstance(next_paragraph, ParagraphInfo):
                    break
                if _paragraph_role(next_paragraph, convention).kind != "verse_quote":
                    break
                next_content, next_references = _build_inline_content(
                    next_paragraph,
                    convention=convention,
                    relationships=relationships,
                    diagnostics=diagnostics,
                    note_id=note_id,
                )
                referenced_notes.update(next_references)
                stanzas.extend(_build_verse_stanzas(next_paragraph, next_content, note_id, diagnostics))
                paragraph_position += 1
            if not stanzas:
                diagnostics.append(
                    EditorialDiagnostic(
                        code="ambiguous_empty_verse_block",
                        severity="warning",
                        message="bloc de vers entierement vide, contexte ambigu pour une frontiere de strophe",
                        paragraph_index=paragraph.index,
                        style_id=paragraph.style_id,
                        note_id=note_id,
                    )
                )
                continue
            source, source_references, next_position = _citation_source_if_immediate(
                paragraphs, paragraph_position, convention=convention, relationships=relationships,
                diagnostics=diagnostics, note_id=note_id
            )
            referenced_notes.update(source_references)
            blocks.append(VerseQuote(stanzas=tuple(stanzas), source=source))
            paragraph_position = next_position
            continue

        if role.kind == "epigraph":
            if note_id is not None or not (not blocks or isinstance(blocks[-1], Heading)):
                diagnostics.append(
                    EditorialDiagnostic(
                        code="misplaced_epigraph_not_serializable",
                        severity="error",
                        message="epigraphe (style Salutation) hors position de tete de section",
                        paragraph_index=paragraph.index,
                        style_id=paragraph.style_id,
                        note_id=note_id,
                    )
                )
                paragraph_position += 1
                continue
            epigraph_paragraphs = [
                EpigraphParagraph(
                    content=content,
                    source_paragraph_index=paragraph.index,
                    source_style_id=paragraph.style_id,
                )
            ]
            if not content:
                diagnostics.append(
                    EditorialDiagnostic(
                        code="empty_epigraph_paragraph",
                        severity="warning",
                        message="paragraphe d'epigraphe vide",
                        paragraph_index=paragraph.index,
                        style_id=paragraph.style_id,
                        note_id=note_id,
                    )
                )
            paragraph_position += 1
            while paragraph_position < len(paragraphs):
                next_paragraph = paragraphs[paragraph_position]
                if not isinstance(next_paragraph, ParagraphInfo):
                    break
                if _paragraph_role(next_paragraph, convention).kind != "epigraph":
                    break
                next_content, next_references = _build_inline_content(
                    next_paragraph,
                    convention=convention,
                    relationships=relationships,
                    diagnostics=diagnostics,
                    note_id=note_id,
                )
                referenced_notes.update(next_references)
                epigraph_paragraphs.append(
                    EpigraphParagraph(
                        content=next_content,
                        source_paragraph_index=next_paragraph.index,
                        source_style_id=next_paragraph.style_id,
                    )
                )
                if not next_content:
                    diagnostics.append(
                        EditorialDiagnostic(
                            code="empty_epigraph_paragraph",
                            severity="warning",
                            message="paragraphe d'epigraphe vide",
                            paragraph_index=next_paragraph.index,
                            style_id=next_paragraph.style_id,
                            note_id=note_id,
                        )
                    )
                paragraph_position += 1
            blocks.append(Epigraph(paragraphs=tuple(epigraph_paragraphs)))
            continue

        if role.kind == "signature":
            if _is_signature_run_filler(paragraph):
                # Artefact Word frequent : le "style suivant" de Signature est
                # lui-meme, si bien qu'une simple touche Entree (ou un saut de
                # page force avant la section suivante) en fin de bloc laisse
                # un paragraphe Signature sans contenu reel. Il ne doit ni
                # compter dans la limite de deux lignes, ni a lui seul
                # disqualifier la position terminale (voir decisions 0028 et
                # 0031, corpus reel).
                diagnostics.append(
                    EditorialDiagnostic(
                        code="empty_paragraph_ignored",
                        severity="info",
                        message="paragraphe Word vide ignore (artefact de mise en page)",
                        paragraph_index=paragraph.index,
                        style_id=paragraph.style_id,
                        note_id=note_id,
                    )
                )
                paragraph_position += 1
                continue
            run_end = paragraph_position
            effective_length = 0
            while (
                run_end < len(paragraphs)
                and isinstance(paragraphs[run_end], ParagraphInfo)
                and _paragraph_role(paragraphs[run_end], convention).kind == "signature"
            ):
                if not _is_signature_run_filler(paragraphs[run_end]):
                    effective_length += 1
                run_end += 1
            valid_position = (
                note_id is None
                and effective_length <= 2
                and _signature_run_is_terminal(paragraphs, run_end, convention)
            )
            if not valid_position:
                for index in range(paragraph_position, run_end):
                    invalid_block = paragraphs[index]
                    assert isinstance(invalid_block, ParagraphInfo)
                    diagnostics.append(
                        EditorialDiagnostic(
                            code="misplaced_signature_not_serializable",
                            severity="error",
                            message=(
                                "signature d'auteur (style Signature) doit preceder immediatement "
                                "la partie/chapitre/contribution suivante (Titre1 a Titre2) ou la fin "
                                "du document, et compter deux lignes au plus (nom, institution)"
                            ),
                            paragraph_index=invalid_block.index,
                            style_id=invalid_block.style_id,
                            note_id=note_id,
                        )
                    )
                paragraph_position = run_end
                continue
            blocks.append(
                Paragraph(
                    content=content,
                    source_paragraph_index=paragraph.index,
                    source_style_id=paragraph.style_id,
                )
            )
            paragraph_position += 1
            if paragraph_position == run_end:
                # Fin reelle du bloc Signature valide : consommer les
                # paragraphes de bordure sans contenu reel (saut de page/
                # colonne isole inclus, quel que soit leur style) qui ont
                # permis a _signature_run_is_terminal de reconnaitre la
                # position terminale. Un saut de page n'est jamais
                # serialisable en TEI (voir tei/serializer.py) ; sans ce
                # retrait, le paragraphe qui le porte bloquerait la
                # generation meme si la signature elle-meme est acceptee.
                # Voir decision 0035.
                while (
                    paragraph_position < len(paragraphs)
                    and isinstance(paragraphs[paragraph_position], ParagraphInfo)
                    and _is_signature_run_filler(paragraphs[paragraph_position])
                ):
                    filler = paragraphs[paragraph_position]
                    diagnostics.append(
                        EditorialDiagnostic(
                            code="empty_paragraph_ignored",
                            severity="info",
                            message="paragraphe Word vide ignore (artefact de mise en page)",
                            paragraph_index=filler.index,
                            style_id=filler.style_id,
                            note_id=note_id,
                        )
                    )
                    paragraph_position += 1
            continue

        if role.kind == "floating_text":
            if note_id is not None:
                diagnostics.append(
                    EditorialDiagnostic(
                        code="floating_text_in_note_not_serializable",
                        severity="error",
                        message="encadre (style BlockText) non pris en charge dans une note",
                        paragraph_index=paragraph.index,
                        style_id=paragraph.style_id,
                        note_id=note_id,
                    )
                )
                paragraph_position += 1
                continue
            floating_paragraphs = [
                FloatingTextParagraph(
                    content=content,
                    source_paragraph_index=paragraph.index,
                    source_style_id=paragraph.style_id,
                )
            ]
            if not content:
                diagnostics.append(
                    EditorialDiagnostic(
                        code="empty_floating_text_paragraph",
                        severity="warning",
                        message="paragraphe d'encadre vide",
                        paragraph_index=paragraph.index,
                        style_id=paragraph.style_id,
                        note_id=note_id,
                    )
                )
            paragraph_position += 1
            while paragraph_position < len(paragraphs):
                next_paragraph = paragraphs[paragraph_position]
                if not isinstance(next_paragraph, ParagraphInfo):
                    break
                if _paragraph_role(next_paragraph, convention).kind != "floating_text":
                    break
                next_content, next_references = _build_inline_content(
                    next_paragraph,
                    convention=convention,
                    relationships=relationships,
                    diagnostics=diagnostics,
                    note_id=note_id,
                )
                referenced_notes.update(next_references)
                floating_paragraphs.append(
                    FloatingTextParagraph(
                        content=next_content,
                        source_paragraph_index=next_paragraph.index,
                        source_style_id=next_paragraph.style_id,
                    )
                )
                if not next_content:
                    diagnostics.append(
                        EditorialDiagnostic(
                            code="empty_floating_text_paragraph",
                            severity="warning",
                            message="paragraphe d'encadre vide",
                            paragraph_index=next_paragraph.index,
                            style_id=next_paragraph.style_id,
                            note_id=note_id,
                        )
                    )
                paragraph_position += 1
            blocks.append(FloatingText(paragraphs=tuple(floating_paragraphs)))
            continue

        if is_semantically_empty_paragraph(paragraph):
            diagnostics.append(
                EditorialDiagnostic(
                    code="empty_paragraph_ignored",
                    severity="info",
                    message="paragraphe Word vide ignore (artefact de mise en page)",
                    paragraph_index=paragraph.index,
                    style_id=paragraph.style_id,
                    note_id=note_id,
                )
            )
            paragraph_position += 1
            continue

        _diagnose_paragraph_style(paragraph, convention, diagnostics, note_id)
        blocks.append(
            Paragraph(
                content=content,
                source_paragraph_index=paragraph.index,
                source_style_id=paragraph.style_id,
                rendition=role.paragraph_rendition,
            )
        )
        paragraph_position += 1
    return tuple(blocks), referenced_notes


def _citation_source_if_immediate(
    blocks: tuple[ParagraphInfo | TableInfo, ...],
    position: int,
    *,
    convention: WordEditorialConvention,
    relationships: dict[str, RelationshipInfo],
    diagnostics: list[EditorialDiagnostic],
    note_id: str | None,
) -> tuple[BibliographicReference | None, set[tuple[str, str]], int]:
    """Absorber une unique source controlee, seulement si elle est adjacente."""
    if position >= len(blocks) or not isinstance(blocks[position], ParagraphInfo):
        return None, set(), position
    candidate = blocks[position]
    if not convention.is_bibliographic_reference_style(
        candidate.style_id, candidate.style_name, candidate.style_is_custom, candidate.style_type
    ):
        return None, set(), position
    source, references = _build_bibliographic_reference(
        candidate, convention=convention, relationships=relationships, diagnostics=diagnostics, note_id=note_id
    )
    next_position = position + 1
    if next_position < len(blocks):
        following = blocks[next_position]
        if isinstance(following, ParagraphInfo) and convention.is_bibliographic_reference_style(
            following.style_id, following.style_name, following.style_is_custom, following.style_type
        ):
            diagnostics.append(_bibliographic_diagnostic(
                "multiple_bibliographic_sources_not_serializable", "plusieurs sources bibliographiques apres une citation", following, note_id
            ))
    return source, references, next_position


def _build_bibliographic_reference(
    paragraph: ParagraphInfo,
    *,
    convention: WordEditorialConvention,
    relationships: dict[str, RelationshipInfo],
    diagnostics: list[EditorialDiagnostic],
    note_id: str | None,
) -> tuple[BibliographicReference | None, set[tuple[str, str]]]:
    content, references = _build_inline_content(
        paragraph, convention=convention, relationships=relationships, diagnostics=diagnostics, note_id=note_id
    )
    if not content:
        diagnostics.append(_bibliographic_diagnostic(
            "empty_bibliographic_reference_not_serializable", "reference bibliographique vide", paragraph, note_id
        ))
        return None, references
    if _contains_bibliographic_inline(content):
        diagnostics.append(_bibliographic_diagnostic(
            "nested_bibliographic_reference_not_serializable",
            "reference bibliographique inline dans une reference bibliographique",
            paragraph,
            note_id,
        ))
        return None, references
    if _has_active_numbering(paragraph):
        diagnostics.append(_bibliographic_diagnostic(
            "numbered_bibliographic_reference_not_serializable", "reference bibliographique numerotee", paragraph, note_id
        ))
        return None, references
    if paragraph.drawing_count:
        diagnostics.append(_bibliographic_diagnostic(
            "image_in_bibliographic_reference_not_serializable", "image dans une reference bibliographique", paragraph, note_id
        ))
        return None, references
    return BibliographicReference(content, paragraph.index, paragraph.style_id), references


def _invalid_bibliography_style_code(
    paragraph: ParagraphInfo,
    convention: WordEditorialConvention,
) -> str | None:
    """Diagnostiquer seulement les tentatives identifiables de styles bibliographiques controles."""
    if convention.bibliography_start_style_status(
        paragraph.style_id, paragraph.style_name, paragraph.style_is_custom, paragraph.style_type
    ) == "invalid":
        return "invalid_bibliography_start_style"
    if convention.bibliographic_reference_style_status(
        paragraph.style_id, paragraph.style_name, paragraph.style_is_custom, paragraph.style_type
    ) == "invalid":
        return "invalid_bibliographic_reference_style"
    return None


def _contains_bibliographic_inline(items: tuple[EditorialInline, ...]) -> bool:
    for item in items:
        if isinstance(item, BibliographicReferenceInline):
            return True
    return False


def _bibliographic_diagnostic(
    code: str, message: str, paragraph: ParagraphInfo, note_id: str | None, *, severity: DiagnosticSeverity = "error"
) -> EditorialDiagnostic:
    return EditorialDiagnostic(code, severity, message, paragraph.index, style_id=paragraph.style_id, note_id=note_id)


def _has_active_numbering(paragraph: ParagraphInfo) -> bool:
    """Distinguer une liste active de l'annulation Word ``numId=0``."""
    if paragraph.numbering is not None:
        return paragraph.numbering.status != "removed"
    return paragraph.numbering_id is not None and paragraph.numbering_id != "0"


def is_semantically_empty_paragraph(paragraph: ParagraphInfo) -> bool:
    """Determiner si un paragraphe Word n'a aucun contenu editorialement significatif.

    Un paragraphe reellement vide n'a ni texte, ni note, ni lien, ni dessin,
    ni signet, ni numerotation active, ni tabulation, ni saut de page ou de
    colonne : ce n'est qu'un artefact de mise en page.
    """
    if paragraph.text.strip():
        return False
    if paragraph.footnote_reference_ids or paragraph.endnote_reference_ids:
        return False
    if paragraph.hyperlink_count or paragraph.hyperlink_relationship_ids:
        return False
    if paragraph.drawing_count or paragraph.drawing_relationship_ids:
        return False
    if paragraph.bookmark_start_ids:
        return False
    if _has_active_numbering(paragraph):
        return False
    for run in paragraph.runs:
        if run.tabs:
            return False
        if any(break_type in {"page", "column"} for break_type in run.break_types):
            return False
    return True


def _is_signature_run_filler(paragraph: ParagraphInfo) -> bool:
    """Detecter un paragraphe ``Signature`` sans contenu reel, saut de page/
    colonne isole inclus.

    Le style Word integre ``Signature`` s'auto-continue (son "style suivant"
    est lui-meme) : un saut de page force avant la section qui suit (la
    bibliographie, typiquement) peut donc atterrir sur un paragraphe
    ``Signature`` sans texte. A la difference de
    ``is_semantically_empty_paragraph`` (utilisee partout ailleurs, ou un
    saut de page ne doit jamais etre ignore silencieusement), ce filtre
    n'est applique que dans le contexte tres specifique de la suite
    terminale de paragraphes ``Signature`` : voir decision 0031, corpus
    reel. Le saut de page lui-meme n'est jamais serialise ; le perimetre
    etroit de cette exception evite d'affaiblir la regle generale.
    """
    if paragraph.text.strip():
        return False
    if paragraph.footnote_reference_ids or paragraph.endnote_reference_ids:
        return False
    if paragraph.hyperlink_count or paragraph.hyperlink_relationship_ids:
        return False
    if paragraph.drawing_count or paragraph.drawing_relationship_ids:
        return False
    if paragraph.bookmark_start_ids:
        return False
    if _has_active_numbering(paragraph):
        return False
    for run in paragraph.runs:
        if run.tabs:
            return False
    return True


def _signature_run_is_terminal(
    paragraphs: tuple[ParagraphInfo | TableInfo, ...], run_end: int, convention: WordEditorialConvention
) -> bool:
    """Un bloc ``Signature`` est terminal en fin de document, ou juste avant
    un titre de niveau 1 a 2 (partie ou pivot chapitre/contribution suivant,
    voir decision 0037 ; Titre3 est desormais une section interne a la
    contribution, plus une frontiere). Un titre de niveau 3 ou plus reste
    une sous-section de la MEME contribution : la signature ne peut pas le
    preceder.

    Un ou plusieurs paragraphes sans contenu reel (saut de page/colonne
    isole inclus) entre la signature et cette limite ne comptent pas :
    Word insere frequemment un saut de page manuel juste apres une
    signature, sur un paragraphe qui ne porte plus necessairement le style
    ``Signature`` lui-meme (contrairement a l'artefact de la decision
    0031). Voir decision 0035.
    """
    position = run_end
    while (
        position < len(paragraphs)
        and isinstance(paragraphs[position], ParagraphInfo)
        and _is_signature_run_filler(paragraphs[position])
    ):
        position += 1
    if position == len(paragraphs):
        return True
    next_block = paragraphs[position]
    if not isinstance(next_block, ParagraphInfo):
        return False
    role = _paragraph_role(next_block, convention)
    return role.kind == "heading" and role.heading_level is not None and role.heading_level <= 2


def _build_editorial_table(
    table: TableInfo,
    *,
    convention: WordEditorialConvention,
    relationships: dict[str, RelationshipInfo],
    diagnostics: list[EditorialDiagnostic],
    note_id: str | None,
) -> tuple[EditorialTable | None, set[tuple[str, str]]]:
    """Construire uniquement une table Word rectangulaire sans fusion."""
    references: set[tuple[str, str]] = set()
    if not table.rows:
        diagnostics.append(EditorialDiagnostic("empty_table_not_serializable", "error", "table Word vide"))
        return None, references
    if any(not row.cells for row in table.rows):
        diagnostics.append(EditorialDiagnostic("empty_table_row_not_serializable", "error", "ligne de table Word vide"))
        return None, references
    if any(
        cell.has_grid_span or cell.has_vertical_merge or cell.has_horizontal_merge
        for row in table.rows for cell in row.cells
    ):
        diagnostics.append(EditorialDiagnostic("merged_table_cells_not_serializable", "error", "cellules fusionnees dans une table Word"))
        return None, references
    if any(cell.has_nested_table for row in table.rows for cell in row.cells):
        diagnostics.append(EditorialDiagnostic("nested_table_not_serializable", "error", "table imbriquee dans une cellule Word"))
        return None, references
    column_count = len(table.rows[0].cells)
    if any(len(row.cells) != column_count for row in table.rows) or (
        table.declared_column_count is not None and table.declared_column_count != column_count
    ):
        diagnostics.append(EditorialDiagnostic("irregular_table_not_serializable", "error", "table Word non rectangulaire"))
        return None, references
    if any(row.is_header for row in table.rows[1:]):
        diagnostics.append(EditorialDiagnostic("invalid_table_header_not_serializable", "error", "ligne d'en-tete Word hors premiere ligne"))
        return None, references
    rows: list[EditorialTableRow] = []
    for row_index, row in enumerate(table.rows):
        cells: list[EditorialTableCell] = []
        for column_index, cell in enumerate(row.cells):
            nonempty = [paragraph for paragraph in cell.paragraphs if paragraph.text or paragraph.runs]
            if len(nonempty) > 1:
                diagnostics.append(EditorialDiagnostic(
                    "multiple_paragraphs_in_table_cell_not_serializable", "error",
                    "plusieurs paragraphes non vides dans une cellule Word",
                ))
                continue
            content: tuple[EditorialInline, ...] = ()
            if nonempty:
                paragraph = nonempty[0]
                role = _paragraph_role(paragraph, convention)
                cell_style_supported = convention.is_table_cell_style(
                    paragraph.style_id, paragraph.style_name, paragraph.style_is_custom
                )
                controlled_table_cell_style = convention.is_controlled_table_cell_style(
                    paragraph.style_id, paragraph.style_name, paragraph.style_is_custom
                )
                if not cell_style_supported:
                    diagnostics.append(_figure_text_diagnostic(
                        "unsupported_table_cell_style", "style de cellule Word non pris en charge", paragraph, note_id
                    ))
                if paragraph.drawing_count:
                    diagnostics.append(_figure_text_diagnostic(
                        "image_in_table_cell_not_serializable", "image dans une cellule de table", paragraph, note_id
                    ))
                if _has_active_numbering(paragraph):
                    diagnostics.append(_figure_text_diagnostic(
                        "numbered_table_cell_not_serializable", "liste dans une cellule de table", paragraph, note_id
                    ))
                if role.kind != "paragraph" and not controlled_table_cell_style:
                    diagnostics.append(_figure_text_diagnostic(
                        "unsupported_table_cell_content", "contenu de cellule Word non pris en charge", paragraph, note_id
                    ))
                content, cell_references = _build_inline_content(
                    paragraph, convention=convention, relationships=relationships,
                    diagnostics=diagnostics, note_id=note_id,
                )
                references.update(cell_references)
            cells.append(EditorialTableCell(
                content=content,
                role="label" if row.is_header else None,
                source_row_index=row_index,
                source_column_index=column_index,
            ))
        rows.append(EditorialTableRow(
            cells=tuple(cells), role="label" if row.is_header else None, source_row_index=row_index
        ))
    return EditorialTable(
        rows=tuple(rows), column_count=column_count,
        source_block_index=table.source_block_index, source_style_id=table.style_id,
    ), references


def _relationship_index(relationships: tuple[RelationshipInfo, ...]) -> _RelationshipIndex:
    unique: dict[str, RelationshipInfo] = {}
    duplicates: set[str] = set()
    for relationship in relationships:
        if relationship.relationship_id in unique:
            duplicates.add(relationship.relationship_id)
        else:
            unique[relationship.relationship_id] = relationship
    return _RelationshipIndex(unique=unique, duplicates=frozenset(duplicates))


def _build_figure_if_supported(
    paragraphs: tuple[ParagraphInfo | TableInfo, ...],
    position: int,
    *,
    title: Paragraph | None = None,
    convention: WordEditorialConvention,
    relationships: dict[str, RelationshipInfo],
    figure_relationships: _RelationshipIndex,
    media_by_path: dict[str, MediaInfo],
    source_part: str,
    diagnostics: list[EditorialDiagnostic],
    note_id: str | None,
) -> _BuiltFigure | None:
    paragraph = paragraphs[position]
    if not isinstance(paragraph, ParagraphInfo):
        return None
    graphic = _graphic_from_paragraph(
        paragraph,
        convention=convention,
        relationships=relationships,
        figure_relationships=figure_relationships,
        media_by_path=media_by_path,
        source_part=source_part,
        diagnostics=diagnostics,
        note_id=note_id,
    )
    if graphic is None:
        return None
    caption: Paragraph | None = None
    credits: Paragraph | None = None
    references: set[tuple[str, str]] = set()
    next_position = position + 1
    if next_position < len(paragraphs):
        candidate = paragraphs[next_position]
        is_native_caption = isinstance(candidate, ParagraphInfo) and convention.is_figure_caption_style(
            candidate.style_id, candidate.style_is_custom
        )
        is_controlled_caption = isinstance(candidate, ParagraphInfo) and convention.is_controlled_figure_caption_style(
            candidate.style_id, candidate.style_name, candidate.style_is_custom
        )
        if title is None and is_native_caption:
            second_candidate = paragraphs[next_position + 1] if next_position + 1 < len(paragraphs) else None
            second_is_native_caption = isinstance(second_candidate, ParagraphInfo) and convention.is_figure_caption_style(
                second_candidate.style_id, second_candidate.style_is_custom
            )
            if second_is_native_caption:
                # Protocole a deux paragraphes Caption natifs (decision 0033),
                # calque sur celui de Signature : le premier devient le titre
                # de la figure, le second sa legende. Un seul paragraphe
                # Caption garde le comportement d'origine (legende seule).
                title, title_references = _build_figure_text_paragraph(
                    candidate, rendition="figure-title", role_name="title", convention=convention,
                    relationships=relationships, diagnostics=diagnostics, note_id=note_id,
                )
                references.update(title_references)
                next_position += 1
                candidate = second_candidate
                is_native_caption = True
        if is_native_caption or is_controlled_caption:
            caption, caption_references = _build_figure_text_paragraph(
                candidate, rendition="caption", role_name="caption", convention=convention,
                relationships=relationships, diagnostics=diagnostics, note_id=note_id,
            )
            references.update(caption_references)
            next_position += 1
    if next_position < len(paragraphs):
        candidate = paragraphs[next_position]
        if isinstance(candidate, ParagraphInfo) and convention.is_figure_credits_style(
            candidate.style_id, candidate.style_name, candidate.style_is_custom
        ):
            credits, credit_references = _build_figure_text_paragraph(
                candidate, rendition="credits", role_name="credits", convention=convention,
                relationships=relationships, diagnostics=diagnostics, note_id=note_id,
            )
            references.update(credit_references)
            next_position += 1
    return _BuiltFigure(
        figure=EditorialFigure(
            graphic=graphic,
            source_paragraph_index=paragraph.index,
            source_style_id=paragraph.style_id,
            title=title,
            caption=caption,
            credits=credits,
        ),
        next_position=next_position,
        references=references,
    )


def _figure_text_diagnostic(
    code: str, message: str, paragraph: ParagraphInfo, note_id: str | None
) -> EditorialDiagnostic:
    return EditorialDiagnostic(
        code=code,
        severity="error",
        message=message,
        paragraph_index=paragraph.index,
        style_id=paragraph.style_id,
        note_id=note_id,
    )


def _build_figure_text_paragraph(
    paragraph: ParagraphInfo,
    *,
    rendition: str,
    role_name: str,
    convention: WordEditorialConvention,
    relationships: dict[str, RelationshipInfo],
    diagnostics: list[EditorialDiagnostic],
    note_id: str | None,
) -> tuple[Paragraph | None, set[tuple[str, str]]]:
    content, references = _build_inline_content(
        paragraph, convention=convention, relationships=relationships,
        diagnostics=diagnostics, note_id=note_id,
    )
    prefix = "figure_caption" if role_name == "caption" else f"figure_{role_name}"
    if _has_active_numbering(paragraph):
        diagnostics.append(_figure_text_diagnostic(
            f"numbered_{prefix}_not_serializable", f"{role_name} de figure numerote", paragraph, note_id
        ))
    if paragraph.drawing_count:
        diagnostics.append(_figure_text_diagnostic(
            f"image_in_{prefix}_not_serializable", f"image presente dans un {role_name} de figure", paragraph, note_id
        ))
    if not content:
        diagnostics.append(_figure_text_diagnostic(
            f"empty_{prefix}_not_serializable", f"{role_name} de figure vide", paragraph, note_id
        ))
        return None, references
    return Paragraph(
        content=content,
        source_paragraph_index=paragraph.index,
        source_style_id=paragraph.style_id,
        rendition=rendition,  # type: ignore[arg-type]
    ), references


def _graphic_from_paragraph(
    paragraph: ParagraphInfo,
    *,
    convention: WordEditorialConvention,
    relationships: dict[str, RelationshipInfo],
    figure_relationships: _RelationshipIndex,
    media_by_path: dict[str, MediaInfo],
    source_part: str,
    diagnostics: list[EditorialDiagnostic],
    note_id: str | None,
) -> EditorialGraphic | None:
    drawings = _paragraph_drawings(paragraph)
    if not drawings:
        return None
    if _has_active_numbering(paragraph):
        diagnostics.append(
            EditorialDiagnostic(
                code="numbered_figure_not_serializable",
                severity="error",
                message="image dans un paragraphe numerote",
                paragraph_index=paragraph.index,
                style_id=paragraph.style_id,
                note_id=note_id,
            )
        )
        return None
    if not convention.is_figure_container_style(paragraph.style_id, paragraph.style_is_custom):
        diagnostics.append(
            EditorialDiagnostic(
                code="mixed_text_and_image_not_serializable",
                severity="error",
                message="image dans un style de paragraphe non admis comme conteneur de figure",
                paragraph_index=paragraph.index,
                style_id=paragraph.style_id,
                note_id=note_id,
            )
        )
        return None
    if len(drawings) > 1:
        diagnostics.append(
            EditorialDiagnostic(
                code="multiple_images_in_paragraph_not_serializable",
                severity="error",
                message="plusieurs images dans un meme paragraphe",
                paragraph_index=paragraph.index,
                style_id=paragraph.style_id,
                note_id=note_id,
            )
        )
        return None
    if _paragraph_has_non_image_inline(paragraph):
        diagnostics.append(
            EditorialDiagnostic(
                code="mixed_text_and_image_not_serializable",
                severity="error",
                message="texte ou inline non image melange a une image",
                paragraph_index=paragraph.index,
                style_id=paragraph.style_id,
                note_id=note_id,
            )
        )
        return None
    hyperlink_context = _drawing_hyperlink_context(paragraph)
    if hyperlink_context is not None:
        diagnostics.append(
            _figure_error(
                "hyperlinked_image_not_serializable",
                f"image hyperliee non serialisable : {hyperlink_context}",
                paragraph,
                note_id,
                drawings[0],
            )
        )
        return None
    drawing = drawings[0]
    if drawing.invalid_properties:
        diagnostics.append(
            _figure_error(
                "invalid_drawing_property_not_serializable",
                f"proprietes DrawingML invalides : {', '.join(drawing.invalid_properties)}",
                paragraph,
                note_id,
                drawing,
            )
        )
        return None
    if drawing.placement == "anchor":
        diagnostics.append(_figure_error("floating_image_not_serializable", "image flottante Word non serialisable", paragraph, note_id, drawing))
        return None
    if drawing.placement != "inline":
        diagnostics.append(_figure_error("floating_image_not_serializable", "placement d'image Word inconnu", paragraph, note_id, drawing))
        return None
    if drawing.is_cropped:
        diagnostics.append(_figure_error("cropped_image_not_serializable", "image recadree non serialisable", paragraph, note_id, drawing))
        return None
    if (drawing.rotation not in {None, 0}) or drawing.flip_horizontal or drawing.flip_vertical:
        diagnostics.append(_figure_error("transformed_image_not_serializable", "image transformee non serialisable", paragraph, note_id, drawing))
        return None
    if drawing.linked_relationship_ids:
        diagnostics.append(_figure_error("external_image_not_serializable", "image liee externement non serialisable", paragraph, note_id, drawing))
        return None
    if len(drawing.embedded_relationship_ids) != 1:
        diagnostics.append(_figure_error("multiple_image_sources_not_serializable", "source d'image incorporee absente ou multiple", paragraph, note_id, drawing))
        return None
    relationship_id = drawing.embedded_relationship_ids[0]
    if relationship_id in figure_relationships.duplicates:
        diagnostics.append(
            _figure_error(
                "duplicate_image_relationship_not_serializable",
                f"relation d'image dupliquee dans {source_part} : {relationship_id}",
                paragraph,
                note_id,
                drawing,
            )
        )
        return None
    relationship = relationships.get(relationship_id)
    if relationship is None:
        diagnostics.append(_figure_error("missing_image_relationship", f"relation d'image absente : {relationship_id}", paragraph, note_id, drawing))
        return None
    media_path = resolve_internal_media_target(source_part, relationship)
    if relationship.target_mode == "External":
        diagnostics.append(_figure_error("external_image_not_serializable", f"relation d'image externe : {relationship_id}", paragraph, note_id, drawing))
        return None
    if relationship.relationship_type != IMAGE_RELATIONSHIP_TYPE:
        diagnostics.append(_figure_error("unsupported_image_relationship", f"relation d'image de type non pris en charge : {relationship.relationship_type}", paragraph, note_id, drawing))
        return None
    if media_path is None:
        diagnostics.append(_figure_error("unsafe_image_target", f"cible d'image dangereuse : {relationship.target}", paragraph, note_id, drawing))
        return None
    media = media_by_path.get(media_path)
    if media is None:
        diagnostics.append(_figure_error("missing_image_media_part", f"media d'image absent : {media_path}", paragraph, note_id, drawing))
        return None
    content_type = media.content_type
    if content_type not in {"image/png", "image/jpeg"}:
        diagnostics.append(_figure_error("unsupported_image_format", f"format image non pris en charge : {content_type or 'absent'}", paragraph, note_id, drawing))
        return None
    if media.detected_content_type != content_type:
        diagnostics.append(_figure_error("image_content_type_mismatch", f"signature image incoherente pour {media_path}", paragraph, note_id, drawing))
        return None
    if not media.sha256:
        diagnostics.append(_figure_error("unreadable_image_media", f"empreinte image indisponible : {media_path}", paragraph, note_id, drawing))
        return None
    if not drawing.description:
        diagnostics.append(_figure_error("missing_figure_description", "description alternative Word absente", paragraph, note_id, drawing))
        return None
    extension = ".png" if content_type == "image/png" else ".jpg"
    return EditorialGraphic(
        source_part=source_part,
        source_relationship_id=relationship_id,
        source_media_path=media_path,
        media_url=f"media/{media.sha256}{extension}",
        content_type=content_type,  # type: ignore[arg-type]
        sha256=media.sha256,
        description=drawing.description,
        width_emu=drawing.width_emu,
        height_emu=drawing.height_emu,
        source_name=drawing.name,
        source_title=drawing.title,
    )


def resolve_internal_media_target(source_part: str, relationship: RelationshipInfo) -> str | None:
    """Résoudre une cible média interne en chemin ZIP canonique sûr."""
    target = relationship.target
    if not target or target.startswith("/") or "\\" in target:
        return None
    if any(segment == ".." for segment in target.split("/")):
        return None
    base = posixpath.dirname(source_part)
    resolved = posixpath.normpath(posixpath.join(base, target))
    if resolved.startswith("../") or "/../" in resolved or resolved == "..":
        return None
    if not resolved.startswith("word/media/"):
        return None
    return resolved


def _drawing_hyperlink_context(paragraph: ParagraphInfo) -> str | None:
    for run in paragraph.runs:
        if not any(item.kind == "drawing" for item in run.contents):
            continue
        if run.hyperlink_relationship_id:
            return f"relation={run.hyperlink_relationship_id}"
        if run.hyperlink_anchor:
            return f"ancre={run.hyperlink_anchor}"
    return None


def _paragraph_drawings(paragraph: ParagraphInfo) -> tuple[DrawingInfo, ...]:
    return tuple(
        item.drawing
        for run in paragraph.runs
        for item in run.contents
        if item.kind == "drawing" and item.drawing is not None
    )


def _paragraph_has_non_image_inline(paragraph: ParagraphInfo) -> bool:
    for run in paragraph.runs:
        for item in run.contents:
            if item.kind == "drawing":
                continue
            if item.kind == "text" and (item.text or "").strip() == "":
                continue
            return True
    return False


def _figure_error(
    code: str,
    message: str,
    paragraph: ParagraphInfo,
    note_id: str | None,
    drawing: DrawingInfo,
) -> EditorialDiagnostic:
    relationship = (
        drawing.embedded_relationship_ids[0]
        if drawing.embedded_relationship_ids
        else (drawing.linked_relationship_ids[0] if drawing.linked_relationship_ids else "absente")
    )
    name = f", nom={drawing.name}" if drawing.name else ""
    return EditorialDiagnostic(
        code=code,
        severity="error",
        message=f"{message} (relation={relationship}{name})",
        paragraph_index=paragraph.index,
        style_id=paragraph.style_id,
        note_id=note_id,
    )


def _paragraph_role(paragraph: ParagraphInfo, convention: WordEditorialConvention) -> ParagraphRole:
    """Centraliser les informations de style necessaires a la convention."""
    return convention.paragraph_role(
        paragraph.style_id,
        paragraph.outline_level,
        style_name=paragraph.style_name,
        style_is_custom=paragraph.style_is_custom,
    )


def _has_serializable_numbering_core(numbering: object) -> bool:
    """Predicat unique des numerotations Word representables en liste TEI."""
    from mini_metopes.docx import ParagraphNumberingInfo

    return (
        isinstance(numbering, ParagraphNumberingInfo)
        and numbering.list_kind in {"ordered", "bulleted"}
        and numbering.level is not None
        and numbering.num_format is not None
    )


def _is_serializable_list_paragraph(paragraph: ParagraphInfo, role_kind: str) -> bool:
    """Verifier les preconditions editoriales de la passe 8B."""
    numbering = paragraph.numbering
    return (
        role_kind == "paragraph"
        and numbering is not None
        and numbering.origin == "direct"
        and numbering.status == "resolved"
        and _has_serializable_numbering_core(numbering)
        and numbering.picture_bullet_id is None
        and numbering.is_legal is not True
        and numbering.restart_after_level is None
    )


def _numbering_id(paragraph: ParagraphInfo) -> str | None:
    numbering = paragraph.numbering
    if numbering is None:
        return None
    return numbering.numbering_id


def _numbering_ids_for_paragraphs(paragraphs: tuple[ParagraphInfo | TableInfo, ...]) -> set[str]:
    numbering_ids: set[str] = set()
    for paragraph in paragraphs:
        if not isinstance(paragraph, ParagraphInfo):
            continue
        numbering_id = _numbering_id(paragraph)
        if numbering_id is not None:
            numbering_ids.add(numbering_id)
    return numbering_ids


def _diagnose_interrupted_list_continuation(
    paragraph: ParagraphInfo,
    interrupted_numbering_ids: _NumberingInterruptions,
    diagnostics: list[EditorialDiagnostic],
    note_id: str | None,
) -> None:
    numbering = paragraph.numbering
    if numbering is None or numbering.numbering_id not in interrupted_numbering_ids:
        return
    level = "absent" if numbering.level is None else str(numbering.level)
    interruptions = interrupted_numbering_ids[numbering.numbering_id]
    diagnostics.append(
        EditorialDiagnostic(
            code="interrupted_list_continuation_not_serializable",
            severity="error",
            message=(
                "reouverture discontinue d'une meme instance de liste : "
                f"numId={numbering.numbering_id}, ilvl={level}, interruptions={interruptions}"
            ),
            paragraph_index=paragraph.index,
            style_id=paragraph.style_id,
            note_id=note_id,
        )
    )


def _add_interrupted_list_continuation_diagnostic(
    paragraph: ParagraphInfo,
    *,
    interruptions: int,
    diagnostics: list[EditorialDiagnostic],
    note_id: str | None,
) -> None:
    numbering = paragraph.numbering
    if numbering is None:
        return
    level = "absent" if numbering.level is None else str(numbering.level)
    diagnostics.append(
        EditorialDiagnostic(
            code="interrupted_list_continuation_not_serializable",
            severity="error",
            message=(
                "reouverture discontinue d'une meme instance de liste : "
                f"numId={numbering.numbering_id}, ilvl={level}, interruptions={interruptions}"
            ),
            paragraph_index=paragraph.index,
            style_id=paragraph.style_id,
            note_id=note_id,
        )
    )


def _build_list_sequence(
    paragraphs: tuple[ParagraphInfo | TableInfo, ...],
    start_position: int,
    *,
    convention: WordEditorialConvention,
    relationships: dict[str, RelationshipInfo],
    media_by_path: dict[str, MediaInfo],
    source_part: str,
    diagnostics: list[EditorialDiagnostic],
    note_id: str | None,
    interrupted_numbering_ids: _NumberingInterruptions,
) -> tuple[tuple[EditorialList, ...], int, set[tuple[str, str]], set[str]]:
    """Reconstruire une sequence contigue de listes par niveaux OOXML directs.

    Les objets publics restent immuables ; cette fonction utilise seulement des
    constructeurs prives mutables le temps d'etablir les relations parent/enfant.
    """
    first = paragraphs[start_position]
    assert isinstance(first, ParagraphInfo)
    assert first.numbering is not None and first.numbering.level is not None
    root_level = first.numbering.level
    roots: list[_ListBuilder] = []
    active: dict[int, _ListBuilder] = {}
    locally_closed_levels: set[_ClosedNumberingLevel] = set()
    locally_closed_numbering_ids: set[str] = set()
    references: set[tuple[str, str]] = set()
    previous_level: int | None = None
    position = start_position

    while position < len(paragraphs):
        paragraph = paragraphs[position]
        if not isinstance(paragraph, ParagraphInfo):
            break
        role = _paragraph_role(paragraph, convention)
        if not _is_serializable_list_paragraph(paragraph, role.kind):
            if previous_level is not None and _is_list_continuation_candidate(paragraph, role, convention):
                next_position = _handle_list_continuations(
                    paragraphs,
                    position,
                    previous_builder=active[previous_level],
                    previous_signature=active[previous_level].signature,
                    previous_numbering_id=active[previous_level].numbering_id,
                    previous_level=previous_level,
                    convention=convention,
                    relationships=relationships,
                    diagnostics=diagnostics,
                    note_id=note_id,
                    references=references,
                )
                if next_position == position:
                    break
                position = next_position
                continue
            if previous_level is not None and _is_rejected_list_continuation_style(paragraph, convention):
                _diagnose_ambiguous_list_continuation(
                    paragraph,
                    count=1,
                    previous_numbering_id=active[previous_level].numbering_id,
                    previous_level=previous_level,
                    next_paragraph=None,
                    reason="style personnalise",
                    diagnostics=diagnostics,
                    note_id=note_id,
                )
            break
        numbering = paragraph.numbering
        assert numbering is not None and numbering.level is not None
        if paragraph.drawing_count:
            diagnostics.append(
                EditorialDiagnostic(
                    code="image_in_list_item_not_serializable",
                    severity="error",
                    message="image presente dans un item de liste",
                    paragraph_index=paragraph.index,
                    style_id=paragraph.style_id,
                    note_id=note_id,
                )
            )
        level = numbering.level
        active_numbering_ids = {builder.numbering_id for builder in active.values()}
        closed_level = (numbering.numbering_id, level)
        if numbering.numbering_id in interrupted_numbering_ids:
            _diagnose_interrupted_list_continuation(
                paragraph,
                interrupted_numbering_ids,
                diagnostics,
                note_id,
            )
        elif closed_level in locally_closed_levels:
            _add_interrupted_list_continuation_diagnostic(
                paragraph,
                interruptions=0,
                diagnostics=diagnostics,
                note_id=note_id,
            )
        elif (
            numbering.numbering_id in locally_closed_numbering_ids
            and numbering.numbering_id not in active_numbering_ids
        ):
            _add_interrupted_list_continuation_diagnostic(
                paragraph,
                interruptions=0,
                diagnostics=diagnostics,
                note_id=note_id,
            )

        if previous_level is not None and level > previous_level + 1:
            diagnostics.append(
                EditorialDiagnostic(
                    code="list_level_jump_not_serializable",
                    severity="error",
                    message=(
                        "saut de niveau de liste ambigu : "
                        f"{previous_level} vers {level} (numId={numbering.numbering_id})"
                    ),
                    paragraph_index=paragraph.index,
                    style_id=paragraph.style_id,
                    note_id=note_id,
                )
            )
            break
        if level < root_level:
            diagnostics.append(
                EditorialDiagnostic(
                    code="list_root_level_decrease_split",
                    severity="warning",
                    message=(
                        "diminution sous le niveau racine local de liste : "
                        f"{root_level} vers {level}; nouvelle liste racine"
                    ),
                    paragraph_index=paragraph.index,
                    style_id=paragraph.style_id,
                    note_id=note_id,
                )
            )
            break

        content, item_references = _build_inline_content(
            paragraph,
            convention=convention,
            relationships=relationships,
            diagnostics=diagnostics,
            note_id=note_id,
        )
        references.update(item_references)
        item = _ListItemBuilder(
            content=content,
            source_paragraph_index=paragraph.index,
            source_style_id=paragraph.style_id,
        )
        signature = _numbering_signature(numbering)

        if previous_level is None:
            builder = _new_list_builder(numbering, paragraph, diagnostics, note_id)
            roots.append(builder)
            active[level] = builder
            if level != 0:
                diagnostics.append(
                    EditorialDiagnostic(
                        code="list_root_level_normalized",
                        severity="warning",
                        message=f"liste racine observee au niveau OOXML {level}",
                        paragraph_index=paragraph.index,
                        style_id=paragraph.style_id,
                        note_id=note_id,
                    )
                )
        elif level == previous_level:
            builder = active[level]
            if builder.signature != signature:
                locally_closed_levels.add((builder.numbering_id, builder.level))
                locally_closed_numbering_ids.add(builder.numbering_id)
                builder = _new_list_builder(numbering, paragraph, diagnostics, note_id)
                _attach_sibling_list(builder, level, root_level, active, roots)
                active[level] = builder
        elif level > previous_level:
            parent = active[previous_level]
            builder = _new_list_builder(numbering, paragraph, diagnostics, note_id)
            parent.items[-1].child_lists.append(builder)
            active[level] = builder
        else:
            for active_level in tuple(active):
                if active_level > level:
                    locally_closed_levels.add((active[active_level].numbering_id, active[active_level].level))
                    locally_closed_numbering_ids.add(active[active_level].numbering_id)
                    del active[active_level]
            builder = active[level]
            if builder.signature != signature:
                locally_closed_levels.add((builder.numbering_id, builder.level))
                locally_closed_numbering_ids.add(builder.numbering_id)
                builder = _new_list_builder(numbering, paragraph, diagnostics, note_id)
                _attach_sibling_list(builder, level, root_level, active, roots)
                active[level] = builder

        builder.items.append(item)
        previous_level = level
        position += 1

    return (
        tuple(_freeze_list(root, diagnostics, note_id) for root in roots),
        position,
        references,
        _numbering_ids_for_paragraphs(paragraphs[start_position:position]),
    )


def _is_list_continuation_candidate(
    paragraph: ParagraphInfo,
    role: ParagraphRole,
    convention: WordEditorialConvention,
) -> bool:
    return (
        role.kind == "paragraph"
        and convention.is_list_continuation_style(paragraph.style_id, paragraph.style_is_custom)
        and paragraph.numbering is None
        and paragraph.numbering_id is None
    )


def _is_rejected_list_continuation_style(
    paragraph: ParagraphInfo,
    convention: WordEditorialConvention,
) -> bool:
    return (
        paragraph.style_id in convention.list_continuation_style_ids
        and paragraph.style_is_custom is True
        and paragraph.numbering is None
        and paragraph.numbering_id is None
    )


def _handle_list_continuations(
    paragraphs: tuple[ParagraphInfo | TableInfo, ...],
    start_position: int,
    *,
    previous_builder: _ListBuilder,
    previous_signature: tuple[str, int, str, str, int | None, int | None],
    previous_numbering_id: str,
    previous_level: int,
    convention: WordEditorialConvention,
    relationships: dict[str, RelationshipInfo],
    diagnostics: list[EditorialDiagnostic],
    note_id: str | None,
    references: set[tuple[str, str]],
) -> int:
    """Rattacher une suite prouvee de ListParagraph au dernier item numerote."""
    position = start_position
    candidates: list[ParagraphInfo] = []
    while position < len(paragraphs):
        paragraph = paragraphs[position]
        if not isinstance(paragraph, ParagraphInfo):
            break
        role = _paragraph_role(paragraph, convention)
        if not _is_list_continuation_candidate(paragraph, role, convention):
            break
        candidates.append(paragraph)
        position += 1

    next_paragraph = paragraphs[position] if position < len(paragraphs) else None
    next_role = _paragraph_role(next_paragraph, convention) if isinstance(next_paragraph, ParagraphInfo) else None
    if (
        next_paragraph is None
        or next_role is None
        or not _is_serializable_list_paragraph(next_paragraph, next_role.kind)
    ):
        _diagnose_ambiguous_list_continuation(
            candidates[0],
            count=len(candidates),
            previous_numbering_id=previous_numbering_id,
            previous_level=previous_level,
            next_paragraph=next_paragraph if isinstance(next_paragraph, ParagraphInfo) else None,
            reason="fin de sequence",
            diagnostics=diagnostics,
            note_id=note_id,
        )
        return start_position

    next_numbering = next_paragraph.numbering
    assert next_numbering is not None and next_numbering.level is not None
    next_signature = _numbering_signature(next_numbering)
    if next_numbering.numbering_id != previous_numbering_id:
        reason = "autre instance"
    elif next_numbering.level != previous_level:
        reason = "autre niveau"
        if next_numbering.level < previous_level:
            reason = "autre niveau; reprise apres sous-liste ambigue"
    elif next_signature != previous_signature:
        reason = "autre signature"
    else:
        reason = ""

    if reason:
        _diagnose_ambiguous_list_continuation(
            candidates[0],
            count=len(candidates),
            previous_numbering_id=previous_numbering_id,
            previous_level=previous_level,
            next_paragraph=next_paragraph,
            reason=reason,
            diagnostics=diagnostics,
            note_id=note_id,
        )
        return start_position

    target_item = previous_builder.items[-1]
    for candidate in candidates:
        if candidate.drawing_count:
            diagnostics.append(
                EditorialDiagnostic(
                    code="image_in_list_item_not_serializable",
                    severity="error",
                    message="image presente dans une continuation d'item de liste",
                    paragraph_index=candidate.index,
                    style_id=candidate.style_id,
                    note_id=note_id,
                )
            )
        content, continuation_references = _build_inline_content(
            candidate,
            convention=convention,
            relationships=relationships,
            diagnostics=diagnostics,
            note_id=note_id,
        )
        references.update(continuation_references)
        if not content:
            diagnostics.append(
                EditorialDiagnostic(
                    code="empty_list_continuation_not_serializable",
                    severity="error",
                    message="paragraphe de continuation de liste vide",
                    paragraph_index=candidate.index,
                    style_id=candidate.style_id,
                    note_id=note_id,
                )
            )
        target_item.continuation_paragraphs.append(
            Paragraph(
                content=content,
                source_paragraph_index=candidate.index,
                source_style_id=candidate.style_id,
                rendition=None,
            )
        )
    return position


def _diagnose_ambiguous_list_continuation(
    paragraph: ParagraphInfo,
    *,
    count: int,
    previous_numbering_id: str,
    previous_level: int,
    next_paragraph: ParagraphInfo | None,
    reason: str,
    diagnostics: list[EditorialDiagnostic],
    note_id: str | None,
) -> None:
    next_numbering = next_paragraph.numbering if next_paragraph is not None else None
    next_id = next_numbering.numbering_id if next_numbering is not None else "absent"
    next_level_value = next_numbering.level if next_numbering is not None else None
    next_level = "absent" if next_level_value is None else str(next_level_value)
    diagnostics.append(
        EditorialDiagnostic(
            code="ambiguous_list_continuation_not_serializable",
            severity="error",
            message=(
                "continuation de liste ambigue : "
                f"candidats={count}, numId precedent={previous_numbering_id}, "
                f"ilvl precedent={previous_level}, numId suivant={next_id}, "
                f"ilvl suivant={next_level}, raison={reason}"
            ),
            paragraph_index=paragraph.index,
            style_id=paragraph.style_id,
            note_id=note_id,
        )
    )


def _numbering_signature(numbering: object) -> tuple[str, int, str, str, int | None, int | None]:
    from mini_metopes.docx import ParagraphNumberingInfo

    assert isinstance(numbering, ParagraphNumberingInfo)
    assert _has_serializable_numbering_core(numbering)
    return (
        numbering.numbering_id,
        numbering.level,
        numbering.list_kind,
        numbering.num_format,
        numbering.start,
        numbering.restart_after_level,
    )


def _new_list_builder(
    numbering: object,
    paragraph: ParagraphInfo,
    diagnostics: list[EditorialDiagnostic],
    note_id: str | None,
) -> _ListBuilder:
    from mini_metopes.docx import ParagraphNumberingInfo

    assert isinstance(numbering, ParagraphNumberingInfo)
    assert _has_serializable_numbering_core(numbering)
    return _ListBuilder(
        list_kind=numbering.list_kind,
        num_format=numbering.num_format,
        start=numbering.start,
        numbering_id=numbering.numbering_id,
        level=numbering.level,
        level_text=numbering.level_text,
        suffix=numbering.suffix,
        restart_after_level=numbering.restart_after_level,
    )


def _attach_sibling_list(
    builder: _ListBuilder,
    level: int,
    root_level: int,
    active: dict[int, _ListBuilder],
    roots: list[_ListBuilder],
) -> None:
    """Rattacher une nouvelle signature au meme niveau, sans perdre l'ordre."""
    if level == root_level:
        roots.append(builder)
        return
    parent = active[level - 1]
    parent.items[-1].child_lists.append(builder)


def _freeze_list(
    builder: _ListBuilder,
    diagnostics: list[EditorialDiagnostic],
    note_id: str | None,
) -> EditorialList:
    items: list[EditorialListItem] = []
    for item in builder.items:
        children = tuple(_freeze_list(child, diagnostics, note_id) for child in item.child_lists)
        continuations = tuple(item.continuation_paragraphs)
        if not item.content and not children and not continuations:
            diagnostics.append(
                EditorialDiagnostic(
                    code="empty_list_item_not_serializable",
                    severity="error",
                    message="item de liste vide sans sous-liste",
                    paragraph_index=item.source_paragraph_index,
                    style_id=item.source_style_id,
                    note_id=note_id,
                )
            )
        elif not item.content and continuations:
            diagnostics.append(
                EditorialDiagnostic(
                    code="empty_list_item_not_serializable",
                    severity="error",
                    message="item de liste multiparagraphe sans paragraphe initial",
                    paragraph_index=item.source_paragraph_index,
                    style_id=item.source_style_id,
                    note_id=note_id,
                )
            )
        elif not item.content:
            diagnostics.append(
                EditorialDiagnostic(
                    code="empty_parent_list_item",
                    severity="warning",
                    message="item parent de liste sans contenu textuel",
                    paragraph_index=item.source_paragraph_index,
                    style_id=item.source_style_id,
                    note_id=note_id,
                )
            )
        items.append(
            EditorialListItem(
                content=item.content,
                child_lists=children,
                source_paragraph_index=item.source_paragraph_index,
                source_style_id=item.source_style_id,
                continuation_paragraphs=continuations,
            )
        )
    return EditorialList(
        list_kind=builder.list_kind,  # type: ignore[arg-type]
        num_format=builder.num_format,
        start=builder.start,
        source_numbering_id=builder.numbering_id,
        source_level=builder.level,
        level_text=builder.level_text,
        suffix=builder.suffix,
        restart_after_level=builder.restart_after_level,
        items=tuple(items),
    )


def _diagnose_nonserializable_numbering(
    paragraph: ParagraphInfo,
    role_kind: str,
    diagnostics: list[EditorialDiagnostic],
    note_id: str | None,
) -> None:
    """Conserver la raison editoriale exacte d'une liste encore refusee."""
    numbering = paragraph.numbering
    if numbering is None or numbering.status == "removed":
        return
    if role_kind != "paragraph":
        code = "numbered_nonparagraph_style_not_serializable"
        message = f"paragraphe numerote avec role editorial {role_kind}"
    elif numbering.restart_after_level is not None:
        code = "explicit_list_restart_not_serializable"
        message = f"redemarrage explicite de liste Word non serialisable (lvlRestart={numbering.restart_after_level})"
    elif numbering.origin == "style":
        code = "style_based_numbering_not_serializable"
        message = "numerotation portee uniquement par un style Word"
    elif numbering.is_legal is True:
        code = "legal_numbering_not_serializable"
        message = "numerotation legale Word non representable sans perte"
    elif numbering.list_kind == "none":
        code = "numbering_without_marker_not_serializable"
        message = "numerotation Word sans marqueur"
    else:
        code = "unsupported_numbering_not_serializable"
        message = "numerotation Word non resolue ou non prise en charge"
    diagnostics.append(
        EditorialDiagnostic(
            code=code,
            severity="error",
            message=f"{message} (numId={numbering.numbering_id})",
            paragraph_index=paragraph.index,
            style_id=paragraph.style_id,
            note_id=note_id,
        )
    )


def _build_verse_stanzas(
    paragraph: ParagraphInfo,
    content: tuple[EditorialInline, ...],
    note_id: str | None,
    diagnostics: list[EditorialDiagnostic],
) -> tuple[VerseStanza, ...]:
    """Decouper un paragraphe ``IntenseQuote`` en strophes, sans jamais produire de vers vide.

    Une ligne vide isolee entre deux vers par des retours manuels separe deux
    strophes distinctes (deux ``lg``) ; en debut ou fin de paragraphe elle
    n'est qu'un espacement de mise en page et est ignoree. Un paragraphe
    entierement vide ne produit aucune strophe.
    """
    if not content:
        diagnostics.append(
            _diagnostic(
                "empty_verse_paragraph_ignored",
                "info",
                "paragraphe de vers vide ignore (frontiere de strophe ou espacement)",
                paragraph,
                0,
                note_id,
            )
        )
        return ()

    raw_lines: list[tuple[EditorialInline, ...]] = []
    current: list[EditorialInline] = []
    for item in content:
        if isinstance(item, LineBreak):
            raw_lines.append(tuple(current))
            current = []
        else:
            current.append(item)
    raw_lines.append(tuple(current))

    start = 0
    end = len(raw_lines)
    while start < end and not raw_lines[start]:
        start += 1
    while end > start and not raw_lines[end - 1]:
        end -= 1
    trimmed = raw_lines[start:end]

    if not trimmed:
        diagnostics.append(
            _diagnostic(
                "empty_verse_paragraph_ignored",
                "info",
                "paragraphe de vers sans contenu textuel ignore",
                paragraph,
                0,
                note_id,
            )
        )
        return ()

    groups: list[list[tuple[EditorialInline, ...]]] = [[]]
    in_blank_run = False
    for line in trimmed:
        if line:
            groups[-1].append(line)
            in_blank_run = False
        elif not in_blank_run:
            groups.append([])
            diagnostics.append(
                _diagnostic(
                    "verse_stanza_break_from_blank_line",
                    "info",
                    "ligne(s) vide(s) interpretee(s) comme frontiere de strophe",
                    paragraph,
                    0,
                    note_id,
                )
            )
            in_blank_run = True

    return tuple(
        VerseStanza(
            lines=tuple(
                VerseLine(content=line, source_paragraph_index=paragraph.index, line_index=line_index)
                for line_index, line in enumerate(group)
            ),
            source_paragraph_index=paragraph.index,
            source_style_id=paragraph.style_id,
        )
        for group in groups
        if group
    )


def _diagnose_paragraph_style(
    paragraph: ParagraphInfo,
    convention: WordEditorialConvention,
    diagnostics: list[EditorialDiagnostic],
    note_id: str | None,
) -> None:
    style_id = paragraph.style_id
    role = _paragraph_role(paragraph, convention)
    if role.kind == "paragraph" and role.paragraph_rendition is not None:
        return
    if convention.is_figure_caption_style(style_id, paragraph.style_is_custom):
        return
    if style_id is None or style_id in convention.paragraph_style_ids:
        return
    if style_id in convention.deferred_paragraph_style_ids:
        diagnostics.append(
            EditorialDiagnostic(
                code="deferred_paragraph_style",
                severity="error",
                message=f"interpretation editoriale differee pour le style {style_id}",
                paragraph_index=paragraph.index,
                style_id=style_id,
                note_id=note_id,
            )
        )
        return
    if convention.is_table_of_contents_style(style_id, paragraph.style_is_custom):
        diagnostics.append(
            EditorialDiagnostic(
                code="word_generated_toc_not_supported",
                severity="error",
                message=(
                    f"table des matieres Word generee automatiquement detectee (style {style_id}) : "
                    "supprimez-la avant conversion, la structure div/head deja produite en tient lieu"
                ),
                paragraph_index=paragraph.index,
                style_id=style_id,
                note_id=note_id,
            )
        )
        return
    diagnostics.append(
        EditorialDiagnostic(
            code="unsupported_paragraph_style",
            severity="error",
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
        run_content: list[EditorialInline] = []
        for item in run.contents:
            if item.kind == "text":
                if item.text:
                    _append_inline(run_content, TextSpan(text=item.text, marks=marks, link=link, language=run.language))
            elif item.kind == "tab":
                run_content.append(Tab())
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
                _append_break(run_content, item.break_type, paragraph, run_index, note_id, diagnostics)
            elif item.kind == "footnote_reference" and item.reference_id is not None:
                run_content.append(NoteReference(note_id=item.reference_id, note_kind="footnote"))
                references.add(("footnote", item.reference_id))
            elif item.kind == "endnote_reference" and item.reference_id is not None:
                run_content.append(NoteReference(note_id=item.reference_id, note_kind="endnote"))
                references.add(("endnote", item.reference_id))
            elif item.kind == "drawing":
                run_content.append(DrawingReference(relationship_ids=item.relationship_ids))
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
        inline_style_status = convention.bibliographic_reference_inline_style_status(
            run.style_id, run.style_name, run.style_is_custom, run.style_type
        )
        if inline_style_status == "invalid":
            diagnostics.append(_diagnostic(
                "invalid_bibliographic_reference_inline_style",
                "error",
                "style bibliographique inline controle invalide",
                paragraph,
                run_index,
                note_id,
                style_id=run.style_id,
            ))
            continue
        if inline_style_status == "valid":
            if not run_content:
                diagnostics.append(_diagnostic(
                    "empty_bibliographic_reference_inline_not_serializable", "error", "reference bibliographique inline vide",
                    paragraph, run_index, note_id, style_id=run.style_id
                ))
            elif any(isinstance(item, DrawingReference) for item in run_content):
                diagnostics.append(_diagnostic(
                    "drawing_in_bibliographic_reference_inline_not_serializable", "error", "dessin dans une reference bibliographique inline",
                    paragraph, run_index, note_id, style_id=run.style_id
                ))
            elif content and isinstance(content[-1], BibliographicReferenceInline):
                previous = content[-1]
                content[-1] = BibliographicReferenceInline(previous.content + tuple(run_content))
            else:
                content.append(BibliographicReferenceInline(tuple(run_content)))
        else:
            for inline in run_content:
                _append_inline(content, inline)
    return tuple(content), references


def _marks_for_run(
    run: RunInfo,
    convention: WordEditorialConvention,
    paragraph: ParagraphInfo,
    run_index: int,
    note_id: str | None,
    diagnostics: list[EditorialDiagnostic],
) -> tuple[TextMark, ...]:
    if convention.bibliographic_reference_inline_style_status(
        run.style_id, run.style_name, run.style_is_custom, run.style_type
    ) in {"valid", "invalid"}:
        inherited = ()
    else:
        inherited = convention.character_marks(run.style_id)
    if inherited is None:
        diagnostics.append(
            _diagnostic(
                "unsupported_character_style",
                "error",
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
                "error",
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
                "error",
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
        if previous.marks == item.marks and previous.link == item.link and previous.language == item.language:
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
