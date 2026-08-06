# Contrat LaTEI / PURH pour Commons-Publishing Metopes

Ce document fixe le contrat minimal utilise par `purh_site/latei_metadata.py`
et le driver LaTEI experimental. Il ne decrit pas une TEI generique : il
documente les chemins Commons-Publishing / Metopes attestes dans le projet.

Le corps `*.latei_body.tex` reste la source reversible. Le `teiHeader` y est
conserve tel quel par `teiElement[name={teiHeader}]`; les metadonnees extraites
servent seulement au driver PDF LaTEI.

## Sources consultees

- `purh_site/site_structure.py` : extraction des metadonnees web/Zotero depuis
  le `teiHeader`.
- `purh_site/tei_to_model.py` : extraction des metadonnees du modele PDF stable.
- `tests/test_pdf_latex_compile.py` : fragment Metopes realiste avec
  `publicationStmt/ab[@type='book']` et
  `ab[@type='digital_download'][@subtype='PDF']`.
- `tests/test_zotero_metadata.py` : metadonnees Commons-Publishing exposees au
  site.
- `tests/test_reversible_real_metopes_fragments.py` : fallback reversible sur
  elements Metopes non specialises comme `forename`, `surname`, `availability`,
  `licence`.
- `tests/fixtures/metopes/heraldique_ii.book.normalized.xml` : fixture Metopes
  normalisee reelle produite par Impressions/PURH pour `Heraldique et papaute`.
  Elle atteste notamment `publicationStmt/ab[@type='book']`,
  `ab[@type='digital_download'][@subtype='PDF']`,
  `ab[@type='digital_download'][@subtype='EPUB']`, `graphic @url`,
  `div type='section1'`, `section2`, `section3`, `figure/head`, contenus
  mixtes et nombreux `xml:id`.
- `purh_site/reversible/TEI_COVERAGE.md` et
  `purh_site/reversible/LATEX_GRAMMAR.md` : contrat reversible LaTEI.
- `AUDIT_LATEI_PURH_CONVERGENCE.md` : audit de convergence stable PDF / LaTEI.

Non trouves dans le depot par recherche locale : `doc_table_corresp_commons.pdf`
et `Coeur_seul.xml`.

## Metadonnees

| Champ PURH/LaTEI | XPath Commons-Publishing / Metopes | Exemple reel observe | Usage PDF | Conservation round-trip | Statut |
| --- | --- | --- | --- | --- | --- |
| titre principal | `/tei:TEI/tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:title[@type='main']`; fallback documente: premier `title` du `titleStmt` | `Livre Metopes realiste` dans `tests/test_pdf_latex_compile.py` | `\PURHBookTitle`, page de titre, metadonnees PDF | `teiHeader` conserve dans le corps LaTEI | couvert |
| sous-titre | `/tei:TEI/tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:title[@type='sub']` | `Essai de structure PURH` | `\PURHBookSubtitle`, page de titre | conserve | couvert |
| auteur(s) | `/tei:TEI/tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:author` hors `@role='pbd'` | `author/persName/forename/surname` dans tests ajoutes; auteurs simples dans tests existants | contributeurs de titre si presents | conserve | couvert |
| editeur(s) scientifique(s) | `/tei:TEI/tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:editor` | `editor/persName/forename/surname` dans `tests/test_pdf_latex_compile.py` | contributeurs de titre | conserve | couvert |
| directeur(s) | `/tei:TEI/tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:author[@role='pbd']` | convention codee dans `site_structure.py` | contributeurs de titre | conserve | couvert |
| editeur / publisher | `/tei:TEI/tei:teiHeader/tei:fileDesc/tei:publicationStmt//tei:publisher` | `Presses universitaires de Rouen et du Havre` | `\PURHPublisher`, page de titre | conserve | couvert |
| lieu de publication | `/tei:TEI/tei:teiHeader/tei:fileDesc/tei:publicationStmt//tei:pubPlace` | `Rouen` dans `tests/test_pdf_latex_compile.py` | non imprime dans cette passe | conserve | extrait, usage PDF futur |
| annee/date de publication | priorite `publicationStmt//date[@type='publishing']/@when`, puis texte de la date, puis autre `date` | `date type="publishing" when="2026"` | `\PURHYear`, page de titre | conserve | couvert |
| ISBN papier | `publicationStmt/ab[@type='book']//idno[@type='ISBN-13' ou 'ISBN']` | `978-2-87775-000-0` | page de titre; fallback pour `\PURHISBN` si pas d'ISBN PDF | conserve | couvert |
| ISBN PDF | `publicationStmt/ab[@type='digital_download'][@subtype='PDF']//idno[@type='ISBN' ou 'ISBN-13']` | `978-2-87775-001-7` | `\PURHISBN`, page de titre | conserve | couvert |
| ISBN numerique/ePub | `publicationStmt/ab[@type='digital_download'][@subtype='EPUB']//idno[@type='ISBN-13' ou 'ISBN']` | bloc EPUB atteste dans `heraldique_ii.book.normalized.xml`, valeur vide dans cette fixture | aucun usage PDF dans cette passe | conserve | couvert si valeur presente |
| DOI | priorite `ab[@type='digital_download'][@subtype='PDF']//idno[@type='DOI']`, puis `ref[@type='DOI']`, puis DOI direct sous `publicationStmt` | `10.4000/purh.test-realiste` | `\PURHDOI`, page de titre | conserve | couvert |
| collection | `/tei:TEI/tei:teiHeader/tei:fileDesc/tei:seriesStmt/title[@level='s']`, puis premier `title` | `Collection essais` dans `tests/test_zotero_metadata.py` | preambule PURH stable | conserve | couvert |
| numero de collection | `seriesStmt/biblScope[@unit='volume' ou 'number' ou 'issue']` | `42` | preambule PURH stable | conserve | couvert |
| ISSN collection | `seriesStmt//idno[@type='ISSN']` | `2600-1111` | preambule PURH stable si pas d'ISSN livre | conserve | couvert |
| ISSN livre | `publicationStmt/ab[@type='book']//idno[@type='ISSN']` | `2427-0000` dans tests metadata/Zotero | preambule PURH stable | conserve | couvert |
| langue | `profileDesc/langUsage/language/@ident` | `fr` dans tests PDF | non imprime; utile PDF futur | conserve | couvert |
| resume | `profileDesc/abstract[@rend='resume']/p`, puis `abstract[@rend='abstract']/p` | resume dans `tests/test_pdf_latex_compile.py` | non imprime dans cette passe | conserve | couvert |
| mots-cles | non determine dans les sources consultees | non determine | aucun usage PDF | conserve par round-trip si present | non determine |
| droits/licence | non determine comme metadonnees de `teiHeader` dans les sources consultees | `availability/licence` seulement atteste comme element fallback hors extraction metadata dans `tests/test_reversible_real_metopes_fragments.py` | aucun usage PDF | conserve par round-trip si present | non determine |

