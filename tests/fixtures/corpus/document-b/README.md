# Document B — article universitaire courant (Word anglais)

Document produit par un Word anglais : identifiants et noms canoniques
(`Heading1`…, `Quote`, `BodyText`, `ListParagraph`).

Contenu :

- titre principal (`Title`), consommé comme suggestion de métadonnées ;
- trois niveaux de titres → `div` imbriqués avec `head` ;
- citation en prose (`Quote`) → `quote/p` ;
- liste ordonnée décimale → `list type="decimal" n="1"` ;
- liste imbriquée (`ilvl` 1, lowerLetter) → `list type="lowerLetter"` dans
  l'`item` parent ;
- liste non ordonnée à puces → `list type="bulleted"` ;
- paragraphe consécutif (`BodyText`) → `p rend="consecutive"` ;
- hyperlien externe → `ref target="…"` ;
- deux notes de bas de page → `note place="foot"`.

Depuis la passe métadonnées v2, ce document porte des **métadonnées PURH
complètes** (éditeur, date, DOI, ISBN par support, ISSN, licence CC, résumés
français/anglais, quatrième de couverture, mots-clés bilingues, collection,
pagination, responsable d'édition) sérialisées dans le `teiHeader` et le
`front`.

Conversion attendue : succès ; deux diagnostics informatifs documentés
(`publisher_address_not_serialized`, `editorial_responsibility_not_serialized`).
