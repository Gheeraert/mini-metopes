"""Chainage DOCX -> modele editorial -> TEI validee."""

from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from mini_metopes.docx import DocxInspection, InspectionIssue, NoteInfo, ParagraphInfo, inspect_docx_file
from mini_metopes.editorial import (
    NATIVE_WORD_CONVENTION,
    EditorialFigure,
    EditorialList,
    EditorialBuildResult,
    EditorialDiagnostic,
    EditorialDocument,
    EditorialGraphic,
    WordEditorialConvention,
    build_editorial_document,
    NoteReference,
)
from mini_metopes.metadata import DocumentMetadata, extract_metadata_suggestions, metadata_consistency_issues, validate_metadata

from .model import TeiAsset, TeiConversionDiagnostic, TeiConversionResult
from .serializer import serialize_editorial_document_to_tei


MAX_MEDIA_PART_BYTES = 64 * 1024 * 1024
MAX_TOTAL_MEDIA_BYTES = 256 * 1024 * 1024

_BLOCKING_INSPECTION_CODES = frozenset(
    {
        "textboxes_not_inspected",
        "table_not_modeled",
        "missing_numbering_part",
        "unreadable_part",
        "malformed_xml_part",
        "xml_part_too_large",
        "vml_image_not_supported",
        "image_media_too_large",
        "total_image_media_too_large",
        "unreadable_image_media",
    }
)
_NON_BLOCKING_INSPECTION_CODES = frozenset(
    {
        "comments_not_inspected",
        "headers_footers_not_inspected",
        "list_paragraph_without_numbering",
        "missing_numbering_level_assumed_zero",
    }
)
_BLOCKING_EDITORIAL_CODES = frozenset(
    {
        "deferred_paragraph_style",
        "unsupported_paragraph_style",
        "unsupported_character_style",
        "unsupported_break_type",
        "conflicting_vertical_alignment",
        "numbered_nonparagraph_style_not_serializable",
        "style_based_numbering_not_serializable",
        "legal_numbering_not_serializable",
        "numbering_without_marker_not_serializable",
        "unsupported_numbering_not_serializable",
        "interrupted_list_continuation_not_serializable",
        "ambiguous_list_continuation_not_serializable",
        "empty_list_continuation_not_serializable",
        "explicit_list_restart_not_serializable",
        "list_level_jump_not_serializable",
        "empty_list_item_not_serializable",
        "missing_figure_description",
        "hyperlinked_image_not_serializable",
        "duplicate_image_relationship_not_serializable",
        "invalid_drawing_property_not_serializable",
        "floating_image_not_serializable",
        "cropped_image_not_serializable",
        "transformed_image_not_serializable",
        "multiple_image_sources_not_serializable",
        "mixed_text_and_image_not_serializable",
        "multiple_images_in_paragraph_not_serializable",
        "numbered_figure_not_serializable",
        "image_in_list_item_not_serializable",
        "orphan_figure_caption_not_serializable",
        "empty_figure_caption_not_serializable",
        "image_in_figure_caption_not_serializable",
        "numbered_figure_caption_not_serializable",
        "missing_image_relationship",
        "unsupported_image_relationship",
        "external_image_not_serializable",
        "unsafe_image_target",
        "missing_image_media_part",
        "unsupported_image_format",
        "image_content_type_mismatch",
        "multiple_image_sources_not_serializable",
    }
)
_METADATA_SUGGESTION_CODES = frozenset(
    {
        "empty_metadata_suggestion",
        "multiple_docx_titles",
        "multiple_docx_subtitles",
        "metadata_style_not_initial",
    }
)


def convert_docx_to_tei(
    path: Path,
    *,
    metadata: DocumentMetadata | None = None,
    convention: WordEditorialConvention = NATIVE_WORD_CONVENTION,
) -> TeiConversionResult:
    """Convertir un DOCX en TEI Commons Publishing sans ecrire de fichier."""
    if metadata is None:
        return TeiConversionResult(
            None,
            (TeiConversionDiagnostic(
                code="missing_metadata", severity="error",
                message="une conversion DOCX complete exige des metadonnees JSON validees",
                origin="metadata",
            ),),
            (),
        )
    inspection = inspect_docx_file(path)
    suggestions = extract_metadata_suggestions(inspection)
    excluded = frozenset(suggestions.consumed_paragraph_indexes)
    editorial = build_editorial_document(
        inspection, convention=convention, excluded_body_paragraph_indexes=excluded
    )
    diagnostics = prepare_tei_conversion(inspection, editorial)
    metadata_diagnostics: list[TeiConversionDiagnostic] = []
    metadata_validation = validate_metadata(metadata)
    metadata_diagnostics.extend(_metadata_diagnostics(metadata_validation.issues))
    metadata_diagnostics.extend(_metadata_diagnostics(suggestions.diagnostics))
    metadata_diagnostics.extend(_metadata_diagnostics(metadata_consistency_issues(metadata, path, suggestions)))
    diagnostics = _deduplicate_diagnostics(diagnostics + tuple(metadata_diagnostics))
    if any(diagnostic.severity == "error" for diagnostic in diagnostics):
        return TeiConversionResult(None, diagnostics, ())
    result = serialize_editorial_document_to_tei(
        editorial.document,
        metadata=metadata,
        initial_diagnostics=diagnostics,
    )
    if not result.is_successful:
        return result
    assets, asset_diagnostics = _extract_tei_assets(path, editorial.document)
    if asset_diagnostics:
        return TeiConversionResult(None, result.diagnostics + asset_diagnostics, ())
    return replace(result, assets=assets)


