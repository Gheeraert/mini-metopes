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
ordinaire. Un autre style conserve toujours son texte, mais Mini-Metopes le
signale pour permettre une decision editoriale ulterieure.

Un niveau de plan OOXML explicite de 0 a 5 peut aussi devenir un titre lorsque
le style n'est pas l'un des six titres natifs. Cette regle de repli est moins
prioritaire que les identifiants `Heading1` a `Heading6`.

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

Les retours manuels, sauts de page, sauts de colonne et tabulations restent des
objets distincts. Une tabulation n'est pas remplacee par des espaces. Les
dessins et images sont conserves comme references, sans etre encore interpretes
comme des figures editoriales.

## Elements volontairement differes

Les styles **Title**, **Subtitle**, **Quote** et **IntenseQuote** ne sont pas
encore interpretes. En particulier, ils ne deviennent ni titres, ni citations
de prose, ni citations poetiques par defaut. Ils produisent un diagnostic
explicite et restent temporairement des paragraphes ordinaires dans le modele.

Les metadonnees, listes, tableaux, figures editoriales, bibliographies et la
serialisation TEI restent hors de cette version. Les styles Metopes ou locaux
ne sont pas assimiles automatiquement a cette convention native.
