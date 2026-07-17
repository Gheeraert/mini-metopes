# Mini-Métopes

Mini-Métopes prépare la conversion de documents Word structurés vers la TEI
**Commons Publishing**. Il se situe en amont d'Impressions, qui prendra ensuite
en charge les sorties HTML, LaTEI, PDF, EPUB et autres formats.

## État actuel

Mini-Métopes fournit une validation normative Relax NG du noyau Commons
Publishing, une inspection OOXML en lecture seule des fichiers DOCX et une
premiere conversion DOCX -> TEI Commons Publishing pour un sous-ensemble
conservatoire de la convention Word native.

## Développement

Python 3.11 ou supérieur est requis.

```bash
python -m pip install -e .
python -m pip install pytest build
pytest -q
```

Valider un fichier TEI :

```bash
python -m mini_metopes validate chemin/vers/document.xml
```

Inspecter un DOCX :

```powershell
python -m mini_metopes inspect-docx document.docx
python -m mini_metopes inspect-docx document.docx --json
python -m mini_metopes model-docx document.docx
python -m mini_metopes model-docx document.docx --json
python -m mini_metopes edit-metadata document.docx
python -m mini_metopes validate-metadata document.metadata.json
python -m mini_metopes validate-metadata document.metadata.json --source document.docx
python -m mini_metopes convert-docx source.docx sortie.xml
```

La sortie JSON est structurée et déterministe. Chaque run expose aussi un flux
inline ordonné (texte, tabulation, sauts, appels de notes et dessins), sans
confondre les marqueurs textuels de commodité avec les objets OOXML. Les
propriétés de mise en forme rapportées sont les propriétés directement
déclarées dans l'OOXML ; elles ne constituent pas encore la mise en forme
effective calculée par Word.

Le DOCX contient le texte et sa structure. Le JSON associe contient les
metadonnees validees qui alimentent le `teiHeader`. Par defaut,
`document.docx` est associe a `document.metadata.json`; `convert-docx` exige ce
JSON (ou `--metadata`) et ne lance jamais l'interface automatiquement.

`model-docx` applique une premiere convention native Word et produit un modele
editorial avec diagnostics. `convert-docx` serialise le sous-ensemble pris en
charge en TEI Commons Publishing validee. La convention reconnait `Quote` pour
les citations en prose et `IntenseQuote` pour les citations poetiques
(strophes = paragraphes, vers = retours manuels).

Les styles `Title` et `Subtitle` du preambule initial servent uniquement de
suggestions et de controle de coherence avec le JSON; ils ne deviennent pas du
contenu TEI. La conversion propage les diagnostics de l'inspection et du modele editorial.
Elle refuse les styles `Title` et `Subtitle` hors preambule, les styles inconnus,
les listes Word actives, tableaux, zones de texte, dessins, liens internes et
metadonnees riches afin d'eviter une TEI trompeuse. Les commentaires,
en-tetes et pieds de page sont signales comme avertissements lorsqu'ils sont
observes.

Le répertoire `references/` est un corpus documentaire en lecture seule. Il
n'est ni empaqueté ni utilisé directement par les tests ordinaires.

`validate-metadata --source` inspecte le DOCX et affiche les avertissements de
coherence avec le JSON: empreinte modifiee, nom source different, divergences
`Title`/`Subtitle` ou styles de metadonnees hors preambule. Les JSON mal types
sont refuses par diagnostics structures, sans traceback utilisateur. Dans le
`teiHeader`, les ORCID sont normalises; les ROR restent dans le JSON et
produisent `ror_not_serialized` tant que le profil Commons Publishing embarque
ne fournit pas de representation satisfaisante dans cette structure.

Les listes Word sont désormais inspectées et résolues (instances, niveaux,
surcharges, valeurs par défaut WordprocessingML et listes dans les notes), mais
leur conversion TEI sera introduite dans la passe suivante. `numId="0"` est
traité comme une suppression explicite de numérotation, pas comme une liste
active.
