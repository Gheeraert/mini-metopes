# Candidats de futures fixtures

Cette liste est un plan de réduction, non une extraction automatique. Toute
fixture définitive devra recevoir un test, une provenance, une anonymisation si
nécessaire et ne conserver que le phénomène concerné.

## A. Fixtures normatives créées maintenant

Les fichiers de `tests/fixtures/xml/` sont synthétiques et ne dérivent pas du
corpus : TEI minimale, citation en prose, citation poétique avec un `lg`, deux
strophes, citation poétique avec `lg` vide (invalide) et XML mal formé.

Les extensions normatives à ajouter ultérieurement, toujours sous forme XML
minimale et synthétique, sont : note de bas de page, figure/`graphic`, tableau
`table`/`row`/`cell`, liste bibliographique et bibliographie structurée. Elles
ne doivent être ajoutées qu'après avoir isolé la forme minimale autorisée par le
RNG du noyau.

## B. Futures fixtures de conversion

| Priorité | Source de référence | Phénomène à isoler | Réduction / résultat TEI attendu |
| --- | --- | --- | --- |
| haute | `beautes_vitales_XML.zip: Travail_XML/Styles/Ch09_poetique_jardin_japonais_Bonnin.docx` | Vers, strophes, retours manuels, notes dans un chapitre poétique | DOCX neuf réduit et anonymisé ; `cit`/`quote`/`lg`/`l` et `note` explicitement attendus |
| haute | `dissimuler.zip: travail_xml/styles/chap_11_L_oeil_du_pouvoir_Locus_politicus.docx` | 20 blocs `TEIverse`, 223 retours manuels et 50 notes | Cas neuf de quelques lignes : distinguer retour visuel et fin de vers, conserver strophes |
| haute | `coeur_seul.zip: styles/ch_003_chap_1.docx` | Titres hiérarchiques, épigraphes, citations, notes et styles inline | Cas réduit sans texte source ; `div`/`head`, `cit`, `note`, `hi` attendus |
| moyenne | `beautes_vitales_XML.zip: Travail_XML/Styles/Ch05_formes_diversit‚_beaut‚_Cohen.docx` | Figures multiples et une liste | Recréer une figure et une liste fictives ; vérifier le modèle, pas les médias réels |
| moyenne | `beautes_vitales_XML.zip: Travail_XML/Styles/Ch08_beautes_minerales_Nectoux.docx` | Plusieurs figures | Extraire uniquement la structure de figure, sans images ni légendes réelles |
| moyenne | `coeur_seul.zip: styles/ch_008_bibliographie.docx` | Bibliographie et mises en forme | Entrées bibliographiques inventées ; `listBibl` et `bibl` attendus |
| moyenne | `dissimuler.zip: travail_xml/styles/TDM_Locus_politicus.docx` | Table des matières / unités de livre | Examiner avant toute convention ; aucun résultat TEI présumé |

## Décisions de provenance

Avant de créer une fixture DOCX, noter dans un manifeste : chemin exact de
l'archive, réduction pratiquée, phénomène conservé, contenu remplacé ou
anonymisé, résultat TEI décidé et test associé. Les trois corpus sont éditoriaux
et contiennent des données potentiellement protégées : la recréation synthétique
est la voie privilégiée.
