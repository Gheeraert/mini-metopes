# Matrice de validation du contrat de sortie

État, au moment de la passe de stabilisation, des niveaux de validation de la
TEI produite par Mini-Métopes. « Exécuté » signifie : appliqué automatiquement
dans le pipeline normal de conversion.

| Niveau | Exécuté | Testé | Documenté | Notes |
| --- | --- | --- | --- | --- |
| XML bien formé | Oui (lxml, construction d'arbre) | Oui | Oui | toute sérialisation passe par lxml ; `validation.validate_xml_bytes` détecte aussi la mal-formation en domaine `parser` |
| Relax NG Commons Publishing embarqué | **Oui** : `serialize_editorial_document_to_tei` valide chaque TEI avant de la retourner ; échec ⇒ aucun XML produit | Oui : suites `test_validation`, `test_tei_serialization`, corpus (`test_reference_corpus`) | Oui (`PROVENANCE.json` : dépôt fnso `tei-commons-publishing`, commit `f314375`, TEI P5 4.5.0, sans modification locale) | commande CLI `validate` disponible pour des fichiers arbitraires |
| Schéma exact de la chaîne aval, s'il diffère | **Non pris en charge** | Non | Oui (ici) | aucun schéma aval distinct n'est embarqué ; si la chaîne aval retient une autre version du profil, la validation doit être refaite côté consommateur |
| Règles Schematron du profil | **Non exécuté** : les motifs `sch:` inclus dans le RNG sont ignorés par le validateur Relax NG de lxml | Non | Oui (ici) | seule règle liste du profil : `list[@type='gloss']` doit avoir des `label` ; Mini-Métopes n'émet jamais `gloss`. Exécution Schematron possible en chaîne de maintenance (hors exécution normale, cf. décision 0001) |
| Import / consommation par les outils aval (Métopes aval, Lodel, Impressions) | **Non pris en charge** | Non | Oui (ici) | aucune compatibilité complète ne doit être affirmée sans test réel d'import ; à instrumenter avec les consommateurs |

## Politique conservatoire

Aucune TEI n'est produite lorsqu'un diagnostic bloquant subsiste : les erreurs
d'inspection bloquantes, les diagnostics éditoriaux bloquants et l'échec de la
validation Relax NG empêchent tous l'écriture du fichier (la sortie
préexistante n'est pas écrasée).

## Distinction d'avec la compatibilité d'entrée

L'absence de prise en charge des styles Word Métopes (`TEI_*`) est un choix de
périmètre d'**entrée** ; elle ne dit rien de la conformité de **sortie** au
profil Commons Publishing, qui est validée comme ci-dessus. Réciproquement, la
validation contre le RNG issu de l'écosystème Commons Publishing n'implique
aucune reconnaissance des styles Métopes en entrée.
