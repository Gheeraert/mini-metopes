# 0015 — Résolution multilingue des styles natifs Word

## Contexte

La reconnaissance des styles reposait sur les seuls identifiants canoniques
anglais (`Heading1`, `Quote`, `BodyText`, …), complétée d'un repli par nom
uniquement pour `BodyText`. Or Word français écrit des identifiants localisés
(`Titre1`, `Citation`, `Corpsdetexte`, `Notedebasdepage`, …) en conservant le
nom OOXML canonique anglais dans `w:name` (`heading 1`, `Body Text`, …), et
d'autres producteurs (LibreOffice, exports tiers) écrivent des noms affichés
localisés. Les documents français étaient donc largement rejetés.

## Décision

Une résolution centrale, déterministe et pure est ajoutée dans
`editorial/convention.py` :

- `native_style_alias_map(styles)` associe chaque identifiant déclaré non
  personnalisé à un identifiant natif canonique, par nom déclaré normalisé
  (casse, espaces, accents), avec tables séparées paragraphe/caractère
  couvrant les noms canoniques anglais et les noms affichés français ;
- `resolve_convention_for_styles(convention, styles)` étend la convention aux
  identifiants ainsi résolus ; `build_editorial_document` l'applique en
  entrée, sans modifier l'inspection OOXML (la séparation inspection /
  convention est préservée) ;
- l'extraction de suggestions de métadonnées applique la même table pour
  `Title`/`Subtitle` (`Titre`/`Sous-titre`).

Garde-fous :

- un style `w:customStyle="1"` n'est **jamais** résolu, même homonyme d'un
  style natif : les styles personnalisés inconnus (dont les styles Métopes
  `TEI_*`) continuent de produire des diagnostics explicites et bloquants ;
- un identifiant déjà canonique n'est jamais re-signifié par son nom ;
- `basedOn` ne transmet pas d'identité : presque tous les styles dérivent de
  `Normal` et l'adoption de l'identité du parent aplatirait la structure ;
- le repli par `outlineLvl` (0–5 → titre de niveau n+1) reste le comportement
  antérieur, inchangé.

## Conséquences

- Les documents Word français et anglais produisent le même modèle éditorial
  (corpus `document-a` vs `document-b`) ; les noms affichés localisés sont
  couverts (`document-c`).
- La table des noms est normative et versionnée dans
  `docs/conventions/native-word-to-tei-v0.2.md` ; l'ajout d'une langue est un
  changement de convention, pas un changement de code dispersé.
- Limites assumées : autres langues non couvertes (allemand, espagnol…),
  style « Text Body » de LibreOffice non assimilé à `BodyText` (sémantique
  différente : style de corps par défaut, pas paragraphe de suite), style
  absent de `styles.xml` non résolu.

## Décisions restant à valider humainement

- Un style personnalisé doté d'un `outlineLvl` est aujourd'hui accepté comme
  titre (comportement antérieur, couvert par les tests). Le restreindre aux
  styles non personnalisés serait plus conservatoire mais change le contrat.
- `heading_level_jump` reste un diagnostic informatif non bloquant.
- Les styles contrôlés propres à Mini-Métopes (`TEI_figure_*`, `TEI_bibl_*`,
  `TEI_cell`) portent un préfixe qui entretient la confusion avec les styles
  Métopes exclus ; un renommage (par exemple `MM_*`) est envisageable mais
  casserait les documents existants.
