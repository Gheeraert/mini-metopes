# 0026 — Style natif Word `Bibliography`

## Contexte

La bibliographie finale ne pouvait être déclenchée que par le style
personnalisé contrôlé `TEIbiblstart`, avec des entrées `TEIbiblreference` —
deux styles qui n'existent pas dans la galerie native de Word, à l'inverse
de l'orientation générale du projet (limiter au maximum le recours à des
styles personnalisés). Or Word a un style intégré natif **`Bibliography`**
(généré par son gestionnaire de citations, mais utilisable librement comme
n'importe quel style), confirmé dans `references/Word Styles Chart.xlsm`
(styleId anglais invariant, basé sur `Normal`, type paragraphe).

Contrainte réelle : Word n'a **pas** de style de « début de bibliographie »
séparé du style des entrées — contrairement à la convention
`TEIbiblstart`/`TEIbiblreference`. Un titre « Bibliographie » généré par
Word est un simple paragraphe de titre ordinaire (souvent `Heading1`), pas
un style dédié.

## Décision

- `editorial/convention.py` : nouveau `native_bibliography_style_ids`
  (`{"Bibliography"}`) et `is_native_bibliography_reference_style` —
  reconnu **sans** exiger `w:customStyle`, à la différence de tous les
  autres styles contrôlés `TEI_*`. `is_bibliographic_reference_style`
  accepte désormais ce style nativement en plus de `TEIbiblreference`
  contrôlé : un paragraphe `Bibliography` se comporte identiquement à
  `TEIbiblreference` partout où c'est pertinent (référence autonome, source
  immédiate d'une citation, entrée de bibliographie terminale).
- `editorial/builder.py` (`_extract_final_bibliography`) : deux
  déclencheurs mutuellement exclusifs, `TEIbiblstart` restant prioritaire
  s'il est présent (compatibilité totale avec l'existant). En son absence,
  le **premier** paragraphe `Bibliography` rencontré déclenche lui-même la
  bibliographie terminale — sans titre, puisque Word n'a rien à offrir ici.
  Boucle de collecte des entrées factorisée dans
  `_collect_bibliography_entries` pour éviter de dupliquer la logique entre
  les deux chemins.
- `editorial/model.py` / `tei/serializer.py` : `EditorialBibliography` gagne
  `title_required: bool = True` (par défaut, comportement inchangé pour
  `TEIbiblstart`). Le chemin natif le pose à `False` : le sérialiseur omet
  `<head>` (vérifié optionnel dans le schéma, `div`/`listBibl`) au lieu de
  refuser la conversion pour titre vide — l'ancien contrôle
  `empty_bibliography_title_not_serializable` continue de s'appliquer
  normalement quand un titre était attendu (`TEIbiblstart` vide, toujours
  une erreur d'auteur).

## Conséquences

- Une bibliographie entièrement composée avec le style natif `Bibliography`
  se convertit sans aucun style personnalisé, sous forme
  `back/div[@type='bibliography']/listBibl/bibl` sans `<head>`.
- Toutes les règles déjà établies restent valables sans duplication :
  bibliographie unique et terminale (tout contenu après reste refusé,
  `nonterminal_bibliography_not_serializable`), entrées vides/numérotées/
  avec image refusées, etc. — la factorisation par
  `_collect_bibliography_entries` garantit qu'aucune règle n'a été oubliée
  pour le nouveau chemin.
- 441 passed après ajout. Tests dédiés vérifiant : déclenchement sans
  `TEIbiblstart`, sérialisation sans `<head>`, et la règle « unique et
  terminale » appliquée identiquement au chemin natif.

## Limites assumées

- Un titre de bibliographie explicite (« Bibliographie », « Ouvrages
  cités »…) au-dessus d'un bloc `Bibliography` natif n'est pas récupéré
  automatiquement comme `<head>` : il resterait un paragraphe ordinaire
  précédent dans le corps (Heading ou Normal), non rattaché structurellement
  à la bibliographie. Un rattachement automatique (« le titre le plus
  proche avant le premier `Bibliography` devient `<head>` ») a été envisagé
  mais écarté pour cette passe : risque de rattacher à tort un titre de
  section non destiné à la bibliographie. Prolongement futur possible si le
  besoin se confirme sur des documents réels.
- Le style `TEIbiblreference-inline` (citation inline) reste un style de
  caractère contrôlé sans équivalent natif Word identifié — non couvert par
  cette décision.
