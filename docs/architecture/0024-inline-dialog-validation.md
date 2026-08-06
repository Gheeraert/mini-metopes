# 0024 — Validation immédiate dans les dialogues de saisie du GUI

## Contexte

Un audit du dépôt a signalé que le GUI de métadonnées ne donnait aucun
retour de validation avant le clic sur « Enregistrer » : les sept
dialogues de saisie répétable (contributeur, affiliation, identifiant,
financement, résumé, mots-clés, responsable d'édition) collectaient du
texte libre et fermaient sans jamais vérifier son format. L'exemple
concret cité : la règle « nom littéral **ou** nom structuré, jamais les
deux » (`invalid_contributor_name`) n'avait aucune traduction dans
`contributor_dialog` — un·e éditeur·rice remplissant par erreur les deux
champs ne l'apprenait qu'en cliquant sur Enregistrer, via une liste de
codes opaque, loin du formulaire où l'erreur avait été commise.

## Décision

- `gui/metadata_controller.py` : une fonction `*_field_errors` par type
  d'entrée (`contributor_field_errors`, `affiliation_field_errors`,
  `identifier_field_errors`, `funding_field_errors`,
  `abstract_field_errors`, `keyword_group_field_errors`,
  `responsibility_field_errors`, et pour complétude de l'API
  `collection_field_errors`/`license_field_errors`). Chacune place
  l'entrée en cours d'édition dans un document minimal jetable
  (`_probe_metadata`) puis appelle **`validate_metadata`** — jamais de
  règle dupliquée, source unique de vérité déjà établie par les décisions
  précédentes. Seules les erreurs (`severity="error"`) sont remontées :
  les avertissements (ex. `license_spdx_id_mismatch`, décision 0023) ne
  doivent jamais bloquer un dialogue, cohérent avec leur statut
  volontairement non bloquant.
- L'isolement dans un document minimal évite deux écueils : dupliquer les
  règles de validation dans le GUI, et faire remonter des erreurs
  préexistantes ailleurs dans le document (un autre contributeur mal
  formé, par exemple) comme si elles concernaient l'entrée en cours.
- `gui/metadata_editor.py` : un nouvel helper `_validated_form_dialog`
  boucle sur `form_dialog` tant que `field_errors(item)` n'est pas vide,
  affichant les messages dans une boîte d'erreur et rouvrant le
  formulaire avec la saisie précédente pour correction — jamais de
  fermeture silencieuse sur une entrée invalide. Les sept dialogues
  concernés l'utilisent désormais à la place d'un appel direct à
  `form_dialog`.

## Conséquences

- La règle nom littéral/structuré, un ORCID mal formé, un DOI invalide,
  un identifiant SPDX inconnu, etc. sont désormais signalés au moment de
  la saisie, dans le dialogue concerné — pas plus tard, pas sous forme de
  code opaque.
- Purement additif au niveau du modèle de données ; comportement
  observable changé uniquement dans le GUI (le dialogue ne se ferme plus
  sur une saisie invalide). 437 passed après ajout, tests dédiés
  (`tests/test_metadata_editor_field_validation.py`) vérifiant à la fois
  la détection d'erreur et l'absence de faux positif par isolement.

## Limites assumées

- Le périmètre de cette passe est **les dialogues modaux** (entités
  répétables). Les champs scalaires édités directement dans les onglets
  Document/Publication/Droits (titre, langue, collection, nom/URL de
  licence...) restent validés uniquement à l'enregistrement, comme avant
  — `collection_field_errors`/`license_field_errors` existent et sont
  testées pour la cohérence de l'API, mais ne sont pas encore câblées à
  un événement GUI (`FocusOut` ou équivalent) faute d'un mécanisme
  d'affichage inline pour des champs non modaux dans ce GUI. C'est un
  prolongement naturel, pas un oubli.
- La validation reste déclenchée au clic sur « Valider » du dialogue, pas
  à chaque frappe : un compromis délibéré — une validation vraiment
  continue (par frappe) sur des champs comme l'ORCID afficherait des
  erreurs transitoires sur une saisie encore incomplète, ce qui serait
  plus perturbant qu'utile.
