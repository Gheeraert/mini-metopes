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

## Intégration de l'éditeur de métadonnées

L'usage autonome reste la CLI :

```powershell
python -m mini_metopes edit-metadata document.docx
```

Elle ouvre sa propre fenêtre (`tk.Tk()`) et sa propre boucle d'événements, avec
le bouton « Générer la TEI Commons… » disponible et un « Enregistrer sous… »
pour tout nouveau fichier de métadonnées.

Pour une application hôte Tkinter qui veut intégrer ce même éditeur comme
boîte modale (au lieu d'une seconde application indépendante), `mini_metopes.gui`
expose :

```python
from pathlib import Path
from mini_metopes.gui import open_metadata_editor

result = open_metadata_editor(
    parent,                       # une fenetre Tk ou Toplevel existante
    Path("document.docx"),        # obligatoire en usage integre
    metadata_path=None,           # None => convention document.metadata.json
    prompt_for_new_destination=False,
    show_tei_generation=False,
)

if result.status == "saved":
    metadata_json_path = result.metadata_path
```

En mode intégré, `open_metadata_editor` :

- ne crée jamais de `tk.Tk()` ni de nouvelle boucle `mainloop()` : elle ouvre
  un `tk.Toplevel(parent)` modal et bloque l'appelant via `wait_window`
  jusqu'à sa fermeture ;
- charge immédiatement le DOCX fourni (une éventuelle `DocxInspectionError`
  ou `OSError` de chargement initial est relancée telle quelle vers
  l'appelant, sans être affichée par l'éditeur) ;
- avec `prompt_for_new_destination=False`, écrit un nouveau JSON directement
  au chemin fourni (ou à la convention `document.metadata.json`) sans ouvrir
  de sélecteur « Enregistrer sous… » ; avec `True` (valeur par défaut), le
  comportement autonome habituel s'applique ;
- avec `show_tei_generation=False` (valeur par défaut du mode intégré), le
  bouton « Générer la TEI Commons… » n'est pas construit — la génération
  reste à la charge de l'application hôte, après fermeture de l'éditeur.

Le résultat renvoyé (`MetadataEditorResult`) est déterministe :

- `status="saved"` uniquement après un « Enregistrer et fermer » réussi ;
  `metadata_path` contient alors le chemin réellement écrit ;
- `status="cancelled"` sur « Annuler » ou fermeture de la fenêtre — y compris
  si un enregistrement précédent avait déjà écrit un JSON valide sur disque :
  la fermeture ne « valide » pas rétroactivement un état modifié ensuite ;
- un simple clic sur « Enregistrer » (sans fermer) écrit le JSON mais ne
  produit pas encore de résultat : celui-ci n'est renvoyé qu'à la fermeture.

`model-docx` applique une premiere convention native Word et produit un modele
editorial avec diagnostics. `convert-docx` serialise le sous-ensemble pris en
charge en TEI Commons Publishing validee. La convention reconnait `Quote` pour
les citations en prose et `IntenseQuote` pour les citations poetiques
(strophes = paragraphes, vers = retours manuels).

Le style Word integre `BodyText`, affiche en francais comme **Corps de texte**,
devient un paragraphe de suite : le modele porte
`rendition="consecutive"` et la TEI produit `<p rend="consecutive">`. Cette
semantique repose sur le style integre, pas sur les retraits directs `w:ind`.
Les variantes `Corps de texte 2`, `Corps de texte 3` et les styles
personnalises homonymes restent refusees tant qu'aucune convention explicite
n'a ete decidee.

Les styles `Title` et `Subtitle` du preambule initial servent uniquement de
suggestions et de controle de coherence avec le JSON; ils ne deviennent pas du
contenu TEI. La conversion propage les diagnostics de l'inspection et du modele editorial.
Elle refuse les styles `Title` et `Subtitle` hors preambule, les styles inconnus,
les listes Word ambiguës ou non résolues, tableaux, zones de texte, dessins, liens internes et
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

Les listes Word natives résolues sont désormais converties en listes TEI
imbriquées. Les puces illustrées, listes sans marqueur, numérotations par style
et structures ambiguës restent refusées. `numId` identifie l'instance Word et
`ilvl` son niveau : toute réouverture discontinue du même `numId`, même à un
autre niveau, et tout `lvlRestart` explicite restent bloquants tant que
Mini-Métopes ne calcule pas les compteurs effectifs Word. `numId="0"` est traité
comme une suppression explicite de numérotation, pas comme une liste active. Le
résumé `model-docx` compte les listes récursivement, y compris dans les notes.
Le style intégré `ListParagraph` peut prolonger un item lorsque le paragraphe
numéroté suivant reprend exactement la même liste ; ces continuations deviennent
des paragraphes enfants de `<item>`. Les paragraphes `Normal` et les cas
ambigus restent des interruptions conservatoires.

Les images Word simples sont prises en charge lorsqu'elles sont autonomes,
incorporees en DrawingML `wp:inline`, decrites par `wp:docPr/@descr`, et au
format PNG ou JPEG. Elles deviennent des figures TEI avec `graphic`, `figDesc`
et eventuellement une legende `Caption` rendue par `<p rend="caption">`. Les
fichiers medias utilises sont extraits dans un repertoire `media/` a cote du
XML avec un nom fonde sur leur SHA-256. Les images flottantes, VML, liees,
transformees, melangees a du texte ou placees dans des listes restent refusees.

Les figures simples peuvent maintenant recevoir un titre, une legende et des
credits lorsque les styles controles `TEIfiguretitle`, `TEIfigurecaption` et
`TEIfigurecredits` sont declares exactement. Les tableaux Word de premier niveau
deviennent des tableaux TEI lorsqu'ils sont rectangulaires, sans fusion ni
imbrication, et que chaque cellule contient au plus un paragraphe simple. Les
tableaux dans les notes, zones de texte ou listes, ainsi que les cellules
complexes, restent refuses afin de ne pas perdre leur structure.

Les references bibliographiques controlees `TEIbiblreference` sont conservees
en TEI `bibl` : elles peuvent etre autonomes, devenir la source immediate d'une
citation, ou former une bibliographie finale ouverte par `TEIbiblstart`.
Le style de caractere `TEIbiblreference-inline` produit un `bibl` inline. La
bibliographie est unique, terminale et devient `text/back/listBibl`; Mini-Metopes
ne deduit pas de `biblStruct`.
