# Table normative Word natif → modèle éditorial → TEI, v0.2

Ce document est la spécification centrale du contrat de conversion
Mini-Métopes. Il remplace `native-word-to-tei-v0.1.md` et décrit, pour chaque
entrée Word prise en charge : les critères techniques de reconnaissance,
l'objet produit dans le modèle éditorial, la TEI produite, les restrictions et
les diagnostics associés.

## Périmètre

Mini-Métopes convertit des DOCX structurés avec les **styles natifs de Word**
et un petit nombre de conventions complémentaires documentées. Les styles
personnalisés de la chaîne Métopes (`TEI_quote`, `TEI_verse`, `TEI_author` et,
en général, tout style `TEI_*` du modèle Métopes) **ne sont pas une entrée** :
un paragraphe qui porte un tel style est rejeté comme style personnalisé
inconnu (`unsupported_paragraph_style`, bloquant). Cette absence de
compatibilité est un choix d'architecture (voir la décision 0015), vérifié par
`tests/fixtures/corpus/document-d/unknown-custom-style`.

La compatibilité de **sortie** (conformité de la TEI produite au profil
Commons Publishing) est une question distincte, traitée dans
`docs/reference/validation-matrix.md`.

## Reconnaissance multilingue des styles natifs

Un style natif est identifié par une résolution centrale, déterministe et
testée (`editorial/convention.py`, `native_style_alias_map`) :

1. **Identifiant canonique.** Si `w:styleId` est l'identifiant canonique
   anglais (`Heading1`, `Quote`, `BodyText`, …), il est reconnu directement.
   Un identifiant canonique n'est jamais re-signifié par son nom.
2. **Nom déclaré.** Sinon, si le style n'est **pas** personnalisé
   (`w:customStyle` absent ou faux), son `w:name` normalisé (casse, espaces,
   accents) est cherché dans la table de la convention, qui contient les noms
   OOXML canoniques anglais (ce que Word français écrit réellement :
   `heading 1`, `Body Text`, `Intense Quote`, …) et les noms affichés
   localisés français (`Titre 1`, `Corps de texte`, `Citation intense`, …)
   produits par d'autres outils. Les tables des styles de paragraphe et de
   caractère sont séparées.
3. **Niveau de plan.** Un paragraphe sans style reconnu mais doté d'un
   `outlineLvl` (direct ou hérité du style) entre 0 et 5 est traité comme
   titre de niveau `outlineLvl + 1`. C'est le seul repli hiérarchique.
4. **`basedOn` ne transmet aucune identité.** La quasi-totalité des styles,
   y compris personnalisés, dérive de `Normal` ; adopter l'identité du parent
   aplatirait silencieusement la structure. `basedOn` n'est utilisé que pour
   la résolution des numérotations portées par un style (qui reste refusée à
   la sérialisation).

Un style **personnalisé** (`w:customStyle="1"`) n'est jamais résolu, même si
son nom coïncide avec un nom natif. Les styles inconnus produisent des
diagnostics explicites et bloquants.

## Table principale

