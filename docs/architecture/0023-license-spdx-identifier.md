# 0023 — Licence en vocabulaire contrôlé (identifiant SPDX)

## Contexte

`License.name`/`License.url` sont du texte libre : rien n'empêchait deux
personnes d'entrer « CC-BY 4.0 » et « CC BY 4.0 » pour la même licence,
sans normalisation ni avertissement. Un audit du dépôt a recommandé un
vocabulaire contrôlé de type SPDX en complément du texte libre — jamais en
remplacement, pour ne pas casser les licences hors liste (accords
spécifiques, licences maison, absence de licence Creative Commons).

Le schéma Commons Publishing embarqué a été inspecté avant tout ajout :
`<licence>` (`att.pointing.attribute.target` + texte) n'a pas d'attribut
dédié à un identifiant machine — seul `@target` (déjà utilisé pour l'URL)
existe. Il n'y a donc pas de place TEI pour stocker un `spdx_id` distinct :
il reste un champ JSON de confort, jamais sérialisé tel quel, qui sert à
*dériver* `name`/`url` de façon fiable.

## Décision

- `metadata/model.py` : `License` gagne `spdx_id: str | None = None`.
- `metadata/validation.py` : registre `SPDX_LICENSES` (dict figé, sous-ensemble
  volontairement limité aux licences Creative Commons 4.0 et CC0 1.0 — les
  plus frequentes en édition universitaire francophone) :
  - `spdx_id` inconnu du registre → erreur bloquante
    (`invalid_license_spdx_id`) : il n'y a aucune raison légitime de saisir
    un identifiant qui ne sera jamais résolu ;
  - `spdx_id` connu mais `name`/`url` explicites et différents du nom/URL
    canonique → **avertissement** (`license_spdx_id_mismatch`), jamais
    bloquant, conformément à la demande explicite de ne pas casser un cas
    légitime où l'éditeur personnalise volontairement l'affichage ;
  - `spdx_id` connu seul (sans `name`/`url`) → valide, aucune erreur
    `missing_license_name` (le nom sera dérivé).
  - `resolved_license(license)` : fonction pure qui complète `name`/`url`
    depuis `spdx_id` uniquement quand ils sont absents, sans jamais écraser
    une valeur explicite. Utilisée à la fois par la validation
    (indirectement, via le calcul du mismatch) et par la sérialisation TEI,
    pour ne pas dupliquer le registre à deux endroits.
- `tei/serializer.py` : `<licence>`/`<availability>` sont construits à
  partir de `resolved_license(rights.license)`, pas de `rights.license`
  brut — un `spdx_id` seul suffit désormais à produire une licence complète
  et valide.
- `gui/metadata_editor.py` : combobox en lecture seule listant les
  identifiants SPDX connus, à côté des champs libres nom/URL existants,
  avec une note explicite indiquant qu'elle complète les champs vides sans
  les écraser.

## Conséquences

- Un éditeur peut choisir « CC-BY-4.0 » dans une liste plutôt que de taper
  le nom et l'URL exacts : zéro risque de faute de frappe pour les
  licences les plus courantes.
- Le texte libre reste pleinement fonctionnel et prioritaire : `spdx_id`
  ne remplace jamais une valeur déjà saisie, il ne fait que la compléter
  ou signaler (en avertissement) une incohérence.
- Purement additif, 424 passed. Tests à tous les niveaux : validation
  (erreur sur id inconnu, avertissement sur incohérence, cas valide
  id-seul), `resolved_license` en unité, JSON round-trip, TEI (licence
  complète dérivée d'un `spdx_id` seul).

## Limites assumées

- Registre volontairement restreint aux licences Creative Commons 4.0 et
  CC0 1.0. Étendre à d'autres familles (GPL, licences nationales type
  Licence Ouverte Etalab...) est un travail futur explicite, pas un oubli
  — chaque ajout nécessiterait de vérifier le nom/URL canonique exact
  avant intégration, comme pour les noms de styles Word (décision 0020).
- `spdx_id` n'est jamais sérialisé tel quel dans la TEI (aucune place dans
  le schéma) : il ne vit que dans le JSON Mini-Métopes, comme aide de
  saisie. Un consommateur de la TEI seule ne voit que `name`/`url`
  résolus, pas l'identifiant SPDX d'origine.
