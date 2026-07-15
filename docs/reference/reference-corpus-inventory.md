# Inventaire du corpus de référence

## Méthode et précautions

`references/` a été inspecté en lecture seule. Les quatre archives ont été
listées sans extraction durable ; l'archive normative et trois couples
DOCX/XML ont été extraits seulement dans des répertoires temporaires. Aucun
fichier de référence n'a été modifié ni copié dans les tests.

Les corpus contiennent des noms d'auteurs, des textes éditoriaux complets, des
images haute résolution, des PDF/InDesign et des métadonnées éditoriales. Ils
doivent être considérés comme potentiellement confidentiels ou soumis à droits :
aucun contenu substantiel ne sera versionné comme fixture sans décision et
anonymisation.

| Archive | Taille | Contenu et rôle probable | Intérêt fixtures |
| --- | ---: | --- | --- |
| `normative/tei-commons-publishing.zip` | 3,1 Mio | Clone Git officiel : 6 ODD, 5 RNG, 1 XSD, documentation, exemple TEI, licences | Autorité normative, pas fixture de conversion |
| `coeur_seul.zip` | 0,6 Mio | 9 DOCX `styles/`, 9 XML d'unités et `XML/Coeur_seul.xml` (volume) | Couples sobres : titres, paragraphes, citations, notes, bibliographie |
| `dissimuler.zip` | 46,1 Mio | 14 DOCX, 12 XML de chapitres et `Dissimuler_LIVRE.xml`, 21 INDD, 5 PDF et 2 images | Corpus de livre avec vers, notes, citations et production PAO |
| `beautes_vitales_XML.zip` | 415,0 Mio | 23 DOCX, 23 XML d'unités et `Beautes_vitales.xml`, 35 TIFF, 1 JPG | Corpus riche : figures, notes, citations et poésie ; très lourd |

## Couples DOCX/XML

Les couples de même racine dans les répertoires `styles/` et `XML/xml/` sont
des candidats structurés, non une preuve automatique. Trois ont été contrôlés
par titre, intertitres, paragraphes distinctifs, auteur/affiliation, notes et
organisation ; ils sont **certains**. Les autres couples à racine identique
sont **probables** : leurs noms, cardinalités et volumes concordent, mais ils
n'ont pas encore reçu la comparaison interne complète.

| Ensemble | Correspondance | Confiance | Indices contrôlés |
| --- | --- | --- | --- |
| Cœur seul | `styles/ch_003_chap_1.docx` ↔ `XML/ch_003_chap_1.xml` | certain | sur-titre, titre, premier intertitre et deux paragraphes distinctifs ; 46 appels de notes dans DOCX / 46 notes TEI |
| Dissimuler | `travail_xml/styles/chap_11_L_oeil_du_pouvoir_Locus_politicus.docx` ↔ `travail_xml/xml/chap_11_L_oeil_du_pouvoir_Locus_politicus.xml` | certain | titre, sous-titre, auteur, affiliation, premiers paragraphes, 50 notes et 20 groupes de vers / 243 vers dans le XML |
| Beautés vitales | `Travail_XML/Styles/Ch09_poetique_jardin_japonais_Bonnin.docx` ↔ `Travail_XML/XML/Ch09_poetique_jardin_japonais_Bonnin.xml` | certain | titre, auteur, affiliation, paragraphes initiaux et intertitres ; 34 notes et 13 `lg` / 51 `l` |
| Cœur seul | huit autres paires `ch_000` à `ch_008` | probable | même découpage et noms correspondants ; volume `Coeur_seul.xml` |
| Dissimuler | douze paires `chap_1` à `chap_12` | probable | même découpage et noms correspondants ; volume `Dissimuler_LIVRE.xml` |
| Beautés vitales | 22 autres paires `Ch00` à `Ch22` | probable | même découpage et noms correspondants ; volume `Beautes_vitales.xml` |

Les fichiers de titre, table des matières ou volume sans pendant homonyme ne
sont pas classés comme couples : `pages_titre_Locus_politicus.docx` et
`TDM_Locus_politicus.docx` sont seulement des candidats de structure de livre.

## Observations OOXML ponctuelles

| DOCX représentatif | Styles et phénomènes observés |
| --- | --- |
| `ch_003_chap_1.docx` | `TEItitlesup`, `Titre`, `Titre1`, `Titre2`, `TEIquote`, `TEIepigraph`, `TEIparagraphconsecutive`; 46 notes ; gras, italiques, petites capitales, exposants/indices et styles de caractère |
| `chap_11_…Locus_politicus.docx` | `Titre`, `TEItitlesub`, `Titre1`, `TEIquote`, `TEIverse`; 50 notes, 223 retours manuels, 20 paragraphes de vers ; gras/italique/petites capitales/exposants |
| `Ch09_…Bonnin.docx` | `Titre`, `Titre1`, `TEIauthoraut`, `TEIauthorityaffiliation`, `TEIquote`, `TEIverse`, groupes de figures ; 34 notes, 38 retours manuels, 2 signets et styles inline |

Ces trois documents contiennent `word/footnotes.xml`, `word/endnotes.xml`,
`word/numbering.xml` et les relations de `document.xml`. Aucun n'a de tableau,
hyperlien ou dessin dans l'échantillon inspecté. Les corpus XML, en revanche,
montrent aussi figures, listes, références et tableaux selon les unités.

## Phénomènes visibles à retenir

Les XML montrent abondamment titres hiérarchisés, paragraphes, citations,
notes, liens/références et enrichissements `hi`. Les candidats les plus riches
sont `Ch09` (vers et figures), `chap_11` (poésie dense) et les chapitres de
Cœur seul (citations et notes). Les styles affichés sont spécifiques à Métopes,
ce qui confirme qu'une future reconnaissance devra s'appuyer sur les identifiants
OOXML et une convention explicitement approuvée, non sur les libellés seuls.