| Entrée Word native | Critères de reconnaissance | Modèle éditorial | Sortie TEI | Restrictions et diagnostics |
| --- | --- | --- | --- | --- |
| `Heading1`–`Heading6` (« Titre 1 »–« Titre 6 ») | id canonique, nom `heading n`/`titre n`, ou `outlineLvl` 0–5 | `Heading(level)` | `div` hiérarchisés + `head` | saut de niveau : `heading_level_jump` (info, non bloquant) ; titre vide : diagnostic dédié |
| `Normal`, sans style | id/nom `Normal` ou paragraphe sans `pStyle` | `Paragraph` | `p` | paragraphe vide non sérialisable |
| `BodyText` (« Corps de texte ») | id canonique ou nom `Body Text`/`corps de texte`, non personnalisé | `Paragraph(rendition="consecutive")` | `p rend="consecutive"` | `BodyText2`, `BodyText3` et homonymes personnalisés refusés |
| `Quote` (« Citation ») | id/nom, non personnalisé | `ProseQuote` (paragraphes consécutifs regroupés) | `quote` avec `p` (dans `cit` si source bibliographique) | citation vide refusée |
| `IntenseQuote` (« Citation intense ») | id/nom, non personnalisé | `VerseQuote` : 1 paragraphe = 1 strophe, `Maj+Entrée` = vers | `quote` avec `lg` et `l` | vers vides refusés |
| Listes Word natives (numérotation directe résolue) | `numPr` direct, format résolu dans `numbering.xml` | `EditorialList`/`EditorialListItem` | `list` + `item` (voir ci-dessous) | voir `native-word-lists-v0.2.md` et `native-list-continuations-v0.1.md` |
| `ListParagraph` non numéroté (« Paragraphe de liste ») | id/nom, non personnalisé, rattachement prouvé | continuation d'item | `p` supplémentaires dans `item` | rattachement non prouvé : `ambiguous_list_continuation_not_serializable` |
| Notes de bas de page / de fin | appels Word `footnoteReference`/`endnoteReference` | `EditorialNote` + `NoteReference` | `note place="foot"` / `note place="end"` au fil du texte | notes non appelées : avertissement, non sérialisées |
| `FootnoteText`, `EndnoteText` | id/nom, dans les notes | `Paragraph` ordinaire | `p` | — |
| Gras, italique, petites capitales, capitales, exposant, indice | propriétés directes de run et styles `Emphasis`/`Strong` | marques `TextSpan.marks` | `hi rend="bold italic smallcaps caps sup sub"` (ordre stable) | styles de caractère inconnus : `unsupported_character_style`, bloquant |
| Hyperliens externes | `w:hyperlink` avec relation externe | `EditorialLink(kind="external")` | `ref target="…"` | liens internes non matérialisés : diagnostic bloquant |
| `Title`, `Subtitle` (« Titre », « Sous-titre ») initiaux | id/nom, préambule initial du corps | suggestion de métadonnées (consommée) | `titleStmt` via `metadata.json` | hors préambule : `metadata_style_not_initial`, bloquant |
| Style personnalisé quelconque (dont `TEI_quote` et autres `TEI_*` Métopes) | `w:customStyle="1"` non couvert par une convention contrôlée | aucun | aucune | `unsupported_paragraph_style` / `unsupported_character_style`, bloquant |

Les objets refusés en l'état (dessins non conformes à la convention figures,
zones de texte, tableaux non simples, sauts de page/colonne, tabulations…)
bloquent la conversion avec des diagnostics stables ; ils ne sont jamais
transformés silencieusement en paragraphes.

## Vocabulaire XML des listes (vérifié)

Sérialisation actuelle (`tei/serializer.py`) :

- liste à puces : `list type="bulleted"` ;
- liste ordonnée : `list type="<numFmt Word résolu>"` (`decimal`,
  `lowerLetter`, `upperRoman`, …), ce qui conserve le format de numérotation
  Word sans invention ; départ effectif conservé dans `list/@n` ;
- imbrication : sous-`list` dans l'`item` parent, selon `ilvl` ;
- continuations prouvées : `p` multiples dans `item` ;
- ni `@rend` ni `@rendition` ne sont utilisés sur `list` ;
- redémarrages explicites (`lvlRestart`) et reprises discontinues : refusés.

Vérification contre les références disponibles : le RNG Commons Publishing
embarqué déclare `list/@type` **optionnel et ouvert** (jeton sans espace ; les
valeurs `gloss`, `index`, `instructions`, `litany`, `syllogism` ne sont que
*suggérées*) et la seule règle Schematron du schéma sur les listes ne
contraint que `type="gloss"`, jamais émis par Mini-Métopes. Les valeurs
actuelles sont donc valides et documentées ici comme choix de convention.
Aucun exemple normatif aval embarqué n'impose un autre vocabulaire ; tout
changement futur devra être justifié par une contrainte normative, un exemple
de référence ou un comportement observé de la chaîne aval (voir
`validation-matrix.md`, limites).

## Styles contrôlés propres à Mini-Métopes

Les conventions figures, tableaux simples et références bibliographiques
(passes 11–12) utilisent des styles **contrôlés créés par Mini-Métopes**
(`docs/conventions/native-figures-v0.1.md`, `simple-tables-v0.1.md`,
`bibliographic-references-v0.1.md`). Ils sont hors du périmètre de la présente
table et ne constituent pas une compatibilité avec le modèle Métopes : leur
reconnaissance est une correspondance exacte (identifiant, nom, type,
`customStyle`) définie par Mini-Métopes. Leur nommage actuel commence
toutefois par `TEI_`, ce qui entretient une ambiguïté avec les styles Métopes
explicitement exclus ; un renommage éventuel est une décision éditoriale à
valider humainement (voir la décision 0015).

## Corpus de référence

Le contrat ci-dessus est exécuté de bout en bout par
`tests/fixtures/corpus` (documents A à D) et `tests/test_reference_corpus.py` :
sortie TEI byte à byte, validation Relax NG, diagnostics stables,
déterminisme, et rejet explicite de `TEI_quote`.
