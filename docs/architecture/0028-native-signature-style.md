# 0028 — Signature d'auteur via le style natif Word `Signature`

## Contexte

Rien ne permettait de repérer ni de valider la signature d'un article/
chapitre (nom de l'auteur·rice, institution de rattachement) : information
disponible en pratique dans le corps du DOCX (souvent en fin de texte) mais
jamais reliée à `metadata.json/contributors`, qui reste pourtant la source
d'autorité pour le `teiHeader`.

Décision explicite de l'utilisateur sur la méthodologie de rédaction :

1. Le style natif Word **`Signature`** (galerie « Letters », confirmé dans
   `references/Word Styles Chart.xlsm`, styleId anglais invariant, next
   style `Signature` — Word encourage déjà l'enchaînement de plusieurs
   lignes du même style, cohérent avec l'usage prévu) marque la signature.
2. Premier paragraphe `Signature` = prénom et nom ; second = institution de
   rattachement.
3. La signature est systématiquement en fin d'article/chapitre.
4. Le titre du chapitre doit être associé aux éléments de la signature dans
   les métadonnées — implémenté comme un contrôle de cohérence contre
   `metadata.json/contributors`, symétrique au mécanisme déjà existant pour
   `Title`/`Subtitle`.

**Point de vérification qui a changé le apercu initial** : l'attribut
`@rend` de `<p>` dans le schéma Commons Publishing embarqué a une liste
**fermée** (`break`, `consecutive`, `caption`, `credits` — pas de valeur
libre). `<p rend="signature">` envisagé initialement n'aurait pas validé.
Après consultation, décision retenue : `<p>` simple, sans `@rend`.

## Décision

- `editorial/convention.py` : `signature_style_ids` (`{"Signature"}`),
  nouveau `ParagraphRoleKind` `"signature"`.
- `editorial/builder.py` : reconnu **uniquement** en suite terminale d'au
  plus deux paragraphes `Signature` consécutifs, en fin du flux principal
  (jamais dans une note). Ailleurs, ou au-delà de deux lignes,
  `misplaced_signature_not_serializable` (bloquant) — même politique de
  refus conservateur qu'Épigraphe (décision 0027). Une ligne vide est
  un avertissement non bloquant (`empty_signature_paragraph`), pas une
  erreur : les deux positions restent structurellement valides. Chaque
  ligne devient un `Paragraph` ordinaire (`rendition=None`) — visible dans
  le corps TEI comme `<p>` simple, sans marquage distinctif (contrainte du
  schéma).
- `metadata/model.py` : `MetadataSuggestions` gagne `signature_name`/
  `signature_affiliation`, jamais consommés (contrairement à
  `consumed_paragraph_indexes` pour `Title`/`Subtitle` : la signature reste
  du contenu éditorial visible, pas une donnée purement extraite).
- `metadata/extraction.py` : lit la suite terminale de paragraphes
  `Signature` (indépendamment de `editorial/builder.py` — même principe
  déjà établi pour `Title`/`Subtitle`, simple lecture de paragraphes bruts,
  pas de dépendance à la convention éditoriale complète). Une suite de plus
  de deux lignes n'est pas résumée ici (ambiguë) ; seule la conversion la
  refuse explicitement.
- `metadata/merge.py` (`metadata_consistency_issues`) : si une signature est
  détectée, compare le nom (normalisé casse/espaces) à chaque contributeur
  déclaré (`literal_name` ou `prénom nom`) ; absence de correspondance →
  `signature_contributor_not_in_metadata` (avertissement, jamais bloquant —
  cohérent avec `metadata_title_differs_from_docx`). Déjà exposé sans
  changement via `validate-metadata --source` (CLI existante).

## Conséquences

- Une signature bien formée devient un contenu TEI visible fidèle à la
  saisie, tout en étant vérifiée contre les métadonnées déclarées.
- 458 passed après ajout. Tests dédiés
  (`tests/test_editorial_signatures.py`) : une ligne, deux lignes dans
  l'ordre, position invalide (milieu de texte, intérieur d'une note), plus
  de deux lignes, sérialisation sans `@rend`, extraction sans consommation,
  contrôle de cohérence (avertissement et silence selon correspondance).

## Limites assumées

- La comparaison nom-signature/contributeur est une égalité normalisée
  simple (casse, espaces) — pas de tolérance aux variantes (« C. Dubuisson »
  vs « Claire Dubuisson »), pas de correspondance approximative. Un faux
  positif reste un avertissement, jamais bloquant.
- L'institution (second paragraphe) n'est comparée à rien dans les
  métadonnées (`affiliations`) : seul le nom déclenche le contrôle de
  cohérence. Extension possible si le besoin se confirme.
- Comme pour Épigraphe, aucun nom localisé français n'a été ajouté pour
  `Signature` : seul le styleId anglais invariant est reconnu (suffisant,
  puisque non localisé dans `w:styleId`).
