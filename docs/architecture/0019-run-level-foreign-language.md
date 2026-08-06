# 0019 — Langue déclarée au niveau du run (`xml:lang`)

## Contexte

Un audit du dépôt a signalé l'absence de tout mécanisme portant la langue
d'un passage inline : `w:lang` (déclaré par Word sur chaque run, le plus
souvent via la langue de correction) n'était lu nulle part dans
`docx/inspector.py`, et rien dans le modèle éditorial ni la sérialisation TEI
ne permettait de distinguer un mot ou une phrase cité en langue étrangère du
reste du texte. Pour des ouvrages en lettres et sciences humaines, citer en
langue originale (latin, grec, anglais, allemand...) au sein d'un texte en
français est courant ; cette absence était une vraie lacune, pas un détail.

`AGENTS.md` interdit de créer un dialecte TEI local sans décision
documentée. Le schéma Commons Publishing embarqué (`commons-publishing.rng`)
a été inspecté avant tout choix : il **ne définit pas `<foreign>`** (absent
du grammar réduit). En revanche `<hi>` y est explicitement documenté comme
couvrant, entre autres, *« Foreign Words, and Unusual Language »* (§3.3.2 des
TEI Guidelines, cité dans l'annotation du `<define name="hi">`), et accepte
`att.global.attribute.xmllang` — donc `@xml:lang` — en plus de `@rend`. C'est
le mécanisme déjà prévu par le profil, pas une extension inventée.

## Décision

- `docx/model.py` : `RunInfo` gagne un champ `language: str | None`.
- `docx/inspector.py` : `_read_run` le lit via `w:rPr/w:lang/@w:val`, avec
  la même fonction `_child_value` déjà utilisée pour `rStyle`/`vertAlign`
  (aucune lecture ad hoc, aucun regex).
- `editorial/model.py` : `TextSpan` gagne le même champ `language`. Le
  fusionnement de runs adjacents (`_append_inline` dans
  `editorial/builder.py`) compare désormais aussi `language`, en plus de
  `marks` et `link`, pour ne jamais fusionner deux runs déclarés dans des
  langues différentes en un seul span.
- `tei/serializer.py` : un `TextSpan` dont la langue diffère de
  `metadata.language` (sur la **sous-étiquette primaire** uniquement, ex.
  `fr` dans `fr-FR`) est enveloppé dans `<hi xml:lang="...">`, même sans
  autre marque typographique. La comparaison sur la sous-étiquette primaire
  évite de traiter `fr-FR` (réglage courant de Word) comme étranger dans un
  document déclaré `fr` — un faux positif aurait rendu la fonctionnalité
  inutilisable en pratique, la quasi-totalité des runs Word portant une
  langue explicite.
- Sans métadonnées (`metadata=None`), aucune supposition n'est faite : la
  langue déclarée sur un run n'est jamais utilisée pour deviner ce qui est
  « étranger ». C'est un choix délibéré de ne pas deviner une convention non
  approuvée (`AGENTS.md` §17).

## Conséquences

- Nouvelle donnée disponible sans changement de comportement pour les
  documents qui n'en tirent pas parti : un DOCX sans `w:lang` déclaré, ou
  dont toutes les langues de run correspondent au document, produit une TEI
  identique à avant cette décision.
- La détection reste conservatrice : elle ne bloque jamais la conversion,
  elle enrichit seulement la TEI produite (pas de nouveau diagnostic
  bloquant introduit par cette passe).

## Limites assumées

- Seule la langue déclarée au niveau du run (`w:rPr/w:lang`) est lue ; la
  langue de paragraphe par défaut issue de `w:docDefaults`/`w:pPrDefault`
  n'est pas résolue. Un run sans `w:lang` explicite (rare en pratique, Word
  en ajoute systématiquement lors de la saisie) n'est jamais traité comme
  étranger.
- La comparaison ne couvre que la sous-étiquette primaire ; deux variantes
  régionales réellement distinctes de la même langue (ex. `fr` vs `fr-CA`
  dans un contexte où cette distinction serait éditorialement pertinente) ne
  sont pas différenciées. Cela n'a pas été jugé pertinent pour l'usage visé
  (citations en langue étrangère), qui se joue au niveau de la langue, pas
  de la variante régionale.
- `w:lang` porte potentiellement trois attributs (`val` pour le latin,
  `eastAsia`, `bidi`) ; seul `val` est lu, cohérent avec le périmètre latin
  du projet.
