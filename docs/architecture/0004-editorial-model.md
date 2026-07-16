# 0004 — Modele editorial et convention Word native v0.1

## Decision

Mini-Metopes ajoute un modele editorial intermediaire immuable apres
l'inspection OOXML et avant toute serialisation TEI. Le paquet `docx` continue
d'observer les faits OOXML ; le paquet `editorial` applique une convention Word
explicite et construit des blocs, contenus inline, liens, notes et diagnostics.

## Raisons

Les styles et runs Word ne constituent pas encore une semantique editoriale.
La convention `NATIVE_WORD_CONVENTION` centralise les correspondances retenues
pour les titres natifs, `Normal`, `Emphasis` et `Strong`, au lieu de les
disperser dans le lecteur OOXML. Elle pourra etre remplacee ou completee par
d'autres conventions sans modifier l'inspecteur.

La classification des paragraphes suit une priorite explicite. Les styles
`Heading1` a `Heading6` sont reconnus par identifiant stable, meme si leur
niveau de plan declare est contradictoire. `Normal` et les styles differes ne
peuvent pas devenir des titres par repli. Le repli par `outlineLvl` reste
disponible uniquement pour les styles locaux non reconnus ou les paragraphes
sans style.

Le modele conserve les indices et styles sources, mais le document expose
seulement son nom de fichier : aucun chemin local absolu ne devient une donnee
editoriale ou JSON publique.

## Consequences

- Les contenus inline sont construits exclusivement depuis `RunInfo.contents`.
  Les marqueurs de texte de commodite de l'inspecteur ne sont jamais analyses.
- Les `TextSpan` adjacents ayant les memes marques et le meme lien fusionnent,
  y compris entre runs. Les tabulations, sauts, notes, dessins et changements
  de contexte interrompent cette fusion.
- Les notes conservent leurs blocs separes. Les appels absents, doublons et
  notes non appelees deviennent des diagnostics plutot qu'une renumerotation.
- Les relations OOXML sont resolues dans la portee de leur partie : le corps
  utilise `document.xml.rels`, les notes de bas de page `footnotes.xml.rels`
  et les notes de fin `endnotes.xml.rels`.
- Les styles inconnus gardent leur contenu ; sans niveau de plan ils deviennent
  des paragraphes avec diagnostic, avec niveau de plan ils peuvent devenir des
  titres de repli. Les styles `Title`, `Subtitle`, `Quote` et `IntenseQuote`
  sont explicitement differes.
- La serialisation JSON est dediee et deterministe. Chaque bloc et contenu
  inline contient un discriminant `kind`.

## Limites assumees

Cette couche ne calcule pas la cascade complete de mise en forme Word. Elle ne
verifie pas encore l'existence des ancres internes : l'inspection actuelle
conserve l'identifiant technique du signet, tandis que `w:anchor` cible son nom.
Elle ne traite ni les citations, ni les strophes ou vers, ni les listes,
tableaux, figures, metadonnees ou bibliographies.

Elle ne produit aucun XML et aucune correspondance vers des elements TEI. La
validation Commons Publishing reste independante du modele editorial.
