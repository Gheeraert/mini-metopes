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
    inspect_docx_file,
)

from .convention import NATIVE_WORD_CONVENTION, ParagraphRole, WordEditorialConvention
from .model import (
    ColumnBreak,
    DrawingReference,
    EditorialBlock,
    EditorialBuildResult,
    EditorialDiagnostic,
    EditorialDocument,
    EditorialFigure,
    EditorialGraphic,
    EditorialInline,
    EditorialList,
    EditorialListItem,
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

    body_paragraphs = tuple(
        paragraph for paragraph in inspection.paragraphs if paragraph.index not in excluded_body_paragraph_indexes
    )
    blocks, body_references = _build_blocks(
        body_paragraphs,
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
        role = _paragraph_role(paragraph, convention)

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

        if convention.is_figure_caption_style(paragraph.style_id, paragraph.style_is_custom):
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
            blocks.append(ProseQuote(paragraphs=tuple(quote_paragraphs)))
            continue

        if role.kind == "verse_quote":
            stanzas = [_build_verse_stanza(paragraph, content, note_id, diagnostics)]
            paragraph_position += 1
            while paragraph_position < len(paragraphs):
                next_paragraph = paragraphs[paragraph_position]
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
                rendition=role.paragraph_rendition,
            )
        )
        paragraph_position += 1
    return tuple(blocks), referenced_notes


def _has_active_numbering(paragraph: ParagraphInfo) -> bool:
    """Distinguer une liste active de l'annulation Word ``numId=0``."""
    if paragraph.numbering is not None:
        return paragraph.numbering.status != "removed"
    return paragraph.numbering_id is not None and paragraph.numbering_id != "0"


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
    paragraphs: tuple[ParagraphInfo, ...],
    position: int,
    *,
    convention: WordEditorialConvention,
    relationships: dict[str, RelationshipInfo],
    figure_relationships: _RelationshipIndex,
    media_by_path: dict[str, MediaInfo],
    source_part: str,
    diagnostics: list[EditorialDiagnostic],
    note_id: str | None,
) -> _BuiltFigure | None:
    paragraph = paragraphs[position]
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
    references: set[tuple[str, str]] = set()
    next_position = position + 1
    if next_position < len(paragraphs):
        candidate = paragraphs[next_position]
        if convention.is_figure_caption_style(candidate.style_id, candidate.style_is_custom):
            caption_content, caption_references = _build_inline_content(
                candidate,
                convention=convention,
                relationships=relationships,
                diagnostics=diagnostics,
                note_id=note_id,
            )
            references.update(caption_references)
            if _has_active_numbering(candidate):
                diagnostics.append(
                    EditorialDiagnostic(
                        code="numbered_figure_caption_not_serializable",
                        severity="error",
                        message="legende de figure numerotee",
                        paragraph_index=candidate.index,
                        style_id=candidate.style_id,
                        note_id=note_id,
                    )
                )
            if candidate.drawing_count:
                diagnostics.append(
                    EditorialDiagnostic(
                        code="image_in_figure_caption_not_serializable",
                        severity="error",
                        message="image presente dans une legende de figure",
                        paragraph_index=candidate.index,
                        style_id=candidate.style_id,
                        note_id=note_id,
                    )
                )
            if not caption_content:
                diagnostics.append(
                    EditorialDiagnostic(
                        code="empty_figure_caption_not_serializable",
                        severity="error",
                        message="legende de figure vide",
                        paragraph_index=candidate.index,
                        style_id=candidate.style_id,
                        note_id=note_id,
                    )
                )
            caption = Paragraph(
                content=caption_content,
                source_paragraph_index=candidate.index,
                source_style_id=candidate.style_id,
                rendition="caption",
            )
            next_position += 1
    return _BuiltFigure(
        figure=EditorialFigure(
            graphic=graphic,
            caption=caption,
            source_paragraph_index=paragraph.index,
            source_style_id=paragraph.style_id,
        ),
        next_position=next_position,
        references=references,
    )


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


def _is_serializable_list_paragraph(paragraph: ParagraphInfo, role_kind: str) -> bool:
    """Verifier les preconditions editoriales de la passe 8B."""
    numbering = paragraph.numbering
    return (
        role_kind == "paragraph"
        and numbering is not None
        and numbering.origin == "direct"
        and numbering.status == "resolved"
        and numbering.list_kind in {"ordered", "bulleted"}
        and numbering.level is not None
        and numbering.num_format is not None
        and numbering.picture_bullet_id is None
        and numbering.is_legal is not True
        and numbering.restart_after_level is None
    )


def _numbering_id(paragraph: ParagraphInfo) -> str | None:
    numbering = paragraph.numbering
    if numbering is None:
        return None
    return numbering.numbering_id


def _numbering_ids_for_paragraphs(paragraphs: tuple[ParagraphInfo, ...]) -> set[str]:
    numbering_ids: set[str] = set()
    for paragraph in paragraphs:
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
    paragraphs: tuple[ParagraphInfo, ...],
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
    paragraphs: tuple[ParagraphInfo, ...],
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
        role = _paragraph_role(paragraph, convention)
        if not _is_list_continuation_candidate(paragraph, role, convention):
            break
        candidates.append(paragraph)
        position += 1

    next_paragraph = paragraphs[position] if position < len(paragraphs) else None
    next_role = _paragraph_role(next_paragraph, convention) if next_paragraph is not None else None
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
            next_paragraph=next_paragraph,
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
    assert numbering.level is not None and numbering.list_kind in {"ordered", "bulleted"}
    assert numbering.num_format is not None
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
    assert numbering.level is not None and numbering.list_kind in {"ordered", "bulleted"}
    assert numbering.num_format is not None
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
