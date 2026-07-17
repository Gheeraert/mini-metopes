"""Chainage DOCX -> modele editorial -> TEI validee."""

from __future__ import annotations

from pathlib import Path

from mini_metopes.docx import DocxInspection, InspectionIssue, NoteInfo, ParagraphInfo, inspect_docx_file
from mini_metopes.editorial import (
    NATIVE_WORD_CONVENTION,
    EditorialBuildResult,
    EditorialDiagnostic,
    WordEditorialConvention,
    build_editorial_document,
)
from mini_metopes.metadata import DocumentMetadata, extract_metadata_suggestions, metadata_consistency_issues, validate_metadata

from .model import TeiConversionDiagnostic, TeiConversionResult
from .serializer import serialize_editorial_document_to_tei

_BLOCKING_INSPECTION_CODES = frozenset(
    {
        "textboxes_not_inspected",
        "table_not_modeled",
        "missing_numbering_part",
        "unreadable_part",
        "malformed_xml_part",
        "xml_part_too_large",
    }
)
_NON_BLOCKING_INSPECTION_CODES = frozenset(
    {
        "comments_not_inspected",
        "headers_footers_not_inspected",
        "list_paragraph_without_numbering",
    }
)
_BLOCKING_EDITORIAL_CODES = frozenset(
    {
        "deferred_paragraph_style",
        "unsupported_paragraph_style",
        "unsupported_character_style",
        "unsupported_break_type",
        "conflicting_vertical_alignment",
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
    return serialize_editorial_document_to_tei(
        editorial.document,
        metadata=metadata,
        initial_diagnostics=diagnostics,
    )


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
