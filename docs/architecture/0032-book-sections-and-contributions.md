# 0032 — Livre a plusieurs contributions : Titre2/Titre3, Signature par contribution

**Statut : remplacee par la decision 0037** (hierarchie de titres
compatible Impressions, livre entier uniquement, aucune retrocompatibilite).
Conservee comme archive historique.

## Contexte

Le test sur le manuscrit reel (decisions 0030/0031) a mis en evidence
qu'un DOCX peut representer, au-dela du cas « un DOCX = un chapitre »
documente jusqu'ici, **un livre entier ou un extrait multi-chapitres** :
titre du livre, editeurs, plusieurs contributions (recueil collectif) ou
chapitres (monographie), eventuellement regroupes en sections, une
bibliographie generale terminale (0026/0030/0031).

L'utilisateur a demande de reserver deux niveaux de titre Word pour cet
usage :
- **Titre2** = section du livre (regroupe plusieurs contributions) ;
- **Titre3** = titre de contribution (recueil collectif) ou de chapitre
  (monographie) ;

en confirmant explicitement que **Titre1 reste pleinement valide** comme
titre d'un chapitre/article autonome (usage actuel, aucune regression) —
« les deux usages coexistent, Titre1 = titre de chapitre standalone ».

Consequence directe : la **Signature** (0028/0031), jusqu'ici unique et
terminale pour tout le document, doit pouvoir apparaitre **une fois par
contribution**, terminale par rapport a la contribution qui precede, et
etre verifiee contre `metadata.json` pour chaque occurrence — confirme
explicitement par l'utilisateur. La bibliographie generale du livre reste
en revanche unique et terminale pour tout le document (« en Titre1, elle
est forcement la bibliographie generale du livre : il n'y a donc pas
d'ambiguite »), sans changement par rapport a 0026/0030/0031.

## Decision

### 1. Aucune detection de mode « livre » n'est codee

Le mecanisme d'imbrication `<div>` par niveau de titre
(`tei/serializer.py::_append_body_blocks`) est deja entierement generique :
il empile/depile des divisions selon le seul niveau numerique du titre,
sans aucune semantique par niveau. Titre2 suivi de Titre3 s'imbrique donc
deja correctement (`<div><head>Section</head><div><head>Contribution
</head>...</div></div>`) sans aucun changement de code. Une contribution
demarrant directement en Titre3 sans Titre2 (monographie sans sections)
declenche deja le diagnostic informatif existant `heading_level_jump`
(non bloquant) et produit des `<div>` anonymes intermediaires —
comportement deja implemente et teste, pas nouveau.

Consequence assumee : la reservation Titre2/Titre3 est une **convention
d'ecriture documentee** (README, `docs/conventions/`), pas une regle
bloquante. Rien n'empeche techniquement un Titre1 a l'interieur d'un
fichier structure comme un livre ; c'est a la charge de l'auteur du
manuscrit de suivre la convention.

### 2. Signature terminale par contribution (`editorial/builder.py`)

Nouvelle fonction `_signature_run_is_terminal(paragraphs, run_end,
convention)` : un bloc `Signature` est terminal en fin de document, **ou**
juste avant un titre de niveau 1 a 3. Un titre de niveau 4 ou plus reste
une sous-section de la meme contribution : la signature ne peut pas le
preceder. Remplace l'ancienne condition stricte `run_end ==
len(paragraphs)` dans le calcul de `valid_position`. Le comportement pour
un document a contribution unique est inchange (la fin de document reste
valide) — aucune regression sur les tests de 0028/0030/0031.

### 3. Suggestions et coherence multi-signatures

`MetadataSuggestions.signature_name`/`signature_affiliation` (singuliers)
remplaces par `signatures: tuple[SignatureSuggestion, ...]`
(`metadata/model.py`). `extract_metadata_suggestions`
(`metadata/extraction.py`) scanne desormais tout le document et retourne
une entree par suite valide de paragraphes `Signature` (memes regles :
au plus deux lignes, terminale par rapport a la contribution). Detection
volontairement independante de celle du builder (ne depend pas du systeme
complet de convention/role, seulement de
`NATIVE_WORD_CONVENTION.heading_style_ids`) — coherent avec le couplage
deja accepte pour Title/Subtitle dans ce fichier.

`metadata_consistency_issues` (`metadata/merge.py`) boucle sur
`suggestions.signatures` et emet un `signature_contributor_not_in_metadata`
par entree non appariee, avec un chemin distinct
(`f"signatures[{index}]"`) afin que la deduplication d'avertissements
cote GUI (`gui/metadata_controller.py`) n'ecrase pas des avertissements
concernant des signatures differentes.

## Consequences

- 474 passed apres ajout. Tests dedies : signature suivie d'un Titre3
  (`test_signature_followed_by_a_titre3_contribution_heading_is_accepted`),
  d'un Titre2
  (`test_signature_followed_by_a_titre2_section_heading_is_accepted`),
  refus si suivie d'un Titre4
  (`test_signature_followed_by_a_titre4_subsection_heading_is_refused`),
  bout-en-bout deux contributions avec structure `<div>` imbriquee
  verifiee
  (`test_multi_contribution_book_serializes_nested_divs_and_both_signatures`),
  suggestions et coherence multiples
  (`test_extraction_reads_one_signature_per_contribution`,
  `test_consistency_check_warns_per_unmatched_signature_with_distinct_paths`).
- Aucun changement de schema, de serializer, ni de modele
  `document_type` : le seul changement structurel necessaire portait sur
  la Signature.

## Limites assumees

- La convention Titre2=section/Titre3=contribution n'est pas
  bloquante : un manuscrit qui ne la suit pas ne produit aucune erreur
  dediee, seulement la structure `<div>` que ses niveaux de titre
  induisent mecaniquement (eventuellement accompagnee du diagnostic
  generique `heading_level_jump`).
- La detection des suggestions de signature dans `metadata/extraction.py`
  duplique volontairement, en plus simple, la logique de terminaison du
  builder (pas de dependance au systeme complet de roles) : limite deja
  acceptee pour Title/Subtitle dans ce meme fichier.
- Pas de nouvelle valeur `document_type` (« book ») ni d'attribut `@type`
  distinctif sur les `<div>` de section/contribution : rien dans le
  comportement ne branche dessus, et le schema TEI Commons Publishing n'a
  pas de valeur adaptee dans sa liste fermee pour `@type`.
