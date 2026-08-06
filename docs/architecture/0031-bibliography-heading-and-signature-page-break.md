# 0031 — Titre de bibliographie rattaché et sauts de page en fin de signature

## Contexte

Suite directe de la décision 0030 : le même manuscrit réel a révélé que le
correctif initial (bibliographie native sans `<head>`, ligne `Signature`
vide ignorée) ne suffisait pas à couvrir deux situations réelles
supplémentaires, clarifiées par l'utilisateur :

1. **La bibliographie précédée d'un titre de section n'est pas ambiguë.**
   Un titre `Titre1`/`Heading1` (« Bibliographie ») directement au-dessus
   d'un bloc `Bibliography` natif désigne sans ambiguïté la bibliographie
   générale du livre : « il n'y a donc pas d'ambiguïté » (confirmation
   explicite). Le principe « la signature reste à la toute fin » de la
   décision 0028 est conservé, mais doit s'entendre par rapport au corps de
   la contribution, pas par rapport à la bibliographie générale du livre
   qui la suit légitimement.
2. **Un saut de page manuel peut atterrir sur un paragraphe `Signature`
   vide.** Le style intégré `Signature` s'auto-continue (son « style
   suivant » est lui-même) ; un saut de page forcé avant la section
   suivante peut donc se retrouver seul sur un paragraphe stylé
   `Signature`, sans texte.

## Décision

### 1. Titre de bibliographie rattaché (`editorial/builder.py`)

Quand la bibliographie est déclenchée par le seul style natif
`Bibliography` (pas de `TEIbiblstart`), `_extract_final_bibliography`
cherche désormais un titre immédiatement avant le premier paragraphe
`Bibliography` (`_preceding_heading_index`, paragraphes vides ignorés
entre les deux). S'il trouve un titre, il devient le `<head>` de la
bibliographie et est retiré du corps principal — ce qui rend, en
conséquence naturelle, la signature de la contribution qui précède
effectivement terminale par rapport à ce qui reste du corps. Aucune
tolérance ajoutée à la règle de la décision 0028 elle-même : la position
« terminale » est simplement recalculée après que le titre de
bibliographie a été correctement rattaché à la bibliographie plutôt que
laissé comme contenu de corps orphelin.

Si aucun titre ne précède immédiatement (autre contenu interposé), le
comportement précédent (bibliographie sans titre) reste inchangé — pas de
rattachement hasardeux.

### 2. Saut de page isolé en fin de bloc `Signature` (`editorial/builder.py`)

Nouvelle fonction `_is_signature_run_filler`, utilisée **uniquement** dans
le contexte étroit de la suite terminale de paragraphes `Signature` : un
paragraphe sans texte ni note/lien/dessin/signet/numérotation/tabulation,
**y compris s'il contient un saut de page ou de colonne isolé**, est traité
comme un artefact de continuation de style — ignoré, ne compte pas dans la
limite de deux lignes, ne disqualifie pas la position terminale.

Distincte de `is_semantically_empty_paragraph` (utilisée partout ailleurs
dans le code), qui continue de traiter un saut de page comme un contenu
significatif ne devant jamais être ignoré silencieusement — principe du
projet préservé en dehors de ce contexte précis. Le saut de page lui-même
n'est jamais sérialisé ; seul son support (le paragraphe `Signature` vide
qui le porte) est traité comme du bruit dans ce périmètre restreint.

## Conséquences

- Le manuscrit réel (corps → Signature → « Bibliographie » → entrées, avec
  saut de page en fin de bloc `Signature`) se convertit désormais sans
  erreur `misplaced_signature_not_serializable`.
- 468 passed après ajout. Tests dédiés : signature suivie d'un titre de
  bibliographie native (`test_signature_followed_by_a_native_bibliography_heading_is_accepted`),
  saut de page isolé en fin de bloc (`test_trailing_page_break_only_signature_paragraph_does_not_count`).

## Limites assumées

- Le rattachement du titre ne fonctionne que pour le déclenchement natif
  (sans `TEIbiblstart`) : une bibliographie à style contrôlé garde son
  titre porté par le paragraphe `TEIbiblstart` lui-même, comportement
  inchangé.
- Le filtre `_is_signature_run_filler` reste strictement local à la
  détection de fin de bloc `Signature` ; aucun changement de
  `is_semantically_empty_paragraph` ni de la politique générale sur les
  sauts de page ailleurs dans le corps.
