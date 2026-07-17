# 0009 — Listes Word résolues vers le modèle éditorial

## Décision

La résolution de `word/numbering.xml` reste dans `mini_metopes.docx`. La
couche `mini_metopes.editorial` transforme seulement les paragraphes dont la
numérotation directe est résolue de manière sûre en `EditorialList` et
`EditorialListItem`. La couche `mini_metopes.tei` sérialise cet arbre sans
relire `numId` ni `ilvl`.

## Reconstruction

Une liste porte son type (`ordered` ou `bulleted`), son format effectif Word,
son départ, son `numId`, son niveau source et les propriétés de niveau utiles
au diagnostic. Sa signature est `(numId, ilvl, type, numFmt, start,
lvlRestart)`. Une nouvelle signature au même niveau crée une liste sœur.
`numId` est l'identité d'une instance Word, et non une simple apparence : si la
même instance reprend après un paragraphe non numéroté, Mini-Métopes refuse la
conversion avec `interrupted_list_continuation_not_serializable` tant que les
compteurs effectifs Word ne sont pas calculés.

Une montée d'un niveau crée une liste enfant du dernier item. Une descente
referme les listes actives. Une séquence peut commencer à un niveau différent
de zéro : ce niveau reste sa racine locale et déclenche
`list_root_level_normalized`. Une baisse sous cette racine scinde la séquence.
Un saut de plus d'un niveau est ambigu et bloque la conversion avec
`list_level_jump_not_serializable` : aucun parent vide n'est inventé.

## TEI

`EditorialList` devient `<list>`, avec `@type="bulleted"` pour les puces et
`@type` égal au `numFmt` Word pour les listes ordonnées. La convention de cette
passe emploie `list/@n` pour conserver le départ effectif d'une liste ordonnée,
y compris zéro. Un item devient `<item>` ; ses listes enfants sont ajoutées
après son flux inline, sans `<p>` artificiel.

Cette forme est validée par le RNG Commons Publishing embarqué : `list` attend
un ou plusieurs `item`, et `item` accepte le contenu mixte et les listes
imbriquées.

## Limites et refus

Restent refusés : numérotation par style, niveau irrésolu, `numFmt="none"`,
format inconnu, puce illustrée, numérotation légale, saut de niveau ambigu,
reprise d'une même instance après interruption, item vide et rôle éditorial
autre qu'un paragraphe. `levelText`, `suffix` et `lvlRestart` sont conservés
dans le modèle ; ils ne sont pas reproduits comme marqueurs visibles. Tout
`lvlRestart` explicite, y compris `lvlRestart=0` qui signifie que le niveau ne
redémarre jamais, bloque avec `explicit_list_restart_not_serializable`.

Les listes dans les notes suivent exactement le même modèle, mais restent dans
les blocs de leur note. Les continuations non numérotées, listes de définitions,
cases à cocher et calcul intégral des marqueurs Word restent hors périmètre.
Le résumé humain de `model-docx` compte récursivement les listes du corps, les
sous-listes et les listes présentes dans les notes.
