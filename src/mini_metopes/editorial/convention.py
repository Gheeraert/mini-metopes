"""Convention Word native v0.1 appliquee au modele editorial."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .model import TextMark


ParagraphRoleKind = Literal[
    "heading", "paragraph", "prose_quote", "verse_quote", "deferred", "unsupported"
]


@dataclass(frozen=True)
class ParagraphRole:
    """Classification editoriale d'un paragraphe OOXML selon une convention."""

    kind: ParagraphRoleKind
    heading_level: int | None = None


@dataclass(frozen=True)
class WordEditorialConvention:
    """Correspondances OOXML explicites, sans calcul de cascade Word complete."""

    heading_style_ids: tuple[tuple[str, int], ...]
    paragraph_style_ids: frozenset[str]
    character_style_marks: tuple[tuple[str, tuple[TextMark, ...]], ...]
    deferred_paragraph_style_ids: frozenset[str]
    prose_quote_style_ids: frozenset[str]
    verse_quote_style_ids: frozenset[str]

    def paragraph_role(self, style_id: str | None, outline_level: int | None) -> ParagraphRole:
        """Classifier un style sans dupliquer les priorites dans le constructeur."""
        for candidate, level in self.heading_style_ids:
            if style_id == candidate:
                return ParagraphRole("heading", level)
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

    def heading_level(self, style_id: str | None, outline_level: int | None) -> int | None:
        """Retourner le niveau natif prioritaire, puis le niveau de plan explicite."""
        return self.paragraph_role(style_id, outline_level).heading_level

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
    paragraph_style_ids=frozenset({"Normal", "FootnoteText", "EndnoteText"}),
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
)
