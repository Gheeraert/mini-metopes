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


def convert_docx_to_tei(
    path: Path,
    *,
    convention: WordEditorialConvention = NATIVE_WORD_CONVENTION,
) -> TeiConversionResult:
    """Convertir un DOCX en TEI Commons Publishing sans ecrire de fichier."""
    inspection = inspect_docx_file(path)
    editorial = build_editorial_document(inspection, convention=convention)
    diagnostics = prepare_tei_conversion(inspection, editorial)
    if any(diagnostic.severity == "error" for diagnostic in diagnostics):
        return TeiConversionResult(None, diagnostics, ())
    return serialize_editorial_document_to_tei(
        editorial.document,
        initial_diagnostics=diagnostics,
    )


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
        if paragraph.numbering_id is None:
            continue
        level = "absent" if paragraph.numbering_level is None else str(paragraph.numbering_level)
        diagnostics.append(
            TeiConversionDiagnostic(
                code="numbered_paragraph_not_serializable",
                severity="error",
                message=(
                    "paragraphe numerote non serialisable en TEI dans cette passe "
                    f"(numId={paragraph.numbering_id}, ilvl={level})"
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
