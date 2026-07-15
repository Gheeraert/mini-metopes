"""Résultats immuables produits par l'inspection OOXML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InspectionIssue:
    """Information ou avertissement non fatal produit pendant l'inspection."""

    code: str
    message: str
    severity: str
    part: str | None = None
    paragraph_index: int | None = None


@dataclass(frozen=True)
class StyleInfo:
    """Propriétés déclarées d'un style OOXML, sans calculer la cascade Word."""

    style_id: str
    name: str | None
    style_type: str | None
    based_on: str | None
    linked_style: str | None
    is_default: bool
    is_custom: bool | None
    outline_level: int | None
    quick_format: bool | None
    ui_priority: int | None


@dataclass(frozen=True)
class RunInfo:
    """Contenu et propriétés directement déclarées d'un run Word."""

    text: str
    style_id: str | None
    bold: bool | None
    italic: bool | None
    small_caps: bool | None
    caps: bool | None
    superscript: bool
    subscript: bool
    manual_breaks: int
    tabs: int
    footnote_reference_ids: tuple[str, ...]
    endnote_reference_ids: tuple[str, ...]
    break_types: tuple[str, ...]
    drawing_count: int
    drawing_relationship_ids: tuple[str, ...]


@dataclass(frozen=True)
class ParagraphInfo:
    """Observation d'un paragraphe dans l'ordre du corps du document."""

    index: int
    text: str
    style_id: str | None
    style_name: str | None
    outline_level: int | None
    numbering_id: str | None
    numbering_level: int | None
    manual_breaks: int
    footnote_reference_ids: tuple[str, ...]
    endnote_reference_ids: tuple[str, ...]
    hyperlink_count: int
    hyperlink_relationship_ids: tuple[str, ...]
    bookmark_start_ids: tuple[str, ...]
    drawing_count: int
    drawing_relationship_ids: tuple[str, ...]
    runs: tuple[RunInfo, ...]


@dataclass(frozen=True)
class NoteInfo:
    """Texte simple d'une note de bas de page ou de fin."""

    note_id: str
    kind: str
    text: str
    note_type: str | None


@dataclass(frozen=True)
class RelationshipInfo:
    """Relation déclarée par ``word/document.xml``."""

    relationship_id: str
    relationship_type: str
    target: str
    target_mode: str | None


@dataclass(frozen=True)
class MediaInfo:
    """Entrée média inventoriée à partir de l'index ZIP, sans extraction."""

    path: str
    compressed_size: int
    uncompressed_size: int
    content_type: str | None


@dataclass(frozen=True)
class DocxInspection:
    """Résultat structuré et déterministe de l'inspection d'un DOCX."""

    source: Path
    parts: tuple[str, ...]
    styles: tuple[StyleInfo, ...]
    paragraphs: tuple[ParagraphInfo, ...]
    footnotes: tuple[NoteInfo, ...]
    endnotes: tuple[NoteInfo, ...]
    relationships: tuple[RelationshipInfo, ...]
    media: tuple[MediaInfo, ...]
    issues: tuple[InspectionIssue, ...]


class DocxInspectionError(ValueError):
    """Erreur fatale de lecture d'un paquet DOCX.

    ``code`` est stable afin que les appelants puissent distinguer l'absence
    d'un fichier d'un paquet invalide sans analyser le message humain.
    """

    def __init__(self, code: str, message: str, *, part: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.part = part
