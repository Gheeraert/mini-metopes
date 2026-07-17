# Listes Word natives v0.1

Mini-Métopes observe la numérotation native Word à partir de `numPr`, `numId`
et `ilvl`, puis la relie à `num` et `abstractNum` dans `numbering.xml`.

Les formats `decimal`, `decimalZero`, lettres, chiffres romains et certains
formats ordinaux sont classés comme ordonnés ; `bullet` est une puce ; `none`
est une numérotation sans marqueur. Les surcharges de niveau et de départ sont
conservées. `numId="0"` désactive explicitement une numérotation et le
paragraphe reste ordinaire.

Le style natif `ListParagraph` est reconnu. Sans numérotation observable, il
reste un paragraphe et produit un avertissement. Une numérotation héritée d'un
style est signalée mais n'est pas encore résolue. Les puces illustrées sont
signalées et ne sont pas assimilées à des puces textuelles.

Les listes ne sont pas encore converties en TEI : toute liste active bloque
encore `convert-docx`, afin d'éviter une perte structurelle. La passe 8B
traitera le regroupement des éléments et l'imbrication éditoriale.
