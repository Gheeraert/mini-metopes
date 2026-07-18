# 0014 — Références bibliographiques Word

## Décision

Mini-Métopes conserve les références sous forme de contenu inline riche dans
`bibl`, sans décomposition automatique en `biblStruct`.

Trois styles contrôlés du modèle Commons sont reconnus strictement :
`TEIbiblstart` / `TEI_bibl_start`, `TEIbiblreference` /
`TEI_bibl_reference` et `TEIbiblreference-inline` /
`TEI_bibl_reference-inline`. L’identifiant, le nom, le type OOXML et
`customStyle="1"` sont tous requis.

Une référence de paragraphe est absorbée comme source seulement lorsqu'elle
suit immédiatement une citation. Sinon, elle reste un bloc `bibl`. Le début
de bibliographie est reconnu seulement dans le flux principal ; il retire une
bibliographie unique et terminale du corps pour produire `text/back`.

## Conséquences

Une citation sans source conserve la forme historique `quote`. Une citation
avec source devient `cit/quote` suivi de `bibl`. Les références inline sont
des objets éditoriaux, ce qui évite de les confondre avec une simple italique.

Les bibliographies multiples, non terminales, vides ou situées dans une note
sont refusées. Les épigraphes, `biblStruct`, la décomposition des notices et
les bibliographies intermédiaires restent hors périmètre.
