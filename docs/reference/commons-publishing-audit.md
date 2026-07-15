# Audit de TEI Commons Publishing

## Source auditée et décision

L'archive fournie `references/normative/tei-commons-publishing.zip` contient un clone Git
de `https://git.unicaen.fr/fnso/i-fair-ir/tei-commons-publishing.git`. Son
commit courant est `f3143754c0aef940ef6846123de2cd2c23ecddf9` (25 février 2026,
branche `master`), décrit par Git comme `1.0.0-4-gf314375`. Le tag vérifié
`1.0.0` est l'ancêtre `3623d1c874f358a696426c0cf779198b93b5e1f4`.

La référence normative retenue est donc :

| Rôle | Fichier officiel |
| --- | --- |
| ODD noyau | `odd/commons-publishing.odd` |
| RNG embarqué | `rng/commons-publishing.rng` |
| XSD disponible, non utilisé à l'exécution | `xsd/commons-publishing.xsd` |

Le RNG copié dans le paquet a le SHA-256
`f87ddd5a2673fda9994e516653bd9dda185380620ebf4d1a52c2b980a3b5d979` et n'a subi
aucune modification locale. Sa trace exploitable figure dans
`src/mini_metopes/resources/schemas/commons-publishing/PROVENANCE.json`.

Le dépôt documente sa compilation depuis l'ODD avec `teitorelaxng`, TEI P5
`P5_Release_4.5.0` et TEI Stylesheets `v7.54.0`. Ces outils ne sont pas une
dépendance d'exécution de Mini-Métopes.

## Noyau, OpenEdition et Métopes

Le noyau est la cible de Mini-Métopes : il comporte les éléments communs aux
environnements éditoriaux et la documentation du dépôt le déclare compatible
avec Lodel 2 / OpenEdition Books.

`odd/commons-publishing-openedition.odd` est une ODD chaining du noyau. Dans
l'archive auditée, elle ne définit ni `elementSpec` ni `classSpec` propre ; elle
référence les modules du noyau pour produire le livrable
`rng/commons-publishing-openedition.rng`. La documentation précise que Lodel 1
reste couvert par le schéma externe `tei.openedition`, hors périmètre.

`odd/commons-publishing-metopes.odd` ajoute des choix spécifiques à Métopes :
notamment le module `msdescription`, MathML, XInclude, des attributs et contenus
contraints pour des éléments tels que `div`, `p`, `note`, `figure`, `hi`,
`bibl`, ainsi que des règles Schematron. Ce n'est pas la cible de ce projet.
Les XML Métopes du corpus sont donc des témoins de phénomènes éditoriaux, pas
une autorité normative.

## Citations et vers

Le RNG noyau accepte la forme testée :

```xml
<cit type="verse"><quote><lg><l>…</l></lg></quote><bibl>…</bibl></cit>
```

Deux `lg` frères dans le même `quote` sont également valides. Le type `verse`
est cependant un attribut typé générique : le RNG ne contraint pas à lui seul la
relation sémantique entre ce type et `lg`. En particulier, un `l` directement
dans `quote` est Relax NG valide. La future règle qui imposera une strophe pour
une citation poétique sera donc un diagnostic éditorial explicite, pas une
affirmation erronée sur le RNG.

## Licence et redistribution

`LICENSE-FR` et `LICENSE-EN` du dépôt déclarent la licence CeCILL-B ; la
documentation (`docs/source/license.rst`) l'associe explicitement au schéma.
La licence autorise la redistribution non modifiée sous réserve de l'accompagner
du texte de licence. Le paquet inclut donc la copie officielle anglaise complète
(`LICENSE.txt`) ; le dépôt d'origine indique que les versions française et
anglaise sont toutes deux authentiques. La provenance conserve le dépôt et le
commit source. Aucun autre composant du dépôt Commons Publishing n'est copié.

## Relax NG et Schematron

Le RNG embarqué contient des fragments Schematron (au moins 7 `sch:assert` et 9
`sch:report`, ainsi que leurs règles et motifs). `lxml.RelaxNG` compile et
exécute la grammaire Relax NG via libxml2, avec des erreurs de ligne/colonne
lorsqu'elles sont fournies ; il ne transforme ni n'exécute les règles
Schematron incorporées comme annotations. La CLI ne prétend donc jamais offrir
une validation Schematron complète.

Les TEI Stylesheets et Saxon pourront ultérieurement servir à régénérer le RNG,
à extraire/contrôler des règles Schematron et à comparer une nouvelle version,
dans une chaîne de maintenance ou CI isolée de l'application.
