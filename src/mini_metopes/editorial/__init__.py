"""Convention Word native et modele editorial intermediaire."""

from .builder import build_editorial_document, build_editorial_document_from_file
from .convention import NATIVE_WORD_CONVENTION, WordEditorialConvention
from .model import (
    ColumnBreak,
    DiagnosticSeverity,
    DrawingReference,
    EditorialBlock,
    EditorialBuildResult,
    EditorialDiagnostic,
    EditorialDocument,
    EditorialInline,
    EditorialLink,
    EditorialNote,
    Heading,
    LineBreak,
    NoteReference,
    PageBreak,
    Paragraph,
    Tab,
    TextMark,
    TextSpan,
)
from .serialization import editorial_build_result_to_data, editorial_build_result_to_json

__all__ = [
    "ColumnBreak",
    "DiagnosticSeverity",
    "DrawingReference",
    "EditorialBlock",
    "EditorialBuildResult",
    "EditorialDiagnostic",
    "EditorialDocument",
    "EditorialInline",
    "EditorialLink",
    "EditorialNote",
    "Heading",
    "LineBreak",
    "NATIVE_WORD_CONVENTION",
    "NoteReference",
    "PageBreak",
    "Paragraph",
    "Tab",
    "TextMark",
    "TextSpan",
    "WordEditorialConvention",
    "build_editorial_document",
    "build_editorial_document_from_file",
    "editorial_build_result_to_data",
    "editorial_build_result_to_json",
]
