"""Tests du demarrage sans ouverture automatique du selecteur DOCX.

Le principe attendu : la fenetre principale s'ouvre seule, sans aucun
selecteur Windows par-dessus ; seul un clic explicite sur « Localiser le
DOCX... » (ou un chemin fourni en CLI) declenche un chargement.

Les assertions de comportement Tkinter sont regroupees dans un seul test
pilotant une seule fenetre reelle (``invoke()`` sur les boutons, lecture de
leur etat) : instancier plusieurs ``tk.Tk()`` reels dans le meme processus
s'est revele instable sur cet environnement (erreurs Tcl "init.tcl"
intermittentes lors de creations/destructions repetees), donc on minimise le
nombre de fenetres reellement ouvertes plutot que de simuler une validation
visuelle que l'environnement ne supporte pas de facon fiable.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.ttk as ttk
from pathlib import Path

import pytest

import mini_metopes.gui.metadata_editor as editor_module

FIXTURES = Path(__file__).parent / "fixtures"
DOCX = FIXTURES / "docx" / "native-tei-conversion.docx"

_SOURCE = Path(editor_module.__file__).read_text(encoding="utf-8")


def _tk_available() -> bool:
    try:
        root = tk.Tk()
    except tk.TclError:
        return False
    root.destroy()
    return True


requires_display = pytest.mark.skipif(not _tk_available(), reason="pas d'affichage Tkinter disponible")


def _find_button_by_text(root: tk.Misc, text: str) -> ttk.Button | None:
    """Retrouver un bouton par son libelle courant (texte fixe ou variable)."""
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


# --------------------------------------------------------------- hors Tkinter


def test_source_has_no_startup_auto_trigger() -> None:
    """Aucun callback de demarrage ne doit ouvrir le selecteur tout seul."""
    forbidden = ("after_idle(", "<Map>", "<Visibility>")
    for token in forbidden:
        assert token not in _SOURCE, f"declencheur automatique interdit trouve : {token}"


def test_initial_state_is_none_by_construction() -> None:
    """`run_metadata_editor` doit pouvoir demarrer avec `state = None`."""
    assert "state: MetadataEditorState | None = None" in _SOURCE


def test_cli_docx_path_is_loaded_before_mainloop_starts() -> None:
    """Le chargement depuis un chemin CLI precede `root.mainloop()`.

    Confirme statiquement que la branche ``docx_path is not None`` appelle
    ``load_metadata_editor_state`` avant d'entrer dans la boucle Tkinter, donc
    sans dependre d'un clic utilisateur ni ouvrir de selecteur. Le
    comportement de bout en bout (aucune trace, code 2 sur DOCX invalide) est
    deja verifie par ``test_edit_metadata_invalid_docx_returns_2_without_traceback``
    dans ``test_metadata_cli_and_tei.py``, qui emprunte cette meme branche.
    """
    mainloop_index = _SOURCE.index("root.mainloop()")
    load_call_index = _SOURCE.index("state = load_metadata_editor_state(docx_path, metadata_path)")
    assert load_call_index < mainloop_index


def test_business_save_logic_is_untouched() -> None:
    """Les fonctions d'enregistrement restent celles de `metadata_controller`."""
    from mini_metopes.gui import metadata_controller

    assert callable(metadata_controller.requires_save_as)
    assert callable(metadata_controller.change_metadata_destination)
    assert callable(metadata_controller.save_metadata_editor_state)


# ------------------------------------------------------------------- Tkinter


@requires_display
def test_manual_docx_selection_full_flow(monkeypatch) -> None:
    """Parcours complet dans une unique fenetre reelle.

    Verifie, dans l'ordre : (1) aucun selecteur ne s'ouvre seul au demarrage,
    (2) les actions dependant d'un document sont desactivees, (3) annuler le
    selecteur manuel ne cree aucun etat et laisse la fenetre ouverte, (4)
    choisir un DOCX cree un etat normal, active les actions et fait passer le
    bouton a « Relocaliser le DOCX... ».
    """
    responses = iter(["", str(DOCX)])
    dialog_calls = {"n": 0}

    def fake_askopenfilename(**kwargs: object) -> str:
        dialog_calls["n"] += 1
        return next(responses)

    monkeypatch.setattr(filedialog, "askopenfilename", fake_askopenfilename)

    real_tk = tk.Tk

    def spy_tk() -> tk.Tk:
        root = real_tk()

        def stage_initial() -> None:
            assert dialog_calls["n"] == 0
            locate = _find_button_by_text(root, "Localiser le DOCX…")
            save_close = _find_button_by_text(root, "Enregistrer et fermer")
            assert locate is not None
            assert save_close is not None
            assert str(save_close["state"]) == "disabled"

            locate.invoke()  # 1er clic : annulation du selecteur
            assert dialog_calls["n"] == 1
            assert root.winfo_exists()
            assert _find_button_by_text(root, "Localiser le DOCX…") is locate
            assert str(save_close["state"]) == "disabled"

            root.after(20, stage_loaded)

        def stage_loaded() -> None:
            locate = _find_button_by_text(root, "Localiser le DOCX…")
            assert locate is not None
            locate.invoke()  # 2e clic : DOCX choisi
            assert dialog_calls["n"] == 2
            assert _find_button_by_text(root, "Relocaliser le DOCX…") is not None
            save_close = _find_button_by_text(root, "Enregistrer et fermer")
            assert str(save_close["state"]) == "normal"
            root.after(20, root.destroy)

        root.after(80, stage_initial)
        return root

    monkeypatch.setattr(tk, "Tk", spy_tk)

    result = editor_module.run_metadata_editor()

    assert result == 0
    assert dialog_calls["n"] == 2
