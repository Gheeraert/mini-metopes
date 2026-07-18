"""Modele editorial intermediaire, independant de toute serialisation TEI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TextMark = Literal["bold", "italic", "small_caps", "caps", "superscript", "subscript"]
LinkKind = Literal["external", "internal", "unresolved"]
DiagnosticSeverity = Literal["info", "warning", "error"]
EditorialListKind = Literal["ordered", "bulleted"]
ParagraphRendition = Literal["consecutive", "caption"]


@dataclass(frozen=True)
class EditorialLink:
    """Destination OOXML resolue ou conservee de maniere conservatoire."""

    kind: LinkKind
    target: str | None = None
    relationship_id: str | None = None
    anchor: str | None = None


@dataclass(frozen=True)
class TextSpan:
    """Texte et marques typographiques deja normalises pour le modele."""

    text: str
    marks: tuple[TextMark, ...] = ()
    link: EditorialLink | None = None
    kind: Literal["text"] = "text"


@dataclass(frozen=True)
class Tab:
    """Tabulation OOXML conservee sans interpretation editoriale."""

    kind: Literal["tab"] = "tab"


@dataclass(frozen=True)
class LineBreak:
    """Saut de ligne manuel OOXML."""

    kind: Literal["line_break"] = "line_break"


@dataclass(frozen=True)
class PageBreak:
    """Saut de page OOXML."""

    kind: Literal["page_break"] = "page_break"


@dataclass(frozen=True)
class ColumnBreak:
    """Saut de colonne OOXML."""

    kind: Literal["column_break"] = "column_break"


@dataclass(frozen=True)
class NoteReference:
    """Appel de note, conserve meme si sa cible est absente."""

    note_id: str
    note_kind: Literal["footnote", "endnote"]
    kind: Literal["note_reference"] = "note_reference"


@dataclass(frozen=True)
class DrawingReference:
    """Reference de dessin ou d'image sans semantique editoriale prematuree."""

    relationship_ids: tuple[str, ...]
    kind: Literal["drawing_reference"] = "drawing_reference"


EditorialInline = (
    TextSpan | Tab | LineBreak | PageBreak | ColumnBreak | NoteReference | DrawingReference
)


@dataclass(frozen=True)
class Heading:
    """Titre de section detecte par la convention Word courante."""

    level: int
    content: tuple[EditorialInline, ...]
    source_paragraph_index: int
    source_style_id: str | None
    kind: Literal["heading"] = "heading"


@dataclass(frozen=True)
class Paragraph:
    """Paragraphe editorial encore non mappe vers la TEI."""

    content: tuple[EditorialInline, ...]
    source_paragraph_index: int
    source_style_id: str | None
    rendition: ParagraphRendition | None = None
    kind: Literal["paragraph"] = "paragraph"


@dataclass(frozen=True)
class ProseQuoteParagraph:
    """Paragraphe source conserve dans une citation en prose."""

    content: tuple[EditorialInline, ...]
    source_paragraph_index: int
    source_style_id: str | None
    kind: Literal["prose_quote_paragraph"] = "prose_quote_paragraph"


@dataclass(frozen=True)
class ProseQuote:
    """Suite contigue de paragraphes Word utilisant le style ``Quote``."""

    paragraphs: tuple[ProseQuoteParagraph, ...]
    kind: Literal["prose_quote"] = "prose_quote"


@dataclass(frozen=True)
class VerseLine:
    """Vers issu d'un segment separe par un retour manuel Word."""

    content: tuple[EditorialInline, ...]
    source_paragraph_index: int
    line_index: int
    kind: Literal["verse_line"] = "verse_line"


@dataclass(frozen=True)
class VerseStanza:
    """Strophe issue d'un paragraphe Word utilisant ``IntenseQuote``."""

    lines: tuple[VerseLine, ...]
    source_paragraph_index: int
    source_style_id: str | None
    kind: Literal["verse_stanza"] = "verse_stanza"


@dataclass(frozen=True)
class VerseQuote:
    """Suite contigue de strophes Word utilisant le style ``IntenseQuote``."""

    stanzas: tuple[VerseStanza, ...]
    kind: Literal["verse_quote"] = "verse_quote"


@dataclass(frozen=True)
class EditorialListItem:
    """Item de liste Word, avec ses sous-listes immediates dans l'ordre."""

    content: tuple[EditorialInline, ...]
    child_lists: tuple["EditorialList", ...]
    source_paragraph_index: int
    source_style_id: str | None
    continuation_paragraphs: tuple[Paragraph, ...] = ()
    kind: Literal["list_item"] = "list_item"


@dataclass(frozen=True)
class EditorialList:
    """Liste editoriale resolue depuis une instance directe de numerotation Word."""

    list_kind: EditorialListKind
    num_format: str
    start: int | None
    source_numbering_id: str
    source_level: int
    level_text: str | None
    suffix: str | None
    restart_after_level: int | None
    items: tuple[EditorialListItem, ...]
    kind: Literal["list"] = "list"


@dataclass(frozen=True)
class EditorialGraphic:
    """Image éditoriale publiée comme ressource externe content-addressée."""

    source_part: str
    source_relationship_id: str
    source_media_path: str
    media_url: str
    content_type: Literal["image/png", "image/jpeg"]
    sha256: str
    description: str
    width_emu: int | None
    height_emu: int | None
    source_name: str | None = None
    source_title: str | None = None
    kind: Literal["graphic"] = "graphic"


@dataclass(frozen=True)
class EditorialFigure:
    """Figure autonome issue d'une image Word simple."""

    graphic: EditorialGraphic
    caption: Paragraph | None
    source_paragraph_index: int
    source_style_id: str | None
    kind: Literal["figure"] = "figure"


EditorialBlock = Heading | Paragraph | ProseQuote | VerseQuote | EditorialList | EditorialFigure


@dataclass(frozen=True)
class EditorialNote:
    """Note conservee hors de la sequence de blocs principale."""

    note_id: str
    note_kind: Literal["footnote", "endnote"]
    blocks: tuple[EditorialBlock, ...]
    kind: Literal["note"] = "note"


@dataclass(frozen=True)
class EditorialDocument:
    """Document editorial construit depuis une inspection DOCX."""

    source_name: str
    blocks: tuple[EditorialBlock, ...]
    notes: tuple[EditorialNote, ...]
    kind: Literal["document"] = "document"


@dataclass(frozen=True)
class EditorialDiagnostic:
    """Diagnostic stable produit pendant l'application de la convention."""

    code: str
    severity: DiagnosticSeverity
    message: str
    paragraph_index: int | None = None
    run_index: int | None = None
    style_id: str | None = None
    note_id: str | None = None


@dataclass(frozen=True)
class EditorialBuildResult:
    """Document editorial et diagnostics associes."""

    document: EditorialDocument
    diagnostics: tuple[EditorialDiagnostic, ...]
