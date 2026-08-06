"""Convention Word native v0.1 appliquee au modele editorial."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, replace
from typing import Iterable, Literal, Protocol

from .model import ParagraphRendition, TextMark


class StyleDeclaration(Protocol):
    """Sous-ensemble de ``StyleInfo`` requis par la resolution multilingue."""

    style_id: str
    name: str | None
    style_type: str | None
    is_custom: bool | None


ParagraphRoleKind = Literal[
    "heading", "paragraph", "prose_quote", "verse_quote", "epigraph", "signature", "floating_text", "deferred", "unsupported"
]
ControlledStyleStatus = Literal["valid", "invalid", "unrelated"]


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
    epigraph_style_ids: frozenset[str] = frozenset()
    signature_style_ids: frozenset[str] = frozenset()
    floating_text_style_ids: frozenset[str] = frozenset()
    table_of_contents_style_ids: frozenset[str] = frozenset()
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
    native_bibliography_style_ids: frozenset[str] = frozenset()

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
        if style_id in self.epigraph_style_ids:
            return ParagraphRole("epigraph")
        if style_id in self.signature_style_ids:
            return ParagraphRole("signature")
        if style_id in self.floating_text_style_ids:
            return ParagraphRole("floating_text")
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

    def is_table_of_contents_style(self, style_id: str | None, style_is_custom: bool | None) -> bool:
        """Reconnaître une table des matieres Word generee automatiquement.

        Jamais serialisee : la structure ``div``/``head`` deja produite par
        Mini-Metopes en tient lieu (voir decision 0025). Reconnue separement
        du style personnalise inconnu generique pour donner un diagnostic
        actionnable plutot qu'un ``unsupported_paragraph_style`` opaque.
        """
        if style_is_custom is True:
            return False
        return style_id in self.table_of_contents_style_ids

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
        return self.bibliography_start_style_status(style_id, style_name, style_is_custom, style_type) == "valid"

    def is_bibliographic_reference_style(
        self, style_id: str | None, style_name: str | None, style_is_custom: bool | None, style_type: str | None
    ) -> bool:
        if self.is_native_bibliography_reference_style(style_id, style_is_custom):
            return True
        return self.bibliographic_reference_style_status(style_id, style_name, style_is_custom, style_type) == "valid"

    def is_native_bibliography_reference_style(self, style_id: str | None, style_is_custom: bool | None) -> bool:
        """Reconnaître le style natif Word ``Bibliography`` comme une reference.

        A la difference de ``TEIbiblreference``, ce n'est pas un style
        controle : aucune declaration ``w:customStyle`` n'est exigee, et sa
        presence n'est pas non plus rejetee. Un corpus reel a montre que
        Word peut ecrire ``w:customStyle="1"`` sur ``Bibliography`` meme
        quand il est applique tel quel depuis la galerie de styles, sans
        jamais passer par le gestionnaire de citations (voir decision
        0026 addendum) : exiger l'absence de ``customStyle`` rejetait donc
        des documents reels legitimes. Le parametre ``style_is_custom`` est
        conserve dans la signature pour compatibilite des appelants, mais
        n'est plus utilise dans la decision.

        Word n'a pas de style de « debut de bibliographie » separe (voir
        decision 0026) ; la premiere entree Bibliography rencontree
        declenche elle-meme la bibliographie terminale, sans titre.
        """
        del style_is_custom
        return style_id in self.native_bibliography_style_ids

    def is_bibliographic_reference_inline_style(
        self, style_id: str | None, style_name: str | None, style_is_custom: bool | None, style_type: str | None
    ) -> bool:
        return self.bibliographic_reference_inline_style_status(style_id, style_name, style_is_custom, style_type) == "valid"

    def bibliography_start_style_status(
        self, style_id: str | None, style_name: str | None, style_is_custom: bool | None, style_type: str | None
    ) -> ControlledStyleStatus:
        return self._controlled_style_status(
            style_id, style_name, style_is_custom, style_type, self.bibliography_start_style, "paragraph"
        )

    def bibliographic_reference_style_status(
        self, style_id: str | None, style_name: str | None, style_is_custom: bool | None, style_type: str | None
    ) -> ControlledStyleStatus:
        return self._controlled_style_status(
            style_id, style_name, style_is_custom, style_type, self.bibliographic_reference_style, "paragraph"
        )

    def bibliographic_reference_inline_style_status(
        self, style_id: str | None, style_name: str | None, style_is_custom: bool | None, style_type: str | None
    ) -> ControlledStyleStatus:
        return self._controlled_style_status(
            style_id, style_name, style_is_custom, style_type, self.bibliographic_reference_inline_style, "character"
        )

    @staticmethod
    def _is_controlled_style(
        style_id: str | None, style_name: str | None, controlled: tuple[str, str] | None
    ) -> bool:
        return controlled is not None and (style_id, style_name) == controlled

    @staticmethod
    def _controlled_style_status(
        style_id: str | None,
        style_name: str | None,
        style_is_custom: bool | None,
        style_type: str | None,
        controlled: tuple[str, str] | None,
        expected_type: str,
    ) -> ControlledStyleStatus:
        if controlled is None:
            return "unrelated"
        expected_id, expected_name = controlled
        if style_id != expected_id and style_name != expected_name:
            return "unrelated"
        if (
            style_id == expected_id
            and style_name == expected_name
            and style_is_custom is True
            and style_type == expected_type
        ):
            return "valid"
        return "invalid"

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
    epigraph_style_ids=frozenset({"Salutation"}),
    signature_style_ids=frozenset({"Signature"}),
    floating_text_style_ids=frozenset({"BlockText"}),
    table_of_contents_style_ids=frozenset({
        "TOC1", "TOC2", "TOC3", "TOC4", "TOC5", "TOC6", "TOC7", "TOC8", "TOC9", "TOCHeading",
    }),
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
    native_bibliography_style_ids=frozenset({"Bibliography"}),
)


def _normalize_style_name(name: str | None) -> str | None:
    if name is None:
        return None
    return " ".join(name.casefold().split())


def _fold_style_name(name: str | None) -> str | None:
    """Normaliser un nom affiche : casse, espaces, accents.

    Word francais conserve en general le nom OOXML canonique anglais dans
    ``w:name`` mais d'autres producteurs (LibreOffice, exports tiers)
    ecrivent le nom localise ; les deux formes sont donc admises.
    """
    normalized = _normalize_style_name(name)
    if normalized is None:
        return None
    decomposed = unicodedata.normalize("NFKD", normalized)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _name_table(*names_by_canonical: tuple[str, tuple[str, ...]]) -> dict[str, str]:
    table: dict[str, str] = {}
    for canonical, names in names_by_canonical:
        for name in names:
            folded = _fold_style_name(name)
            assert folded is not None and folded not in table, name
            table[folded] = canonical
    return table


# Noms OOXML canoniques (invariants anglais de la specification, ce que Word
# francais ecrit dans ``w:name``) et noms affiches localises (francais,
# anglais, et un sous-ensemble verifie allemand/espagnol - voir la decision
# 0020 pour la methode de verification et les entrees volontairement
# absentes faute de confirmation suffisante) susceptibles d'apparaitre chez
# d'autres producteurs.
NATIVE_PARAGRAPH_STYLE_NAMES: dict[str, str] = _name_table(
    ("Heading1", ("heading 1", "titre 1", "überschrift 1", "título 1")),
    ("Heading2", ("heading 2", "titre 2", "überschrift 2", "título 2")),
    ("Heading3", ("heading 3", "titre 3", "überschrift 3", "título 3")),
    ("Heading4", ("heading 4", "titre 4", "überschrift 4", "título 4")),
    ("Heading5", ("heading 5", "titre 5", "überschrift 5", "título 5")),
    ("Heading6", ("heading 6", "titre 6", "überschrift 6", "título 6")),
    ("Normal", ("normal", "standard")),
    ("BodyText", ("body text", "corps de texte", "textkörper", "texto independiente")),
    ("Quote", ("quote", "citation", "zitat", "cita")),
    ("IntenseQuote", ("intense quote", "citation intense")),
    ("ListParagraph", ("list paragraph", "paragraphe de liste", "listenabsatz", "párrafo de lista")),
    ("FootnoteText", ("footnote text", "note de bas de page", "fußnotentext", "texto de nota al pie")),
    ("EndnoteText", ("endnote text", "note de fin", "endnotentext", "texto de nota al final")),
    ("Title", ("title", "titre", "titel", "título")),
    ("Subtitle", ("subtitle", "sous-titre", "untertitel", "subtítulo")),
    ("Caption", ("caption", "légende", "beschriftung", "título de ilustración")),
    ("Bibliography", ("bibliography", "bibliographie")),
)

NATIVE_CHARACTER_STYLE_NAMES: dict[str, str] = _name_table(
    ("Emphasis", ("emphasis", "accentuation", "énfasis")),
    ("Strong", ("strong", "élevé")),
    ("Hyperlink", ("hyperlink", "lien hypertexte")),
    ("FollowedHyperlink", ("followedhyperlink", "followed hyperlink", "lien hypertexte suivi visité")),
    ("FootnoteReference", ("footnote reference", "appel note de bas de p.")),
    ("EndnoteReference", ("endnote reference", "appel de note de fin")),
)

_CANONICAL_NATIVE_STYLE_IDS: frozenset[str] = frozenset(
    set(NATIVE_PARAGRAPH_STYLE_NAMES.values()) | set(NATIVE_CHARACTER_STYLE_NAMES.values())
)


def native_style_alias_map(styles: Iterable[StyleDeclaration]) -> dict[str, str]:
    """Associer les identifiants localises aux identifiants natifs canoniques.

    Resolution centrale et deterministe :

    - seul un style non personnalise (``w:customStyle`` absent ou faux) peut
      etre reconnu comme style natif ;
    - un identifiant deja canonique n'est jamais re-signifie par son nom ;
    - la correspondance se fait uniquement sur le nom affiche normalise
      (casse, espaces, accents) present dans la table de la convention ;
    - ``basedOn`` ne transmet volontairement aucune identite : la plupart des
      styles, y compris personnalises, derivent de ``Normal`` et l'adoption de
      l'identite du parent aplatirait silencieusement la structure.

    Les styles personnalises inconnus restent donc sans alias et continuent de
    produire des diagnostics explicites.
    """
    aliases: dict[str, str] = {}
    for style in styles:
        if style.is_custom is True:
            continue
        if style.style_id in _CANONICAL_NATIVE_STYLE_IDS:
            continue
        folded = _fold_style_name(style.name)
        if folded is None:
            continue
        if style.style_type == "character":
            canonical = NATIVE_CHARACTER_STYLE_NAMES.get(folded)
        else:
            canonical = NATIVE_PARAGRAPH_STYLE_NAMES.get(folded)
        if canonical is not None:
            aliases[style.style_id] = canonical
    return aliases


def resolve_convention_for_styles(
    convention: WordEditorialConvention,
    styles: Iterable[StyleDeclaration],
) -> WordEditorialConvention:
    """Etendre la convention aux identifiants localises du document.

    La convention retournee reconnait, pour chaque ensemble d'identifiants
    natifs, les identifiants declares dans ``styles.xml`` dont le nom resout
    vers le meme style natif. Les styles controles ``TEI_*`` de la convention
    ne sont pas concernes : ils restent des correspondances exactes.
    """
    aliases = native_style_alias_map(styles)
    if not aliases:
        return convention
    ids_for: dict[str, tuple[str, ...]] = {}
    for declared, canonical in aliases.items():
        ids_for[canonical] = ids_for.get(canonical, ()) + (declared,)

    def _expand(ids: frozenset[str]) -> frozenset[str]:
        expanded = set(ids)
        for canonical in ids:
            expanded.update(ids_for.get(canonical, ()))
        return frozenset(expanded)

    heading_style_ids = tuple(convention.heading_style_ids) + tuple(
        (declared, level)
        for canonical, level in convention.heading_style_ids
        for declared in ids_for.get(canonical, ())
    )
    character_style_marks = tuple(convention.character_style_marks) + tuple(
        (declared, marks)
        for canonical, marks in convention.character_style_marks
        for declared in ids_for.get(canonical, ())
    )
    return replace(
        convention,
        heading_style_ids=heading_style_ids,
        character_style_marks=character_style_marks,
        paragraph_style_ids=_expand(convention.paragraph_style_ids),
        deferred_paragraph_style_ids=_expand(convention.deferred_paragraph_style_ids),
        prose_quote_style_ids=_expand(convention.prose_quote_style_ids),
        verse_quote_style_ids=_expand(convention.verse_quote_style_ids),
        epigraph_style_ids=_expand(convention.epigraph_style_ids),
        signature_style_ids=_expand(convention.signature_style_ids),
        floating_text_style_ids=_expand(convention.floating_text_style_ids),
        consecutive_paragraph_style_ids=_expand(convention.consecutive_paragraph_style_ids),
        list_continuation_style_ids=_expand(convention.list_continuation_style_ids),
        figure_container_style_ids=_expand(convention.figure_container_style_ids),
        figure_caption_style_ids=_expand(convention.figure_caption_style_ids),
        native_bibliography_style_ids=_expand(convention.native_bibliography_style_ids),
    )
