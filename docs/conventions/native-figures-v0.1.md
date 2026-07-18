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

## Invariants de securite 10A1

Les images hyperliees sont refusees, y compris lorsqu'elles sont seules dans le
paragraphe : le lien par relation ou par ancre interne porterait une semantique
non modelisee.

Un identifiant de relation duplique dans la partie source rend la figure non
serialisable si l'image le reference. Les doublons non utilises ne modifient pas
les relations uniques.

Toute cible de relation contenant un segment brut `..`, une barre oblique
inverse, une forme absolue ou une valeur vide est refusee avant normalisation.

Les valeurs DrawingML presentes mais invalides ne sont pas assimilees a une
absence de valeur. Elles produisent `invalid_drawing_property_not_serializable`.

La limite totale de medias s'applique seulement aux medias utilises par la TEI,
apres deduplication. Avant ecriture, tous les assets sont prevalider ; un asset
invalide ou un conflit empeche toute ecriture de media et preserve le XML
existant.

## Details de figure 11

Une figure peut etre precedee du style controle exact et personnalise
`TEIfiguretitle` / `TEI_figure_title`, puis suivie de `Caption` ou du style
controle `TEIfigurecaption` / `TEI_figure_caption`, et enfin du style controle
`TEIfigurecredits` / `TEI_figure_credits`. Les styles homonymes ou voisins ne
sont pas reconnus. Le titre devient `head`; la legende et les credits deviennent
respectivement `p rend="caption"` et `p rend="credits"`.
