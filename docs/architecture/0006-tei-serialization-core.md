# 0006 - Premiere serialisation TEI Commons Publishing

## Decision

Le paquet `mini_metopes.tei` applique d'abord un precontrole conservatoire sur
la chaine inspection OOXML -> modele editorial -> TEI. Il propage les
diagnostics produits par l'inspecteur et par le constructeur editorial, puis
serialise le modele immuable avec `lxml` seulement si aucun diagnostic bloquant
n'a ete rencontre. L'arbre obtenu est valide par le RNG Commons Publishing
embarque. L'ecriture n'est autorisee qu'apres validation ; elle utilise un
fichier temporaire voisin et un remplacement atomique.

## Structures normatives retenues

Le `teiHeader` minimal contient `fileDesc/titleStmt/title`, `publicationStmt/p`
et `sourceDesc/p`. Le titre est le seul nom du fichier DOCX : c'est un titre
technique provisoire, sans metadonnee bibliographique inventee.

Les titres deviennent des `div` imbriques avec `head`. Un saut de niveau cree
des `div` anonymes intermediaires afin de conserver la profondeur source. Le
contenu avant le premier titre reste directement dans `body`, ce que le RNG
autorise.

`Paragraph` devient `p`. `ProseQuote` devient `quote` contenant un `p` par
paragraphe. `VerseQuote` devient `quote` contenant un `lg` par strophe et un
`l` par vers. Les notes sont placees exactement a leur appel comme `note`
avec `place="foot"` ou `place="end"`.

Les paragraphes Word natifs de notes (`FootnoteText`, `EndnoteText`) sont
modelises comme paragraphes ordinaires. Les styles de caracteres
`FootnoteReference` et `EndnoteReference` sont neutres. Les marques OOXML
`footnoteRef` et `endnoteRef`, presentes au debut du contenu de note pour
afficher son numero dans Word, ne sont pas des contenus editoriaux : elles ne
deviennent ni texte, ni appel de note, ni element TEI supplementaire.

Les marques deviennent un unique `hi/@rend`, avec les valeurs admises par le
RNG : `bold`, `italic`, `small-caps`, `uppercase`, `sup`, `sub`. Un lien
externe devient `ref/@target`. Un retour manuel devient `lb`. Les styles Word
natifs `Hyperlink` et `FollowedHyperlink` sont reconnus comme styles visuels
neutres : ils ne portent pas la semantique du lien, qui vient des relations
OOXML.

## Refus explicites

Le precontrole bloque les structures que Mini-Metopes sait ne pas modeliser
encore : zones de texte, tableaux, listes Word, parties XML illisibles ou
mal formees, et parties XML trop volumineuses. Les tableaux et zones de texte
sont observes dans `document.xml`, `footnotes.xml` et `endnotes.xml`.

Les styles de paragraphes differes (`Title`, `Subtitle`) ou inconnus bloquent
la conversion afin d'eviter de transformer des metadonnees ou une semantique
locale en simples paragraphes. Les styles de caracteres inconnus, les sauts
OOXML inconnus et un conflit exposant/indice bloquent aussi la conversion.

Les avertissements sur les commentaires, en-tetes et pieds de page sont
propages mais ne bloquent pas encore la conversion, car leur contenu n'est pas
integre au corps editorial courant.

Le profil ne propose pas de representation admise ici pour les sauts de page,
de colonne ou les tabulations : ils bloquent donc la conversion au moment de
la serialisation. Les dessins, liens internes ou non resolus,
paragraphes/titres/vers/strophes vides, citations manuellement vides et notes
manquantes ou dupliquees sont aussi bloquants. Un titre rencontre dans une note
produit `heading_in_note_not_serializable` : cette version ne cree pas de
divisions TEI dans une `note`. Une pile de notes actives protege contre les
cycles. Les notes non appelees ne sont jamais ajoutees artificiellement.

Cette passe ne produit ni figures, ni listes, ni tableaux, ni metadonnees
riches, ni cibles de signets. Elle ne modifie pas le RNG et n'utilise ni XSLT,
ni Java, ni Saxon.
