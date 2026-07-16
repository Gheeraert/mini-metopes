# Mini-Métopes

Mini-Métopes prépare la conversion de documents Word structurés vers la TEI
**Commons Publishing**. Il se situe en amont d'Impressions, qui prendra ensuite
en charge les sorties HTML, LaTEI, PDF, EPUB et autres formats.

## État actuel

Mini-Métopes fournit une validation normative Relax NG du noyau Commons
Publishing et une inspection OOXML en lecture seule des fichiers DOCX. Cette
inspection inventorie notamment les styles, paragraphes, runs, notes,
numérotations, relations et médias sans modifier le document.

La conversion DOCX → TEI n'est pas encore implémentée.

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
```

La sortie JSON est structurée et déterministe. Chaque run expose aussi un flux
inline ordonné (texte, tabulation, sauts, appels de notes et dessins), sans
confondre les marqueurs textuels de commodité avec les objets OOXML. Les
propriétés de mise en forme rapportées sont les propriétés directement
déclarées dans l'OOXML ; elles ne constituent pas encore la mise en forme
effective calculée par Word.

`model-docx` applique une premiere convention native Word et produit un modele
editorial avec diagnostics, sans encore serialiser de TEI. La conversion DOCX
vers TEI reste donc volontairement non implementee.

Le répertoire `references/` est un corpus documentaire en lecture seule. Il
n'est ni empaqueté ni utilisé directement par les tests ordinaires.
