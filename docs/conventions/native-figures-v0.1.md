# Figures Word natives v0.1

Cette convention couvre uniquement les images Word simples et autonomes.

## Image

Le paragraphe d'image doit :

- être sans style, ou porter `Normal`, `FootnoteText` ou `EndnoteText` ;
- ne pas être un style personnalisé ;
- contenir exactement une image DrawingML `wp:inline` ;
- ne contenir aucun texte significatif, lien, note, tabulation ou retour manuel ;
- utiliser une relation interne `r:embed` vers `word/media/`.

Les images flottantes, liées, VML, transformées, recadrées, multiples ou placées
dans des listes sont refusées.

## Description accessible

La description est obligatoire et vient seulement de `wp:docPr/@descr`.
Mini-Métopes n'invente pas de texte alternatif à partir de la légende, du titre
Word, du nom de fichier ou du nom `Picture ...`.

## Légende

Le paragraphe suivant est une légende uniquement s'il porte l'identifiant exact
`Caption` et si ce style n'est pas personnalisé. Aucun repli par nom visible
(`Légende`, `Caption`, etc.) n'est appliqué.

La légende devient :

```xml
<p rend="caption">...</p>
```

Une légende `Caption` sans figure immédiatement précédente est bloquante.

## TEI et médias

La figure devient :

```xml
<figure>
  <graphic url="media/<sha256>.png"/>
  <figDesc>Description accessible.</figDesc>
  <p rend="caption">Légende facultative.</p>
</figure>
```

Les formats acceptés sont PNG et JPEG. Les fichiers sont écrits dans `media/`
à côté du XML, avec un nom fondé sur le SHA-256 complet du contenu. Les JPEG
sortent avec l'extension `.jpg`, même si le DOCX utilisait `.jpeg`.

Les médias inutilisés dans le DOCX ne sont pas exportés.
