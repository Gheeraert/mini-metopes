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
