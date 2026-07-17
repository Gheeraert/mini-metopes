# 0008 — Résolution de la numérotation Word

## Décision

La couche `mini_metopes.docx` lit `word/numbering.xml` dans un modèle
immuable : définitions `abstractNum`, instances `num`, niveaux `lvl` et
surcharges `lvlOverride` / `startOverride`. Chaque paragraphe garde son
observation brute (`numbering_id`, `numbering_level`) et porte désormais une
résolution effective distincte.

`numPr` direct est prioritaire. `numId="0"` signifie que la numérotation est
supprimée : ce n'est pas une liste active. Les numérotations provenant d'un
style, y compris via `basedOn`, sont observées mais non résolues ; elles sont
signalées conservatoirement. Les cycles `basedOn` sont diagnostiqués.

## Conséquences

Les formats usuels sont classés en `ordered`, `bulleted`, `none` ou
`unsupported`. Les puces illustrées restent non prises en charge. La même
résolution est appliquée au document, aux notes de bas de page et aux notes de
fin, avec la partie OOXML et l'identifiant de note dans les diagnostics.

Cette passe n'introduit ni `EditorialList`, ni regroupement de listes, ni
élément TEI `<list>`. La conversion TEI refuse donc toujours toute
numérotation active, mais le diagnostic contient `numId`, niveau, genre et
format observés.
