# ADR 0001 — Moteur Python et schémas Commons Publishing officiels

## Contexte

Mini-Métopes doit produire un pivot TEI consommable par Impressions, sans créer
un dialecte TEI local ni rendre Java, Saxon ou les TEI Stylesheets nécessaires à
l'exécution ordinaire.

## Décision

Le moteur, les diagnostics et la future lecture OOXML sont écrits en Python. Le
RNG officiel du noyau Commons Publishing est embarqué sans modification et
validé avec `lxml.RelaxNG`. Java, Saxon et les TEI Stylesheets restent des outils
de maintenance éventuels : régénération contrôlée du schéma, comparaison de
versions et contrôles approfondis.

> Le moteur est développé par Mini-Métopes ; le modèle TEI reste celui de
> Commons Publishing.

## Conséquences

La validation courante fonctionne hors réseau et indépendamment du répertoire
courant, grâce à `importlib.resources`. Elle vérifie Relax NG seulement ; les
règles Schematron présentes comme annotations dans le RNG ne sont pas exécutées
par `lxml.RelaxNG`.

Les futures couches resteront séparées : lecture OOXML, modèle éditorial,
normalisation, sérialisation TEI, validation normative, diagnostics éditoriaux
et intégration légère dans Impressions. Aucune de ces couches n'est encore
implémentée, hors validation.

## Limites

Le schéma est figé à sa provenance documentée. Une mise à jour exige un nouvel
audit, une provenance mise à jour et des tests de régression ; elle ne doit pas
être remplacée silencieusement par une compilation locale.

