from dataclasses import replace
from pathlib import Path

from mini_metopes.docx import inspect_docx_file
from mini_metopes.metadata import extract_metadata_suggestions


FIXTURES = Path(__file__).parent / "fixtures" / "docx"


def test_initial_title_and_subtitle_are_suggested_by_stable_style_id() -> None:
    inspection = inspect_docx_file(FIXTURES / "native-tei-conversion.docx")
    suggestions = extract_metadata_suggestions(inspection)
    assert (suggestions.title, suggestions.subtitle, suggestions.consumed_paragraph_indexes) == ("Une conversion synthetique", "Metadonnees JSON et TEI", (0, 1))


def test_title_after_body_is_not_consumed_and_is_an_error() -> None:
    inspection = inspect_docx_file(FIXTURES / "native-tei-conversion.docx")
    changed = replace(inspection, paragraphs=inspection.paragraphs[2:] + (inspection.paragraphs[0],))
    suggestions = extract_metadata_suggestions(changed)
    assert "metadata_style_not_initial" in [issue.code for issue in suggestions.diagnostics]
