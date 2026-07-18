# 0016 — Métadonnées v2 et teiHeader Commons Publishing

## Contexte

Le modèle v1 (titre, contributeurs, affiliations, résumé plat, mots-clés
plats) ne suffisait pas aux publications des PURH : éditeur, responsables
d'édition, identifiants par support, licence, résumés multilingues,
quatrième de couverture, collection simple, pagination. La passe 3 étend le
JSON compagnon et sa sérialisation dans le `teiHeader`, sans compatibilité
ascendante (choix assumé, `schema_version` passe à `2.0`).

## Décisions

- **Modèle v2** (`metadata/model.py`) : groupes `source_document` (chemin
  relatif au JSON + SHA-256, jamais de base64), `document`, `contributors`
  (rôles `author`, `editor`, `translator`, `scientific_editor`, `other` +
  libellé), `affiliations`, `editorial_responsibility`, `publication`,
  `identifiers`, `rights`, `abstracts`, `keywords` (groupes linguistiques),
  `collection` simple, `pagination`. Spécification et table JSON → TEI :
  `docs/conventions/metadata-json-v2.md`.
- **Toutes les cibles TEI ont été vérifiées contre le RNG embarqué** avant
  d'être figées. Le profil n'admet ni `editionStmt`/`respStmt`, ni `abstract`
  dans `profileDesc`, ni `seriesStmt`, `extent`, `pubPlace`, `address` ;
  `idno/@type` est une énumération fermée. En conséquence : résumés dans
  `text/front/div[@type='abstract']` (quatrième distinguée par `n`), collection
  et pagination dans un second `sourceDesc/bibl`, responsable d'édition
  conservé en JSON seulement avec diagnostic explicite. Les pratiques Métopes
  observées dans `references/corpora` (grands blocs `ab` de `publicationStmt`,
  `abstract[@rend]`, balises vides `licence target="#"`) ne valident pas ce
  RNG et ne sont pas reproduites.
- **Aucune balise vide ni valeur de substitution** : les groupes absents ne
  produisent rien ; un détail de publication sans éditeur bloque
  (`missing_publisher_for_publication_details`) au lieu d'inventer une agence.
- **Profil institutionnel** : `profiles/purh.json` + fusion explicite
  (`metadata/profile.py`) où le JSON document gagne toujours ; aucune
  constante PURH dans le sérialiseur.
- **Éditeur Tkinter** refondu en cinq onglets défilables (Document, Auteurs,
  Publication, Résumés et mots-clés, Droits et identifiants), listes
  synthétiques avec Ajouter/Modifier/Supprimer et Monter/Descendre, boutons
  Enregistrer/Charger, relocalisation du DOCX introuvable ; toute la logique
  reste dans `gui/metadata_controller.py`, testable sans Tk.

## Conséquences

- Le corpus `document-b` porte des métadonnées PURH complètes de bout en
  bout, validées RNG et relues.
- Les anciens JSON v1 sont rejetés explicitement ; les fixtures et les
  générateurs ont été régénérés.

## Décisions restant à valider humainement

- Non-sérialisation du responsable d'édition (le profil devrait-il évoluer
  vers `editionStmt`/`respStmt`, comme le TEI général le permet ?).
- Marquage de la quatrième de couverture par `div/@n='back-cover'`.
- Non-sérialisation de `pagination.extent`, du lieu et de l'adresse de
  l'éditeur, du support précis (pdf/epub) des eISBN.
- Rôle TEI unique `edt` pour `editor` et `scientific_editor`.
