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
