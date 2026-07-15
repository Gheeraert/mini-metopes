"""Inspection en lecture seule des paquets DOCX OOXML."""

from .inspector import inspect_docx_file
from .model import (
    DocxInspection,
    DocxInspectionError,
    InspectionIssue,
    MediaInfo,
    NoteInfo,
    ParagraphInfo,
    RelationshipInfo,
    RunInfo,
    StyleInfo,
)

__all__ = [
    "DocxInspection",
    "DocxInspectionError",
    "InspectionIssue",
    "MediaInfo",
    "NoteInfo",
    "ParagraphInfo",
    "RelationshipInfo",
    "RunInfo",
    "StyleInfo",
    "inspect_docx_file",
]
