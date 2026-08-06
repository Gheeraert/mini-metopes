# 0027 — Épigraphe via le style natif Word `Salutation`

## Contexte

Aucune épigraphe n'était reconnue : un paragraphe d'épigraphe stylé
`Quote` devenait une citation ordinaire (`<cit>`), sémantiquement fausse
(une épigraphe n'est pas une citation argumentative au fil du texte), et
stylé `Normal` il se perdait dans le corps sans distinction.

Vérification avant décision : `<epigraph>` existe dans le schéma Commons
Publishing embarqué, membre de `model.divWrapper` — autorisé en tête de
`<div>` (mélangé librement avec `<head>`) et en fin de division. Contenu
accepté : `model.common` (dont `model.pLike`, donc `<p>`), suffisant pour
une épigraphe (citation + attribution sur plusieurs paragraphes). Le style
natif Word **`Salutation`** (galerie « Letters », confirmé dans
`references/Word Styles Chart.xlsm`, styleId anglais invariant, basé sur
`Normal`) a été retenu par décision explicite de l'utilisateur.

## Décision

- `editorial/convention.py` : `epigraph_style_ids` (`{"Salutation"}`),
  nouveau `ParagraphRoleKind` `"epigraph"`.
- `editorial/model.py` : `Epigraph(paragraphs: tuple[EpigraphParagraph, ...])`,
  ajouté à `EditorialBlock`.
- `editorial/builder.py` : une suite contigüe de paragraphes `Salutation`
  devient un unique bloc `Epigraph` (même schéma de collecte que
  `ProseQuote`/`VerseQuote` : premier paragraphe déclenche, les suivants de
  même rôle sont absorbés tant qu'ils se succèdent).
- **Contrainte de position, volontairement stricte** : un `Epigraph` n'est
  reconnu que s'il suit **immédiatement** un `Heading`, ou s'il ouvre le
  document (aucun bloc précédent). Ailleurs dans le flux, ou à l'intérieur
  d'une note, il est refusé (`misplaced_epigraph_not_serializable`,
  bloquant) plutôt que silencieusement absorbé comme paragraphe ordinaire —
  cohérent avec le principe « refuser plutôt que produire une TEI
  trompeuse ». Seule la position immédiatement après le titre est
  couverte dans cette passe (voir Limites).
- `tei/serializer.py` : sérialisé comme `<epigraph><p>…</p>…</epigraph>`,
  positionné en XML naturellement entre `<head>` et le reste du contenu de
  la division, sans logique de placement dédiée — l'ordre du flux
  éditorial (garanti par la contrainte de position ci-dessus) suffit.

## Conséquences

- Une épigraphe en tête de chapitre/section est désormais représentée
  fidèlement, sans dialecte TEI local.
- 448 passed après ajout. Tests dédiés
  (`tests/test_editorial_epigraphs.py`) : paragraphe unique, plusieurs
  paragraphes consécutifs, épigraphe liminaire sans titre précédent,
  position invalide (milieu de section, intérieur d'une note), sérialisation
  TEI complète avec validation RNG, paragraphe vide refusé.

## Limites assumées

- Seule la position **en tête** de section est reconnue (`model.divTop`).
  Une épigraphe de fin de division (`model.divBottom`, ex. un post-scriptum
  épigraphique) n'est pas couverte — prolongement futur explicite si le
  besoin se confirme, pas un oubli.
- Aucune table de noms localisés n'a été ajoutée pour `Salutation` (pas de
  nom français vérifié à ce jour, contrairement à la prudence déjà établie
  par la décision 0020) : seul le styleId anglais invariant est reconnu,
  ce qui couvre déjà les installations Word françaises puisque `w:styleId`
  ne se localise pas pour les styles intégrés.
