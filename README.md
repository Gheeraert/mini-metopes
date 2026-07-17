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
python -m mini_metopes convert-docx source.docx sortie.xml
```

La sortie JSON est structurée et déterministe. Chaque run expose aussi un flux
inline ordonné (texte, tabulation, sauts, appels de notes et dessins), sans
confondre les marqueurs textuels de commodité avec les objets OOXML. Les
propriétés de mise en forme rapportées sont les propriétés directement
déclarées dans l'OOXML ; elles ne constituent pas encore la mise en forme
effective calculée par Word.

`model-docx` applique une premiere convention native Word et produit un modele
editorial avec diagnostics. `convert-docx` serialise le sous-ensemble pris en
charge en TEI Commons Publishing validee. La convention reconnait `Quote` pour
les citations en prose et `IntenseQuote` pour les citations poetiques
(strophes = paragraphes, vers = retours manuels).

La conversion propage les diagnostics de l'inspection et du modele editorial.
Elle refuse actuellement les styles `Title` et `Subtitle`, les styles inconnus,
les listes Word, tableaux, zones de texte, dessins, liens internes et
metadonnees riches afin d'eviter une TEI trompeuse. Les commentaires,
en-tetes et pieds de page sont signales comme avertissements lorsqu'ils sont
observes.

Le répertoire `references/` est un corpus documentaire en lecture seule. Il
n'est ni empaqueté ni utilisé directement par les tests ordinaires.
