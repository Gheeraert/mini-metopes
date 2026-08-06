# 0029 — Encadré via le style natif Word `Block Text`

## Contexte

Aucun mécanisme ne permettait de représenter un encadré (aparté, focus,
« pour aller plus loin »…) — élément fréquent en édition savante,
interrompant le flux principal sans en faire partie. Le style natif Word
**`Block Text`** (styleId `BlockText`, confirmé dans
`references/Word Styles Chart.xlsm` : « Intended for block quotations
("extracts"), indented on both sides ») a été retenu par décision explicite
de l'utilisateur, en réemploi assumé — Word le documente pour des citations
en bloc, ici repositionné comme encadré structurel, sur le même principe
que `Salutation` réemployé pour les épigraphes (décision 0027).

Vérification avant décision : `<floatingText>` existe dans le schéma
Commons Publishing embarqué (« interrupts the text containing it at any
point and after which the surrounding text resumes »), membre de
`model.attributable` → `model.inter` → `model.common`, donc autorisé comme
enfant direct de `<div>` au même titre que `<p>`. Son contenu est
**structurellement plus lourd** que les autres blocs éditoriaux du projet :
il exige un `<body>` imbriqué obligatoire (`choice` à une seule branche,
`ref name="body"`), lui-même exigeant au moins un `model.common` (`<p>`
suffit, pas besoin de `<div>` imbriqué).

## Décision

- `editorial/convention.py` : `floating_text_style_ids` (`{"BlockText"}`),
  nouveau `ParagraphRoleKind` `"floating_text"`.
- `editorial/model.py` : `FloatingText(paragraphs: tuple[FloatingTextParagraph, ...])`,
  ajouté à `EditorialBlock`.
- `editorial/builder.py` : une suite contiguë de paragraphes `BlockText`
  devient un bloc `FloatingText` (même schéma de collecte que
  `ProseQuote`/`Epigraph`). **Aucune contrainte de position** contrairement
  à Épigraphe/Signature : un encadré peut interrompre le flux principal
  n'importe où, conformément à la sémantique même de `<floatingText>` dans
  les TEI Guidelines. Seule contrainte retenue : jamais à l'intérieur d'une
  note (`floating_text_in_note_not_serializable`, bloquant) — un encadré
  imbriqué dans une note de bas de page serait d'une complexité
  éditoriale disproportionnée pour cette passe.
- `tei/serializer.py` : `<floatingText><body><p>…</p>…</body></floatingText>`,
  positionné naturellement dans le flux XML à l'endroit où les paragraphes
  `BlockText` apparaissaient — pas de logique de placement dédiée. Garde
  spécifique nécessaire : contrairement à `<epigraph>` (contenu facultatif),
  `<body>` **exige** au moins un enfant valide ; si tous les paragraphes de
  l'encadré sont vides, la conversion est refusée
  (`empty_floating_text_not_serializable`) plutôt que de produire un
  `<body/>` vide et invalide.

## Conséquences

- Un encadré Word devient un `<floatingText>` valide, sans dialecte TEI
  local, sans interrompre la reconnaissance du reste du flux (texte avant
  et après préservé normalement).
- 464 passed après ajout. Tests dédiés
  (`tests/test_editorial_floating_text.py`) : paragraphe unique, plusieurs
  consécutifs, absence de contrainte de position (vérifiée explicitement
  contre les codes de refus d'Épigraphe/Signature), refus dans une note,
  sérialisation complète avec structure `<body>` imbriquée validée par le
  RNG, refus si tous les paragraphes sont vides (garde `<body>` non vide).

## Limites assumées

- Un encadré ne peut contenir que des paragraphes simples (`<p>`) : pas de
  liste, citation, figure ou tableau imbriqué dans cette passe — chaque
  paragraphe `BlockText` devient un `<p>` via `_build_inline_content`,
  identique au traitement d'un paragraphe ordinaire. Le schéma permettrait
  plus (imbrication de `<div>`/`<list>`/etc. dans `<body>`), mais cela
  sortait du périmètre demandé.
- Comme pour Épigraphe/Signature, aucun nom localisé français n'a été
  ajouté pour `BlockText` : seul le styleId anglais invariant est reconnu.
