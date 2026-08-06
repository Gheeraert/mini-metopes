"""Suggestions conservatoires depuis les styles Title/Subtitle et Signature du DOCX."""

from __future__ import annotations

from mini_metopes.docx import DocxInspection, ParagraphInfo
from mini_metopes.editorial.convention import NATIVE_WORD_CONVENTION, native_style_alias_map

from .model import MetadataIssue, MetadataSuggestions, SignatureSuggestion

_HEADING_STYLE_IDS_UP_TO_LEVEL_2 = frozenset(
    style_id for style_id, level in NATIVE_WORD_CONVENTION.heading_style_ids if level <= 2
)


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
    signatures = _extract_signature_suggestions(inspection.paragraphs, aliases)
    return MetadataSuggestions(title, subtitle, tuple(issues), tuple(consumed), signatures)


def _extract_signature_suggestions(
    paragraphs: tuple[ParagraphInfo, ...], aliases: dict[str, str]
) -> tuple[SignatureSuggestion, ...]:
    """Lire chaque suite de paragraphes ``Signature`` terminale par
    contribution (nom, institution) : fin de document, ou juste avant un
    titre de niveau 1 a 2 (decision 0037, livre entier uniquement).

    Jamais consommees : contrairement a Title/Subtitle, ces paragraphes
    restent du contenu editorial visible (voir editorial/builder.py). Une
    suite de plus de deux lignes est ambigue et n'est pas resumee ici ; la
    conversion la refusera explicitement (``misplaced_signature_not_serializable``).
    Detection independante de celle du builder (ne depend pas du systeme
    complet de convention/role), coherent avec le couplage deja accepte
    pour Title/Subtitle dans ce fichier.
    """
    suggestions: list[SignatureSuggestion] = []
    position = 0
    total = len(paragraphs)

    def resolved_style(index: int) -> str | None:
        style = paragraphs[index].style_id
        return aliases.get(style, style) if style is not None else style

    while position < total:
        if resolved_style(position) != "Signature":
            position += 1
            continue
        run: list[str] = []
        while position < total and resolved_style(position) == "Signature":
            run.append(paragraphs[position].text.strip())
            position += 1
        terminal = position == total or resolved_style(position) in _HEADING_STYLE_IDS_UP_TO_LEVEL_2
        if terminal and run and len(run) <= 2:
            name = run[0] or None
            affiliation = (run[1] or None) if len(run) > 1 else None
            suggestions.append(SignatureSuggestion(name, affiliation))
    return tuple(suggestions)
