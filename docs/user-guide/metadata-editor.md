# Éditeur de métadonnées

Lancez `python -m mini_metopes edit-metadata document.docx` (ou sans argument
pour choisir le DOCX). L'éditeur ouvre ou crée le JSON voisin du DOCX
(`document.metadata.json`) et propose le titre et le sous-titre issus des
styles Word natifs `Title`/`Subtitle` (y compris localisés). La langue
initiale est `fr` et le type initial `chapter`.

La fenêtre est organisée en cinq onglets, avec défilement si nécessaire :

1. **Document** — fichiers (avec « Relocaliser le DOCX… » si le document a
   bougé), titre, sous-titre, langue BCP 47, type, diagnostics ;
2. **Auteurs** — auteurs et contributeurs (rôle, ORCID, courriel,
   affiliations), ordre modifiable par Monter/Descendre ; affiliations
   réutilisables ;
3. **Publication** — éditeur (avec « Appliquer un profil… » pour charger les
   valeurs stables, par exemple `profiles/purh.json`), date, responsables
   d'édition, collection simple, pagination ;
4. **Résumés et mots-clés** — résumés typés (résumé, abstract traduit,
   quatrième de couverture) et groupes de mots-clés par langue ;
5. **Droits et identifiants** — détenteur, mention, licence (nom + URL),
   identifiants (DOI, ISBN par support, ISSN, identifiant local).

Les listes répétables s'éditent par Ajouter / Modifier / Supprimer, jamais par
une prolifération de champs. « Charger… » ouvre un autre JSON de métadonnées ;
si son DOCX est introuvable, l'éditeur propose de le relocaliser. Le JSON
mémorise un chemin de préférence relatif et l'empreinte SHA-256 du DOCX ;
l'empreinte n'est mise à jour que lors d'un enregistrement volontaire.

Enregistrez avant de convertir. La commande
`python -m mini_metopes validate-metadata document.metadata.json` contrôle le
JSON sans ouvrir Word ; `convert-docx … --profile profiles/purh.json` applique
les valeurs institutionnelles par défaut sans les recopier dans chaque JSON.

## Diagnostics visibles

L'onglet Document affiche les diagnostics de chargement et de cohérence :
empreinte DOCX différente, nom de source différent, titre ou sous-titre Word
différent du JSON, JSON invalide, valeurs invalides (ORCID, ISBN, DOI, date,
URL…). Les erreurs empêchent l'enregistrement tant que le formulaire n'est pas
corrigé. Les avertissements restent visibles mais le JSON demeure la source
d'autorité.
