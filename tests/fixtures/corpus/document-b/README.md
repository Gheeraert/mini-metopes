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

Depuis la passe 3 (métadonnées), ce document porte des **métadonnées PURH
complètes**. Sont sérialisés dans le `teiHeader` et le `front` : éditeur (nom
et URL), date, DOI, ISBN print et PDF, ISSN, licence CC, détenteur et mention
de droits, résumés français/anglais, quatrième de couverture, mots-clés
bilingues, collection (titre, ISSN, volume) et pagination.

Restent **uniquement dans le JSON**, avec diagnostics explicites : le
responsable d'édition (le profil embarqué n'admet ni `editionStmt` ni
`respStmt`), le lieu et l'adresse de l'éditeur (pas de `pubPlace`/`address`),
et le support précis de l'ISBN électronique (sérialisé `eISBN` sans
distinction pdf/epub/html).

Conversion attendue : succès ; deux diagnostics informatifs documentés
(`publisher_address_not_serialized`, `editorial_responsibility_not_serialized`).

Le fichier `expected.xml` est généré puis validé contre le RNG embarqué ; il
doit encore faire l'objet d'une validation éditoriale humaine avant d'être
considéré comme référence définitive.
