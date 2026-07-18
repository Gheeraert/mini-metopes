# Références bibliographiques Word v0.1

Les styles Word contrôlés suivants sont les seuls signaux bibliographiques :

- `TEIbiblstart` — `TEI_bibl_start` : titre de la bibliographie finale ;
- `TEIbiblreference` — `TEI_bibl_reference` : référence de bloc, source de
  citation ou entrée finale selon le contexte ;
- `TEIbiblreference-inline` — `TEI_bibl_reference-inline` : référence dans un
  contenu inline.

Les styles doivent être personnalisés et déclarés avec le type OOXML exact.
Leur seul nom visible ne suffit jamais.

La bibliographie finale est unique, terminale et contient au moins une entrée.
Après son titre, seuls ses paragraphes de référence sont admis (les
séparateurs `Normal` vides sont ignorés avec information). Elle devient :

```xml
<back><div type="bibliography"><head>…</head><listBibl><bibl>…</bibl></listBibl></div></back>
```

Mini-Métopes ne produit ni `biblStruct`, ni analyse d'auteur, titre, date,
éditeur ou DOI. Une référence est conservée comme contenu riche de `bibl`.