def _metadata_diagnostics(issues: tuple[object, ...]) -> tuple[TeiConversionDiagnostic, ...]:
    """Adapter les diagnostics metadata sans brouiller leur code stable."""
    from mini_metopes.metadata import MetadataIssue

    result: list[TeiConversionDiagnostic] = []
    for issue in issues:
        assert isinstance(issue, MetadataIssue)
        result.append(
            TeiConversionDiagnostic(
                code=issue.code,
                severity=issue.severity,
                message=issue.message,
                origin="metadata",
                metadata_path=issue.path,
            )
        )
    return tuple(result)


def _deduplicate_diagnostics(
    diagnostics: tuple[TeiConversionDiagnostic, ...],
) -> tuple[TeiConversionDiagnostic, ...]:
    seen: set[tuple[object, ...]] = set()
    result: list[TeiConversionDiagnostic] = []
    for diagnostic in diagnostics:
        if diagnostic.origin == "metadata" and diagnostic.code in _METADATA_SUGGESTION_CODES:
            key = (diagnostic.origin, diagnostic.code)
        else:
            key = (
                diagnostic.origin,
                diagnostic.code,
                diagnostic.metadata_path,
                diagnostic.source_part,
                diagnostic.source_paragraph_index,
                diagnostic.note_id,
                diagnostic.run_index,
                diagnostic.style_id,
            )
        if key in seen:
            continue
        seen.add(key)
        result.append(diagnostic)
    return tuple(result)


def prepare_tei_conversion(
    inspection: DocxInspection,
    editorial: EditorialBuildResult,
) -> tuple[TeiConversionDiagnostic, ...]:
    """Verifier conservatoirement les pertes connues avant serialisation TEI."""
    diagnostics: list[TeiConversionDiagnostic] = []
    diagnostics.extend(_inspection_diagnostics(inspection.issues))
    diagnostics.extend(_numbering_diagnostics(inspection))
    diagnostics.extend(_editorial_diagnostics(editorial.diagnostics))
    return tuple(diagnostics)


def _inspection_diagnostics(
    issues: tuple[InspectionIssue, ...],
) -> tuple[TeiConversionDiagnostic, ...]:
    diagnostics: list[TeiConversionDiagnostic] = []
    for issue in issues:
        severity = _inspection_severity(issue)
        diagnostics.append(
            TeiConversionDiagnostic(
                code=issue.code,
                severity=severity,
                message=issue.message,
                origin="inspection",
                source_paragraph_index=issue.paragraph_index,
                source_part=issue.part,
                note_id=issue.note_id,
            )
        )
    return tuple(diagnostics)


def _inspection_severity(issue: InspectionIssue) -> str:
    if issue.code in _NON_BLOCKING_INSPECTION_CODES:
        return "warning"
    if issue.code in _BLOCKING_INSPECTION_CODES or issue.severity == "error":
        return "error"
    return "error"


def _numbering_diagnostics(inspection: DocxInspection) -> tuple[TeiConversionDiagnostic, ...]:
    diagnostics: list[TeiConversionDiagnostic] = []
    diagnostics.extend(_paragraph_numbering_diagnostics(inspection.paragraphs, part="word/document.xml"))
    for note in inspection.footnotes:
        diagnostics.extend(_note_numbering_diagnostics(note, part="word/footnotes.xml"))
    for note in inspection.endnotes:
        diagnostics.extend(_note_numbering_diagnostics(note, part="word/endnotes.xml"))
    return tuple(diagnostics)


def _note_numbering_diagnostics(note: NoteInfo, *, part: str) -> tuple[TeiConversionDiagnostic, ...]:
    return _paragraph_numbering_diagnostics(
        note.paragraphs,
        part=part,
        note_id=note.note_id,
    )


