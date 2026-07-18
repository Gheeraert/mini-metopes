# Corpus de référence Mini-Métopes

Petit corpus de bout en bout utilisant exclusivement les styles natifs de
Word et les conventions Mini-Métopes. Il constitue la référence exécutable du
contrat `DOCX natif → modèle éditorial → TEI Commons Publishing`.

Chaque document comprend :

- `source.docx` — paquet OOXML reproductible (horodatages ZIP fixés) ;
- `metadata.json` — métadonnées validées, `sha256` lié au DOCX ;
- `expected.xml` — TEI attendue, absente quand la conversion doit être
  refusée ;
- `expected-diagnostics.json` — diagnostics attendus, dans l'ordre produit ;
- `README.md` — intention éditoriale du cas.

Régénération : `python tools/create_reference_corpus.py`. Le script refuse de
régénérer un cas dont le contrat (succès ou blocage) a changé. Les
`expected.xml` régénérés doivent être relus comme des objets éditoriaux avant
d'être validés.

Les styles Word Métopes (`TEI_quote`, `TEI_verse`, etc.) sont hors périmètre
d'entrée : le cas `document-d/unknown-custom-style` vérifie explicitement leur
rejet.

Tests associés : `tests/test_reference_corpus.py`.
