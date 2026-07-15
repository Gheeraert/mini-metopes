# 0003 — Flux inline OOXML structuré

## Décision

L'inspection OOXML expose les contenus de chaque run dans un flux immuable et
ordonné de `RunContentInfo`. Chaque entrée possède un discriminant `kind` :
`text`, `tab`, `break`, `footnote_reference`, `endnote_reference` ou `drawing`.
Les données utiles à chaque nature de contenu restent explicites : texte,
type de saut, identifiant de note ou relations d'un dessin.

`RunInfo.text` reste disponible comme vue de commodité. Il est construit à
partir de ce flux unique : les tabulations deviennent `\t`, les sauts de ligne
deviennent `\n`, les appels de note et dessins deviennent des marqueurs lisibles.
Les sauts de page et de colonne n'ajoutent aucun caractère. Ces marqueurs ne
sont jamais une source sémantique et ne devront pas être analysés pour une
future conversion.

## Raisons

Un texte aplati ne distingue pas un texte littéral tel que `[footnote:7]` d'un
véritable appel de note. Il perd également l'ordre fiable des objets inline.
Le flux typé permet au futur modèle éditorial de consommer directement les
faits OOXML, sans analyse de chaînes ni expressions régulières.

Les sauts sont conservés comme événements distincts : `line`, `page` et
`column`. Seul `line` alimente le compteur historique des sauts manuels. Cette
distinction protège en particulier la future reconstruction des vers.

Un run situé dans `w:hyperlink` conserve soit son identifiant de relation
externe (`r:id`), soit son ancre interne (`w:anchor`). La relation complète
reste stockée une seule fois au niveau du document.

Les notes ne sont plus seulement aplaties : chaque `NoteInfo` conserve ses
paragraphes, leurs runs et leurs contenus inline, avec des index locaux. Son
champ `text` est une vue de commodité construite à partir de ces paragraphes.

## Conséquences

- Les paragraphes du document principal et ceux des notes utilisent la même
  logique de lecture, tout en restant dans des séquences séparées.
- La sortie JSON contient le flux inline, les contextes d'hyperlien et les
  paragraphes structurés des notes ; elle reste déterministe et ne divulgue
  pas de chemin local absolu.
- La couche ne résout toujours pas la cascade complète de styles Word et ne
  décide aucune signification éditoriale.

## Limites assumées

Cette passe ne construit pas de modèle éditorial, ne définit pas de convention
Word vers TEI et ne produit aucun XML TEI. Les tableaux, champs complexes,
commentaires, équations, en-têtes, pieds de page et le contenu des zones de
texte restent hors périmètre.
