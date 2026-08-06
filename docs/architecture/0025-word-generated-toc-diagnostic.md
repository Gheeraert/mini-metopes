# 0025 — Diagnostic dédié pour une table des matières Word générée

## Contexte

Un document Word contenant une table des matières générée automatiquement
(fonctionnalité native courante) porte des paragraphes stylés
`TOC1`–`TOC9`/`TOCHeading`. Ces styles n'étaient reconnus nulle part dans
`editorial/convention.py` : le premier rencontré bloquait la conversion via
le diagnostic générique `unsupported_paragraph_style`, sans rien indiquer à
l'utilisateur sur la cause réelle ni la marche à suivre.

Vérification avant décision : le schéma Commons Publishing embarqué n'a
**aucune** valeur `@type` sur `<div>` pour une table des matières (liste
fermée à 12 valeurs : `abstract`, `ack`, `appendix`, `bibliography`,
`correction`, `dedication`, `reviewed`, `section1`–`6`). Ce n'est pas un
manque : la structure `div`/`head` hiérarchique que Mini-Métopes produit
déjà porte intrinsèquement l'information de table des matières. L'afficher
sous forme imprimée est une responsabilité de rendu (HTML/PDF/EPUB), donc
d'Impressions en aval, pas de la TEI source.

## Décision

- `editorial/convention.py` : nouveau champ `table_of_contents_style_ids`
  sur `WordEditorialConvention`, peuplé avec les dix styleId canoniques
  (`TOC1`…`TOC9`, `TOCHeading`) dans `NATIVE_WORD_CONVENTION`, vérifiés
  contre `references/Word Styles Chart.xlsm` (styleId anglais invariants,
  non localisés dans `w:styleId` — seul le nom affiché change de langue,
  cohérent avec les styles déjà reconnus par identifiant comme `Heading1`).
- `editorial/builder.py` (`_diagnose_paragraph_style`) : reconnaît ce style
  **avant** le repli générique et émet `word_generated_toc_not_supported`
  (bloquant, message explicite : « supprimez-la avant conversion, la
  structure div/head déjà produite en tient lieu ») au lieu de
  `unsupported_paragraph_style`.

## Conséquences

- Aucune sérialisation TEI d'une table des matières n'est ajoutée — ce
  n'est pas le but ; seul le diagnostic change, de générique à actionnable.
- Sévérité déclarée directement `error` à l'émission (cohérent avec la
  décision 0018 : aucune liste de reclassement à tenir à jour).
- 438 passed après ajout, test dédié vérifiant que le nouveau code apparaît
  et que l'ancien (`unsupported_paragraph_style`) n'apparaît plus pour ce
  cas.

## Limites assumées

- Les styleId localisés autres qu'anglais (si un producteur tiers écrit un
  nom affiché différent) ne sont pas résolus vers ce nouvel ensemble par la
  table de noms de la décision 0015/0020 — non ajouté à
  `resolve_convention_for_styles`. Un style TOC non canonique retombe sur
  `unsupported_paragraph_style` (toujours bloquant, message moins
  spécifique). Prolongement futur explicite, pas un oubli : le cas courant
  (Word générant `TOC1`…`TOC9` en styleId anglais invariant, quelle que
  soit la langue de l'interface) est déjà couvert.
