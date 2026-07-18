# Procédure de test manuel — éditeur de métadonnées

Test humain de l'interface Tkinter (non couvert par pytest, qui ne lance
jamais Tk). Durée indicative : 15 minutes. Prérequis : un DOCX de travail,
par exemple une copie de `tests/fixtures/corpus/document-c/source.docx`
(grec non requis dans le DOCX : le grec est testé via les métadonnées).

1. **Ouverture** — `python -m mini_metopes edit-metadata copie.docx`.
   Vérifier : titre/sous-titre proposés depuis les styles Word `Title`/
   `Subtitle`, chemins DOCX et JSON affichés dans l'onglet Document.
2. **Onglet Document** — saisir langue `fr-FR`, type `chapter` ; vérifier
   qu'une langue invalide (`français`) est refusée à l'enregistrement.
3. **Onglet Auteurs** — créer deux auteurs (dont un avec ORCID
   `0000-0002-1825-0097`) et une affiliation référencée par les deux ;
   réordonner avec Monter/Descendre ; vérifier le refus de suppression d'une
   affiliation encore utilisée.
4. **Onglet Publication** — cliquer « Appliquer un profil… » et choisir
   `profiles/purh.json` : nom, lieu, adresse et URL PURH doivent se remplir
   sans écraser une valeur déjà saisie. Ajouter une date `2026-03`, un
   responsable d'édition, une collection et une pagination 125–148.
5. **Onglet Résumés et mots-clés** — ajouter un résumé français, un abstract
   grec polytonique (`Περὶ τῆς τραγῳδίας — ᾠδή, ῥυθμός`) et une quatrième de
   couverture de deux paragraphes ; deux groupes de mots-clés (fr, grc) ;
   réordonner et vérifier la conservation de l'ordre.
6. **Onglet Droits et identifiants** — licence CC avec URL ; un DOI, un ISBN
   print et un ISBN pdf (vérifier qu'un ISBN sans support est refusé à
   l'enregistrement, ainsi qu'un ISBN à clé fausse).
7. **Enregistrement** — « Enregistrer » ; ouvrir le JSON : vérifier
   `schema_version: "1.0"`, chemin `source_document.path` **relatif**, grec
   intact, aucun groupe vide.
8. **Rechargement** — fermer, relancer l'éditeur : toutes les listes et leur
   ordre doivent réapparaître ; « Charger… » sur le même JSON doit aboutir au
   même état.
9. **Relocalisation** — déplacer le DOCX dans un sous-dossier, relancer via
   « Charger… » : l'éditeur signale le DOCX introuvable et propose de le
   relocaliser ; après relocalisation puis enregistrement, le `path` relatif
   est mis à jour.
10. **Conversion** — `python -m mini_metopes convert-docx copie.docx sortie.xml
    --metadata copie.metadata.json` : succès attendu ; contrôler dans
    `sortie.xml` le `teiHeader` (éditeur, idno, licence), le `front`
    (résumés, grec intact, `n="back-cover"`), les notes du corps.
11. **Validation RNG** — `python -m mini_metopes validate sortie.xml` doit
    afficher `VALIDE`.
