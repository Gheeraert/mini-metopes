from dataclasses import replace
from pathlib import Path

from mini_metopes.gui.metadata_controller import create_initial_metadata_state, load_metadata_editor_state, remove_affiliation
from mini_metopes.metadata import load_metadata_file, metadata_consistency_issues
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
