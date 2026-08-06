# 0018 — Source unique de la sévérité des diagnostics

## Contexte

`tei/conversion.py` reclassait la sévérité bloquante/non bloquante des
diagnostics via deux allowlists distinctes, séparées des points d'émission
réels :

- `_BLOCKING_INSPECTION_CODES` (13 entrées) — en pratique **totalement
  inerte** : `_inspection_severity` renvoyait déjà `"error"` par défaut pour
  tout code absent de `_NON_BLOCKING_INSPECTION_CODES`, avant même de
  consulter cette liste. Y ajouter ou en retirer un code n'avait donc aucun
  effet observable ; un mainteneur pouvait raisonnablement croire l'inverse.
- `_BLOCKING_EDITORIAL_CODES` (~90 entrées) — celle-ci avait un effet réel :
  `_editorial_diagnostics` promouvait en `"error"` tout diagnostic dont le
  code y figurait, quelle que soit la sévérité déclarée à l'émission dans
  `editorial/builder.py`. Un audit du dépôt a signalé le risque : un nouveau
  code bloquant ajouté dans `builder.py` sans mise à jour parallèle de cette
  liste dans `conversion.py` resterait silencieusement non bloquant.

Vérification exhaustive (script AST sur les 39 sites de construction
`EditorialDiagnostic(...)` de `editorial/builder.py`) : sur les ~90 codes de
`_BLOCKING_EDITORIAL_CODES`, seuls 5 étaient réellement promus (c'est-à-dire
émis avec une sévérité `"warning"`/`"info"` à la source alors que le projet
les traite comme bloquants) :

- `deferred_paragraph_style` (`"info"` à l'émission)
- `unsupported_paragraph_style` (`"warning"`)
- `unsupported_character_style` (`"warning"`)
- `conflicting_vertical_alignment` (`"warning"`)
- `unsupported_break_type` (`"warning"`)

Tous les autres codes de la liste étaient déjà émis avec `severity="error"`
à la source : la liste était pour eux une redite sans effet.

## Décision

- Les 5 codes ci-dessus sont désormais émis avec `severity="error"`
  directement dans `editorial/builder.py`, à l'endroit même où le code est
  choisi. Aucun changement de comportement : ils bloquaient déjà la
  conversion via l'ancienne promotion.
- `_editorial_diagnostics` (`tei/conversion.py`) fait désormais confiance à
  `diagnostic.severity` tel qu'émis, sans reclassement. `_BLOCKING_EDITORIAL_CODES`
  est supprimée.
- `_BLOCKING_INSPECTION_CODES`, dont l'inertie est démontrée ci-dessus, est
  supprimée. `_inspection_severity` reste volontairement **fail-closed par
  défaut** : toute observation d'inspection bloque la conversion sauf figurer
  dans `_NON_BLOCKING_INSPECTION_CODES` (liste courte et à jour :
  `comments_not_inspected`, `headers_footers_not_inspected`,
  `list_paragraph_without_numbering`, `missing_numbering_level_assumed_zero`).
  C'est la seule liste de reclassement restante, et elle reste nécessaire :
  la sévérité propre à `InspectionIssue` décrit l'observation en elle-même
  (ex. `vml_image_not_supported` est `"warning"` au sens "j'ai vu une image
  VML", pas "je bloque"), pas la politique de blocage.
- Tests ajoutés dans `tests/test_editorial_builder.py` verrouillant que
  chacun des 5 codes porte `severity="error"` dès sa construction dans
  `build_editorial_document`, sans dépendre d'une promotion externe.

## Conséquences

- Une seule liste de reclassement subsiste dans tout le pipeline
  (`_NON_BLOCKING_INSPECTION_CODES`), au lieu de trois. Le risque identifié
  par l'audit — un nouveau code bloquant émis dans `editorial/builder.py`
  sans mise à jour d'une liste séparée dans `tei/conversion.py` — est éliminé
  pour les diagnostics éditoriaux : la sévérité colocalisée avec l'émission
  du code fait foi directement.
- Le risque symétrique reste possible côté inspection dans l'autre sens : un
  nouveau code ajouté à `_NON_BLOCKING_INSPECTION_CODES` par erreur
  désactiverait un blocage voulu. C'est un risque plus visible (ajout
  explicite à une courte liste positive) que l'ancien (omission silencieuse
  dans une longue liste de ~90 entrées), et il correspond au comportement
  déjà en vigueur avant cette décision — aucune régression introduite.
- Suite de tests exécutée en totalité après chaque étape du refactor
  (`pytest -q`, 404 passed / 2 skipped) : aucune régression observée, ce qui
  confirme que les 5 promotions identifiées couvraient l'intégralité de
  l'écart entre sévérité déclarée et comportement réel.

## Limites assumées

- Cette décision ne touche pas à l'asymétrie de conception entre les deux
  chemins (inspection : fail-closed par défaut ; éditorial : sévérité
  déclarée fait foi). Les unifier complètement (par exemple en généralisant
  le fail-closed par défaut aux diagnostics éditoriaux) changerait le
  comportement pour les codes actuellement non bloquants par défaut
  (`empty_heading`, `heading_level_jump`, `tab_in_editorial_content`, etc.)
  et sortait du périmètre de cette passe, volontairement limitée à
  supprimer les listes dupliquées sans changer aucun résultat de
  conversion observable.
