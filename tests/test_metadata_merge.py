from dataclasses import replace
from pathlib import Path

from mini_metopes.gui.metadata_controller import (
    create_initial_metadata_state,
    is_metadata_dirty,
    load_metadata_editor_state,
    remove_affiliation,
    save_metadata_editor_state,
    update_affiliation,
    update_contributor,
)
from mini_metopes.metadata import load_metadata_file, metadata_consistency_issues, metadata_to_json
import pytest


FIXTURES = Path(__file__).parent / "fixtures"


def test_json_remains_authoritative_and_conflicts_are_warnings(tmp_path: Path) -> None:
    docx = FIXTURES / "docx" / "native-tei-conversion.docx"
    loaded = load_metadata_file(FIXTURES / "metadata" / "native-tei-conversion.metadata.json")
    assert loaded.metadata is not None
    state = create_initial_metadata_state(docx, tmp_path / "missing.json")
    assert state.metadata.title == "Une conversion synthetique"
    changed = replace(loaded.metadata, title="Titre JSON")
    codes = [issue.code for issue in metadata_consistency_issues(changed, docx, state.suggestions)]
    assert "metadata_title_differs_from_docx" in codes


def test_controller_refuses_removing_used_affiliation(tmp_path: Path) -> None:
    docx = FIXTURES / "docx" / "native-tei-conversion.docx"
    state = load_metadata_editor_state(docx, FIXTURES / "metadata" / "native-tei-conversion.metadata.json")
    with pytest.raises(ValueError):
        remove_affiliation(state, "affiliation-1")


def test_controller_loads_consistency_warnings_and_invalid_json(tmp_path: Path) -> None:
    docx = FIXTURES / "docx" / "native-tei-conversion.docx"
    loaded = load_metadata_file(FIXTURES / "metadata" / "native-tei-conversion.metadata.json")
    assert loaded.metadata is not None
    changed = replace(loaded.metadata, title="Titre JSON", source=replace(loaded.metadata.source, sha256="b" * 64))
    metadata_path = tmp_path / "changed.metadata.json"
    metadata_path.write_text(metadata_to_json(changed), encoding="utf-8")

    state = load_metadata_editor_state(docx, metadata_path)
    codes = [issue.code for issue in state.issues]
    assert "metadata_source_changed" in codes
    assert "metadata_title_differs_from_docx" in codes
    assert not state.loaded_from_invalid_json

    invalid_path = tmp_path / "invalid.metadata.json"
    invalid_path.write_text('{"document": []}', encoding="utf-8")
    invalid = load_metadata_editor_state(docx, invalid_path)
    assert invalid.loaded_from_invalid_json
    assert "invalid_metadata_structure" in [issue.code for issue in invalid.issues]


def test_save_updates_sha_and_dirty_snapshot(tmp_path: Path) -> None:
    docx = FIXTURES / "docx" / "native-tei-conversion.docx"
    state = load_metadata_editor_state(docx, FIXTURES / "metadata" / "native-tei-conversion.metadata.json")
    changed = replace(state, metadata=replace(state.metadata, source=replace(state.metadata.source, sha256="b" * 64)))
    assert is_metadata_dirty(changed.saved_metadata, changed.metadata)
    saved = save_metadata_editor_state(replace(changed, metadata_path=tmp_path / "saved.metadata.json"))
    assert not saved.dirty
    assert not is_metadata_dirty(saved.saved_metadata, saved.metadata)
    assert "metadata_source_changed" not in [issue.code for issue in saved.issues]


def test_controller_renames_editable_identifiers_and_references() -> None:
    docx = FIXTURES / "docx" / "native-tei-conversion.docx"
    state = load_metadata_editor_state(docx, FIXTURES / "metadata" / "native-tei-conversion.metadata.json")
    contributor = replace(state.metadata.contributors[0], contributor_id="person-tony")
    state = update_contributor(state, "person-1", contributor)
    assert state.metadata.contributors[0].contributor_id == "person-tony"

    affiliation = replace(state.metadata.affiliations[0], affiliation_id="affiliation-urn")
    state = update_affiliation(state, "affiliation-1", affiliation)
    assert state.metadata.affiliations[0].affiliation_id == "affiliation-urn"
    assert "affiliation-urn" in state.metadata.contributors[0].affiliation_ids
    assert "affiliation-1" not in state.metadata.contributors[0].affiliation_ids
    with pytest.raises(ValueError):
        update_affiliation(state, "affiliation-urn", replace(affiliation, affiliation_id="affiliation-2"))
