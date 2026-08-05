# 0017 — Blocage conditionnel des en-têtes/pieds de page porteurs de texte

## Contexte

`headers_footers_not_inspected` était émis en `info` (non bloquant) dès
qu'une partie `word/headerN.xml` ou `word/footerN.xml` existait dans le
paquet, sans lecture de son contenu. Un audit du dépôt a signalé que c'était
le seul point du pipeline où « produire une TEI valide mais incomplète »
n'était pas empêché : un titre courant, un titre de partie ou un colophon
placé par l'auteur dans un en-tête Word disparaissait silencieusement de la
TEI, contrairement au principe « refuser plutôt que produire une TEI
trompeuse » appliqué partout ailleurs.

Un simple blocage inconditionnel dès qu'une partie en-tête/pied de page
existe aurait cependant produit une régression massive : la quasi-totalité
des documents Word réels contiennent une partie d'en-tête ou de pied de
page, le plus souvent uniquement pour un champ `PAGE`/`NUMPAGES`. Ce champ
automatique laisse un `<w:t>` contenant le résultat mis en cache (ex. `2`)
sans qu'aucun texte n'ait été rédigé. Le corpus de fixtures en contient un
exemple réel
(`tests/fixtures/docx/conclusion_racine_queer_styles_natifs_minimetopes.docx`,
`word/header1.xml`) : son seul contenu textuel est `2`, un résultat de champ
`PAGE`.

## Décision

`docx/inspector.py` lit désormais le contenu de chaque partie
en-tête/pied de page et distingue :

- texte rédigé (`<w:t>` hors résultat de champ) → `header_footer_text_not_serializable`,
  `severity="warning"` côté inspection, classé bloquant dans
  `tei/conversion.py` (`_BLOCKING_INSPECTION_CODES`) ;
- absence de texte rédigé (partie vide, ou ne contenant que des champs
  automatiques) → `headers_footers_not_inspected` conservé en `info`, non
  bloquant, comme avant.

La détection de « résultat de champ » couvre :

- les champs simples `w:fldSimple` (résultat mis en cache dans les
  descendants, exclus intégralement) ;
- les champs complexes `w:fldChar` (`begin`/`separate`/`end`) : le texte
  entre `separate` et `end` est le résultat calculé, exclu ; `w:instrText`
  (le code de champ lui-même) est également exclu.

Implémentation par analyse structurée `lxml` (`root.iter`, comparaison de
noms qualifiés), sans regex sur l'OOXML, conformément à `AGENTS.md` §11.

## Conséquences

- Un en-tête/pied de page ne contenant qu'un numéro de page continue de
  convertir silencieusement (diagnostic informatif inchangé).
- Un en-tête/pied de page portant du texte rédigé bloque désormais la
  conversion avec un diagnostic explicite pointant la partie concernée,
  au lieu d'omettre ce texte sans avertissement.
- Les commentaires (`comments_not_inspected`) restent hors périmètre de
  cette décision : une annotation de relecture n'est pas un texte destiné
  à la publication, contrairement à un en-tête/pied de page.

## Limites assumées

- Un champ complexe dont le résultat mis en cache est absent (document
  jamais mis à jour dans Word) peut laisser un `<w:t>` vide entre
  `separate` et `end` ; ce cas se comporte comme prévu (aucun texte rédigé
  détecté) mais n'a pas été spécifiquement testé.
- Les champs imbriqués (un champ complexe contenant un autre champ) ne sont
  pas gérés au-delà d'un simple suivi séquentiel de l'état
  `begin`/`separate`/`end` : un cas réel de champ imbriqué dans un
  en-tête n'a pas été rencontré dans le corpus de référence.
