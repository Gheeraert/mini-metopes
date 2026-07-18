# Continuations de listes Word v0.1

Pour prolonger un item de liste par un second paragraphe dans Mini-Métopes,
utilisez le style Word intégré `ListParagraph` sur le paragraphe de
continuation, sans numérotation observable.

Cette passe ne reconnaît aucun nom localisé comme `Paragraphe de liste` : seul
l'identifiant OOXML exact `ListParagraph` est utilisé. Un style personnalisé
portant artificiellement cet identifiant n'est pas accepté.

Une continuation est publiée seulement si le paragraphe numéroté suivant reprend
exactement la même liste :

- même `numId` ;
- même `ilvl` ;
- même type de liste ;
- même format et mêmes propriétés de départ.

Ainsi :

```text
42/0
ListParagraph
42/0
```

devient un item multiparagraphe. En TEI :

```xml
<item>
  <p>Paragraphe initial.</p>
  <p>Continuation.</p>
</item>
```

Un item simple reste en contenu mixte direct et ne reçoit pas de `<p>`
artificiel.

Ne sont pas interprétés comme continuations :

- un paragraphe `Normal` ;
- une reprise avec un autre `numId` ;
- une reprise à un autre niveau ;
- une continuation placée en fin de liste ;
- une continuation après une sous-liste avant le retour au parent ;
- une numérotation non résolue ou portée par style.

Le style `BodyText` / `Corps de texte` reste la convention du paragraphe de
suite `<p rend="consecutive">`. Il n'est pas utilisé pour rattacher un
paragraphe à un item de liste. Inversement, `ListParagraph` utilisé comme
continuation ne reçoit pas automatiquement `rend="consecutive"`.

Les mêmes règles valent dans les notes de bas de page et les notes de fin.
Mini-Métopes n'utilise pas les retraits `w:ind` pour deviner une continuation.
Un paragraphe `ListParagraph` portant `numId="0"` reste un paragraphe non
numéroté ordinaire dans cette version ; cette suppression explicite ne sert pas
à prouver une continuation.
