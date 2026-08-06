# 0036 — Repli par nom localisé pour le style natif `Bibliography`

## Contexte

Signalé par l'utilisateur : un manuscrit réel utilisant le style Word
« Bibliographie » (interface française) échouait avec
`unsupported_paragraph_style`, malgré l'utilisation apparente du style
intégré natif. Investigation directe sur `docs/reference/manuscrit_reel_input.docx` :
Word peut écrire `w:styleId="Bibliographie"` avec `w:name="Bibliography"`
— notamment après une collision de nom (plusieurs révisions du document
ayant produit `Bibliographie1`, `Bibliography1`, `Bibliographie2` en plus
de l'original), résolue en réappliquant le style intégré depuis
l'interface française.

Contrairement à `Heading1`–`6`, `Title`, `Subtitle`, `BodyText`, `Quote`,
`Caption`, etc., le style `Bibliography` (décision 0026) n'avait **aucun
repli par nom localisé** : `is_native_bibliography_reference_style`
comparait uniquement l'identifiant exact `Bibliography`, et
`native_bibliography_style_ids` n'était pas de ceux étendus par
`resolve_convention_for_styles` (l'oubli remonte à la décision 0026, qui
a ajouté le style hors du système général d'alias `NATIVE_PARAGRAPH_STYLE_NAMES`
mis en place par la décision 0015/0020).

## Décision

Deux changements ciblés dans `editorial/convention.py` :

1. Ajout de l'entrée `("Bibliography", ("bibliography", "bibliographie"))`
   à `NATIVE_PARAGRAPH_STYLE_NAMES`. Seules l'anglais canonique et le
   français (confirmé directement par le corpus réel, langue de travail
   du projet) sont ajoutés — pas d'allemand/espagnol non vérifiés,
   cohérent avec la méthode de preuve de la décision 0020.
2. `native_bibliography_style_ids=_expand(convention.native_bibliography_style_ids)`
   ajouté à la liste des ensembles étendus par `resolve_convention_for_styles`
   — jusqu'ici oublié, alors que le mécanisme général existait déjà pour
   toutes les autres conventions de style.

Aucun changement à `is_native_bibliography_reference_style` elle-même : la
résolution passe entièrement par le mécanisme d'alias déjà en place
(`native_style_alias_map` associe `styleId → "Bibliography"` avant que la
convention ne soit consultée), donc la garde « pas de repli par nom
visible » documentée pour d'autres styles ne s'applique pas ici — c'est
au contraire le comportement recherché, symétrique avec `Heading`/`Title`/`Caption`.

## Conséquences

- 482 passed après ajout. Tests dédiés :
  `test_bibliography_style_resolves_by_canonical_or_localized_name`
  (`tests/test_native_style_resolution.py`),
  `test_bibliography_style_id_localized_to_french_is_recognized_by_name`
  (`tests/test_bibliographic_references.py`, reproduit exactement le
  motif `styleId="Bibliographie"` / `w:name="Bibliography"` observé dans
  le corpus réel).
- Re-test du manuscrit réel : les erreurs `unsupported_paragraph_style`
  liées à la bibliographie ont disparu ; les diagnostics restants
  (légendes de figure orphelines, image transformée) sont sans rapport
  avec cette décision.

## Limites assumées

- Seuls l'anglais et le français sont couverts. Allemand/espagnol non
  ajoutés faute de vérification indépendante (même seuil de preuve que la
  décision 0020) ; un document non couvert échoue toujours proprement
  (`unsupported_paragraph_style`), jamais silencieusement.
- Ne couvre pas les variantes numérotées issues de collisions Word
  (`Bibliographie1`, `Bibliography1`, `Bibliographie2`…) : leur nom
  affiché (`w:name`) est lui aussi généralement suffixé
  (`w:name="Bibliographie1"`), donc non reconnu par cette table de noms
  exacts — volontairement, un motif `Bibliography\d+` risquerait
  d'associer un style personnalisé distinct à tort (voir mise en garde de
  la décision 0020 sur les entrées devinées). La correction reste
  manuelle dans le document pour ces variantes.
