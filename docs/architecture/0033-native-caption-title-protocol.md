# 0033 — Style natif `Caption` : protocole a deux paragraphes (titre + legende)

## Contexte

Suite directe de la demande initiale sur les styles natifs (point 5,
laissee en suspens apres 0027-0032) : « les titres et legendes d'image
[doivent utiliser] le style "Caption" [...] selon un protocole comparable
[a celui de Signature] : premiere ligne "Caption" = Titre de la figure,
seconde ligne "Caption" = Legende. »

Le style natif `Caption` etait deja reconnu (`figure_caption_style_ids`,
decision anterieure a cette serie) mais uniquement comme legende : un seul
paragraphe `Caption` immediatement apres l'image devenait `<p
rend="caption">`, sans notion de titre. Le titre de figure n'existait
jusqu'ici que via le style **controle** `TEIfiguretitle`
(`w:customStyle="1"`, obligatoire avant l'image) — cf.
`docs/conventions/native-word-to-tei-v0.2.md`.

## Decision

### Protocole a deux paragraphes (`editorial/builder.py::_build_figure_if_supported`)

Apres une image, si **deux** paragraphes `Caption` natifs se suivent
immediatement (et qu'aucun titre n'a deja ete fourni par un
`TEIfiguretitle` precedent l'image) :
- le **premier** devient le titre de la figure (`<head>`, meme chemin de
  serialisation que `TEIfiguretitle`) ;
- le **second** devient la legende (`<p rend="caption">`, comportement
  inchange).

Si un **seul** paragraphe `Caption` suit l'image, le comportement
d'origine est preserve integralement : legende seule, aucun titre —
retro-compatibilite explicite, aucune migration necessaire pour les
documents existants qui n'utilisent qu'une legende.

Le protocole calque celui de `Signature` (decision 0028) : le nombre de
paragraphes consecutifs du meme style natif determine leur role (1 ligne
= un role ; 2 lignes = deux roles distincts, dans un ordre fixe).

### Non-ambiguite avec le titre controle

Si un titre a deja ete fourni par le style controle `TEIfiguretitle`
avant l'image, le protocole a deux paragraphes ne s'applique pas : au
plus un paragraphe `Caption` est consomme comme legende (comportement
d'origine). Un second `Caption` immediatement apres resterait alors non
consomme et declencherait le diagnostic existant
`orphan_figure_caption_not_serializable` au tour de boucle suivant —
signale, jamais perdu silencieusement.

### Reutilisation, aucun nouveau code de serialisation

`_build_figure_text_paragraph` (deja utilisee pour `TEIfiguretitle`) est
reutilisee telle quelle avec `role_name="title"` : memes diagnostics
(`numbered_figure_title_not_serializable`,
`image_in_figure_title_not_serializable`, etc.), meme validation cote
serializer (`empty_figure_title_not_serializable`,
`unsupported_paragraph_rendition`). Aucun changement dans
`tei/serializer.py` ni dans le modele `EditorialFigure` (le champ
`title` existait deja, alimente jusqu'ici uniquement par
`TEIfiguretitle`).

## Methodologie d'ecriture (a documenter pour les autrices/auteurs)

Pour une figure avec titre et legende, sans recourir a un style
personnalise :
1. Inserer l'image (paragraphe `Normal`/vide contenant le dessin).
2. Juste apres, un premier paragraphe style `Caption` : le **titre** de
   la figure.
3. Juste apres, un second paragraphe style `Caption` : la **legende**.

Pour une legende seule (sans titre), un seul paragraphe `Caption` apres
l'image suffit, comme auparavant.

## Consequences

- 476 passed apres ajout. Tests dedies :
  `test_two_consecutive_native_captions_become_figure_title_and_caption`,
  `test_single_native_caption_still_becomes_a_caption_only`
  (`tests/test_figures.py`).
- Le style controle `TEIfiguretitle` reste disponible et documente pour
  les cas ou l'autrice/auteur prefere placer le titre **avant** l'image
  plutot qu'apres (aucun retrait de fonctionnalite).

## Limites assumees

- Le protocole ne s'applique qu'aux paragraphes `Caption` **natifs**
  (`w:customStyle` absent ou faux) ; le style controle
  `TEIfigurecaption` reste un canal separe a un seul paragraphe, sans
  notion de titre associee.
- Une figure avec titre voulu et legende voulue doit imperativement avoir
  les deux paragraphes `Caption` consecutifs, sans paragraphe interposé ;
  un paragraphe non-Caption entre les deux romprait le protocole (le
  premier deviendrait alors une legende seule, comportement du paragraphe
  isole).
