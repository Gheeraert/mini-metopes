# 0005 - Citations natives Word dans le modele editorial

## Probleme

Le texte aplati d'un paragraphe ne permet pas de distinguer une citation de
prose composee de plusieurs paragraphes d'une citation poetique composee de
strophes et de vers.

## Decision

La convention native v0.1 reconnait l'identifiant OOXML `Quote` comme citation
en prose et `IntenseQuote` comme citation poetique. Des paragraphes `Quote`
consecutifs deviennent un `ProseQuote`, tout en gardant des
`ProseQuoteParagraph` distincts. Des paragraphes `IntenseQuote` consecutifs
deviennent un `VerseQuote` ; chaque paragraphe devient une `VerseStanza` et
chaque `LineBreak` devient une separation entre `VerseLine`.

Les retours de page et de colonne, les liens, notes, tabulations et dessins
restent des objets inline, dans l'ordre source. Les retours manuels ne sont pas
conserves a l'interieur du contenu de chaque vers car ils servent de separateur.
Les vers vides sont conserves et signales ; une strophe vide contient un vers
vide et ne produit qu'un diagnostic de strophe vide.

La meme construction est appliquee aux notes de bas de page et de fin avec les
relations propres a leur partie OOXML.

## Consequences et limites

Les styles sont reconnus par leurs identifiants, jamais par leur nom localise.
`Quote` et `IntenseQuote` priment sur un eventuel niveau de plan. Il ne s'agit
pas d'une semantique Word universelle : c'est une convention Mini-Metopes
documentee. Aucune TEI n'est produite dans cette passe ; le mapping vers les
structures Commons Publishing reste une decision ulterieure.
