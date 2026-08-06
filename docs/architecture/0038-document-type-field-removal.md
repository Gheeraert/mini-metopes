# 0038 — Suppression du champ `document_type`

*Remplace la décision 0034 (ajout de la valeur `"book"` à l'énumération),
retirée sans rétrocompatibilité.*

## Contexte

Décision 0037 : Mini-Métopes ne produit désormais que du XML de livres
entiers. Le champ `document.type` du JSON de métadonnées
(`article`/`chapter`/`book`/`introduction`/`conclusion`/`bibliography`/`other`)
n'a plus de sens utile : un seul type existerait (« livre »), et les
décisions 0032/0034 avaient déjà établi qu'il n'était lu nulle part dans
`tei/serializer.py` ni la logique éditoriale (purement descriptif, zéro
branchement de code, vérifié par recherche directe).

## Décision

**Suppression complète du champ**, pas réduction à `Literal["book"]` (qui
n'apporterait aucun signal — chaque document est déjà connu comme un
livre par la portée documentée de l'outil, décision 0037) :

- `metadata/model.py` : retrait de `DocumentType` et du champ
  `document_type` sur `DocumentMetadata`.
- `metadata/validation.py` : retrait de `_DOCUMENT_TYPES` et du contrôle
  `invalid_document_type`.
- `metadata/serialization.py` : retrait de l'écriture et de la lecture du
  champ JSON `document.type`.
- `gui/metadata_editor.py` : retrait du menu déroulant `_DOCUMENT_TYPES`
  (`ttk.Combobox`), de `type_var`, et de son câblage
  sauvegarde/chargement — champ jamais branché à un comportement, listé
  explicitement par l'utilisateur comme à retirer.
- `gui/metadata_controller.py` : retrait de `document_type="chapter"`
  (valeur par défaut codée en dur) des deux constructeurs de métadonnées
  initiales.
- `docs/conventions/metadata-json-v1.md` : retrait de la ligne
  `document.type` de la table de structure et de la liste de codes de
  diagnostic.

### `METADATA_SCHEMA_VERSION` incrémentée à `"2.0"`

Suppression de champ = rupture de forme JSON. Un ancien `metadata.json`
(`schema_version: "1.0"`, avec `document.type`) échoue désormais
explicitement (`unsupported_schema_version`) plutôt que d'être
silencieusement accepté avec une clé ignorée — cohérent avec « aucune
rétrocompatibilité requise » (décision 0037). Les 22 fixtures JSON du
dépôt (corpus de référence et `tests/fixtures/metadata/`) ont été migrées
en conséquence : `schema_version` porté à `"2.0"`, clé `document.type`
retirée.

## Conséquences

- Suite complète verte après la passe (492 passed). Tests mécaniquement
  mis à jour : tout `DocumentMetadata(...)`/`_probe_metadata(...)` passant
  `document_type=` a perdu ce kwarg ; `test_book_document_type_is_valid`
  et le cas `invalid_document_type` de `test_validation_codes` supprimés
  (le champ et son code de diagnostic n'existent plus).
- Le lecteur JSON reste permissif envers une clé `document.type`
  résiduelle qui subsisterait dans un fichier par ailleurs valide
  (`schema_version: "2.0"`) : elle serait simplement ignorée, sans
  diagnostic dédié. Le bump de version reste le signal de rupture
  principal et suffisant.

## Limites assumées

- Aucune migration automatique des anciens `metadata.json` (`schema_version:
  "1.0"`) n'est fournie : ils doivent être recréés ou édités manuellement
  (retrait de `document.type`, passage à `"2.0"`), cohérent avec l'absence
  de rétrocompatibilité requise.
