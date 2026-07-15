# Mini-Métopes — Instructions du dépôt

## 1. Mission du projet

Mini-Métopes est un projet Python autonome destiné à convertir des documents `.docx` éditorialement structurés vers une TEI conforme au modèle **Commons Publishing**.

La chaîne cible est :

```text
DOCX
→ lecture OOXML
→ modèle éditorial Python intermédiaire
→ TEI Commons Publishing
→ validation normative
→ diagnostics éditoriaux
```

Mini-Métopes produit le pivot éditorial TEI.

Il ne prend pas en charge les transformations situées en aval, notamment :

- génération du site HTML ;
- génération LaTEI ;
- composition PDF ;
- génération EPUB ;
- publication du livre.

Ces responsabilités appartiennent au projet Impressions ou à d’autres applications consommatrices.

Mini-Métopes doit toutefois exposer, à terme, une API Python et une CLI permettant son intégration dans Impressions sans couplage fort.

---

## 2. Principes d’architecture

### 2.1 Moteur Python, norme externe

La logique de conversion et les diagnostics sont développés en Python.

Le vocabulaire TEI, les structures autorisées et la validité du résultat sont déterminés par les schémas officiels Commons Publishing.

Principe directeur :

> Le moteur est développé par le projet ; la TEI ne l’est pas.

Ne crée pas de dialecte TEI local sans décision explicite et documentée.

Ne modifie jamais silencieusement un schéma officiel.

### 2.2 Pas de Java ou Saxon à l’exécution

Java, Saxon et les TEI Stylesheets ne doivent pas être des dépendances nécessaires à l’utilisation normale de Mini-Métopes.

Ils peuvent être utilisés dans une chaîne de maintenance ou d’intégration continue pour :

- compiler un ODD ;
- régénérer les schémas ;
- produire la documentation ;
- effectuer une validation approfondie ;
- comparer deux versions du standard.

La validation courante doit pouvoir fonctionner en Python à partir des schémas officiels embarqués.

### 2.3 Modèle intermédiaire obligatoire

Ne transforme pas directement les paragraphes DOCX en éléments XML au moyen d’une longue suite de conditions.

La conversion devra passer par un modèle éditorial Python explicite et testable.

Exemples futurs de concepts :

- document ;
- unité éditoriale ;
- section ;
- paragraphe ;
- contenu inline ;
- citation ;
- citation poétique ;
- strophe ;
- vers ;
- liste ;
- note ;
- figure ;
- tableau ;
- référence bibliographique.

Ne crée pas toutes ces classes prématurément. Introduis-les au fur et à mesure des besoins établis.

### 2.4 Séparation des responsabilités

Conserve une séparation nette entre :

1. lecture du DOCX et de l’OOXML ;
2. reconstruction du modèle éditorial ;
3. normalisation ;
4. diagnostics ;
5. sérialisation TEI ;
6. validation normative ;
7. interface en ligne de commande ;
8. future intégration dans une interface graphique.

---

## 3. Référence normative

Le dossier :

```text
references/
```

contient notamment une copie du dépôt officiel TEI Commons Publishing.

La cible normative principale est le **noyau Commons Publishing**, non l’extension Métopes.

L’ODD, le RNG, les exemples et la documentation doivent être inspectés avant toute décision de modélisation.

La hiérarchie d’autorité est la suivante :

1. schéma officiel Commons Publishing retenu et versionné ;
2. ODD source correspondant ;
3. documentation officielle ;
4. exemples officiels valides ;
5. corpus éditorial réel ;
6. sorties produites par Métopes.

Une sortie Métopes réelle ne constitue jamais, à elle seule, la preuve qu’une structure est :

- valide ;
- recommandée ;
- nécessaire ;
- sémantiquement correcte.

Les XML Métopes servent à comprendre les pratiques, les cas rencontrés et les compatibilités attendues. Ils ne doivent pas être reproduits servilement.

---

## 4. Politique du dossier `references/`

Le dossier `references/` est un corpus documentaire et expérimental.

