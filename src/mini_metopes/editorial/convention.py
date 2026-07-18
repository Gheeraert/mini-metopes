"""Convention Word native v0.1 appliquee au modele editorial."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .model import ParagraphRendition, TextMark


ParagraphRoleKind = Literal[
    "heading", "paragraph", "prose_quote", "verse_quote", "deferred", "unsupported"
]


@dataclass(frozen=True)
class ParagraphRole:
    """Classification editoriale d'un paragraphe OOXML selon une convention."""

    kind: ParagraphRoleKind
    heading_level: int | None = None
    paragraph_rendition: ParagraphRendition | None = None


@dataclass(frozen=True)
class WordEditorialConvention:
    """Correspondances OOXML explicites, sans calcul de cascade Word complete."""

    heading_style_ids: tuple[tuple[str, int], ...]
    paragraph_style_ids: frozenset[str]
    character_style_marks: tuple[tuple[str, tuple[TextMark, ...]], ...]
    deferred_paragraph_style_ids: frozenset[str]
    prose_quote_style_ids: frozenset[str]
    verse_quote_style_ids: frozenset[str]
    consecutive_paragraph_style_ids: frozenset[str] = frozenset()
    excluded_consecutive_paragraph_style_ids: frozenset[str] = frozenset()
    consecutive_paragraph_style_names: frozenset[str] = frozenset()
    list_continuation_style_ids: frozenset[str] = frozenset()
    figure_container_style_ids: frozenset[str] = frozenset()
    figure_caption_style_ids: frozenset[str] = frozenset()
    figure_title_style: tuple[str, str] | None = None
    controlled_figure_caption_style: tuple[str, str] | None = None
    figure_credits_style: tuple[str, str] | None = None
    table_cell_style: tuple[str, str] | None = None
    bibliography_start_style: tuple[str, str] | None = None
    bibliographic_reference_style: tuple[str, str] | None = None
    bibliographic_reference_inline_style: tuple[str, str] | None = None

    def paragraph_role(
        self,
        style_id: str | None,
        outline_level: int | None,
        *,
        style_name: str | None = None,
        style_is_custom: bool | None = None,
    ) -> ParagraphRole:
        """Classifier un style sans dupliquer les priorites dans le constructeur."""
        for candidate, level in self.heading_style_ids:
            if style_id == candidate:
                return ParagraphRole("heading", level)
        if self._is_consecutive_paragraph_style(style_id, style_name, style_is_custom):
            return ParagraphRole("paragraph", paragraph_rendition="consecutive")
        if style_id in self.paragraph_style_ids:
            return ParagraphRole("paragraph")
        if style_id in self.prose_quote_style_ids:
            return ParagraphRole("prose_quote")
        if style_id in self.verse_quote_style_ids:
            return ParagraphRole("verse_quote")
        if style_id in self.deferred_paragraph_style_ids:
            return ParagraphRole("deferred")
        if outline_level is not None and 0 <= outline_level <= 5:
            return ParagraphRole("heading", outline_level + 1)
        if style_id is None:
            return ParagraphRole("paragraph")
        return ParagraphRole("unsupported")

    def _is_consecutive_paragraph_style(
        self,
        style_id: str | None,
        style_name: str | None,
        style_is_custom: bool | None,
    ) -> bool:
        """Reconnaître uniquement le style Word integre BodyText non personnalise."""
        if style_is_custom is True:
            return False
        if style_id in self.excluded_consecutive_paragraph_style_ids:
            return False
        if style_id in self.consecutive_paragraph_style_ids:
            return True
        return _normalize_style_name(style_name) in self.consecutive_paragraph_style_names

    def heading_level(self, style_id: str | None, outline_level: int | None) -> int | None:
        """Retourner le niveau natif prioritaire, puis le niveau de plan explicite."""
        return self.paragraph_role(style_id, outline_level).heading_level

    def is_list_continuation_style(
        self,
        style_id: str | None,
        style_is_custom: bool | None,
    ) -> bool:
        """Reconnaître le style integre ListParagraph comme candidat explicite."""
        if style_is_custom is True:
            return False
        return style_id in self.list_continuation_style_ids

    def is_figure_container_style(
        self,
        style_id: str | None,
        style_is_custom: bool | None,
    ) -> bool:
        """Reconnaître les styles intégrés admis pour un paragraphe image autonome."""
        if style_is_custom is True:
            return False
        return style_id is None or style_id in self.figure_container_style_ids

    def is_figure_caption_style(
        self,
        style_id: str | None,
        style_is_custom: bool | None,
    ) -> bool:
        """Reconnaître le style intégré Caption sans repli par nom visible."""
        if style_is_custom is True:
            return False
        return style_id in self.figure_caption_style_ids

    def is_controlled_figure_caption_style(
        self, style_id: str | None, style_name: str | None, style_is_custom: bool | None
    ) -> bool:
        return style_is_custom is True and self._is_controlled_style(
            style_id, style_name, self.controlled_figure_caption_style
        )

    def is_figure_title_style(
        self, style_id: str | None, style_name: str | None, style_is_custom: bool | None
    ) -> bool:
        return style_is_custom is True and self._is_controlled_style(
            style_id, style_name, self.figure_title_style
        )

    def is_figure_credits_style(
        self, style_id: str | None, style_name: str | None, style_is_custom: bool | None
    ) -> bool:
        return style_is_custom is True and self._is_controlled_style(
            style_id, style_name, self.figure_credits_style
        )

    def is_table_cell_style(
        self, style_id: str | None, style_name: str | None, style_is_custom: bool | None
    ) -> bool:
        if style_id is None:
            return True
        if style_id == "Normal" and style_is_custom is not True:
            return True
        return style_is_custom is True and self._is_controlled_style(
            style_id, style_name, self.table_cell_style
        )

    def is_controlled_table_cell_style(
        self, style_id: str | None, style_name: str | None, style_is_custom: bool | None
    ) -> bool:
        return style_is_custom is True and self._is_controlled_style(
            style_id, style_name, self.table_cell_style
        )

    def is_bibliography_start_style(
        self, style_id: str | None, style_name: str | None, style_is_custom: bool | None, style_type: str | None
    ) -> bool:
        return style_is_custom is True and style_type == "paragraph" and self._is_controlled_style(style_id, style_name, self.bibliography_start_style)

    def is_bibliographic_reference_style(
        self, style_id: str | None, style_name: str | None, style_is_custom: bool | None, style_type: str | None
    ) -> bool:
        return style_is_custom is True and style_type == "paragraph" and self._is_controlled_style(style_id, style_name, self.bibliographic_reference_style)

    def is_bibliographic_reference_inline_style(
        self, style_id: str | None, style_name: str | None, style_is_custom: bool | None, style_type: str | None
    ) -> bool:
        return style_is_custom is True and style_type == "character" and self._is_controlled_style(style_id, style_name, self.bibliographic_reference_inline_style)

    @staticmethod
    def _is_controlled_style(
        style_id: str | None, style_name: str | None, controlled: tuple[str, str] | None
    ) -> bool:
        return controlled is not None and (style_id, style_name) == controlled

    def character_marks(self, style_id: str | None) -> tuple[TextMark, ...] | None:
        """Retourner les marques associees a un style de caractere reconnu."""
        if style_id is None:
            return ()
        for candidate, marks in self.character_style_marks:
            if style_id == candidate:
                return marks
        return None


