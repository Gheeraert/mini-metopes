"""Tests hors Tkinter du contrat public de ``open_metadata_editor``.

``MetadataEditorResult`` et le cablage textuel de ``prompt_for_new_destination``
/ ``show_tei_generation`` sont testables sans jamais construire de widget. Les
parcours pilotant reellement une fenetre Tkinter (nouvelle fenetre integree,
enregistrement, annulation, bouton TEI) sont dans
``test_metadata_editor_embedding.py``.
"""

from __future__ import annotations

from pathlib import Path

from mini_metopes.gui import MetadataEditorResult, open_metadata_editor, run_metadata_editor
from mini_metopes.gui.metadata_editor_api import MetadataEditorResult as ExportedResult
import mini_metopes.gui.metadata_editor as editor_module

FIXTURES = Path(__file__).parent / "fixtures"
DOCX = FIXTURES / "docx" / "native-tei-conversion.docx"

_SOURCE = Path(editor_module.__file__).read_text(encoding="utf-8")
_API_SOURCE = Path(editor_module.__file__).parent.joinpath("metadata_editor_api.py").read_text(encoding="utf-8")


def test_public_api_is_exported_from_the_gui_package() -> None:
    """Le contrat integre est accessible sans toucher aux modules internes."""
    assert MetadataEditorResult is ExportedResult
    assert callable(open_metadata_editor)
    assert callable(run_metadata_editor)


def test_result_type_has_no_tkinter_dependency() -> None:
    """``MetadataEditorResult`` doit rester importable sans jamais charger Tkinter."""
    assert "tkinter" not in _API_SOURCE
    assert "import tk" not in _API_SOURCE


def test_saved_result_reports_saved_true_with_path(tmp_path: Path) -> None:
    result = MetadataEditorResult("saved", DOCX, tmp_path / "document.metadata.json")
    assert result.saved is True


def test_cancelled_result_reports_saved_false_without_path() -> None:
    result = MetadataEditorResult("cancelled", DOCX, None)
    assert result.saved is False
    assert result.metadata_path is None


def test_saved_status_without_metadata_path_is_not_considered_saved() -> None:
    """Garde-fou de coherence : ``saved`` exige un chemin, pas seulement le statut."""
    result = MetadataEditorResult("saved", DOCX, None)
    assert result.saved is False


def test_save_as_dialog_is_gated_by_prompt_for_new_destination() -> None:
    """La destination n'est demandee par selecteur que si ``prompt_for_new_destination`` l'exige."""
    assert "if requires_save_as(candidate) and prompt_for_new_destination:" in _SOURCE


def test_invalid_json_confirmation_is_independent_of_the_destination_prompt() -> None:
    """La confirmation d'ecrasement d'un JSON invalide reste inconditionnelle.

    Elle doit s'executer avant le branchement sur ``prompt_for_new_destination``,
    qu'un nouveau JSON soit cree ou qu'un JSON existant invalide soit remplace.
    """
    confirm_index = _SOURCE.index("JSON invalide", _SOURCE.index("loaded_from_invalid_json and not messagebox.askyesno"))
    gate_index = _SOURCE.index("if requires_save_as(candidate) and prompt_for_new_destination:")
    assert confirm_index < gate_index


def test_generate_button_creation_is_gated_by_show_tei_generation() -> None:
    """Le bouton de generation TEI n'est construit que si ``show_tei_generation`` est vrai."""
    assert "if show_tei_generation:\n        generate_button = ttk.Button(actions, text=\"Générer la TEI Commons…\", command=generate_tei)" in _SOURCE


def test_shared_builder_is_reused_by_both_entry_points() -> None:
    """``run_metadata_editor`` et ``open_metadata_editor`` construisent depuis la meme fonction."""
    assert _SOURCE.count("_build_metadata_editor(") == 3  # definition + 2 appels


def _open_metadata_editor_code_body() -> str:
    """Isoler le code de ``open_metadata_editor``, apres sa docstring."""
    start = _SOURCE.index("def open_metadata_editor(")
    docstring_end = _SOURCE.index('"""', _SOURCE.index('"""', start) + 3) + 3
    return _SOURCE[docstring_end:]


def test_open_metadata_editor_never_creates_a_new_tk_root() -> None:
    """Le mode integre doit uniquement instancier un ``Toplevel``, jamais un ``Tk``."""
    body = _open_metadata_editor_code_body()
    assert "tk.Toplevel(parent)" in body
    assert "tk.Tk()" not in body


def test_open_metadata_editor_never_calls_mainloop() -> None:
    body = _open_metadata_editor_code_body()
    assert "mainloop" not in body
    assert "wait_window(window)" in body
