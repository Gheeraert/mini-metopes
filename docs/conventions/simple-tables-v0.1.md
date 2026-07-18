# Tables Word simples v0.1

Une table publiee doit etre un `w:tbl` de premier niveau du corps, rectangulaire
et sans `gridSpan`, `vMerge`, `hMerge` ni table imbriquee. Chaque cellule est
vide ou contient un seul paragraphe utilisant aucun style, `Normal` non
personnalise, ou exactement le style controle `TEIcell` / `TEI_cell` declare
personnalise.

`w:trPr/w:tblHeader` n'est accepte que sur la premiere ligne. Il devient
`<row role="label">` et ses cellules deviennent `<cell role="label">`.
Les autres cellules restent inline; une cellule Word vide devient `<cell/>`.

La sortie est `table rows="…" cols="…"`, suivie de `row` et `cell`, sans
largeurs, bordures, titre, legende ni credit de table. Les tableaux dans les
notes et zones de texte, les listes, images et citations dans les cellules
restent refuses.
