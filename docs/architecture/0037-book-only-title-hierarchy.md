# 0037 — Livre entier uniquement : hiérarchie de titres compatible Impressions

*Remplace la décision 0032 (hiérarchie Titre1=chapitre autonome/Titre2=section/
Titre3=contribution), retirée sans rétrocompatibilité.*

## Contexte

Nouveau contrat du projet : Mini-Métopes ne produira plus jamais de XML pour
un article ou un chapitre isolé, uniquement des livres entiers. La gestion
des titres doit être reconstruite en conséquence, **et rendue compatible
avec « Impressions »**, le pipeline aval (PDF/LaTEI) qui consomme cette TEI.
La référence de vérité est `docs/architecture/METOPES_COMMONS_LATEI_CONTRACT.md`,
en particulier son « Tableau des niveaux de titre XML ».

## Blocage identifié et résolu : incompatibilité du RNG embarqué

Le schéma RelaxNG embarqué (`commons-publishing.rng`) était incompatible
avec le contrat Impressions tel quel :

- `div/@type` était une liste fermée (`abstract, ack, appendix,
  bibliography, correction, dedication, reviewed, section1`–`section6`)
  sans `chapter`, `part`, ni `titlePage`.
- `p/@rend` était fermé à `break, consecutive, caption, credits`, sans
  `title-main`/`title-sub`.
- `<text>` n'admettait qu'un seul `<body>` (choix à une seule option) —
  `<group>` n'était pas défini du tout, rendant structurellement
  impossible la forme « ouvrage collectif = plusieurs `<text>` groupés,
  chacun avec sa page de titre ».

**Décision** : extension du RNG embarqué (`PROVENANCE.json` mis à jour,
`local_modifications: true`), en s'appuyant exclusivement sur la
sémantique standard TEI P5 (`group`, `titlePage`-comme-div-typé, ces
valeurs de `@type`/`@rend`) — pas d'invention, un simple retour à des
pièces standard omises par cette version ODD-générée du profil Commons
Publishing :

1. `div/@type` : ajout de `part`, `chapter`, `titlePage`.
2. `p/@rend` : ajout de `title-main`, `title-sub`.
3. Nouvel élément `<group>` (modèle TEI P5 standard `front?, (text+ |
   group+), back?`, attribut `type` en `token` libre — seule la valeur
   `article` est attestée par le contrat, rien n'indique une liste close
   côté TEI Guidelines).
4. `model.resource` étendu (`text | group`, classe TEI standard).
5. `<text>` admet désormais `body` **ou** `group`.

Vérifié par `tests/test_rng_schema_extensions.py` (nouvelles valeurs
acceptées, cas négatif prouvant que le reste de l'énumération reste
fermé).

## Nouvelle hiérarchie de titres (aucune rétrocompatibilité)

| Niveau Word | Rôle | Sortie TEI |
| --- | --- | --- |
| Titre1 | partie du livre, facultative | `div type="part"` |
| Titre2 | pivot : chapitre (monographie) ou contribution (ouvrage collectif) | `div type="chapter"` ou `group type="article"`/`text`/`front`/`div type="titlePage"` |
| Titre3–Titre6 | sections internes | `div type="section1"`–`section4` |

Titre6 → `section4` est une extrapolation assumée du motif (le schéma
admet déjà `section4`–`section6`, mais aucune ligne du contrat ne couvre
ce niveau explicitement) — signalée comme telle dans le code
(`tei/serializer.py::_MONOGRAPH_DIV_TYPES`), pas présentée comme un fait
du contrat.

`heading_style_ids` (Heading1..6 → niveau 1..6, `editorial/convention.py`)
reste inchangé : c'est un fait Word, pas une décision de forme TEI. Seule
la signification des niveaux, côté sérialisation, change.

## Détection monographie / ouvrage collectif : automatique, structurelle

Aucun champ manuel, aucun menu déroulant (cohérent avec le retrait du menu
`document_type`, voir décision 0038) : `tei/serializer.py::_is_collective_work`
compte les titres de niveau 2 dans `document.blocks` — **2 ou plus**
déclenchent la forme collective, **0 ou 1** gardent la forme monographie.

### Forme monographie

`_append_body_blocks` assigne `@type` par niveau
(`_MONOGRAPH_DIV_TYPES`) lors de la création de chaque `<div>`. Aucun
changement de la structure d'imbrication elle-même (pile `divisions`
existante).

### Forme ouvrage collectif

`_split_into_contributions` découpe `document.blocks` à chaque titre de
niveau 2 ; `_append_collective_group` construit `<group type="article">`
puis, par contribution : `<text><front><div type="titlePage">
<p rend="title-main">{titre}</p></div></front><body>…</body></text>`. Le
contenu du corps réutilise `_append_body_blocks` avec un nouveau
paramètre `base_level=2` : les titres de niveau 3+ y gardent leur `@type`
absolu (`section1`+) mais l'imbrication redémarre localement, sans quoi
les niveaux 1/2 déjà consommés (partie/pivot) auraient généré des `<div>`
anonymes de padding superflus.

### Edge case : partie contenant un ouvrage collectif

TEI n'admet pas `<text>`/`<group>` comme enfant de `<div>` : une partie
(Titre1) ne peut donc pas contenir plusieurs contributions sous le modèle
standard. Refusé explicitement (`part_with_collective_work_not_serializable`,
bloquant) plutôt qu'une tentative de repli silencieux ou une redéfinition
plus large de la racine du document, hors périmètre de cette passe.

## Seuil de terminaison de Signature

`_signature_run_is_terminal` (`editorial/builder.py`) : le seuil passe de
`heading_level <= 3` à `<= 2` — Titre3 est désormais une section interne
à la contribution, plus une frontière. Docstring et message du diagnostic
`misplaced_signature_not_serializable` mis à jour en conséquence.

## Ce qui ne change pas

- `_extract_final_bibliography`/`_preceding_heading_index` : déjà
  agnostiques au niveau de titre, aucun changement.
- `_append_bibliography` : déjà `<div type="bibliography">`, déjà valide.
- Le mécanisme Signature (extraction du nom, contrôle de cohérence contre
  `contributors`) reste inchangé dans son principe.
- Pas de métadonnées structurées par contribution : le contrat ne montre
  l'auteur qu'au niveau `teiHeader` du livre entier ; la correspondance
  signature ↔ `contributors` (déjà en place) reste le seul mécanisme de
  rattachement auteur↔contribution.

## Conséquences

- 494 passed après la passe titres/structure (avant la suppression de
  `document_type`, décision 0038). Nouveaux fichiers de test :
  `tests/test_rng_schema_extensions.py`, `tests/test_book_title_hierarchy.py`.
  Golden fixtures `tests/fixtures/corpus/*/expected.xml` régénérées et
  vérifiées diff par diff (uniquement l'ajout de `@type`, structure
  inchangée).
- `tests/test_editorial_signatures.py` : tests liés à l'ancien seuil
  Titre1-3 réécrits pour la nouvelle sémantique (Titre3 refusé au lieu
  d'accepté ; nouveaux cas Titre1/Titre2 acceptés) ; le test de nesting
  Section>Contribution de la décision 0032 est retiré, remplacé par la
  couverture group/text/titlePage de `test_book_title_hierarchy.py`.

## Limites assumées

- Pas de sous-titre de contribution (`p rend="title-sub"`) : aucune
  convention d'écriture Word ne l'indique encore ; documenté comme limite
  assumée plutôt que deviné.
- Partie + ouvrage collectif refusé explicitement, pas résolu
  structurellement (nécessiterait une refonte plus large de la racine du
  document, hors périmètre).
