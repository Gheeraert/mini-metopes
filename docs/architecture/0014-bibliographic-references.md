# 0014 — Références bibliographiques Word

## Décision

Mini-Métopes conserve les références sous forme de contenu inline riche dans
`bibl`, sans décomposition automatique en `biblStruct`.

Trois styles contrôlés du modèle Commons sont reconnus strictement :
`TEIbiblstart` / `TEI_bibl_start`, `TEIbiblreference` /
`TEI_bibl_reference` et `TEIbiblreference-inline` /
`TEI_bibl_reference-inline`. L’identifiant, le nom, le type OOXML et
`customStyle="1"` sont tous requis.

Une tentative identifiable d'utiliser l'un de ces styles avec une définition
incomplète ou usurpée ne retombe pas sur les diagnostics génériques de style.
Mini-Métopes produit respectivement `invalid_bibliography_start_style`,
`invalid_bibliographic_reference_style` ou
`invalid_bibliographic_reference_inline_style` lorsque l'identifiant exact ou
le nom exact est présent mais que les autres propriétés ne correspondent pas.

Une référence de paragraphe est absorbée comme source seulement lorsqu'elle
suit immédiatement une citation. Sinon, elle reste un bloc `bibl`. Le début
de bibliographie est reconnu seulement dans le flux principal ; il retire une
bibliographie unique et terminale du corps pour produire `text/back`.

Les références inline ne sont jamais admises dans le contenu d'un autre
`bibl` : ni référence autonome, ni source de citation, ni entrée finale, ni
titre de bibliographie. Le constructeur et le sérialiseur défensif produisent
`nested_bibliographic_reference_not_serializable` avant toute validation RNG.

## Conséquences

Une citation sans source conserve la forme historique `quote`. Une citation
avec source devient `cit/quote` suivi de `bibl`. Les références inline sont
des objets éditoriaux, ce qui évite de les confondre avec une simple italique.

Les bibliographies multiples, non terminales, vides ou situées dans une note
sont refusées. Les épigraphes, `biblStruct`, la décomposition des notices et
les bibliographies intermédiaires restent hors périmètre.

Le résumé `model-docx` compte les références bibliographiques inline par un
parcours récursif du modèle éditorial : paragraphes, citations, notes, items
de listes, continuations, cellules de tableaux, titres, légendes et crédits de
figures. Les objets ne sont pas recompteurs par les listes ou notes déjà
descendues.
