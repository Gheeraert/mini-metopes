# 0007 — Métadonnées JSON et éditeur

## Décision

Les métadonnées sont un modèle Python immuable, versionné par
`schema_version: "1.0"`, et enregistrées dans un JSON voisin du DOCX. Le JSON
est l'autorité du `teiHeader`; la couche Tkinter est seulement un client du
contrôleur testable `mini_metopes.gui.metadata_controller`.

## Sources et cohérence

`chapitre.docx` est associé à `chapitre.metadata.json`. Le JSON ne contient que
le nom du DOCX et son SHA-256, jamais un chemin absolu. L'empreinte détecte une
modification mais ne rend pas les métadonnées invalides. `Title` et `Subtitle`
initiaux sont des suggestions; ils sont consommés uniquement si un JSON valide
est fourni, et toute divergence est un avertissement dont le JSON reste maître.

## TEI Commons Publishing

Le RNG embarqué accepte `title@type`, `author`, `editor`, `persName`, `idno`
ORCID, `affiliation`, `langUsage` et `keywords`. Les affiliations sont rendues
inline sans `xml:id`: le profil ne fournit pas ici de registre partagé, et un
identifiant répété serait invalide. `translator`, `compiler` et `contributor`
sont provisoirement rendus comme `editor` avec avertissement, car ce profil ne
permet pas `respStmt` dans `titleStmt`. Le résumé reste dans le JSON et produit
un avertissement: `abstract` n'est pas admis sous `profileDesc` par le RNG.

## Limites

L'éditeur ne déclenche jamais une conversion, et aucune métadonnée de livre
multi-fichiers, ISBN, DOI, date de publication, liste, tableau ou figure n'est
introduite dans cette passe.
