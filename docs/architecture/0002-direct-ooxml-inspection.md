# 0002 — Inspection OOXML directe avant toute conversion

## Décision

Mini-Métopes lit les DOCX directement comme des archives ZIP et analyse les
parties OOXML utiles avec `lxml`. Cette couche n'utilise pas `python-docx` et
n'extrait jamais globalement une archive sur le disque.

Elle produit un modèle d'inspection immuable : styles, paragraphes, runs,
notes, relations et médias. Ce modèle est distinct du futur modèle éditorial ;
il décrit ce qui est déclaré dans le document, sans décider de la TEI à
produire.

## Raisons

L'OOXML expose des informations nécessaires aux futures décisions éditoriales
(identifiants de styles, relations, appels de notes, retours manuels,
numérotation) que l'on veut contrôler explicitement. Une couche légère fondée
sur `zipfile` et `lxml` suffit à ce stade et évite une dépendance supplémentaire
à l'exécution.

La lecture XML désactive les entités externes, le chargement de DTD et le réseau.
Chaque partie XML est limitée en taille avant lecture. Une partie principale
absente ou mal formée est une erreur fatale typée ; une partie optionnelle
inexploitable devient un avertissement d'inspection.

## Conséquences

- Les identifiants de styles (`styleId`) et leurs noms affichés sont exposés
  séparément.
- Les propriétés de run signalent seulement les déclarations directes :
  `true`, `false` explicite et absence de déclaration restent distincts. La
  cascade complète de Word (styles liés, `basedOn`, thèmes et propriétés de
  document) n'est pas calculée.
- Les paragraphes restent distincts des sauts manuels. Les sauts de page et de
  colonne sont signalés dans les types de saut, sans être assimilés à une fin de
  vers.
- Les parties optionnelles (`styles.xml`, `numbering.xml`, notes, relations,
  types de contenu) sont lues lorsqu'elles existent. Les médias sont inventoriés
  grâce à l'index ZIP, sans charger leurs octets.
- Les appels de notes et dessins sont matérialisés dans le texte reconstruit par
  des marqueurs ASCII explicites (`[footnote:…]`, `[endnote:…]`, `[drawing]`),
  tandis que leurs identifiants structurés restent disponibles séparément.

## Limites assumées

Cette passe ne résout pas la mise en forme effective Word, ne modélise pas les
tableaux, commentaires, en-têtes ou pieds de page, et ne reconstruit pas le
format visuel des listes. Elle ne détermine aucune convention Word → TEI et ne
produit aucun XML TEI.

La conversion viendra seulement après la définition et les tests d'un modèle
éditorial intermédiaire. L'inspecteur fournit les faits OOXML nécessaires à ce
travail, pas une interprétation éditoriale.