Il peut contenir :

- le dépôt Commons Publishing archivé ;
- des documents Word stylés ;
- des XML produits par Métopes ;
- des couples DOCX/XML ;
- des livres ou chapitres éditoriaux réels ;
- de la documentation technique.

### Règles impératives

- Considère `references/` comme **en lecture seule**.
- Ne modifie, ne renomme et ne reformate aucun fichier de référence.
- N’écrase jamais une sortie XML existante.
- N’extrais pas durablement une archive complète dans le dépôt sans nécessité.
- Utilise un dossier temporaire pour les inspections.
- N’inclus pas `references/` dans le paquet Python ni dans la wheel.
- N’utilise pas les gros corpus comme dépendances des tests unitaires ordinaires.
- Ne copie pas un document éditorial complet dans `tests/fixtures/`.
- Signale tout problème de licence, de confidentialité ou de taille avant de proposer de versionner un corpus réel.

Lorsque des documents DOCX et XML semblent correspondre, établis la relation par inspection et non par simple ressemblance de nom.

---

## 5. Politique des fixtures

Les fixtures doivent être :

- petites ;
- stables ;
- lisibles ;
- ciblées sur un comportement ;
- indépendantes les unes des autres autant que possible ;
- dépourvues de données personnelles inutiles ;
- suffisamment explicites pour qu’un humain comprenne immédiatement le test.

Organisation indicative :

```text
tests/fixtures/
├── xml/
│   ├── valid/
│   └── invalid/
├── docx/
├── expected/
└── manifests/
```

### 5.1 Origine des fixtures

Une fixture peut être :

1. créée spécifiquement pour un test ;
2. extraite et réduite à partir d’un document de référence ;
3. construite pour reproduire un défaut constaté dans un corpus réel.

Lorsqu’une fixture dérive d’un fichier de `references/`, ajoute une trace de provenance dans un manifeste ou un commentaire documentaire :

- fichier source ;
- type de réduction effectuée ;
- phénomène conservé ;
- contenu anonymisé ou remplacé ;
- raison du test.

Ne conserve que la structure nécessaire au phénomène testé.

### 5.2 Candidats et fixtures validées

Lors d’un audit, Codex peut produire une liste de **candidats à la création de fixtures**.

Il ne doit pas transformer automatiquement des dizaines de cas réels en fixtures définitives.

Une fixture définitive doit avoir :

- un objectif clair ;
- un résultat attendu explicite ;
- un test associé ;
- une taille raisonnable ;
- une provenance compréhensible.

### 5.3 Deux catégories de tests

Distingue toujours :

#### Tests normatifs

Ils vérifient qu’un XML est valide ou invalide contre le schéma officiel.

#### Tests de conversion ou de régression

Ils vérifient qu’un DOCX ou un modèle Python produit la structure TEI décidée par le projet.

Ne confonds pas conformité au schéma et qualité éditoriale.

Un document peut être valide mais éditorialement mauvais.

---

## 6. Lecture du DOCX

Le format réellement pris en charge sera `.docx`.

L’ancien format binaire `.doc` ne doit pas être analysé directement. Une éventuelle conversion préalable vers `.docx` devra rester une étape séparée.

Un DOCX est une archive OOXML. Ne suppose pas qu’une bibliothèque de haut niveau expose toutes les informations utiles.

Les phénomènes importants peuvent nécessiter l’inspection directe de :

- `word/document.xml` ;
- `word/styles.xml` ;
- `word/numbering.xml` ;
- `word/footnotes.xml` ;
- `word/endnotes.xml` ;
- fichiers de relations ;
- médias embarqués ;
- commentaires, signets ou renvois.

Une bibliothèque telle que `python-docx` pourra éventuellement être utilisée comme commodité, mais elle ne devra pas masquer ou faire perdre des informations nécessaires.

Toute perte volontaire d’information doit être documentée et signalée.

---

## 7. Styles Word

Le projet vise prioritairement les styles natifs et les fonctionnalités ordinaires de Word.

