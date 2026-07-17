# Métadonnées JSON v1

Le fichier associé à `document.docx` est `document.metadata.json`. Il contient
un titre obligatoire, langue BCP 47, type contrôlé, contributeurs, affiliations,
résumé, mots-clés et empreinte SHA-256 du DOCX. Les personnes sont soit
structurées (`given_name`/`family_name`), soit littérales (`literal_name`), sans
mélange. Les identifiants éditables suivent par défaut `person-1` et
`affiliation-1`.

Le JSON est enregistré avec UTF-8, deux espaces, ordre stable et saut final. Un
fichier existant n'est remplacé qu'après validation et écriture atomique.
L'ORCID est vérifié hors ligne, de même que la forme d'une URL ROR.

`Title` et `Subtitle` Word initiaux préremplissent le formulaire; après
enregistrement ils ne l'emportent jamais sur le JSON. Un style de métadonnée
placé après le premier paragraphe de corps bloque la conversion.
