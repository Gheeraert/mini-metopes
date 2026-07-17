# Listes Word natives v0.2

Mini-Métopes convertit les listes Word dont la numérotation directe est
résolue : listes ordonnées (`decimal`, lettres, chiffres romains et formats
natifs reconnus) et listes à puces textuelles. L'imbrication suit le niveau
OOXML `ilvl` : un niveau de plus devient une sous-liste du dernier item.

Un paragraphe ordinaire interrompt une liste. Un changement de `numId` ou de
format au même niveau crée une nouvelle liste. En revanche, reprendre le même
`numId` après une interruption non numérotée n'est pas assimilé à une nouvelle
liste : la conversion est refusée tant que Mini-Métopes ne calcule pas les
compteurs effectifs Word. Une liste qui commence au niveau 1 ou 2 est conservée
comme liste racine, avec un avertissement ; Mini-Métopes n'invente pas de parent
vide. Un saut de niveau, par exemple 0 vers 2, est refusé.

Le départ effectif Word (`start` ou `startOverride`) est conservé dans le TEI
par `list/@n` pour les listes ordonnées. Les marqueurs visibles Word ne sont
pas recopiés dans le texte des items.

Ne sont pas encore publiables : `numId=0` n'est pas une liste et reste un
paragraphe ; numérotation portée seulement par un style, puces illustrées,
listes sans marqueur, numérotation légale, listes ambiguës et cases à cocher.
Tout `lvlRestart` explicite est également refusé, y compris `lvlRestart=0`, car
il modifie les règles de redémarrage des compteurs Word. Les mêmes règles
s'appliquent dans les notes de bas de page et de fin. Le résumé `model-docx`
compte les listes récursivement, y compris les sous-listes et les listes des
notes.
