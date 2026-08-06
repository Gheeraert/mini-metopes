# 0035 — Saut de page apres une signature accepte, quel que soit son style

## Contexte

Signale par l'utilisateur : « les sauts de page après signature bloquent
la génération du XML ». Investigation : deux problemes distincts se
combinaient.

1. `_signature_run_is_terminal` (decision 0032) ne reconnaissait la
   position terminale d'une signature que si le paragraphe qui suit
   immediatement le bloc `Signature` est soit la fin du document, soit un
   titre de niveau 1 a 3. Un saut de page manuel qui atterrit sur un
   paragraphe qui **ne porte plus le style `Signature`** (style suivant
   change par l'auteur, ou simplement un autre style par defaut) n'etait
   ni l'un ni l'autre : `misplaced_signature_not_serializable`.
2. Meme apres correction du point 1, le paragraphe porteur du saut de
   page restait un bloc `Paragraph` ordinaire envoye a la serialisation —
   or `tei/serializer.py` refuse **categoriquement** tout `PageBreak` /
   `ColumnBreak` rencontre en dehors du contexte etroit deja exclu par la
   decision 0031 (`break_not_serializable`, toujours une erreur, jamais
   silencieux). Sans traitement specifique, le document restait bloque
   meme apres la premiere correction.

## Decision

### 1. Terminalite : sauter les paragraphes de bordure sans contenu reel, quel que soit leur style

`_signature_run_is_terminal` (`editorial/builder.py`) avance desormais
au-dela de tout paragraphe verifiant `_is_signature_run_filler` (texte
vide, aucune note/lien/dessin/signet/numerotation/tabulation — saut de
page ou de colonne isole inclus) **avant** de verifier si la position est
terminale (fin de document ou titre de niveau 1 a 3). Contrairement a la
decision 0031, `_is_signature_run_filler` ne verifie pas le style du
paragraphe : elle s'applique ici a n'importe quel paragraphe de bordure,
pas seulement a ceux encore styles `Signature`.

### 2. Consommation : ne jamais laisser un saut de page atteindre la serialisation

Une fois la signature validee comme terminale, le dernier paragraphe du
bloc `Signature` consomme aussi, immediatement apres lui, tout paragraphe
de bordure sans contenu reel qui a permis cette reconnaissance —
diagnostic `empty_paragraph_ignored` (info, non bloquant), exactement le
meme traitement que la decision 0031 applique deja aux paragraphes
`Signature` vides. Ces paragraphes ne deviennent jamais des blocs `Paragraph`
et n'atteignent donc jamais `_append_inline`, qui les aurait
systematiquement refuses (`break_not_serializable`).

## Portee

Le perimetre reste strictement le meme qu'en 0031 : uniquement les
paragraphes de bordure **immediatement adjacents a la fin d'un bloc
`Signature` valide**. `is_semantically_empty_paragraph` (utilisee partout
ailleurs dans le corps) n'est pas modifiee : un saut de page en dehors de
ce contexte precis reste un contenu significatif, jamais ignore
silencieusement, et continue de produire `break_not_serializable` s'il
atteint la serialisation.

## Consequences

- 480 passed apres ajout. Tests dedies :
  `test_trailing_page_break_on_a_normal_paragraph_after_signature_is_accepted`,
  `test_page_break_on_a_normal_paragraph_before_the_next_contribution_is_accepted`,
  `test_page_break_after_signature_no_longer_blocks_tei_generation`
  (reproduction directe du bug signale, bout-en-bout via
  `convert_docx_to_tei`) — `tests/test_editorial_signatures.py`.

## Limites assumees

- Ne couvre que la position immediatement apres un bloc `Signature`
  valide. Un saut de page ailleurs dans le corps continue de bloquer la
  conversion (`break_not_serializable`) : ce comportement general n'est
  pas remis en cause par cette decision.
