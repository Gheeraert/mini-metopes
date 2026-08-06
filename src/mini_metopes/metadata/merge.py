"""Priorite du JSON et diagnostic des divergences avec le DOCX."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from .discovery import compute_file_sha256
from .model import DocumentMetadata, MetadataIssue, MetadataSuggestions


def metadata_consistency_issues(metadata: DocumentMetadata, docx_path: Path, suggestions: MetadataSuggestions) -> tuple[MetadataIssue, ...]:
    """Comparer sans jamais modifier le JSON, qui demeure la source d'autorite."""
    issues: list[MetadataIssue] = []
    recorded_name = PurePosixPath(metadata.source.path.replace("\\", "/")).name
    if recorded_name != docx_path.name:
        issues.append(MetadataIssue("metadata_source_filename_changed", "warning", "nom du DOCX different du JSON", "source_document.path"))
    if metadata.source.sha256 != compute_file_sha256(docx_path):
        issues.append(MetadataIssue("metadata_source_changed", "warning", "empreinte du DOCX modifiee", "source_document.sha256"))
    if suggestions.title is not None and suggestions.title != metadata.title:
        issues.append(MetadataIssue("metadata_title_differs_from_docx", "warning", "le titre JSON differe du Title Word", "document.title"))
    if suggestions.subtitle != metadata.subtitle and suggestions.subtitle is not None:
        issues.append(MetadataIssue("metadata_subtitle_differs_from_docx", "warning", "le sous-titre JSON differe du Subtitle Word", "document.subtitle"))
    for index, signature in enumerate(suggestions.signatures):
        if signature.name is not None and not _signature_matches_a_contributor(signature.name, metadata):
            issues.append(MetadataIssue(
                "signature_contributor_not_in_metadata", "warning",
                f"la signature Word ({signature.name!r}) ne correspond a aucun contributeur du JSON",
                f"signatures[{index}]",
            ))
    return tuple(issues)


def _signature_matches_a_contributor(signature_name: str, metadata: DocumentMetadata) -> bool:
    normalized = _normalize_name(signature_name)
    for contributor in metadata.contributors:
        candidates = (
            contributor.literal_name,
            " ".join(part for part in (contributor.given_name, contributor.family_name) if part) or None,
        )
        if any(candidate is not None and _normalize_name(candidate) == normalized for candidate in candidates):
            return True
    return False


def _normalize_name(value: str) -> str:
    return " ".join(value.casefold().split())
