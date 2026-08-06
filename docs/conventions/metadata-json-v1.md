# Métadonnées JSON (schema_version 1.0)

Spécification du JSON compagnon des DOCX Mini-Métopes. Le JSON porte les
**métadonnées** ; les styles natifs Word portent la **structure du contenu**.
Les styles Word Métopes restent hors périmètre, et aucun champ de métadonnées
ne doit être encodé au moyen d'un style `TEI_*` dans le document Word.

Ce contrat est la première version stable du JSON compagnon
(`schema_version: "1.0"`). Les JSON du prototype antérieur (champ `source`,
résumé et mots-clés plats) ne sont ni acceptés ni migrés : aucun JSON de
production antérieur n'existe.

## Principes

- lisible, explicite, versionné (`schema_version`), déterministe (UTF-8,
  deux espaces, ordre stable, saut de ligne final, double sérialisation
  identique octet par octet) ;
- indépendant de la présentation Word ;
- générique : aucune constante PURH dans le moteur ; les valeurs
  institutionnelles stables viennent d'un profil facultatif
  (`profiles/purh.json`) que le JSON du document surcharge toujours ;
- les groupes facultatifs absents ne sont pas émis, ni en JSON ni en TEI.

## Lien vers le DOCX source

```json
"source_document": { "path": "chapitres/conclusion_racine.docx", "sha256": "…" }
```

- `path` : de préférence relatif à l'emplacement du JSON (séparateurs `/`) ;
  absolu seulement quand aucun relatif n'existe (autre lecteur Windows) ;
- résolu à l'ouverture par rapport au JSON ; si le DOCX est introuvable,
  l'éditeur propose de le relocaliser ;
