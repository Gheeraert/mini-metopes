"""Suggestions conservatoires depuis les styles Title et Subtitle du DOCX."""

from __future__ import annotations

from mini_metopes.docx import DocxInspection
from mini_metopes.editorial.convention import native_style_alias_map

from .model import MetadataIssue, MetadataSuggestions


def extract_metadata_suggestions(inspection: DocxInspection) -> MetadataSuggestions:
    """Lire seulement le preambule initial compose de Title/Subtitle natifs."""
    title: str | None = None
    subtitle: str | None = None
    consumed: list[int] = []
    issues: list[MetadataIssue] = []
    preamble = True
    aliases = native_style_alias_map(inspection.styles)
    for paragraph in inspection.paragraphs:
        style = paragraph.style_id
        if style is not None:
            style = aliases.get(style, style)
        if preamble and style in {"Title", "Subtitle"}:
            text = paragraph.text.strip()
            if not text:
                issues.append(MetadataIssue("empty_metadata_suggestion", "error", f"{style} initial vide", f"paragraphs[{paragraph.index}]"))
            elif style == "Title":
                if title is None:
                    title = text
                    consumed.append(paragraph.index)
                else:
                    issues.append(MetadataIssue("multiple_docx_titles", "warning", "plusieurs Title initiaux", f"paragraphs[{paragraph.index}]"))
            else:
                if subtitle is None:
                    subtitle = text
                    consumed.append(paragraph.index)
                else:
                    issues.append(MetadataIssue("multiple_docx_subtitles", "warning", "plusieurs Subtitle initiaux", f"paragraphs[{paragraph.index}]"))
            continue
        preamble = False
        if style in {"Title", "Subtitle"}:
            issues.append(MetadataIssue("metadata_style_not_initial", "error", f"{style} hors preambule initial", f"paragraphs[{paragraph.index}]"))
    return MetadataSuggestions(title, subtitle, tuple(issues), tuple(consumed))
