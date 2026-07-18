# Document D — cas invalides ou limites

Chaque sous-dossier documente un refus (ou une limite explicite) du
convertisseur. Aucun de ces cas ne doit produire silencieusement une TEI
dégradée.

- `unknown-custom-style` — un paragraphe porte le style personnalisé
  `TEI_quote` du modèle Métopes. Diagnostic bloquant
  `unsupported_paragraph_style`, aucune TEI. Ce cas fixe le périmètre voulu :
  les styles Word Métopes ne sont pas une entrée de Mini-Métopes.
- `heading-level-jump` — saut de `Titre 1` à `Titre 4`. Aujourd'hui
  diagnostic **non bloquant** `heading_level_jump` (info) : la TEI est
  produite avec la hiérarchie observée. Durcir ce comportement serait un
  changement de contrat à valider humainement.
- `discontinuous-list` — réouverture d'une même instance de liste Word après
  interruption. Diagnostic bloquant
  `interrupted_list_continuation_not_serializable`, aucune TEI.
- `textbox` — zone de texte Word. Diagnostic bloquant
  `textboxes_not_inspected`, aucune TEI.
- `malformed-package` — le fichier n'est pas une archive ZIP. L'inspection
  lève `DocxInspectionError` avec le code stable `not_zip`
  (`expected-diagnostics.json` enregistre `inspection_error`).
