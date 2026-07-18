# Document A — cas minimal (Word français)

Document produit par un Word français : identifiants de styles localisés
(`Titre`, `Titre1`, `Titre2`, `Notedebasdepage`, `Appelnotedebasdep`) avec les
noms OOXML canoniques anglais dans `w:name` (`Title`, `heading 1`, …). Il
exerce la résolution multilingue par identifiant localisé + nom canonique.

Contenu :

- titre principal (`Titre`/Title), consommé comme suggestion de métadonnées ;
- titres de niveaux 1 et 2 → `div` hiérarchisés avec `head` ;
- paragraphes normaux → `p` ;
- italique et gras directs → `hi rend="italic"` / `hi rend="bold"` ;
- une note de bas de page → `note place="foot"`.

Conversion attendue : succès, aucun diagnostic.
