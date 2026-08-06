# 0021 — Génération TEI en arrière-plan avec fenêtre d'attente

## Contexte

`generate_tei()` (`gui/metadata_editor.py`) appelait `generate_tei_commons`
(inspection OOXML, construction du modèle éditorial, validation Relax NG,
écriture des médias) de façon synchrone sur le thread principal Tk. Le seul
retour visuel était un curseur sablier (`root.configure(cursor="watch")`).
Un audit du dépôt a signalé que pour un document volumineux (plusieurs
images, chapitre entier), la fenêtre reste gelée sans aucune confirmation
que Mini-Métopes travaille toujours — rien ne distingue « en cours » de
« planté » pour l'utilisateur.

## Décision

- La conversion tourne désormais sur un `threading.Thread` dédié
  (`daemon=True`) ; le thread principal ne fait plus qu'attendre le résultat
  via un `queue.Queue`, interrogée par polling `root.after(100, poll)`
  (pattern standard Tkinter : la boucle Tk n'est jamais bloquée, et aucun
  widget n'est manipulé depuis le thread d'arrière-plan — seule la queue,
  thread-safe, est partagée).
- Une fenêtre modale (`_show_generation_wait_window`) s'affiche pendant la
  génération : message explicite, barre de progression indéterminée
  animée (`ttk.Progressbar(mode="indeterminate")`) pour donner un signal
  visuel continu que l'application n'est pas figée, et fermeture
  programmatique désactivée (`protocol("WM_DELETE_WINDOW", lambda: None)`)
  le temps de la génération — il n'y a pas de mécanisme d'annulation
  coopératif dans `convert_docx_to_tei`, donc laisser fermer la fenêtre
  laisserait une conversion orpheline tourner sans retour possible.
- Le bouton « Générer la TEI Commons… » est désactivé pendant la génération,
  comme avant, mais sa restauration (avec fermeture de la fenêtre d'attente)
  a désormais lieu inconditionnellement en tête de `poll()`, avant toute
  distinction succès/échec — remplace l'ancien `try/finally` synchrone par
  l'équivalent asynchrone.
- `docx_path` et `metadata` sont capturés dans des variables locales avant
  le lancement du thread plutôt que relus depuis `state` (fermeture
  partagée avec le thread principal) au moment où le thread s'exécute :
  évite tout accès concurrent à une variable mutable partagée entre
  threads.

## Conséquences

- L'interface reste réactive pendant la génération ; l'utilisateur reçoit
  une confirmation visuelle continue (barre animée) plutôt qu'un seul
  changement de curseur statique.
- Pas de changement du contrat fonctionnel : mêmes messages de succès/échec
  (`_report_generation_outcome`), mêmes conditions de blocage.
- Tests mis à jour (`tests/test_metadata_editor_generate_gui.py`) : les
  assertions structurelles sur le code source sont adaptées à la nouvelle
  forme (thread + queue + poll), et un nouveau test verifie que la fenêtre
  d'attente s'affiche pendant la génération et disparaît une fois terminée,
  dans le test Tkinter complet (`test_manual_generation_full_flow`, qui
  reste marqué `requires_display` et n'exécute que si un affichage Tk
  fonctionnel est disponible).

## Limites assumées

- Aucune annulation utilisateur pendant la génération : c'est un choix
  délibéré, pas un oubli — `convert_docx_to_tei` n'a pas de point
  d'interruption coopératif, et tuer un thread Python de force est jugé
  plus risqueux (état partiellement écrit) qu'attendre la fin.
- `test_manual_generation_full_flow` (le seul test à driver une vraie
  fenêtre Tk pour ce parcours) échoue de façon non liée à cette décision
  sur cette machine lorsqu'il est exécuté isolément (Tcl `init.tcl`
  introuvable lors d'une seconde instanciation `tk.Tk()`) — reproduit à
  l'identique sur le code non modifié, donc hors périmètre de cette passe ;
  il est correctement ignoré (`skip`) dans la suite complète.