Les noms affichés peuvent varier selon la langue de Word. Ne fonde pas la reconnaissance uniquement sur des chaînes visibles telles que :

- `Titre 1` ;
- `Heading 1` ;
- `Citation` ;
- `Quote`.

Inspecte les identifiants et propriétés OOXML stables lorsque cela est possible.

Ne fige pas une convention de métadonnées ou une correspondance Word → TEI qui n’a pas encore été explicitement approuvée.

Toute nouvelle correspondance doit être :

- documentée ;
- testée ;
- compatible avec Commons Publishing ;
- compréhensible pour un utilisateur non spécialiste de la TEI.

---

## 8. Citations poétiques

Les citations poétiques appartiennent au noyau fonctionnel du projet. Elles ne sont pas un profil spécialisé facultatif.

Le modèle doit pouvoir distinguer :

- citation en prose ;
- citation poétique ;
- strophe ;
- vers ;
- source bibliographique ;
- enrichissements inline dans un vers ;
- appel de note dans un vers ;
- retour visuel d’un vers long ;
- véritable fin de vers.

La structure TEI privilégiée doit être vérifiée contre le schéma officiel Commons Publishing.

Structure attendue, sous réserve de validation normative :

```xml
<cit type="verse">
  <quote>
    <lg>
      <l>Premier vers</l>
      <l>Deuxième vers</l>
    </lg>
  </quote>
  <bibl>Source de la citation</bibl>
</cit>
```

Plusieurs strophes doivent rester plusieurs groupes de vers distincts.

Ne transforme jamais une citation poétique en simple paragraphe comportant seulement des éléments `<br>` ou leurs équivalents.

Les sauts automatiques dus à la largeur de la page Word ne sont pas des fins de vers.

---

## 9. Métadonnées

Le projet utilisera une section de métadonnées simple dans le DOCX.

La convention exacte n’est pas encore définitivement arrêtée.

Ne crée pas de format complexe, de macros Word ou de dépendance au modèle Métopes sans demande explicite.

Les objectifs sont :

- simplicité pour l’auteur et l’éditrice ;
- données lisibles directement dans Word ;
- correspondances explicites ;
- diagnostics précis ;
- génération d’un `teiHeader` Commons Publishing propre ;
- absence de champs artificiellement vides lorsque le standard ne les exige pas.

---

## 10. Qualité du code Python

Le code doit être :

- simple ;
- clair ;
- typé ;
- documenté avec mesure ;
- déterministe ;
- testable ;
- réutilisable ;
- indépendant du répertoire courant ;
- compatible avec l’installation en paquet.

### Préférences

- Utilise `pathlib.Path`.
- Utilise des `dataclass` lorsque cela clarifie le modèle.
- Préfère de petites fonctions cohérentes.
- Ajoute des docstrings aux API publiques.
- Préserve les causes des exceptions utiles.
- Fournis des résultats structurés plutôt que d’imprimer depuis la bibliothèque.
- Réserve les sorties console à la CLI.
- Utilise `importlib.resources` pour les ressources embarquées.

### À éviter

- fonctions géantes ;
- état global mutable ;
- chemins absolus ;
- regex appliquées directement au XML ou au contenu OOXML lorsque l’analyse structurée est possible ;
- captures générales de type `except Exception` sans justification ;
- dépendances lourdes ou redondantes ;
- abstractions créées avant l’existence d’un besoin ;
- transformations silencieuses ;
- correction automatique ambiguë sans diagnostic.

---

## 11. XML et sécurité

Pour toute lecture XML :

- désactive les accès réseau ;
- évite la résolution arbitraire d’entités externes ;
- ne charge pas implicitement de DTD distante ;
- distingue XML mal formé et XML non conforme ;
- conserve les numéros de ligne lorsque disponibles ;
- ne modifie pas silencieusement les espaces significatifs ;
- traite correctement les espaces de noms.

Le namespace TEI doit être manipulé explicitement.

---

## 12. Validation

La validation courante doit utiliser le RNG officiel Commons Publishing embarqué avec le paquet.

