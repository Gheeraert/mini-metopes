# 0011 — Paragraphes de continuation dans les items de liste Word

## Problème

Word permet de prolonger visuellement un item de liste par un paragraphe non
numéroté. Mini-Métopes ne peut pas l'inférer depuis les retraits `w:ind` sans
risque : un paragraphe `Normal` entre deux items reste donc une interruption de
liste.

## Décision

Le seul candidat explicite est le style Word intégré `ListParagraph`. Il est
reconnu uniquement par son identifiant OOXML exact, sans repli par nom localisé.
Un style explicitement personnalisé par `w:customStyle="1"` n'est pas un
candidat.

Une continuation est acceptée seulement lorsque la preuve contextuelle est
complète :

1. un item numéroté direct et résolu vient d'être construit ;
2. un ou plusieurs paragraphes `ListParagraph` non numérotés suivent ;
3. le paragraphe numéroté suivant reprend le même `numId`, le même `ilvl` et
   la même signature de liste que l'item précédent.

La signature comparée reprend celle des listes 8B : `numId`, niveau, type,
format, départ et redémarrage. `numId="0"` reste une suppression explicite de
numérotation et n'est jamais une liste active. Dans cette première version, un
candidat de continuation doit toutefois ne porter aucune numérotation observable
afin de préserver les paragraphes `ListParagraph` à `numId="0"` déjà utilisés
comme paragraphes ordinaires.

## Modèle

`EditorialListItem` conserve son flux inline initial et reçoit désormais :

```text
continuation_paragraphs: tuple[Paragraph, ...]
```

Ces paragraphes sont des `Paragraph` ordinaires avec `rendition=None`. Ils ne
sont pas des paragraphes de suite `BodyText` : la continuation structurelle
d'un item et l'absence d'alinéa typographique sont deux notions différentes.

La séquence conservée est :

1. contenu du paragraphe numéroté initial ;
2. paragraphes de continuation ;
3. sous-listes éventuelles.

Mini-Métopes ne crée pas de continuation après une sous-liste avant le retour au
niveau parent, car l'appartenance serait ambiguë.

## TEI

Un item simple conserve la forme mixte existante :

```xml
<item>Texte de l'item</item>
```

Dès qu'un item possède une continuation, le paragraphe initial est également
enveloppé afin de rendre les frontières explicites :

```xml
<item>
  <p>Premier paragraphe.</p>
  <p>Continuation.</p>
</item>
```

Les sous-listes restent placées après tous les paragraphes de l'item. Cette
structure est validée contre le RNG Commons Publishing embarqué.

## Refus conservatoires

Sont bloqués par `ambiguous_list_continuation_not_serializable` : continuation
suivie d'une autre instance, d'un autre niveau, d'une autre signature, d'un
titre ou de la fin du document. Un paragraphe `Normal` reste une interruption et
déclenche les diagnostics de reprise discontinue existants. Un candidat vide
produit `empty_list_continuation_not_serializable`.

Le même algorithme s'applique séparément au corps, aux notes de bas de page et
aux notes de fin ; aucun état ne traverse une frontière de partie ou de note.

## Limites

Cette passe ne traite pas les paragraphes de continuation implicites, les
retraits géométriques, les listes de définitions, les cases à cocher, les puces
illustrées, les calculs de compteurs Word, LaTEI ni PDF.
