# 0020 — Extension allemande et espagnole des noms de styles natifs

## Contexte

La décision 0015 couvrait uniquement les noms affichés français et anglais
dans `NATIVE_PARAGRAPH_STYLE_NAMES`/`NATIVE_CHARACTER_STYLE_NAMES`, et
signalait explicitement cette limite (« autres langues non couvertes :
allemand, espagnol… »). Un audit du dépôt a confirmé que la portée
« multilingue » annoncée était plus étroite que le nom ne le laisse penser.

Le risque principal d'une extension de cette table n'est pas l'absence de
couverture (qui échoue proprement : `unsupported_paragraph_style`, bloquant)
mais une **entrée incorrecte** : un nom localisé mal orthographié ou
inventé associerait silencieusement un style Word à la mauvaise convention,
produisant une TEI structurellement valide mais sémantiquement fausse — le
seul type d'erreur que `AGENTS.md` interdit absolument (« ne pas deviner une
convention non approuvée »).

## Méthode de vérification

Chaque nom ajouté a été recherché individuellement (recherche web,
recoupement de plusieurs sources indépendantes lorsque possible) avant
d'être intégré. Aucun nom n'a été ajouté sur la seule base d'une déduction
morphologique non recoupée, **sauf** deux cas explicitement signalés
ci-dessous où l'analogie avec un terme confirmé était jugée suffisamment
fiable (couple note de bas de page / note de fin, dont la construction est
strictement parallèle et confirmée dans les deux langues pour la moitié de
la paire).

## Décision

Noms ajoutés à `NATIVE_PARAGRAPH_STYLE_NAMES` (`editorial/convention.py`),
sous-ensemble volontairement limité aux entrées vérifiées :

| Style canonique | Allemand | Espagnol |
| --- | --- | --- |
| `Heading1`–`Heading6` | `Überschrift 1`–`6` | `Título 1`–`6` |
| `Normal` | `Standard` | *(déjà couvert : `Normal`)* |
| `BodyText` | `Textkörper` | `Texto independiente` |
| `Quote` | `Zitat` | `Cita` |
| `ListParagraph` | `Listenabsatz` | `Párrafo de lista` |
| `FootnoteText` | `Fußnotentext` | `Texto de nota al pie` |
| `EndnoteText` | `Endnotentext` (analogie) | `Texto de nota al final` (analogie) |
| `Title` | `Titel` | `Título` |
| `Subtitle` | `Untertitel` | `Subtítulo` |
| `Caption` | `Beschriftung` | `Título de ilustración` |

`NATIVE_CHARACTER_STYLE_NAMES` : ajout de `Énfasis` (espagnol) pour
`Emphasis`, seule entrée de style de caractère suffisamment confirmée.

**Volontairement exclu de cette passe**, faute de confirmation
suffisamment fiable :

- `IntenseQuote` en allemand et espagnol (aucune source directe trouvée ;
  candidats plausibles mais non corroborés : `Intensives Zitat`, `Cita
  intensa`). C'est la structure de citation poétique, cœur fonctionnel du
  projet (`AGENTS.md` §8) : une erreur ici serait la plus coûteuse possible,
  d'où un seuil de preuve plus élevé.
- `Strong`, `Hyperlink`, `FollowedHyperlink`, `FootnoteReference`,
  `EndnoteReference` en allemand (candidats non recoupés).
- Toute langue au-delà de l'allemand et l'espagnol (italien, portugais,
  néerlandais…) : non demandée, non recherchée.

Un style non couvert échoue toujours proprement en
`unsupported_paragraph_style`/`unsupported_character_style` (bloquant), donc
cette exclusion ne dégrade rien par rapport à l'état antérieur : elle laisse
simplement hors périmètre ce qui n'a pas pu être vérifié, au lieu de le
deviner.

Vérification de non-collision : `_name_table` lève une `AssertionError` au
chargement du module si un nom normalisé (casse, espaces, accents) est
associé à deux styles canoniques différents. Toutes les entrées ajoutées ont
été chargées sans déclenchement de cette garde.

## Conséquences

- Un document Word en allemand ou espagnol utilisant exclusivement les
  styles listés ci-dessus (hors citation poétique) est désormais reconnu
  au même titre qu'un document français ou anglais.
- Aucune régression possible sur les documents existants : seules de
  nouvelles associations nom→identifiant sont ajoutées, aucune existante
  n'est modifiée.
- Tests ajoutés dans `tests/test_native_style_resolution.py`
  (`test_german_word_style_names_resolve_through_canonical_names`,
  `test_spanish_word_style_names_resolve_through_canonical_names`),
  suivant le motif déjà établi pour le français.

## Limites assumées

- `EndnoteText` en allemand et espagnol repose sur une analogie non
  recoupée indépendamment (voir tableau) ; à confirmer contre une
  installation Word réelle ou une source faisant autorité avant d'en faire
  une garantie absolue.
- Aucun test contre un DOCX réellement produit par une installation Word en
  allemand ou espagnol : la vérification s'est faite par recherche
  documentaire, pas par corpus réel (cohérent avec `AGENTS.md` §5.2 : un
  corpus réel serait un ajout ultérieur, pas un prérequis à cette passe).
- `IntenseQuote` et les styles de caractère restants demeurent un travail
  futur explicite, pas un oubli.
