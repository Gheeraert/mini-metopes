# Convention Word native vers TEI v0.1

Mini-Metopes convertit actuellement les styles Word natifs suivants :

- `Heading1` a `Heading6` (souvent affiches « Titre 1 » a « Titre 6 ») deviennent des sections TEI ;
- `Normal` devient un paragraphe ;
- `BodyText`, affiche comme `Corps de texte` ou `Body Text`, devient un paragraphe de suite `<p rend="consecutive">` ;
- `Quote` devient une citation en prose ;
- `IntenseQuote` devient une citation poetique ; un paragraphe est une strophe et `Maj+Entree` separe les vers ;
- les listes Word natives resolues deviennent des listes TEI, avec continuations explicites `ListParagraph` lorsque le rattachement est prouve ;
- gras, italique, petites capitales, capitales, exposant et indice deviennent des enrichissements TEI ;
- les notes Word deviennent des notes TEI ;
- les hyperliens externes deviennent des liens TEI.

Les noms visibles Word peuvent etre localises : Mini-Metopes s'appuie sur les
identifiants OOXML. Un nouveau paragraphe dans une citation poetique commence
une strophe ; un paragraphe normal termine une citation consecutive.

Le paragraphe de suite est une semantique editoriale, pas une deduction
geometrique : un paragraphe `Normal` avec un retrait direct nul ne devient pas
`rend="consecutive"`. Les variantes `BodyText2`, `BodyText3` et les styles
personnalises homonymes restent refusees.

Les styles natifs `FootnoteText` et `EndnoteText` sont acceptes comme
paragraphes ordinaires a l'interieur des notes. Les styles automatiques
`FootnoteReference` et `EndnoteReference` sont neutres : la semantique de la
note vient de l'appel Word, puis de l'element TEI `note`, pas du style visuel.
Les marques internes `footnoteRef` et `endnoteRef` qui affichent le numero au
debut de la note Word ne sont pas reprises comme texte TEI.

La conversion refuse actuellement les dessins ou images, liens internes,
vers vides, paragraphes vides, listes Word ambiguës ou non resolues, tableaux
et zones de texte. Ces objets ne sont pas transformes silencieusement en
paragraphes.

Les titres `Title` et `Subtitle` sont reserves aux metadonnees futures : leur
presence bloque donc la conversion TEI pour eviter un `teiHeader` trompeur ou
une transformation en simple paragraphe. Les styles de paragraphes ou de
caracteres inconnus bloquent egalement la conversion tant qu'une convention
explicite n'a pas ete decidee.

Les commentaires, en-tetes et pieds de page Word sont signales comme
avertissements. Ils ne bloquent pas encore une conversion du corps principal,
mais ils restent visibles dans les diagnostics.
