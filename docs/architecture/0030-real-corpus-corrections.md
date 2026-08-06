# 0030 — Corrections issues du premier test sur un manuscrit réel (B7)

## Contexte

Premier test de bout en bout sur un document réel
(`docs/reference/manuscrit_reel_input.docx`, hors dépôt — corpus personnel,
non versionné conformément à la politique `references/`/`docs/reference/`
en lecture seule). L'inspection (`inspect-docx`, `model-docx`,
`convert-docx`) a révélé deux bugs concrets dans les décisions 0026 et 0028,
et deux questions de conception tranchées par l'utilisateur en faveur de la
rigueur (corriger le manuscrit plutôt qu'étendre la convention).

## Bugs corrigés

### 1. Style natif `Bibliography` marqué `w:customStyle="1"` par Word (décision 0026)

`is_native_bibliography_reference_style` exigeait `style_is_custom is not
True`, en prévision d'une collision avec un style personnalisé sans
rapport. Le manuscrit réel montre que Word peut écrire
`w:customStyle="1"` sur `Bibliography` même appliqué tel quel depuis la
galerie de styles, sans jamais passer par le gestionnaire de citations —
l'hypothèse initiale ne correspondait pas au comportement réel de Word.
La garde est supprimée : seul le `styleId` (`Bibliography`) fait foi,
suffisamment spécifique pour ne pas risquer de collision fortuite.

### 2. Ligne `Signature` vide en fin de bloc (décision 0028)

Le manuscrit a trois paragraphes `Signature` consécutifs : nom,
institution, puis une ligne vide — artefact Word courant (le « style
suivant » de `Signature` est `Signature` lui-même ; une touche Entrée en
fin de bloc laisse un paragraphe vide du même style). L'ancienne règle
comptait cette ligne vide dans la limite de deux, rejetant tout le bloc.
`editorial/builder.py` traite désormais un paragraphe `Signature`
sémantiquement vide comme n'importe quel paragraphe vide ordinaire
(`empty_paragraph_ignored`, non bloquant), sans le compter ni le laisser
disqualifier la position terminale.

## Questions de conception tranchées (aucun changement de code)

- **Titre/Sous-titre sur plusieurs paragraphes consécutifs** (titre long
  scindé en deux `Titre`, ou « Textes réunis par » + noms des éditeurs sur
  deux `Sous-titre`) : règle inchangée, un seul paragraphe de chaque
  accepté dans le préambule. Le manuscrit doit être corrigé (fusion en un
  seul paragraphe, ou données déplacées vers `metadata.json`).
- **Signature suivie d'un titre de bibliographie** (`corps → Signature →
  Titre1 "Bibliographie" → entrées`) : règle inchangée, `Signature` doit
  rester l'élément terminal absolu. Le manuscrit doit être réordonné.

Ces deux points restent des limites assumées documentées, pas des bugs :
`convert-docx` les signale avec des diagnostics précis
(`multiple_docx_titles`/`multiple_docx_subtitles` + `deferred_paragraph_style`
pour le premier ; `misplaced_signature_not_serializable` pour le second),
jamais de perte silencieuse.

## Conséquences

- 466 passed après correction. Tests dédiés reproduisant précisément les
  deux artefacts réels : `test_native_bibliography_style_is_recognized_even_when_word_marks_it_custom`
  (`tests/test_bibliographic_references.py`),
  `test_trailing_empty_signature_paragraph_does_not_count_toward_the_limit`
  (`tests/test_editorial_signatures.py`).
- Confirme la valeur de tester contre un corpus réel plutôt que seulement
  des fixtures synthétiques construites à la main (§5.2 `AGENTS.md`) : les
  deux bugs corrigés ici reposent sur des comportements Word que la
  construction manuelle de fixtures n'aurait pas fait apparaître
  spontanément (hypothèses raisonnables mais fausses sur `customStyle` et
  sur l'absence d'artefacts de paragraphe vide liés au style suivant).
