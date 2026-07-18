# Convention Word native v0.1

Cette convention est la premiere etape de Mini-Metopes. Elle lit les styles et
fonctionnalites natives de Word, sans exiger de modele Word, de macro ou de
styles Metopes. Elle ne produit pas encore de TEI.

## Styles de paragraphes reconnus

Utilisez les styles Word **Titre 1** a **Titre 6**. Selon la langue de Word,
leur nom affiche peut etre `Titre 1`, `Heading 1` ou une autre traduction. Le
programme reconnait leur identifiant OOXML stable (`Heading1` a `Heading6`),
pas leur libelle visible.

Le style **Normal**, ou l'absence de style de paragraphe, produit un paragraphe
ordinaire. Le style Word integre **Corps de texte** (`BodyText`) produit un
paragraphe de suite, conserve dans le modele par
`rendition="consecutive"`. Mini-Metopes accepte aussi les noms integres exacts
`Corps de texte` et `Body Text` lorsqu'ils ne sont pas declares comme styles
personnalises. Les identifiants de variantes connues `BodyText2` et
`BodyText3` sont exclus avant ce repli par nom. Les variantes `Corps de texte
2`, `Corps de texte 3`, `Retrait corps de texte` et les homonymes
personnalises ne sont pas reconnus.

Un autre style conserve toujours son texte. S'il ne porte pas de niveau de plan
exploitable, Mini-Metopes le signale pour permettre une decision editoriale
ulterieure.

Un niveau de plan OOXML explicite de 0 a 5 peut aussi devenir un titre lorsque
le style n'est pas l'un des six titres natifs. Cette regle de repli est moins
prioritaire que les identifiants `Heading1` a `Heading6`.

La priorite est volontairement stricte : les titres natifs gagnent toujours,
puis `Normal` et les styles explicitement differes restent des paragraphes,
meme s'ils portent un niveau de plan. Le repli par niveau de plan ne s'applique
qu'aux styles locaux non reconnus, ou a un paragraphe sans style qui declare
lui-meme un niveau de plan.

## Texte et mises en forme

Le gras, l'italique, les petites capitales, les capitales, l'exposant et
l'indice directement declares dans Word sont conserves dans le modele
editorial. Les styles de caracteres natifs **Emphasis** et **Strong** sont
respectivement interpretes comme italique et gras.

Une propriete directe prime sur le style de caractere : un run `Strong` avec
`gras = faux` reste donc non gras. Les autres styles de caracteres ne sont pas
devines ; leur texte et leurs proprietes directes restent conserves, avec un
diagnostic.

## Notes, liens et sauts

Les notes de bas de page et de fin natives sont conservees separement, avec
leurs paragraphes et leur contenu enrichi. Les appels restent places dans le
flux principal. Les hyperliens externes conservent leur cible et les renvois
internes conservent leur ancre.

Dans les notes, les styles de paragraphes natifs `FootnoteText` et
`EndnoteText` sont traites comme des paragraphes ordinaires. Les styles de
caracteres `FootnoteReference` et `EndnoteReference` sont des styles
automatiques neutres : ils ne produisent aucune marque typographique dans le
modele editorial.

Word place souvent au debut d'une note une marque automatique `footnoteRef` ou
`endnoteRef`, qui affiche le numero de la note dans Word. Cette marque n'est
pas du contenu editorial : Mini-Metopes ne la transforme ni en texte, ni en
nouvel appel de note, ni en note recursive. La numerotation visible sera prise
en charge par le moteur de rendu des notes TEI.

Les retours manuels, sauts de page, sauts de colonne et tabulations restent des
objets distincts. Une tabulation n'est pas remplacee par des espaces. Les
dessins et images sont conserves comme references, sans etre encore interpretes
comme des figures editoriales.

La convention `BodyText` ne lit pas les retraits directs `w:ind` : un
paragraphe `Normal` sans alinea par mise en forme directe reste un paragraphe
normal dans cette passe.

Les styles de caracteres Word natifs **Hyperlink** et **FollowedHyperlink**
sont reconnus comme styles visuels neutres. Ils ne produisent pas de marque
typographique et ne portent pas la semantique du lien : la cible du lien vient
des relations OOXML.

## Citations natives

Utilisez le style Word natif **Citation** (`Quote`) pour une citation en prose.
Plusieurs paragraphes consecutifs utilisant ce style forment une seule citation,
mais chaque paragraphe reste distinct. Un paragraphe normal termine la citation.
Un retour manuel reste un retour manuel dans le paragraphe de citation.

Utilisez le style Word natif **Citation intense** (`IntenseQuote`) pour une
citation poetique. Cette association est une convention Mini-Metopes, pas une
semantique universelle imposee par Word. Dans cette convention, un paragraphe
Word est une strophe ; un retour manuel (`Maj+Entree`) separe les vers ; un
nouveau paragraphe (`Entree`) commence donc une nouvelle strophe. Des
paragraphes consecutifs `IntenseQuote` appartiennent a la meme citation, et un
paragraphe normal la termine. Les noms affiches peuvent etre localises : seule
la reconnaissance des identifiants OOXML `Quote` et `IntenseQuote` est stable.

Ces deux styles restent des citations meme si Word leur associe un niveau de
plan : ils ne deviennent jamais des titres par repli.

## Elements volontairement differes

Les styles **Title** et **Subtitle** ne sont pas encore interpretes. Ils
produisent un diagnostic explicite et restent temporairement des paragraphes
ordinaires dans le modele, meme si le fichier DOCX leur associe un niveau de
plan. Dans la conversion TEI courante, leur presence bloque l'ecriture afin de
ne pas transformer des metadonnees potentielles en paragraphes du corps.

Les metadonnees, listes, tableaux, figures editoriales et bibliographies
restent hors de cette version. La conversion TEI bloque les listes, tableaux,
zones de texte et styles inconnus afin d'eviter une TEI incomplete ou
trompeuse. Les styles Metopes ou locaux ne sont pas assimiles automatiquement a
cette convention native.
