# Références bibliographiques Word v0.1

Les styles Word contrôlés suivants sont les seuls signaux bibliographiques :

- `TEIbiblstart` — `TEI_bibl_start` : titre de la bibliographie finale ;
- `TEIbiblreference` — `TEI_bibl_reference` : référence de bloc, source de
  citation ou entrée finale selon le contexte ;
- `TEIbiblreference-inline` — `TEI_bibl_reference-inline` : référence dans un
  contenu inline.

Les styles doivent être personnalisés et déclarés avec le type OOXML exact.
Leur seul nom visible ne suffit jamais.

Si un style porte l'identifiant exact ou le nom exact d'un style contrôlé mais
échoue sur le nom, l'identifiant, le type OOXML, `customStyle="1"` ou la
présence dans `styles.xml`, il est refusé par un diagnostic spécialisé :

- `invalid_bibliography_start_style` ;
- `invalid_bibliographic_reference_style` ;
- `invalid_bibliographic_reference_inline_style`.

Ces codes ne concernent pas les styles ordinaires inconnus.

La bibliographie finale est unique, terminale et contient au moins une entrée.
Après son titre, seuls ses paragraphes de référence sont admis (les
séparateurs `Normal` vides sont ignorés avec information). Elle devient :

```xml
<back><div type="bibliography"><head>…</head><listBibl><bibl>…</bibl></listBibl></div></back>
```

Mini-Métopes ne produit ni `biblStruct`, ni analyse d'auteur, titre, date,
éditeur ou DOI. Une référence est conservée comme contenu riche de `bibl`.

Une référence inline `TEIbiblreference-inline` est autorisée dans les contenus
éditoriaux ordinaires testés : paragraphe, citation, note, item et
continuation de liste, cellule de tableau, légende ou crédits de figure. Elle
est interdite dans un contenu déjà sérialisé comme `bibl`, afin de ne jamais
produire `<bibl><bibl>…</bibl></bibl>`.

Le compteur CLI `Références bibliographiques inline` parcourt récursivement
ces contextes et ne compte pas deux fois un objet atteint par une sous-liste ou
une note.
