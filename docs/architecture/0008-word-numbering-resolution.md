# 0008 - Resolution de la numerotation Word

## Decision

La couche `mini_metopes.docx` lit `word/numbering.xml` dans un modele
immuable : definitions `abstractNum`, instances `num`, niveaux `lvl` et
surcharges `lvlOverride` / `startOverride`. Chaque paragraphe garde son
observation brute (`numbering_id`, `numbering_level`) et porte une resolution
effective distincte.

`NumberingLevelInfo` conserve les valeurs OOXML brutes observees. En revanche,
`ParagraphNumberingInfo` expose les valeurs effectives applicables au
paragraphe. Les defauts WordprocessingML sont donc appliques seulement lors de
la resolution : `numFmt` absent vaut `decimal`, `start` absent vaut `0`, et
`suff` absent vaut `tab`.

Ces defauts ne s'appliquent qu'a un element reellement absent. Un element
present sans attribut `w:val`, par exemple `<w:numFmt/>`, `<w:suff/>`,
`<w:start/>`, `<w:startOverride/>` ou `<w:lvlRestart/>`, est une valeur OOXML
incomplete. Elle produit un diagnostic et rend la resolution du paragraphe
concerne non resolue, au lieu d'etre assimilee a la valeur par defaut.

`numPr` direct est prioritaire. `numId="0"` signifie que la numerotation est
supprimee : ce n'est pas une liste active. Cette suppression est egalement
respectee lorsqu'elle est portee par un style et annule alors une eventuelle
numerotation heritee d'un parent `basedOn`. Les numerotations actives provenant
d'un style, y compris via `basedOn`, sont observees mais non resolues ; elles
sont signalees conservatoirement. Les cycles `basedOn` sont diagnostiques.

Les identifiants de numerotation doivent etre des entiers decimaux non
negatifs. Cette regle vaut aussi pour les identifiants obligatoires des
definitions `abstractNum/@abstractNumId` et `num/@numId` : s'ils sont absents ou
invalides, l'element est ignore apres diagnostic et aucune definition partielle
n'est enregistree. Ils restent stockes comme chaines dans le modele public,
mais les recherches, les doublons et l'ordre deterministe utilisent leur valeur
numerique canonique. Ainsi `1` et `01` ne creent pas deux definitions
concurrentes. Les niveaux Word natifs acceptes vont de `0` a `8`.

La lecture distingue un element absent, un element present sans `w:val` et une
valeur invalide. Un `ilvl` absent peut etre remplace par le niveau `0` lorsque
celui-ci existe, avec `missing_numbering_level_assumed_zero`. En revanche,
`<w:ilvl/>`, `ilvl="abc"` ou `ilvl="9"` produit `invalid_numbering_level` et ne
declenche jamais cette hypothese.

## Consequences

Les formats usuels sont classes en `ordered`, `bulleted`, `none` ou
`unsupported`. Les puces illustrees restent non prises en charge. La meme
resolution est appliquee au document, aux notes de bas de page et aux notes de
fin, avec la partie OOXML, l'index local du paragraphe et l'identifiant de note
dans les diagnostics.

Le resume `inspect-docx` compte les numerotations actives du corps, des notes de
bas de page et des notes de fin ; `numId="0"` en est toujours exclu.

Cette passe n'introduit ni `EditorialList`, ni regroupement de listes, ni
element TEI `<list>`. La conversion TEI refuse donc toujours toute numerotation
active, mais le diagnostic contient `numId`, niveau, genre et format effectif
observes. L'avertissement `missing_numbering_level_assumed_zero` est non
bloquant en lui-meme : dans cette passe, c'est la liste active qui bloque encore
la serialisation TEI.
