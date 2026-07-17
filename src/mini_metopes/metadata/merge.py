"""Priorite du JSON et diagnostic des divergences avec le DOCX."""

from __future__ import annotations

from pathlib import Path

from .discovery import compute_file_sha256
from .model import DocumentMetadata, MetadataIssue, MetadataSuggestions


def metadata_consistency_issues(metadata: DocumentMetadata, docx_path: Path, suggestions: MetadataSuggestions) -> tuple[MetadataIssue, ...]:
    """Comparer sans jamais modifier le JSON, qui demeure la source d'autorite."""
    issues: list[MetadataIssue] = list(suggestions.diagnostics)
    if metadata.source.filename != docx_path.name:
        issues.append(MetadataIssue("metadata_source_filename_changed", "warning", "nom du DOCX different du JSON", "source.filename"))
    if metadata.source.sha256 != compute_file_sha256(docx_path):
        issues.append(MetadataIssue("metadata_source_changed", "warning", "empreinte du DOCX modifiee", "source.sha256"))
    if suggestions.title is not None and suggestions.title != metadata.title:
        issues.append(MetadataIssue("metadata_title_differs_from_docx", "warning", "le titre JSON differe du Title Word", "document.title"))
    if suggestions.subtitle != metadata.subtitle and suggestions.subtitle is not None:
        issues.append(MetadataIssue("metadata_subtitle_differs_from_docx", "warning", "le sous-titre JSON differe du Subtitle Word", "document.subtitle"))
    return tuple(issues)