- le DOCX n'est **jamais** incorporé en base64 ;
- `sha256` fige l'état du document ; toute divergence produit
  `metadata_source_changed` (avertissement, le JSON reste l'autorité).

## Structure

| Groupe | Champs | Obligatoire | Hérité du profil |
| --- | --- | --- | --- |
| `schema_version` | `"1.0"` | oui | — |
| `source_document` | `path`, `sha256` | oui | — |
| `document` | `title`, `subtitle`, `language` (BCP 47), `type` (`article`, `chapter`, `introduction`, `conclusion`, `bibliography`, `other`) | titre, langue, type | — |
| `contributors[]` | `id`, `role` (`author`, `editor`, `translator`, `scientific_editor`, `other`+`role_label`), `given_name`/`family_name` **ou** `literal_name`, `orcid`, `email`, `affiliations[]` (IDs) | liste possible vide ; ordre significatif | — |
| `affiliations[]` | `id`, `name`, `unit`, `city`, `country`, `ror` (URL https ror.org) | — | — |
| `editorial_responsibility[]` | `responsibility`, `name` | — | — |
| `publication` | `publisher.name/place/address[]/url`, `publication_date` (`AAAA`, `AAAA-MM`, `AAAA-MM-JJ`) | — | `publisher.*` |
| `identifiers[]` | `type` (`doi`, `isbn-13`, `isbn-10`, `issn`, `eissn`, `local`), `value`, `format` (`print`, `pdf`, `epub`, `html`) | format obligatoire pour un ISBN | — |
| `rights` | `holder`, `statement`, `license.name`, `license.url`, `license.spdx_id` (sous-ensemble CC 4.0 + CC0, voir décision 0023) | nom de licence obligatoire avec URL, sauf `spdx_id` renseigné | `holder` |
| `abstracts[]` | `type` (`summary`, `abstract`, `back-cover`), `language`, `text` (un paragraphe par ligne) | — | — |
| `keywords[]` | `language`, `scheme` (défaut `keywords`), `items[]` | ordre conservé, pas de déduplication automatique | — |
| `collection` | `title`, `issn`, `volume`, `editor` — collection simple uniquement | titre si présent | — |
| `pagination` | `from`+`to` **ou** `extent` (exclusifs) | — | — |
| `funding[]` | `funder`, `grant_number` | funder obligatoire par entrée si le tableau est présent | — |

Le titre et le sous-titre peuvent être suggérés depuis les styles Word natifs
`Title`/`Subtitle` (y compris localisés `Titre`/`Sous-titre`), mais le JSON
reste la source autoritative ; les divergences produisent les avertissements
`metadata_title_differs_from_docx` / `metadata_subtitle_differs_from_docx`.

Exemples : `tests/fixtures/metadata/minimal.json` (minimal),
`complete-purh.json` (complet PURH), `multilingual.json`
(Unicode, grec ancien) et `tests/fixtures/corpus/document-b/metadata.json`
(corpus de bout en bout).

## Normalisations (locales, sans réseau)

- **ORCID** : URI `https://orcid.org/…` admise, normalisée vers
  `0000-0000-0000-000X` ; clé ISO 7064 mod 11-2 vérifiée.
- **ISBN** : tirets/espaces ignorés pour la vérification (clé ISBN-10 ou
  ISBN-13) ; la forme saisie est conservée dans le JSON et la TEI ; le format
  de publication n'est jamais deviné.
- **DOI** : URI `doi.org`/`dx.doi.org` ou préfixe `doi:` admis, normalisé vers
  `10.xxxx/suffixe` ; aucune résolution réseau.
- **ISSN** : normalisé vers `NNNN-NNNC`, clé mod 11 vérifiée.
- **Langues** : syntaxe BCP 47 raisonnable (`fr`, `fr-FR`, `en-GB`, `la`,
  `grc`) ; aucune liste fermée ; `fr-FR` n'est jamais réduit à `fr` ni
  l'inverse.
- **Dates** : `AAAA`, `AAAA-MM`, `AAAA-MM-JJ` ; jamais complétées ; les
  dates calendaires impossibles (`2026-02-31`, `2025-02-29`) sont refusées.
- **URL** : forme http(s) contrôlée pour licence, ROR, éditeur ; sans appel
  réseau.
- **Mots-clés** : les doublons à la casse ou aux accents près sont signalés
  (`similar_keywords`, avertissement) mais jamais dédupliqués.

## Table JSON → TEI (profil Commons Publishing embarqué)

| JSON | TEI | Remarques |
| --- | --- | --- |
| `document.title` / `subtitle` | `titleStmt/title[@type='main'|'sub']` | |
| `contributors` role `author` | `titleStmt/author[@role='aut']/persName(forename+surname|texte)` | ordre conservé |
| role `editor`, `scientific_editor` | `titleStmt/editor[@role='edt']` | distinction conservée en JSON seulement |
| role `translator` | `titleStmt/editor[@role='trl']` | |
| role `other` | `titleStmt/editor[@role='ctb']` | `role_label` JSON seulement (info) |
| `orcid` | `author|editor/idno[@type='ORCID']` | normalisé |
| `affiliations` référencées | `author|editor/affiliation` (texte) | `ror` non sérialisé (avertissement) |
| `publication.publisher.name` | `publicationStmt/publisher` | obligatoire dès qu'un détail de publication existe (`missing_publisher_for_publication_details`, bloquant) |
| `publisher.url` | `publicationStmt/ref[@target][@type='site']` | |
| `publisher.place`, `address` | non sérialisés | pas de `pubPlace`/`address` dans le profil (info) |
| `publication_date` | `publicationStmt/date[@when][@type='publishing']` | |
| `identifiers` doi | `idno[@type='DOI']` (valeur normalisée) | |
| isbn-13/10 + `print` | `idno[@type='pISBN']` | |
| isbn-13/10 + `pdf`/`epub`/`html` | `idno[@type='eISBN']` | le support précis reste en JSON |
| issn / eissn | `idno[@type='pISSN'|'eISSN']` (normalisé) | |
| local | `idno[@type='documentnumber']` | |
| `rights.license` | `availability/licence[@target=url]` (texte = nom) | jamais de `target` de substitution |
| `rights.statement`, `holder` | `availability/p`, `availability/p` (`© …`) | |
| `document.language` | `profileDesc/langUsage/language[@ident]` | |
| `keywords[]` | `profileDesc/textClass/keywords[@scheme][@xml:lang]/list/item` | un `keywords` par groupe, ordre conservé |
| `abstracts[]` | `text/front/div[@type='abstract'][@xml:lang]`, un `p` par ligne | le profil embarqué n'admet pas `abstract` dans `profileDesc` |
| abstract `back-cover` | idem + `@n='back-cover'` | attribut libre `n`, documenté ici |
| `collection` | second `sourceDesc/bibl/series` : `title`, `editor`, `biblScope[@unit='volume']`, `idno[@type='pISSN']` | pas de `seriesStmt` dans le profil |
| `pagination.from`/`to` | `sourceDesc/bibl/biblScope[@unit='page']` (`125-148`) | pas de `@from/@to` dans le profil |
| `pagination.extent` | non sérialisé (`pagination_extent_not_serialized`, avertissement) | pas d'`extent` dans le profil |
| `editorial_responsibility` | non sérialisé (`editorial_responsibility_not_serialized`, info) | pas d'`editionStmt`/`respStmt` dans le profil |
| `contributors[].email` | non sérialisé (info) | |
| `funding[]` | `titleStmt/funder/orgName` + `funder/idno[@type='funder_registry']` si `grant_number` | un `funder` par entrée, ordre conservé ; `funder` (nom) toujours sérialisé, `grant_number` seulement si présent |

Aucune structure vide ni valeur de substitution n'est produite : sans
métadonnées, `publicationStmt` retombe sur son paragraphe descriptif, et
`front`, `textClass`, `availability`, `bibl` sont simplement absents.

## Codes de diagnostic

Validation (`error` sauf mention) : `unsupported_schema_version`,
`missing_title`, `missing_language`, `invalid_language`,
`invalid_document_type`, `invalid_source_path`, `invalid_source_sha256`,
`invalid_contributor_id`, `invalid_contributor_role`,
`missing_contributor_role_label`, `invalid_contributor_name`, `invalid_orcid`,
`invalid_email`, `invalid_affiliation_reference`,
`unknown_affiliation_reference`, `duplicate_contributor_id`,
`duplicate_affiliation_id`, `invalid_affiliation_id`,
`invalid_affiliation_name`, `invalid_ror`, `invalid_responsibility`,
`invalid_responsibility_name`, `invalid_publisher_name`,
`invalid_publisher_url`, `invalid_publisher_address`,
`invalid_publication_date`, `invalid_identifier_type`,
`invalid_identifier_format`, `invalid_identifier_value`, `invalid_doi`,
`invalid_isbn`, `missing_identifier_format`, `invalid_issn`,
`invalid_rights_holder`, `invalid_rights_statement`, `invalid_license_name`,
`invalid_license_url`, `missing_license_name`, `invalid_abstract_type`,
`empty_abstract`, `invalid_keyword_scheme`, `empty_keyword_group`,
`invalid_keyword`, `similar_keywords` (warning),
`invalid_collection_title`, `invalid_collection_volume`,
`invalid_collection_editor`,
`conflicting_pagination`, `incomplete_pagination`, `invalid_pagination`,
`invalid_funder`, `invalid_grant_number`,
`invalid_license_spdx_id`, `license_spdx_id_mismatch` (warning).

Chargement : `invalid_json`, `invalid_metadata_structure`,
`missing_metadata_field`, `invalid_field_type`, `metadata_file_unreadable`.
Profil : `profile_file_unreadable`, `invalid_profile_json`,
`invalid_profile_structure`, `invalid_profile_id`.
Cohérence : `metadata_source_filename_changed`, `metadata_source_changed`,
`metadata_title_differs_from_docx`, `metadata_subtitle_differs_from_docx`,
`signature_contributor_not_in_metadata`.
Sérialisation TEI : `missing_publisher_for_publication_details` (bloquant),
`pagination_extent_not_serialized` (warning),
`editorial_responsibility_not_serialized`, `publisher_address_not_serialized`,
`contributor_email_not_serialized`,
`contributor_role_serialized_as_contributor` (info), `ror_not_serialized`,
`unreferenced_affiliation_not_serialized` (warning).

## Profil institutionnel

`profiles/purh.json` fournit `publisher.{name,place,address,url}` et
`rights_holder`. Application : CLI `convert-docx --profile profiles/purh.json`
ou bouton « Appliquer un profil… » de l'éditeur. Le profil ne remplit que les
valeurs absentes du document et n'est jamais requis.

## Versionnement et évolutions

`schema_version` suit un versionnement majeur.mineur : un ajout de champ
facultatif incrémente le mineur (les lecteurs 2.x acceptent) ; tout changement
de forme ou de sémantique d'un champ existant incrémente le majeur et fait
l'objet d'une nouvelle spécification datée. Aucun mécanisme de migration
automatique n'est fourni ; la version affichée dans le JSON est vérifiée au
chargement.