## Rendu contextuel de `head`

| Contexte XML Metopes | Sens documentaire | Rendu PDF LaTEI provisoire | Conservation round-trip |
| --- | --- | --- | --- |
| `div type="chapter"` + `head` | titre de chapitre | `\chapter{...}` via contexte `teiDiv` | corps conserve `\teiHead{...}` |
| `div type="part"` + `head` | partie | non determine dans les sources de corps consultees; fallback sobre pour l'instant | conserve |
| `div type="section"` ou `section1` + `head` | section de niveau 1 | `\section{...}` | conserve |
| `div type="section2"` + `head` | section de niveau 2 | `\subsection{...}` | conserve |
| `div type="section3"` + `head` | section de niveau 3 | `\subsubsection{...}` | conserve |
| `front` + `head` | liminaire ou titre de division front | non determine pour un rendu definitif; fallback sobre | conserve |
| `back` + `head` | arriere-texte | non determine pour un rendu definitif; fallback sobre | conserve |
| `figure/head` | titre ou legende de figure | titre discret en gras dans `teiFigure` | conserve |
| `table/head` | titre de tableau | titre discret en gras dans `teiTable` | conserve |
| `listBibl/head` | titre de bibliographie | non determine; `listBibl` reste fallback generique | conserve |
| contexte inconnu | titre non interprete | rendu sobre en gras, non destructeur | conserve |

## Tableau des niveaux de titre XML

Synthese des deux conventions de titre attestees dans le depot : les
metadonnees `teiHeader` pour le livre entier, et `front/div[@type='titlePage']`
pour chaque contribution d'un ouvrage collectif (`group[@type='article']`).

| Niveau editorial | Element / attribut XML | Contexte | Rendu LaTEI actuel | Statut |
| --- | --- | --- | --- | --- |
| Titre de l'ouvrage | `teiHeader/fileDesc/titleStmt/title[@type='main']` | metadonnees du livre entier | `\PURHBookTitle`, page de titre | couvert |
| Sous-titre de l'ouvrage | `teiHeader/fileDesc/titleStmt/title[@type='sub']` | metadonnees du livre entier | `\PURHBookSubtitle`, page de titre | couvert |
| Titre de partie | `div[@type='part']` + `head` | corps, niveau le plus haut | non determine ; fallback sobre | a faire |
| Titre de chapitre | `div[@type='chapter']` + `head` | corps | `\chapter{...}` | couvert |
| Titre d'article / contribution | `group[@type='article']/front/div[@type='titlePage']/p[@rend='title-main']` | ouverture de contribution (ouvrage collectif) | `\lateiContributionTitle` (parbox 104 mm) | couvert |
| Sous-titre d'article / contribution | meme `titlePage`, `p[@rend='title-sub']` | idem | `\lateiContributionSubtitle` | couvert |
| Section niveau 1 (intertitre) | `div[@type='section']` ou `section1` + `head` | corps du chapitre/article | `\section{...}` | couvert |
| Section niveau 2 | `div[@type='section2']` + `head` | corps | `\subsection{...}` | couvert |
| Section niveau 3 | `div[@type='section3']` + `head` | corps | `\subsubsection{...}` | couvert |
| Bibliographie | `listBibl/head` | generalement en `back` ou fin d'article | non determine ; `listBibl` reste fallback generique | a faire |
| Tableau | `table/head` | corps | titre discret en gras dans `teiTable` | couvert (sobre) |
| Figure | `figure/head` | corps | titre/legende discret en gras dans `teiFigure` | couvert (sobre) |
| Index | aucune convention `div[@type='index']` observee dans le depot | - | non implemente | non determine |

Notes :

- `\tocdepth` est fixe a `0` : seules les entrees de partie et de
  contribution/chapitre apparaissent dans la table des matieres generee ;
  les sections de niveau 1/2/3 (intertitres) sont exclues du sommaire meme
  si elles produisent bien un titre visible dans le texte (voir
  `tests/test_latei_toc_depth_and_pagestyle.py`).
- "Partie", "bibliographie" et "index" sont marques **non determine** : le
  round-trip conserve le XML source sans le perdre, mais aucun rendu LaTeX
  dedie n'est encore defini pour ces niveaux.

## Regles de prudence

- Aucun champ extrait ne remplace le `teiHeader` original.
- Les champs absents restent vides.
- Les identifiants `idno` sont classes en Python d'apres `@type`, pour eviter
  les XPath `translate()` fragiles.
- Toute information non comprise doit continuer a traverser le round-trip via le
  noyau reversible et le fallback `teiElement`.
