# 0012 — Figures Word natives simples

## Problème

Mini-Métopes inspectait déjà les dessins Word, mais les refusait faute de
modèle éditorial. La passe 10A introduit seulement les images autonomes dont la
publication TEI peut être prouvée sans interpréter la mise en page Word.

## Choix

Une figure est reconnue depuis un paragraphe Word autonome contenant exactement
un `w:drawing` DrawingML `wp:inline`, sans texte significatif ni autre objet
inline. Les styles de conteneur admis sont les identifiants intégrés `Normal`,
`FootnoteText`, `EndnoteText`, ou l'absence de style. Aucun repli par nom
localisé n'est utilisé.

La source de l'image doit être une relation interne OOXML de type image,
incorporée par `r:embed`, résolue vers `word/media/...`. Les relations externes,
liées par `r:link`, dangereuses, absentes ou de mauvais type sont bloquantes.

Le texte alternatif accessible provient uniquement de `wp:docPr/@descr`, après
normalisation des espaces de bord. `wp:docPr/@title`, le nom Word et le nom de
fichier ne sont jamais utilisés comme remplacement.

Le paragraphe immédiatement suivant est consommé comme légende seulement s'il
porte le style intégré exact `Caption`, non personnalisé. Il devient un
`Paragraph(rendition="caption")`.

## Modèle

Le modèle éditorial ajoute :

- `EditorialGraphic`, qui conserve la partie source, la relation, le chemin
  média interne, le type MIME, le SHA-256, la description et les dimensions EMU ;
- `EditorialFigure`, qui associe un `EditorialGraphic` à une légende facultative.

Les octets binaires ne sont pas placés dans le modèle éditorial.

## TEI

La forme produite est :

```xml
<figure>
  <graphic url="media/<sha256>.png"/>
  <figDesc>Description accessible.</figDesc>
  <p rend="caption">Légende.</p>
</figure>
```

La légende est facultative. `figDesc` est obligatoire pour les figures DOCX de
cette passe. Les dimensions Word ne sont pas sérialisées tant que leur mapping
Commons Publishing n'est pas décidé.

## Médias

Les médias acceptés sont `image/png` et `image/jpeg`, avec vérification de
signature minimale. Les sorties sont content-addressées :

- `media/<sha256>.png`
- `media/<sha256>.jpg`

La conversion retourne des `TeiAsset` triés et dédupliqués. L'écriture crée ou
réutilise les médias avant d'écrire le XML atomiquement en dernier. Un média
existant au bon chemin mais au mauvais hash bloque l'écriture.

## Refus conservatoires

Sont refusés : images flottantes `wp:anchor`, VML, sources multiples, images
externes, formats non PNG/JPEG, signatures incohérentes, recadrage, rotation,
retournement, images mélangées avec du texte, plusieurs images dans un
paragraphe, images numérotées, images dans des items de listes, légendes
orphelines, légendes vides ou contenant une image.

Un échec d'écriture du XML après écriture d'un média content-addressé peut
laisser un média orphelin, mais ne corrompt jamais une TEI existante.

## Durcissement 10A1

Une image placee dans un `w:hyperlink` est refusee, que le lien soit porte par
une relation ou par une ancre interne. La semantique de lien d'une image n'est
pas encore modelisee et ne doit pas disparaitre silencieusement.

Les relations de la partie source sont indexees sans ecrasement silencieux. Si
un dessin reference un identifiant de relation duplique, la figure est refusee :
Mini-Metopes ne choisit ni la premiere ni la derniere declaration.

Les cibles de medias sont controlees avant `posixpath.normpath` : cible vide,
cible absolue, barre oblique inverse et segment brut `..` sont bloques. Une
cible telle que `./media/image.png` reste acceptable si sa forme canonique reste
strictement sous `word/media/`.

Les proprietes DrawingML distinguent absence et valeur invalide. Une dimension
absente peut rester inconnue ; une dimension presente mais non numerique, nulle
ou negative devient bloquante. Les rotations, flips, recadrages et placements
incoherents (`wp:inline` et `wp:anchor` simultanes, multiples ou absents) sont
traites de la meme maniere.

La limite totale des medias est appliquee pendant l'extraction uniquement aux
medias effectivement references par la TEI, apres deduplication. Les medias
inutilises presents dans `word/media/` ne bloquent pas la conversion.

L'ecriture effectue une prevalidation complete de tous les `TeiAsset` avant le
premier octet ecrit : chemin, type MIME, signature, extension, SHA-256 reel,
nom content-addresse exact, conflits internes et conflits avec des fichiers
existants.