def _paragraph_numbering_diagnostics(
    paragraphs: tuple[ParagraphInfo, ...],
    *,
    part: str,
    note_id: str | None = None,
) -> tuple[TeiConversionDiagnostic, ...]:
    diagnostics: list[TeiConversionDiagnostic] = []
    for paragraph in paragraphs:
        resolution = paragraph.numbering
        if resolution is not None and resolution.status == "removed":
            continue
        if _is_editorially_supported_numbering(resolution):
            continue
        if _is_editorially_supported_numbering_except_restart(resolution):
            continue
        if resolution is None and paragraph.numbering_id is None:
            continue
        numbering_id = resolution.numbering_id if resolution is not None else paragraph.numbering_id
        level_value = resolution.level if resolution is not None else paragraph.numbering_level
        level = "absent" if level_value is None else str(level_value)
        details = ""
        if resolution is not None:
            details = (
                f", kind={resolution.list_kind or 'inconnu'}, "
                f"numFmt={resolution.num_format or 'inconnu'}"
            )
        diagnostics.append(
            TeiConversionDiagnostic(
                code="numbered_paragraph_not_serializable",
                severity="error",
                message=(
                    "paragraphe numerote non serialisable en TEI dans cette passe "
                    f"(numId={numbering_id}, ilvl={level}{details})"
                ),
                origin="inspection",
                source_paragraph_index=paragraph.index,
                note_id=note_id,
                source_part=part,
            )
        )
    return tuple(diagnostics)


def _is_editorially_supported_numbering(resolution: object) -> bool:
    """Les seules listes que la passe 8B confie au modele editorial."""
    from mini_metopes.docx import ParagraphNumberingInfo

    return (
        isinstance(resolution, ParagraphNumberingInfo)
        and resolution.origin == "direct"
        and resolution.status == "resolved"
        and resolution.list_kind in {"ordered", "bulleted"}
        and resolution.level is not None
        and resolution.num_format is not None
        and resolution.picture_bullet_id is None
        and resolution.is_legal is not True
        and resolution.restart_after_level is None
    )


def _is_editorially_supported_numbering_except_restart(resolution: object) -> bool:
    """Laisser le constructeur editorial porter le diagnostic precis de restart."""
    from mini_metopes.docx import ParagraphNumberingInfo

    return (
        isinstance(resolution, ParagraphNumberingInfo)
        and resolution.origin == "direct"
        and resolution.status == "resolved"
        and resolution.list_kind in {"ordered", "bulleted"}
        and resolution.level is not None
        and resolution.num_format is not None
        and resolution.picture_bullet_id is None
        and resolution.is_legal is not True
        and resolution.restart_after_level is not None
    )


def _editorial_diagnostics(
    diagnostics: tuple[EditorialDiagnostic, ...],
) -> tuple[TeiConversionDiagnostic, ...]:
    result: list[TeiConversionDiagnostic] = []
    for diagnostic in diagnostics:
        severity = "error" if diagnostic.code in _BLOCKING_EDITORIAL_CODES else diagnostic.severity
        result.append(
            TeiConversionDiagnostic(
                code=diagnostic.code,
                severity=severity,
                message=diagnostic.message,
                origin="editorial",
                source_paragraph_index=diagnostic.paragraph_index,
                note_id=diagnostic.note_id,
                run_index=diagnostic.run_index,
                style_id=diagnostic.style_id,
            )
        )
    return tuple(result)


