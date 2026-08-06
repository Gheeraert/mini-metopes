# 0034 — Type de document `book`

## Contexte

Depuis la décision 0032, un DOCX peut représenter un livre entier à
plusieurs contributions plutôt qu'un seul chapitre/article. L'énumération
`document.type` du JSON de métadonnées (`article`, `chapter`,
`introduction`, `conclusion`, `bibliography`, `other`) ne le distinguait
pas explicitement — classer un tel document comme `"chapter"` ou
`"other"` est trompeur à la relecture du JSON.

## Décision

Ajout de la valeur `"book"` à l'énumération `DocumentType`
(`metadata/model.py`), au frozenset de validation `_DOCUMENT_TYPES`
(`metadata/validation.py`) et à la liste `_DOCUMENT_TYPES` du menu
déroulant de l'éditeur graphique (`gui/metadata_editor.py`).

Purement descriptif et sans effet de bord : comme les autres valeurs de
`document_type`, `"book"` n'est lu ni par `tei/serializer.py` ni par la
logique éditoriale (aucun branchement sur ce champ, vérifié à la
décision 0032, section « hors périmètre »). Il ne change ni la
détection de structure (toujours purement mécanique par niveau de titre,
voir 0032) ni la validation de la Signature.

## Consequences

- 477 passed apres ajout. Test dedie : `test_book_document_type_is_valid`
  (`tests/test_metadata_validation.py`).
- Documentation mise a jour : README, `docs/conventions/metadata-json-v1.md`,
  `docs/conventions/native-word-to-tei-v0.2.md`.

## Limites assumées

- Reste une classification a but humain uniquement ; si un jour un
  comportement doit varier selon le type de document, cette decision
  devra etre revisitee (pas de detection de mode codee a ce jour, voir
  0032).
