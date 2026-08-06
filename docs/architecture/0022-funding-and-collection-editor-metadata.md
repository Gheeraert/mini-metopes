# 0022 — Métadonnées de financement et éditeur de collection

## Contexte

Un audit du dépôt a signalé deux lacunes concrètes du modèle de
métadonnées pour un usage en presses universitaires :

- aucun champ pour mentionner un financement (ANR, ERC…), alors que c'est
  une exigence courante de reconnaissance de financeur pour une
  publication en sciences humaines ;
- `Collection` (`title`, `issn`, `volume`) ne portait pas de champ pour la
  personne dirigeant la collection, alors que `EditorialResponsibility`
  existe pour un rôle éditorial voisin mais n'est explicitement jamais
  sérialisé en TEI (`editorial_responsibility_not_serialized`) et n'est pas
  rattaché à une collection en particulier.

## Décision

Avant tout ajout de champ, le schéma Commons Publishing embarqué a été
inspecté (conformément à `AGENTS.md` §3) :

- `<funder>` existe dans `model.respLike` de `<titleStmt>`, aux côtés de
  `<author>`/`<editor>` : contenu `oneOrMore(orgName | idno)`. L'attribut
  `idno[@type='funder_registry']` est explicitement prévu pour un
  identifiant de subvention.
- `<series>` (déjà utilisé pour `collection`) accepte `<editor>` en enfant
  direct, contenu `macro.phraseSeq` (texte simple suffisant).

Aucun élément n'a donc dû être inventé.

- `metadata/model.py` : nouvelle dataclass `Funding(funder, grant_number=None)`,
  champ `DocumentMetadata.funding: tuple[Funding, ...] = ()`. `Collection`
  gagne `editor: str | None = None`.
- `metadata/validation.py` : `funder` obligatoire par entrée (`invalid_funder`),
  `grant_number` non vide s'il est fourni (`invalid_grant_number`),
  `collection.editor` non vide s'il est fourni (`invalid_collection_editor`)
  — même sévérité et même style que les validations `Collection` existantes.
- `metadata/serialization.py` : JSON `funding[]` (`funder`, `grant_number`)
  et `collection.editor`, absents du JSON quand vides (pas de structure
  factice, cohérent avec le reste du module).
- `tei/serializer.py` : chaque `Funding` devient un `<funder>` dans
  `titleStmt`, après les contributeurs ; `collection.editor` devient
  `<editor>` dans `<series>`, avant `biblScope`/`idno` (ordre libre dans le
  schéma, choisi pour la lisibilité).
- `gui/metadata_editor.py` : champ « Éditeur de la collection » ajouté au
  cadre Collection existant ; nouvelle liste répétable « Financement »
  (organisme, numéro de subvention) dans l'onglet Publication, câblée via
  `sequence_actions` — le même mécanisme générique déjà utilisé pour les
  identifiants et les responsables d'édition, sans nouveau code de
  câblage ad hoc.

`schema_version` n'est **pas** incrémenté : la politique documentée
(`docs/conventions/metadata-json-v1.md` §Versionnement) prévoit un
incrément mineur pour un champ facultatif, mais aucun des ajouts facultatifs
précédents (`identifiers`, `abstracts`, `collection`, `pagination`…) ne l'a
fait en pratique — `METADATA_SCHEMA_VERSION` vaut toujours `"1.0"`. Bumper
ici seul aurait cassé tous les fixtures/JSON existants pour une
incohérence préexistante, hors périmètre de cette décision.

## Conséquences

- Un financement ANR/ERC est désormais représentable de bout en bout :
  JSON → validation → `teiHeader/titleStmt/funder` → RNG valide.
- Une collection peut porter son éditeur, sérialisé dans le second
  `sourceDesc/bibl/series`, distinct de `editorial_responsibility` (qui
  reste non sérialisée, portée éditoriale du document entier, pas de la
  collection).
- Purement additif : tests existants inchangés, 417 passed après ajout.
- Tests ajoutés à tous les niveaux : modèle/validation
  (`test_metadata_validation.py`), sérialisation JSON round-trip et JSON
  mal typé (`test_metadata_serialization.py`), TEI
  (`test_metadata_tei_header.py`, cas positif complet avec deux
  financements dont un sans numéro de subvention, pour vérifier que
  `idno` reste absent quand `grant_number` est `None`).

## Limites assumées

- `Funding.funder` est une chaîne libre, non normalisée : pas de registre
  contrôlé (ex. Crossref Funder Registry / ROR pour les organismes de
  financement). `idno[@type='funder_registry']` porte ici le numéro de
  subvention fourni par l'utilisateur, pas un identifiant de registre
  vérifié — cohérent avec le principe du projet de ne jamais deviner une
  valeur non fournie.
- Un seul champ éditeur par collection (texte libre), pas une référence
  structurée vers un `Contributor` existant : suffisant pour l'usage
  demandé (mention en colophon), pas une modélisation relationnelle
  complète. Une évolution future pourrait relier un éditeur de collection
  à un `contributor_id` existant si le besoin se confirme.
