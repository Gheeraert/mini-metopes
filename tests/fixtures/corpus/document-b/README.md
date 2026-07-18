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

Conversion attendue : succès, aucun diagnostic.
