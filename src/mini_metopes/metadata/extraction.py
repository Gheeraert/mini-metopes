"""Suggestions conservatoires depuis les styles Title/Subtitle et Signature du DOCX."""

from __future__ import annotations

from mini_metopes.docx import DocxInspection, ParagraphInfo
from mini_metopes.editorial.convention import native_style_alias_map

from .model import MetadataIssue, MetadataSuggestions


def extract_metadata_suggestions(inspection: DocxInspection) -> MetadataSuggestions:
    """Lire le preambule initial (Title/Subtitle) et la signature terminale (Signature)."""
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
    signature_name, signature_affiliation = _extract_signature_suggestion(inspection.paragraphs, aliases)
    return MetadataSuggestions(title, subtitle, tuple(issues), tuple(consumed), signature_name, signature_affiliation)


def _extract_signature_suggestion(
    paragraphs: tuple[ParagraphInfo, ...], aliases: dict[str, str]
) -> tuple[str | None, str | None]:
    """Lire la suite terminale de paragraphes ``Signature`` (nom, institution).

    Jamais consommee : contrairement a Title/Subtitle, ces paragraphes
    restent du contenu editorial visible (voir editorial/builder.py). Une
    suite de plus de deux lignes est ambigue et n'est pas resumee ici ; la
    conversion la refusera explicitement (``misplaced_signature_not_serializable``).
    """
    run: list[str] = []
    for paragraph in reversed(paragraphs):
        style = paragraph.style_id
        if style is not None:
            style = aliases.get(style, style)
        if style != "Signature":
            break
        run.append(paragraph.text.strip())
    if not run or len(run) > 2:
        return None, None
    ordered = list(reversed(run))
    name = ordered[0] or None
    affiliation = (ordered[1] or None) if len(ordered) > 1 else None
    return name, affiliation
