# Listes Word natives v0.1

Mini-Metopes observe la numerotation native Word a partir de `numPr`, `numId`
et `ilvl`, puis la relie a `num` et `abstractNum` dans `numbering.xml`.

La convention distingue l'observation brute et la resolution effective. Les
niveaux `NumberingLevelInfo` gardent les valeurs presentes dans l'OOXML. Les
paragraphes resolus appliquent les defauts WordprocessingML : format `decimal`
si `numFmt` est absent, depart `0` si `start` est absent, suffixe `tab` si
`suff` est absent.

Les identifiants `abstractNumId` et `numId` doivent etre des entiers decimaux
non negatifs. Les formes `1` et `01` sont numeriquement ambiguës et signalees
comme doublons. Les niveaux natifs Word acceptes vont de `0` a `8`. Une valeur
absente et une valeur invalide ne sont pas equivalentes : un niveau absent peut
etre suppose `0` lorsque le niveau 0 existe ; un niveau invalide bloque la
resolution.

Les formats `decimal`, `decimalZero`, lettres, chiffres romains et certains
formats ordinaux sont classes comme ordonnes ; `bullet` est une puce ; `none`
est une numerotation sans marqueur. Les surcharges de niveau et de depart sont
conservees. Les puces illustrees (`numPicBullet`, `lvlPicBulletId`) sont
signalees et ne sont pas assimilees a des puces textuelles.

`numId="0"` desactive explicitement une numerotation et le paragraphe reste
ordinaire. La meme regle s'applique quand cette suppression est portee par un
style : elle annule la numerotation heritee d'un parent `basedOn`.

Le style natif `ListParagraph` est reconnu. Sans numerotation observable, il
reste un paragraphe et produit un avertissement contextualise avec la partie
OOXML, l'index local et, dans les notes, l'identifiant de note. Une numerotation
active heritee d'un style est signalee mais n'est pas encore resolue.

Les listes presentes dans les notes de bas de page et les notes de fin sont
inspectees comme celles du corps. Le resume `inspect-docx` compte le total des
paragraphes numerotes actifs dans ces trois parties, sans compter les
paragraphes ou styles portant `numId="0"`.

Les listes ne sont pas encore converties en TEI : toute liste active bloque
encore `convert-docx`, afin d'eviter une perte structurelle. La passe 8B
traitera le regroupement des elements et l'imbrication editoriale.
