# Éditeur de métadonnées

Lancez `python -m mini_metopes edit-metadata document.docx`. L'éditeur ouvre ou
crée le JSON voisin du DOCX. Il propose le titre et le sous-titre issus des
styles Word natifs `Title` et `Subtitle`, puis permet de les modifier. La langue
initiale est `fr` et le type initial `chapter`.

Enregistrez avant de convertir. La commande
`python -m mini_metopes validate-metadata document.metadata.json` contrôle le
JSON sans ouvrir Word. La conversion utilise ce JSON, jamais les seules valeurs
visuelles de Word. L'empreinte est mise à jour seulement lors d'un enregistrement
volontaire.

## Diagnostics visibles

La zone Document affiche les diagnostics de chargement et de coherence:
empreinte DOCX differente, nom de source different, titre ou sous-titre Word
different du JSON, ou JSON invalide. Les erreurs empechent l'enregistrement tant
que le formulaire n'est pas corrige. Les avertissements restent visibles mais le
JSON demeure la source d'autorite.

Si le JSON existant est invalide, l'editeur affiche des valeurs de secours
issues du DOCX et demande une confirmation explicite avant d'ecraser ce fichier.
Modifier un champ, un contributeur, une affiliation ou l'ordre des contributeurs
marque immediatement la fenetre comme modifiee. Le bouton Annuler et la croix de
fermeture demandent la meme confirmation.

Les identifiants `person-*` et `affiliation-*` sont editables. Renommer une
affiliation met automatiquement a jour les references des contributeurs. Une
collision d'identifiant est refusee.
