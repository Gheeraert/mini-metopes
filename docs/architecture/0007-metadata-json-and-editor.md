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

## Micropasse 7A

Le chargement du JSON passe desormais par un decodage type avant construction du
modele. Les erreurs de forme ne doivent jamais atteindre le validateur sous
forme d'objets Python incompatibles. Les diagnostics stables sont
`invalid_metadata_structure`, `invalid_field_type` et
`missing_metadata_field`, avec des chemins comme `document.title`,
`contributors[0].role` ou `affiliations[1].name`.

Les diagnostics de metadonnees ont l'origine `metadata` dans le resultat de
conversion TEI. L'ordre retenu est: inspection, modele editorial, validation des
metadonnees, suggestions Word, coherence JSON/DOCX, serialisation, validation
normative. Les diagnostics de suggestions Word sont dedoublonnes par code pour
eviter qu'un meme probleme soit signale deux fois dans la conversion.

Le controleur de l'editeur charge les avertissements de coherence dans l'etat
affiche. La fenetre montre les diagnostics dans la zone Document. Un JSON
invalide declenche un etat de secours explicite et son ecrasement demande une
confirmation. Le suivi des modifications compare l'etat courant a l'instantane
sauvegarde; le bouton Annuler et la croix de fermeture utilisent la meme
confirmation.

Les identifiants de contributeurs et d'affiliations restent editables. Le
controleur recoit l'ancien identifiant, preserve la position de l'objet renomme,
refuse les collisions et met a jour les references des contributeurs lorsqu'une
affiliation est renommee.

L'ORCID est normalise avant serialisation, y compris pour un contributeur saisi
sous forme de nom litteral. Le ROR reste conserve dans le JSON. Le RNG Commons
Publishing embarque ne permet pas de le representer proprement dans
`affiliation` dans cette structure de header; la conversion emet donc
`ror_not_serialized` plutot que de perdre cette donnee silencieusement.
`document_type`, `contributor_id` et `affiliation_id` restent des donnees
d'orchestration et de controle du JSON dans cette version.
