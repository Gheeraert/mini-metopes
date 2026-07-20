"""Cablage du bouton « Generer la TEI Commons... » dans l'editeur Tkinter.

Meme principe que ``test_metadata_editor_startup.py`` : des assertions
statiques sur le code source pour les proprietes structurelles (ordre des
verifications, aucune duplication du coeur de conversion), et un seul test
pilotant une fenetre Tkinter reelle pour le parcours complet quand un
affichage est disponible.
"""

from __future__ import annotations

import shutil
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import tkinter.ttk as ttk
from pathlib import Path

import pytest

import mini_metopes.gui.metadata_editor as editor_module

FIXTURES = Path(__file__).parent / "fixtures"
DOCX = FIXTURES / "docx" / "native-tei-conversion.docx"
JSON = FIXTURES / "metadata" / "native-tei-conversion.metadata.json"

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


def test_generation_calls_the_shared_core_and_nothing_else() -> None:
    """La GUI ne doit pas reimplementer la conversion ou l'ecriture TEI.

    ``convert_docx_to_tei`` / ``write_tei_conversion_result`` ne doivent
    apparaitre nulle part dans le module GUI : seule ``generate_tei_commons``
    (dans ``metadata_controller``) les appelle.
    """
    assert "convert_docx_to_tei" not in _SOURCE
    assert "write_tei_conversion_result" not in _SOURCE
    assert "generate_tei_commons(state.docx_path, state.metadata, output_path)" in _SOURCE


def test_generation_reuses_the_shared_save_logic_before_choosing_output() -> None:
    """L'enregistrement des metadonnees precede le choix du fichier XML."""
    save_call_index = _SOURCE.index("save_current_metadata(close=False, show_success=False)")
    xml_dialog_index = _SOURCE.index('title="Générer la TEI Commons"')
    assert save_call_index < xml_dialog_index


def test_generation_aborts_when_metadata_save_is_cancelled() -> None:
    """Le retour False de save_current_metadata doit interrompre la generation."""
    save_call = _SOURCE.index("if not save_current_metadata(close=False, show_success=False):")
    following = _SOURCE[save_call : save_call + 90]
    assert "return" in following
    generation_index = _SOURCE.index("outcome = generate_tei_commons(")
    assert save_call < generation_index


def test_generation_aborts_when_output_path_is_cancelled() -> None:
    """Annuler le choix du XML ne doit pas declencher la conversion."""
    dialog_index = _SOURCE.index('title="Générer la TEI Commons"')
    cancel_index = _SOURCE.index("if not selected:\n            return", dialog_index)
    generation_index = _SOURCE.index("outcome = generate_tei_commons(")
    assert dialog_index < cancel_index < generation_index


def test_generate_button_is_wired_into_the_shared_enable_disable_logic() -> None:
    """Le bouton de generation suit exactement la meme regle que les boutons d'enregistrement."""
    start = _SOURCE.index("def set_editor_enabled")
    enable_block = _SOURCE[start:]
    end = enable_block.index("\n\n", 10)
    assert "generate_button.configure(state=" in enable_block[:end]


def test_generation_restores_the_ui_in_a_finally_block() -> None:
    """Le curseur et le bouton doivent revenir a la normale, meme en cas d'erreur."""
    try_index = _SOURCE.index("outcome = generate_tei_commons(state.docx_path, state.metadata, output_path)")
    finally_index = _SOURCE.index("finally:", try_index)
    restore_block = _SOURCE[finally_index : finally_index + 200]
    assert 'cursor=""' in restore_block
    assert "generate_button.configure(state=\"normal\"" in restore_block


# ------------------------------------------------------------------- Tkinter


@requires_display
def test_manual_generation_full_flow(monkeypatch, tmp_path: Path) -> None:
    """Parcours complet : chargement, generation, message de succes, reutilisation du JSON."""
    docx_copy = tmp_path / "article.docx"
    json_copy = tmp_path / "article.metadata.json"
    shutil.copyfile(DOCX, docx_copy)
    shutil.copyfile(JSON, json_copy)

    open_calls = {"n": 0}

    def fake_askopenfilename(**kwargs: object) -> str:
        open_calls["n"] += 1
        return str(docx_copy)

    save_dialog_titles: list[str] = []
    xml_outputs = [tmp_path / "premiere.xml", tmp_path / "seconde.xml"]

    def fake_asksaveasfilename(**kwargs: object) -> str:
        title = str(kwargs.get("title", ""))
        save_dialog_titles.append(title)
        if title == "Générer la TEI Commons":
            return str(xml_outputs[sum(1 for value in save_dialog_titles if value == title) - 1])
        return str(json_copy)

    info_messages: list[tuple[str, str]] = []
    error_messages: list[tuple[str, str]] = []

    monkeypatch.setattr(filedialog, "askopenfilename", fake_askopenfilename)
    monkeypatch.setattr(filedialog, "asksaveasfilename", fake_asksaveasfilename)
    monkeypatch.setattr(messagebox, "showinfo", lambda title, message, **kwargs: info_messages.append((title, message)))
    monkeypatch.setattr(messagebox, "showerror", lambda title, message, **kwargs: error_messages.append((title, message)))

    real_tk = tk.Tk

    def spy_tk() -> tk.Tk:
        root = real_tk()

        def stage_initial() -> None:
            generate_button = _find_button_by_text(root, "Générer la TEI Commons…")
            assert generate_button is not None
            assert str(generate_button["state"]) == "disabled"

            locate = _find_button_by_text(root, "Localiser le DOCX…")
            assert locate is not None
            locate.invoke()
            root.after(20, stage_loaded)

        def stage_loaded() -> None:
            generate_button = _find_button_by_text(root, "Générer la TEI Commons…")
            assert generate_button is not None
            assert str(generate_button["state"]) == "normal"

            generate_button.invoke()
            root.after(20, stage_generated_once)

        def stage_generated_once() -> None:
            assert xml_outputs[0].exists()
            assert len(info_messages) == 1
            assert str(xml_outputs[0]) in info_messages[0][1]
            assert "Validation Commons Publishing : réussie" in info_messages[0][1]
            assert not error_messages
            generate_button = _find_button_by_text(root, "Générer la TEI Commons…")
            assert generate_button is not None
            assert str(generate_button["state"]) == "normal"

            generate_button.invoke()
            root.after(20, stage_generated_twice)

        def stage_generated_twice() -> None:
            assert xml_outputs[1].exists()
            assert len(info_messages) == 2
            assert save_dialog_titles.count("Enregistrer les metadonnees sous…") == 0
            root.after(20, root.destroy)

        root.after(80, stage_initial)
        return root

    monkeypatch.setattr(tk, "Tk", spy_tk)

    result = editor_module.run_metadata_editor()

    assert result == 0
    assert not error_messages
