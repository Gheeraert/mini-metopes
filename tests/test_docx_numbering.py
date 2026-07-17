"""Resolution conservative des definitions de numerotation Word."""

from __future__ import annotations

from pathlib import Path

from mini_metopes.docx import inspect_docx_file
from mini_metopes.tei import convert_docx_to_tei
from mini_metopes.metadata import load_metadata_file


FIXTURES = Path(__file__).parent / "fixtures"


def test_native_lists_resolve_definitions_overrides_and_notes() -> None:
    inspection = inspect_docx_file(FIXTURES / "docx" / "native-lists.docx")

    definition = inspection.numbering_definitions.abstract_definitions[0]
    assert definition.abstract_numbering_id == "10"
    assert [level.num_format for level in definition.levels] == ["decimal", "bullet", "lowerLetter"]
    assert [instance.numbering_id for instance in inspection.numbering_definitions.instances] == ["42", "43"]
    assert inspection.numbering_definitions.instances[1].level_overrides[0].start_override == 5

    assert inspection.paragraphs[1].numbering is not None
    assert inspection.paragraphs[1].numbering.list_kind == "ordered"
    assert inspection.paragraphs[2].numbering is not None
    assert inspection.paragraphs[2].numbering.list_kind == "bulleted"
    assert inspection.paragraphs[6].numbering is not None
    assert inspection.paragraphs[6].numbering.start == 5
    assert inspection.paragraphs[7].numbering is not None
    assert inspection.paragraphs[7].numbering.num_format == "lowerLetter"
    assert inspection.footnotes[0].paragraphs[0].numbering is not None
    assert inspection.endnotes[0].paragraphs[0].numbering is not None


def test_numid_zero_is_explicitly_removed_and_does_not_block_alone() -> None:
    inspection = inspect_docx_file(FIXTURES / "docx" / "native-lists.docx")
    removed = inspection.paragraphs[-1]
    assert removed.numbering_id == "0"
    assert removed.numbering is not None
    assert removed.numbering.status == "removed"


def test_lists_remain_conservatively_blocking_for_tei_conversion() -> None:
    metadata = load_metadata_file(
        FIXTURES / "metadata" / "native-tei-conversion.metadata.json"
    ).metadata
    assert metadata is not None
    result = convert_docx_to_tei(FIXTURES / "docx" / "native-lists.docx", metadata=metadata)
    assert result.xml_bytes is None
    diagnostics = [item for item in result.diagnostics if item.code == "numbered_paragraph_not_serializable"]
    assert diagnostics
    assert any("kind=ordered" in item.message for item in diagnostics)
    assert any("kind=bulleted" in item.message for item in diagnostics)
