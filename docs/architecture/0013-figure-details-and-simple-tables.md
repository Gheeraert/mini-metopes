# Figures enrichies et tables Word simples

## Decision

La passe 11 conserve la separation DOCX -> modele editorial -> TEI. Les
paragraphes controles de figure deviennent des objets `Paragraph` contextuels
dans `EditorialFigure`; les tableaux Word du corps sont observes sous la forme
de blocs ordonnes et deviennent `EditorialTable`.

## Figures

Seuls les styles personnalises exacts `TEIfiguretitle` / `TEI_figure_title`,
`TEIfigurecaption` / `TEI_figure_caption` et `TEIfigurecredits` /
`TEI_figure_credits` sont reconnus. `Caption` reste le seul style integre de
legende admis. L'ordre TEI est `head`, `graphic`, `figDesc`, legende, credits.

## Tables

`DocxInspection.body_blocks` conserve l'ordre des `w:p` et `w:tbl` de premier
niveau sans changer `inspection.paragraphs`. Une table V1 est rectangulaire,
sans fusion ni imbrication, avec une ligne `tblHeader` seulement en premiere
position et au plus un paragraphe significatif par cellule. Le RNG Commons
Publishing embarque autorise `table/@rows`, `@cols`, `row/@role` et
`cell/@role`; il est utilise sans modification.

Les tableaux de note, de zone de texte, fusionnes, imbriques, irreguliers et
les contenus de cellule non reconnus restent bloquants.

## Limites

Cette decision ne couvre ni titre ni credits de table, ni cellules fusionnees,
ni plusieurs paragraphes par cellule, ni figures dans les listes ou sorties
LaTEI/PDF.
