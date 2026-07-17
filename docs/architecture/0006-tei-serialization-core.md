# 0006 - Premiere serialisation TEI Commons Publishing

## Decision

Le paquet `mini_metopes.tei` serialise le modele editorial immuable avec
`lxml`, puis valide l'arbre obtenu par le RNG Commons Publishing embarque.
L'ecriture n'est autorisee qu'apres validation ; elle utilise un fichier
temporaire voisin et un remplacement atomique.

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

Les marques deviennent un unique `hi/@rend`, avec les valeurs admises par le
RNG : `bold`, `italic`, `small-caps`, `uppercase`, `sup`, `sub`. Un lien
externe devient `ref/@target`. Un retour manuel devient `lb`.

## Refus explicites

Le profil ne propose pas de representation admise ici pour les sauts de page,
de colonne ou les tabulations : ils bloquent donc la conversion. Les dessins,
liens internes ou non resolus, paragraphes/titres/vers/strophes vides et notes
manquantes ou dupliquees sont aussi bloquants. Une pile de notes actives protege
contre les cycles. Les notes non appelees ne sont jamais ajoutees artificiellement.

Cette passe ne produit ni figures, ni listes, ni tableaux, ni metadonnees
riches, ni cibles de signets. Elle ne modifie pas le RNG et n'utilise ni XSLT,
ni Java, ni Saxon.
