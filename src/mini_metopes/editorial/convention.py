"""Convention Word native v0.1 appliquee au modele editorial."""

from __future__ import annotations

from dataclasses import dataclass

from .model import TextMark


@dataclass(frozen=True)
class WordEditorialConvention:
    """Correspondances OOXML explicites, sans calcul de cascade Word complete."""

    heading_style_ids: tuple[tuple[str, int], ...]
    paragraph_style_ids: frozenset[str]
    character_style_marks: tuple[tuple[str, tuple[TextMark, ...]], ...]
    deferred_paragraph_style_ids: frozenset[str]

    def heading_level(self, style_id: str | None, outline_level: int | None) -> int | None:
        """Retourner le niveau natif prioritaire, puis le niveau de plan explicite."""
        for candidate, level in self.heading_style_ids:
            if style_id == candidate:
                return level
        if style_id in self.paragraph_style_ids or style_id in self.deferred_paragraph_style_ids:
            return None
        if outline_level is not None and 0 <= outline_level <= 5:
            return outline_level + 1
        return None

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
    paragraph_style_ids=frozenset({"Normal"}),
    character_style_marks=(("Emphasis", ("italic",)), ("Strong", ("bold",))),
    deferred_paragraph_style_ids=frozenset({"Title", "Subtitle", "Quote", "IntenseQuote"}),
)
