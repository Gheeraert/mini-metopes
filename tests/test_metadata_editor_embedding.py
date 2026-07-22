"""Tests Tkinter cibles de ``open_metadata_editor`` (mode integre).

Meme principe que ``test_metadata_editor_startup.py`` : une seule fenetre
Tkinter reelle pour l'ensemble du parcours, pilotee par ``root.after`` pour
enchainer des etapes sans dependre d'un ``mainloop`` externe
(``open_metadata_editor`` utilise ``wait_window``, qui pompe deja la boucle
d'evenements). Plusieurs ``tk.Tk()`` reels crees/detruits en rafale dans le
meme processus se sont montres instables sur cet environnement ; on garde
donc un seul parent pour tout le scenario et on n'ouvre que des ``Toplevel``
successifs dessus, ce que le mode integre est justement cense faire.
"""

from __future__ import annotations

import shutil
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import tkinter.ttk as ttk
from pathlib import Path

import pytest

from mini_metopes.gui import open_metadata_editor
from mini_metopes.metadata import load_metadata_file, resolve_source_document_path

FIXTURES = Path(__file__).parent / "fixtures"
DOCX = FIXTURES / "docx" / "native-tei-conversion.docx"


def _tk_available() -> bool:
    try:
        root = tk.Tk()
    except tk.TclError:
        return False
    root.destroy()
    return True


requires_display = pytest.mark.skipif(not _tk_available(), reason="pas d'affichage Tkinter disponible")


def _find_button_by_text(root: tk.Misc, text: str) -> ttk.Button | None:
    stack = list(root.winfo_children())
    while stack:
        widget = stack.pop()
        if isinstance(widget, ttk.Button):
            varname = widget.cget("textvariable")
            value = root.getvar(varname) if varname else widget.cget("text")
            if value == text:
                return widget
        stack.extend(widget.winfo_children())
    return None


def _find_toplevels(parent: tk.Tk) -> list[tk.Toplevel]:
    return [child for child in parent.winfo_children() if isinstance(child, tk.Toplevel)]


@requires_display
def test_embedded_editor_full_flow(tmp_path: Path, monkeypatch) -> None:
    """Parcours complet du mode integre dans une unique fenetre hote reelle.

    Verifie dans l'ordre : (1) un seul ``Toplevel`` enfant, aucune deuxieme
    racine, annulation propre laissant le parent utilisable ; (2) le bouton de
    generation TEI absent par defaut puis present avec
    ``show_tei_generation=True`` ; (3) l'enregistrement d'un nouveau JSON sans
    aucun ``asksaveasfilename`` quand ``prompt_for_new_destination=False`` ;
    (4) le contrat public complet (statut, chemin, JSON valide, source
    resolue vers le DOCX) attendu par le futur appel de l'orchestrateur.
    """
    parent = tk.Tk()
    monkeypatch.setattr(messagebox, "showinfo", lambda title, message, **kwargs: None)
    monkeypatch.setattr(messagebox, "showerror", lambda title, message, **kwargs: None)
    monkeypatch.setattr(messagebox, "askyesno", lambda title, message, **kwargs: True)
    try:
        docx_copy = tmp_path / "article.docx"
        shutil.copyfile(DOCX, docx_copy)
        target = tmp_path / "article.metadata.json"

        # --- (1) annulation : un seul Toplevel, parent toujours vivant ensuite.
        def cancel_stage() -> None:
            toplevels = _find_toplevels(parent)
            assert len(toplevels) == 1
            window = toplevels[0]
            assert _find_button_by_text(window, "Générer la TEI Commons…") is None
            cancel = _find_button_by_text(window, "Annuler")
            assert cancel is not None
            cancel.invoke()

        parent.after(80, cancel_stage)
        cancelled = open_metadata_editor(
            parent, docx_copy, metadata_path=target,
            prompt_for_new_destination=False, show_tei_generation=False,
        )
        assert cancelled.status == "cancelled"
        assert cancelled.metadata_path is None
        assert not target.exists()
        assert parent.winfo_exists()
        assert not _find_toplevels(parent)

        # --- (2) bouton de generation TEI present uniquement si demande.
        def tei_button_stage() -> None:
            window = _find_toplevels(parent)[0]
            assert _find_button_by_text(window, "Générer la TEI Commons…") is not None
            cancel = _find_button_by_text(window, "Annuler")
            assert cancel is not None
            cancel.invoke()

        parent.after(80, tei_button_stage)
        open_metadata_editor(
            parent, docx_copy, metadata_path=target,
            prompt_for_new_destination=False, show_tei_generation=True,
        )
        assert not _find_toplevels(parent)

        # --- (3) et (4) enregistrement direct sans selecteur de destination.
        def save_as_called(**kwargs: object) -> str:
            raise AssertionError("asksaveasfilename ne doit pas etre appele quand prompt_for_new_destination=False")

        monkeypatch.setattr(filedialog, "asksaveasfilename", save_as_called)

        def save_stage() -> None:
            window = _find_toplevels(parent)[0]
            save_close = _find_button_by_text(window, "Enregistrer et fermer")
            assert save_close is not None
            save_close.invoke()

        parent.after(80, save_stage)
        saved = open_metadata_editor(
            parent, docx_copy, metadata_path=target,
            prompt_for_new_destination=False, show_tei_generation=False,
        )

        assert saved.status == "saved"
        assert saved.saved is True
        assert saved.metadata_path == target
        assert target.exists()

        loaded = load_metadata_file(target)
        assert loaded.valid
        assert loaded.metadata is not None
        resolved = resolve_source_document_path(loaded.metadata.source.path, target)
        assert resolved.resolve() == docx_copy.resolve()

        assert parent.winfo_exists()
        assert not _find_toplevels(parent)
    finally:
        parent.destroy()
