"""Tests du choix de destination « Enregistrer sous… » (hors Tkinter)."""

from pathlib import Path

from mini_metopes.gui.metadata_controller import (
    change_metadata_destination,
    create_initial_metadata_state,
    load_metadata_editor_state,
    requires_save_as,
    save_metadata_editor_state,
)
from mini_metopes.metadata import resolve_source_document_path

FIXTURES = Path(__file__).parent / "fixtures"
DOCX = FIXTURES / "docx" / "native-tei-conversion.docx"
VALID_JSON = FIXTURES / "metadata" / "native-tei-conversion.metadata.json"


def test_docx_without_json_requires_save_as(tmp_path: Path) -> None:
    state = create_initial_metadata_state(DOCX, tmp_path / "missing.metadata.json")
    assert state.metadata_file_exists is False
    assert requires_save_as(state) is True
    assert not (tmp_path / "missing.metadata.json").exists()


def test_existing_valid_json_does_not_require_save_as() -> None:
    state = load_metadata_editor_state(DOCX, VALID_JSON)
    assert state.loaded_from_invalid_json is False
    assert state.metadata_file_exists is True
    assert requires_save_as(state) is False


def test_existing_invalid_json_is_not_treated_as_new(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid.metadata.json"
    invalid_path.write_text('{"document": []}', encoding="utf-8")
    state = load_metadata_editor_state(DOCX, invalid_path)
    assert state.loaded_from_invalid_json is True
    assert state.metadata_file_exists is True
    assert requires_save_as(state) is False


def test_change_destination_updates_metadata_path(tmp_path: Path) -> None:
    state = create_initial_metadata_state(DOCX, tmp_path / "missing.metadata.json")
    new_path = tmp_path / "sub" / "chosen.metadata.json"
    new_path.parent.mkdir()
    changed = change_metadata_destination(state, new_path)
    assert changed.metadata_path == new_path


def test_change_destination_recomputes_source_path_relative_to_new_folder(tmp_path: Path) -> None:
    state = create_initial_metadata_state(DOCX, tmp_path / "missing.metadata.json")
    new_dir = tmp_path / "elsewhere"
    new_dir.mkdir()
    new_path = new_dir / "chosen.metadata.json"
    changed = change_metadata_destination(state, new_path)
    resolved = resolve_source_document_path(changed.metadata.source.path, new_path)
    assert resolved.resolve() == DOCX.resolve()


def test_change_destination_preserves_sha256(tmp_path: Path) -> None:
    state = create_initial_metadata_state(DOCX, tmp_path / "missing.metadata.json")
    original_sha = state.metadata.source.sha256
    new_path = tmp_path / "chosen.metadata.json"
    changed = change_metadata_destination(state, new_path)
    assert changed.metadata.source.sha256 == original_sha
    assert changed.dirty is True


def test_save_after_destination_change_no_longer_requires_save_as(tmp_path: Path) -> None:
    state = create_initial_metadata_state(DOCX, tmp_path / "missing.metadata.json")
    new_path = tmp_path / "chosen.metadata.json"
    changed = change_metadata_destination(state, new_path)
    saved = save_metadata_editor_state(changed)
    assert saved.metadata_file_exists is True
    assert requires_save_as(saved) is False
    assert new_path.exists()


def test_no_write_occurs_until_destination_is_chosen(tmp_path: Path) -> None:
    state = create_initial_metadata_state(DOCX, tmp_path / "missing.metadata.json")
    assert requires_save_as(state)
    assert list(tmp_path.iterdir()) == []
