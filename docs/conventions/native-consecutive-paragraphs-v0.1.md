# Convention paragraphes de suite v0.1

Utilisez le style Word intégré **Corps de texte** pour indiquer un paragraphe
de suite, c'est-à-dire un paragraphe typographiquement continu avec le bloc
précédent et sans alinéa de première ligne dans une future sortie papier.

Mini-Métopes reconnaît d'abord l'identifiant OOXML `BodyText`. Il accepte aussi
les noms intégrés exacts `Corps de texte` et `Body Text`, car le nom visible
peut varier selon la langue de Word. La comparaison est exacte après
normalisation des espaces et de la casse.

Ne sont pas reconnus dans cette version :

- `Corps de texte 2` ;
- `Corps de texte 3` ;
- `Body Text 2` ;
- `Retrait corps de texte` ;
- les styles personnalisés nommés artificiellement `Corps de texte` ;
- le style Métopes `TEI_paragraph_consecutive`.

Dans le modèle éditorial, ce style devient :

```text
Paragraph(rendition="consecutive")
```

Dans la TEI Commons Publishing, il devient :

```xml
<p rend="consecutive">...</p>
```

Le contenu inline est conservé : texte, gras, italique, liens, appels de notes
et retours manuels restent à leur place. La règle s'applique aussi dans les
notes.

Mini-Métopes ne déduit pas cette sémantique de la mise en forme directe. Un
paragraphe `Normal` doté d'un retrait Word direct `w:firstLine="0"` reste donc
un paragraphe normal dans cette passe.

Si un paragraphe `BodyText` est aussi un paragraphe de liste Word résolu, il
devient un item de liste. La liste est prioritaire et aucun `rend="consecutive"`
n'est ajouté à l'`<item>`.