NATIVE_WORD_CONVENTION = WordEditorialConvention(
    heading_style_ids=(
        ("Heading1", 1),
        ("Heading2", 2),
        ("Heading3", 3),
        ("Heading4", 4),
        ("Heading5", 5),
        ("Heading6", 6),
    ),
    paragraph_style_ids=frozenset({"Normal", "FootnoteText", "EndnoteText", "ListParagraph"}),
    character_style_marks=(
        ("Emphasis", ("italic",)),
        ("Strong", ("bold",)),
        ("Hyperlink", ()),
        ("FollowedHyperlink", ()),
        ("FootnoteReference", ()),
        ("EndnoteReference", ()),
    ),
    deferred_paragraph_style_ids=frozenset({"Title", "Subtitle"}),
    prose_quote_style_ids=frozenset({"Quote"}),
    verse_quote_style_ids=frozenset({"IntenseQuote"}),
    consecutive_paragraph_style_ids=frozenset({"BodyText"}),
    excluded_consecutive_paragraph_style_ids=frozenset({"BodyText2", "BodyText3"}),
    consecutive_paragraph_style_names=frozenset({"corps de texte", "body text"}),
    list_continuation_style_ids=frozenset({"ListParagraph"}),
    figure_container_style_ids=frozenset({"Normal", "FootnoteText", "EndnoteText"}),
    figure_caption_style_ids=frozenset({"Caption"}),
    figure_title_style=("TEIfiguretitle", "TEI_figure_title"),
    controlled_figure_caption_style=("TEIfigurecaption", "TEI_figure_caption"),
    figure_credits_style=("TEIfigurecredits", "TEI_figure_credits"),
    table_cell_style=("TEIcell", "TEI_cell"),
    bibliography_start_style=("TEIbiblstart", "TEI_bibl_start"),
    bibliographic_reference_style=("TEIbiblreference", "TEI_bibl_reference"),
    bibliographic_reference_inline_style=("TEIbiblreference-inline", "TEI_bibl_reference-inline"),
)


def _normalize_style_name(name: str | None) -> str | None:
    if name is None:
        return None
    return " ".join(name.casefold().split())
