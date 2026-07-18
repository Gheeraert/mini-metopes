"""Résultats immuables produits par l'inspection OOXML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


RunContentKind = Literal[
    "text",
    "tab",
    "break",
    "footnote_reference",
    "endnote_reference",
    "drawing",
]


@dataclass(frozen=True)
class RunContentInfo:
    """Element inline observe dans un run, dans l'ordre OOXML."""

    kind: RunContentKind
    text: str | None = None
    break_type: str | None = None
    reference_id: str | None = None
    relationship_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class InspectionIssue:
    """Information ou avertissement non fatal produit pendant l'inspection."""

    code: str
    message: str
    severity: str
    part: str | None = None
    paragraph_index: int | None = None
    note_id: str | None = None


NumberingListKind = Literal["ordered", "bulleted", "none", "unsupported"]
NumberingResolutionStatus = Literal["resolved", "removed", "unresolved", "unsupported"]


@dataclass(frozen=True)
class NumberingLevelInfo:
    """Definition OOXML brute d'un niveau de numerotation."""

    level: int
    start: int | None
    num_format: str | None
    level_text: str | None
    suffix: str | None
    paragraph_style_id: str | None
    restart_after_level: int | None
    is_legal: bool | None
    picture_bullet_id: str | None
    invalid_properties: tuple[str, ...] = ()


@dataclass(frozen=True)
class AbstractNumberingInfo:
    """Definition abstraite ``w:abstractNum``."""

    abstract_numbering_id: str
    multi_level_type: str | None
    name: str | None
    levels: tuple[NumberingLevelInfo, ...]


@dataclass(frozen=True)
class NumberingLevelOverrideInfo:
    """Surcharge d'un niveau dans une instance ``w:num``."""

    level: int
    start_override: int | None
    level_override: NumberingLevelInfo | None
    invalid_properties: tuple[str, ...] = ()


@dataclass(frozen=True)
class NumberingInstanceInfo:
    """Instance ``w:num`` associee a une definition abstraite."""

    numbering_id: str
    abstract_numbering_id: str | None
    level_overrides: tuple[NumberingLevelOverrideInfo, ...]


@dataclass(frozen=True)
class NumberingDefinitionsInfo:
    """Ensemble immutable des definitions lues dans ``numbering.xml``."""

    abstract_definitions: tuple[AbstractNumberingInfo, ...] = ()
    instances: tuple[NumberingInstanceInfo, ...] = ()


@dataclass(frozen=True)
class ParagraphNumberingInfo:
    """Resolution conservative de la numerotation d'un paragraphe."""

    numbering_id: str
    level: int | None
    status: NumberingResolutionStatus
    abstract_numbering_id: str | None
    list_kind: NumberingListKind | None
    num_format: str | None
    level_text: str | None
    start: int | None
    suffix: str | None
    restart_after_level: int | None
    is_legal: bool | None
    picture_bullet_id: str | None
    origin: Literal["direct", "style"]


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
    numbering_id: str | None = None
    numbering_level: int | None = None
    numbering_level_invalid: bool = False
    numbering_properties_present: bool = False
    numbering_id_invalid: bool = False


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
    contents: tuple[RunContentInfo, ...]
    hyperlink_relationship_id: str | None
    hyperlink_anchor: str | None


@dataclass(frozen=True)
class ParagraphInfo:
    """Observation d'un paragraphe dans l'ordre du corps du document."""

    index: int
    text: str
    style_id: str | None
    style_name: str | None
    style_is_custom: bool | None
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
    numbering: ParagraphNumberingInfo | None = None


@dataclass(frozen=True)
class NoteInfo:
    """Note de bas de page ou de fin avec ses paragraphes observes."""

    note_id: str
    kind: str
    text: str
    paragraphs: tuple[ParagraphInfo, ...]
    note_type: str | None


@dataclass(frozen=True)
class RelationshipInfo:
    """Relation déclarée par une partie OOXML."""

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
    footnote_relationships: tuple[RelationshipInfo, ...]
    endnote_relationships: tuple[RelationshipInfo, ...]
    media: tuple[MediaInfo, ...]
    issues: tuple[InspectionIssue, ...]
    numbering_definitions: NumberingDefinitionsInfo = NumberingDefinitionsInfo()


class DocxInspectionError(ValueError):
    """Erreur fatale de lecture d'un paquet DOCX.

    ``code`` est stable afin que les appelants puissent distinguer l'absence
    d'un fichier d'un paquet invalide sans analyser le message humain.
    """

    def __init__(self, code: str, message: str, *, part: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.part = part
