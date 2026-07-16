# Ecart observe avec la convention Word native v0.1

Ce rapport applique le constructeur editorial aux trois DOCX deja inspectes,
en lisant les archives dans un repertoire temporaire. Aucun DOCX, texte ou
XML de `references/corpora/` n'est copie dans le depot.

La convention v0.1 ne reconnait explicitement que `Heading1` a `Heading6` et
`Normal`. Dans les trois documents, les titres observes utilisent surtout les
styles locaux `Titre1` et `Titre2`. Ils ont ete detectes uniquement grace a
leur niveau de plan OOXML explicite : ce constat ne transforme pas ces styles
en correspondances natives permanentes.

## `coeur_seul.zip` — chapitre 3

- Source inspectee : `styles/ch_003_chap_1.docx`.
- 60 paragraphes, 1 051 runs et 46 notes de bas de page.
- Paragraphes sans style : 35. Titres detectes par niveau de plan : 2 niveau 1
  (`Titre1`) et 3 niveau 2 (`Titre2`).
- Styles non reconnus par la convention : `TEIepigraph` (2),
  `TEIparagraphconsecutive` (2), `TEIquote` (14), `TEItitlesup` (1) et
  `Titre` (1), soit 20 paragraphes une fois les titres de plan comptes a part.
- Diagnostics dominants : 223 `unsupported_character_style` et 66
  `unsupported_paragraph_style` (le second total inclut aussi les notes).

## `dissimuler.zip` — chapitre 11

- Source inspectee :
  `travail_xml/styles/chap_11_L_oeil_du_pouvoir_Locus_politicus.docx`.
- 61 paragraphes, 987 runs et 50 notes de bas de page.
- Paragraphes sans style : 31. Quatre titres de niveau 1 sont detectes par
  niveau de plan sur le style local `Titre1`.
- Styles non reconnus : `TEIauthoraut` (1), `TEIauthorityaffiliation` (1),
  `TEIquote` (2), `TEItitlesub` (1), `TEIverse` (20) et `Titre` (1), soit
  26 paragraphes.
- Diagnostic dominant : 76 `unsupported_paragraph_style`.

## `beautes_vitales_XML.zip` — chapitre 9

- Source inspectee :
  `Travail_XML/Styles/Ch09_poetique_jardin_japonais_Bonnin.docx`.
- 111 paragraphes, 975 runs et 34 notes de bas de page.
- Paragraphes sans style : 68. Onze titres de niveau 1 sont detectes par
  niveau de plan sur `Titre1`.
- Styles non reconnus : `TEIauthoraut` (1), `TEIauthorityaffiliation` (1),
  `TEIfigure-grpend` (1), `TEIfigure-grpstart` (1), `TEIfigureend` (4),
  `TEIfigurestart` (4), `TEIfiguretitle` (5), `TEIquote` (1), `TEIverse` (13)
  et `Titre` (1), soit 32 paragraphes.
- Diagnostics dominants : 25 `unsupported_character_style` et 66
  `unsupported_paragraph_style` (ce dernier total inclut aussi les notes).

## Conclusion

Les styles Metopes `TEI...` et les styles locaux historiques restent observes,
conserves comme paragraphes ou texte, puis signales. Ils ne sont pas assimiles
a `Normal`, `Quote`, `IntenseQuote`, `Heading1` ou a une quelconque structure
TEI. Le rapport mesure donc l'ecart entre des corpus reels et la convention
native, sans introduire de convention cachee.
# Note de convention native

Les styles historiques `TEIquote` et `TEIverse` restent hors de la convention
native : seuls les identifiants OOXML `Quote` et `IntenseQuote` sont reconnus
pour les citations dans la passe 5.
