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

## Robustesse et diagnostics

Le JSON est decode champ par champ avant validation metier. Une racine non
objet, une section non objet, un champ obligatoire absent ou une valeur de type
incorrect produit un diagnostic localise. Exemples de chemins:
`document.title`, `document.keywords[0]`, `contributors[0].role`,
`affiliations[0].ror`.

Les identifiants editables ne sont pas corriges silencieusement. Un identifiant
vide, entoure d'espaces ou duplique apres suppression des espaces initiaux et
finaux est invalide. Renommer une affiliation dans l'editeur met a jour les
references des contributeurs; une collision est refusee.

La forme ROR acceptee est une URL HTTPS de `ror.org` avec un identifiant unique,
par exemple `https://ror.org/03yrm5c26`. Aucun service web n'est contacte. Dans
la TEI actuelle, le ROR n'est pas serialise par le profil Commons Publishing
embarque; la conversion produit `ror_not_serialized`.

Les ORCID sont normalises vers la forme `0000-0002-1825-0097`, y compris si le
JSON contient `https://orcid.org/0000-0002-1825-0097` et y compris pour un nom
litteral.