Le schéma doit être accompagné :

- de sa licence ;
- de sa provenance ;
- de son chemin source ;
- du commit ou tag vérifié ;
- de l’indication d’éventuelles modifications locales.

La bibliothèque de validation doit retourner un résultat structuré contenant au minimum :

- validité ;
- messages ;
- lignes ;
- colonnes lorsqu’elles existent ;
- nature des erreurs.

Documente précisément les limites de `lxml.RelaxNG`, notamment vis-à-vis des éventuelles assertions Schematron intégrées ou associées.

Ne prétends jamais qu’un document a subi une validation Schematron complète si seule la grammaire Relax NG a été exécutée.

---

## 13. Tests

Après une modification fonctionnelle, exécute les tests pertinents.

Lorsque le socle du projet est en place, la vérification complète attendue sera au minimum :

```bash
pytest -q
python -m build
```

Inspecte la wheel lorsqu’une ressource embarquée ou le packaging est modifié.

Les tests doivent couvrir :

- cas valide ;
- cas invalide ;
- XML mal formé ;
- ressources empaquetées ;
- API publique ;
- CLI ;
- codes de sortie ;
- citations poétiques ;
- cas réels réduits issus du corpus de référence lorsque cela est pertinent.

Un test ne doit pas dépendre d’un chemin local propre à une machine.

---

## 14. Documentation des décisions

Toute décision structurante doit être consignée dans `docs/`.

Utilise des notes d’architecture courtes pour les décisions telles que :

- choix du moteur Python ;
- rôle des TEI Stylesheets ;
- version du schéma Commons Publishing ;
- modèle de citation poétique ;
- convention de métadonnées ;
- stratégie de lecture OOXML ;
- découpage des unités éditoriales ;
- politique de diagnostics.

Une décision documentée doit expliquer :

- le problème ;
- les options ;
- le choix ;
- ses conséquences ;
- ses limites.

---

## 15. Dépendances

N’ajoute pas de dépendance d’exécution sans nécessité démontrée.

Avant d’ajouter une dépendance :

1. vérifie si la bibliothèque standard suffit ;
2. vérifie sa maintenance et sa licence ;
3. explique sa fonction précise ;
4. limite son usage à une couche clairement identifiée ;
5. ajoute les tests correspondants.

Ne remplace pas un petit besoin maîtrisable par un framework général.

---

## 16. Git et modifications

Avant toute modification :

- inspecte `git status` ;
- examine les fichiers existants ;
- respecte les changements déjà présents ;
- ne supprime pas le travail de l’utilisateur ;
- ne lance pas de restauration globale.

Ne committe rien sauf demande explicite.

Ne pousse rien vers un dépôt distant sauf demande explicite.

Ne modifie jamais le projet Impressions depuis le dépôt Mini-Métopes.

Ne renomme pas massivement des fichiers sans nécessité.

Ne reformate pas des fichiers sans rapport avec la tâche.

---

## 17. Méthode de travail

Pour chaque tâche importante :

1. inspecte l’existant ;
2. identifie les contraintes normatives ;
3. propose ou applique une modification limitée ;
4. ajoute ou adapte les tests ;
5. exécute les vérifications ;
6. examine le diff ;
7. rends compte précisément.

Lorsqu’un comportement est ambigu :

- cherche d’abord dans les schémas, l’ODD, la documentation et les références ;
- distingue fait observé, exigence normative et décision du projet ;
- n’invente pas une convention silencieusement.

Une solution partielle, bien testée et explicitement limitée, vaut mieux qu’une prise en charge large mais fragile.

---

## 18. Compte rendu attendu

À la fin de chaque passe, indique :

- fichiers créés ou modifiés ;
- décisions prises ;
- références normatives utilisées ;
- tests exécutés ;
- résultats ;
- limites ;
- problèmes rencontrés ;
- éléments volontairement laissés hors périmètre ;
- prochaine passe logique.

Ne présente pas comme achevé ce qui n’a pas été testé.
