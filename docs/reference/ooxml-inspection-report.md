# Rapport d'inspection OOXML — corpus réel

## Méthode et précautions

Les trois DOCX ont été extraits individuellement, en lecture seule, depuis les
archives de `references/corpora/` vers des fichiers temporaires. Ils n'ont pas
été recopiés dans le dépôt. Les résultats ci-dessous proviennent de l'API
`mini_metopes.docx.inspect_docx_file` et ne reproduisent aucun passage des
ouvrages.

Les nombres de runs, de paragraphes et de retours manuels décrivent les
structures OOXML présentes, non une convention de conversion future.

| Document | Paragraphes | Runs | Notes de bas de page / fin | Retours manuels | Paragraphes numérotés | Liens | Signets | Dessins / médias |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `coeur_seul.zip:styles/ch_003_chap_1.docx` | 60 | 1 051 | 46 / 0 | 0 | 0 | 0 | 0 | 0 / 0 |
| `dissimuler.zip:travail_xml/styles/chap_11_L_oeil_du_pouvoir_Locus_politicus.docx` | 61 | 987 | 50 / 0 | 223 | 0 | 0 | 0 | 0 / 0 |
| `beautes_vitales_XML.zip:Travail_XML/Styles/Ch09_poetique_jardin_japonais_Bonnin.docx` | 111 | 975 | 34 / 0 | 38 | 0 | 0 | 2 | 0 / 0 |

## Cœur seul — chapitre 3

Les styles effectivement employés sont `TEIquote` (14 paragraphes), `Titre2`
(3), `Titre1` (2), `TEIparagraphconsecutive` (2), `TEIepigraph` (2), puis
`TEItitlesup` et `Titre` (un chacun). L'inspecteur retrouve les 46 notes
annoncées dans l'inventaire de passe 1. Aucun retour manuel, lien, signet,
dessin ou média n'est déclaré dans le document principal.

La seule information non couverte est la présence d'en-têtes ou pieds de page,
signalée comme telle. Les styles de titres, de citation et de paragraphes
consécutifs seront des candidats utiles pour établir ultérieurement une
convention DOCX, mais aucune correspondance TEI n'est décidée ici.

## Dissimuler — chapitre 11

Les styles dominants sont `TEIverse` (20 paragraphes), `Titre1` (4),
`TEIquote` (2), puis `Titre`, `TEItitlesub`, `TEIauthoraut` et
`TEIauthorityaffiliation` (un chacun). Les 50 notes et les 223 retours manuels
observés lors de la passe 1 sont confirmés. L'absence de numérotation, liens,
signets, dessins et médias est également confirmée.

Ce document montre nettement l'intérêt de conserver séparément paragraphes et
retours manuels : 20 paragraphes de style `TEIverse` contiennent de nombreux
retours, sans que l'inspecteur les interprète comme une structure poétique TEI.

## Beautés vitales — chapitre 9

Les styles employés sont `TEIverse` (13), `Titre1` (11), `TEIfiguretitle` (5),
`TEIfigurestart` (4), `TEIfigureend` (4), puis `Titre`, `TEIauthoraut`,
`TEIauthorityaffiliation`, `TEIquote`, `TEIfigure-grpstart` et
`TEIfigure-grpend` (un chacun). L'inspecteur retrouve 34 notes, 38 retours
manuels et 2 signets. Il ne trouve ni dessin OOXML ni média dans ce DOCX, malgré
les styles de figure : ces styles signalent une structure éditoriale potentielle,
pas la preuve d'une image embarquée.

## Écarts et enseignements par rapport à la passe 1

Les décomptes de notes et de retours manuels concordent avec l'inventaire de
référence. La passe 2 confirme que les styles de figure ne coïncident pas
nécessairement avec des relations image ou des fichiers sous `word/media/` : la
future conversion devra vérifier ces deux niveaux séparément.

Les trois documents n'emploient ni hyperliens ni listes OOXML dans le corps
inspecté. Ces phénomènes restent couverts par les fixtures synthétiques, mais
devront être recherchés dans d'autres unités du corpus avant toute convention
générale.

## Limites de ce rapport

La couche actuelle n'inspecte pas la cascade effective des styles, les
en-têtes/pieds de page, les commentaires ou la structure interne des tableaux.
Elle ne déduit aucune sémantique TEI et ne compare pas encore les résultats aux
XML Métopes correspondants.
