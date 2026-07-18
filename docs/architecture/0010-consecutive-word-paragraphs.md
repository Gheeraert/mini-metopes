# ADR 0010 — Paragraphes Word de suite

## Problème

Les textes éditoriaux distinguent souvent un paragraphe courant d'un
paragraphe de suite sans alinéa de première ligne. Cette information ne doit
pas être déduite fragilement d'une géométrie Word ponctuelle, car les retraits
directs, la cascade des styles et les modèles locaux peuvent varier.

## Décision

Mini-Métopes reconnaît explicitement le style Word intégré `BodyText`, affiché
en français comme **Corps de texte**, comme un paragraphe de suite. Le modèle
éditorial conserve cette sémantique par `Paragraph.rendition =
"consecutive"`. La sérialisation Commons Publishing produit :

```xml
<p rend="consecutive">...</p>
```

Le style `Normal` reste un paragraphe courant sans rendition.

## Reconnaissance du style

La reconnaissance principale repose sur l'identifiant OOXML stable `BodyText`.
Un repli exact par nom est accepté pour les noms intégrés `Corps de texte` et
`Body Text`, après normalisation de la casse et des espaces. Ce repli est
refusé pour tout style explicitement personnalisé par `w:customStyle="1"`.

Les styles `Corps de texte 2`, `Corps de texte 3`, `Retrait corps de texte`,
les styles locaux ressemblants et le style Métopes `TEI_paragraph_consecutive`
ne sont pas assimilés à cette convention.

## Conséquences

La couche DOCX expose `ParagraphInfo.style_is_custom` afin que la convention
puisse distinguer un style intégré d'un homonyme personnalisé. La couche
éditoriale conserve la sémantique ; la couche TEI se contente de sérialiser
`rend="consecutive"` lorsqu'elle est présente.

Un paragraphe `BodyText` portant une numérotation Word directe résolue reste un
item de liste : la sémantique de liste est prioritaire et aucun
`rend="consecutive"` n'est ajouté sur `<item>`.

La même règle s'applique dans les notes. Le profil Commons Publishing embarqué
autorise `p@rend` dans une note ; les tests valident ce cas contre le RNG.

## Limites

Cette passe ne lit pas les retraits OOXML `w:ind`, `w:firstLine`,
`w:hanging`, ni la cascade typographique Word. Un paragraphe `Normal` avec un
retrait direct nul reste donc un paragraphe courant. Les futures sorties
LaTEI/PDF pourront transformer `rendition="consecutive"` en `\noindent` ou en
macro contrôlée, mais cette passe ne produit ni LaTeX ni PDF.