def _extract_tei_assets(
    docx_path: Path,
    document: EditorialDocument,
) -> tuple[tuple[TeiAsset, ...], tuple[TeiConversionDiagnostic, ...]]:
    graphics = _document_graphics(document)
    if not graphics:
        return (), ()
    diagnostics: list[TeiConversionDiagnostic] = []
    assets: dict[str, TeiAsset] = {}
    try:
        archive = ZipFile(docx_path)
    except (BadZipFile, OSError) as error:
        return (), (
            TeiConversionDiagnostic(
                code="unreadable_image_media",
                severity="error",
                message=f"impossible de rouvrir le DOCX pour extraire les medias : {error}",
            ),
        )
    with archive:
        unique_graphics: dict[str, EditorialGraphic] = {}
        for graphic in graphics:
            unique_graphics.setdefault(graphic.media_url, graphic)
        media_infos: dict[str, object] = {}
        total_media_bytes = 0
        for graphic in unique_graphics.values():
            try:
                info = archive.getinfo(graphic.source_media_path)
            except KeyError:
                diagnostics.append(
                    TeiConversionDiagnostic(
                        code="missing_image_media_part",
                        severity="error",
                        message=f"media absent pendant l'extraction : {graphic.source_media_path}",
                        origin="serialization",
                    )
                )
                continue
            if info.file_size > MAX_MEDIA_PART_BYTES:
                diagnostics.append(
                    TeiConversionDiagnostic(
                        code="image_media_too_large",
                        severity="error",
                        message=f"media image trop volumineux : {graphic.source_media_path}",
                        origin="serialization",
                    )
                )
                continue
            total_media_bytes += info.file_size
            media_infos[graphic.media_url] = info
        if total_media_bytes > MAX_TOTAL_MEDIA_BYTES:
            diagnostics.append(
                TeiConversionDiagnostic(
                    code="total_image_media_too_large",
                    severity="error",
                    message="taille totale des medias image utilises trop volumineuse",
                    origin="serialization",
                )
            )
        if diagnostics:
            return (), tuple(diagnostics)
        for graphic in unique_graphics.values():
            info = media_infos[graphic.media_url]
            try:
                data = archive.read(info)
            except (BadZipFile, OSError, RuntimeError, NotImplementedError, EOFError) as error:
                diagnostics.append(
                    TeiConversionDiagnostic(
                        code="unreadable_image_media",
                        severity="error",
                        message=f"media image illisible pendant l'extraction : {graphic.source_media_path}",
                        origin="serialization",
                    )
                )
                continue
            sha256 = hashlib.sha256(data).hexdigest()
            if sha256 != graphic.sha256:
                diagnostics.append(
                    TeiConversionDiagnostic(
                        code="image_media_changed_during_conversion",
                        severity="error",
                        message=f"empreinte modifiee pendant la conversion : {graphic.source_media_path}",
                    )
                )
                continue
            if _detected_content_type(data) != graphic.content_type:
                diagnostics.append(
                    TeiConversionDiagnostic(
                        code="image_content_type_mismatch",
                        severity="error",
                        message=f"signature image incoherente pendant l'extraction : {graphic.source_media_path}",
                    )
                )
                continue
            assets[graphic.media_url] = TeiAsset(
                relative_path=graphic.media_url,
                content_type=graphic.content_type,
                sha256=graphic.sha256,
                data=data,
            )
    return tuple(assets[key] for key in sorted(assets)), tuple(diagnostics)


def _document_graphics(document: EditorialDocument) -> tuple[EditorialGraphic, ...]:
    result: list[EditorialGraphic] = []
    for block in document.blocks:
        result.extend(_block_graphics(block))
    notes = {(note.note_kind, note.note_id): note for note in document.notes}
    pending = list(_block_note_references(document.blocks))
    visited: set[tuple[str, str]] = set()
    while pending:
        key = pending.pop(0)
        if key in visited:
            continue
        visited.add(key)
        note = notes.get(key)
        if note is None:
            continue
        for block in note.blocks:
            result.extend(_block_graphics(block))
        pending.extend(reference for reference in _block_note_references(note.blocks) if reference not in visited)
    return tuple(result)


def _block_graphics(block: object) -> tuple[EditorialGraphic, ...]:
    if isinstance(block, EditorialFigure):
        return (block.graphic,)
    if isinstance(block, EditorialList):
        result: list[EditorialGraphic] = []
        for item in block.items:
            for child in item.child_lists:
                result.extend(_block_graphics(child))
        return tuple(result)
    return ()


def _block_note_references(blocks: tuple[object, ...]) -> tuple[tuple[str, str], ...]:
    result: list[tuple[str, str]] = []
    for block in blocks:
        result.extend(_object_note_references(block))
    return tuple(result)


def _object_note_references(item: object) -> tuple[tuple[str, str], ...]:
    if isinstance(item, EditorialFigure):
        if item.caption is None:
            return ()
        return _inline_note_references(item.caption.content)
    if isinstance(item, EditorialList):
        result: list[tuple[str, str]] = []
        for list_item in item.items:
            result.extend(_inline_note_references(list_item.content))
            for paragraph in list_item.continuation_paragraphs:
                result.extend(_inline_note_references(paragraph.content))
            for child in list_item.child_lists:
                result.extend(_object_note_references(child))
        return tuple(result)
    content = getattr(item, "content", None)
    if isinstance(content, tuple):
        return _inline_note_references(content)
    stanzas = getattr(item, "stanzas", None)
    if isinstance(stanzas, tuple):
        result: list[tuple[str, str]] = []
        for stanza in stanzas:
            for verse in stanza.lines:
                result.extend(_inline_note_references(verse.content))
        return tuple(result)
    paragraphs = getattr(item, "paragraphs", None)
    if isinstance(paragraphs, tuple):
        result: list[tuple[str, str]] = []
        for paragraph in paragraphs:
            result.extend(_inline_note_references(paragraph.content))
        return tuple(result)
    return ()


def _inline_note_references(content: tuple[object, ...]) -> tuple[tuple[str, str], ...]:
    return tuple(
        (inline.note_kind, inline.note_id)
        for inline in content
        if isinstance(inline, NoteReference)
    )


def _detected_content_type(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None
