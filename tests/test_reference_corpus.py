"""Corpus de référence Mini-Métopes : contrat de bout en bout."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from mini_metopes.docx import DocxInspectionError
from mini_metopes.metadata import load_metadata_file
from mini_metopes.tei import convert_docx_to_tei
from mini_metopes.validation import validate_xml_bytes


CORPUS = Path(__file__).parent / "fixtures" / "corpus"
VALID_DOCUMENTS = ("document-a", "document-b", "document-c")
BLOCKED_CASES = (
    "document-d/unknown-custom-style",
    "document-d/discontinuous-list",
    "document-d/textbox",
)


def _convert(directory: Path):
    loaded = load_metadata_file(directory / "metadata.json")
    assert loaded.metadata is not None, loaded.issues
    return convert_docx_to_tei(directory / "source.docx", metadata=loaded.metadata)


def _expected_diagnostics(directory: Path):
    return json.loads((directory / "expected-diagnostics.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", VALID_DOCUMENTS)
def test_valid_corpus_documents_produce_the_expected_tei(name: str) -> None:
    directory = CORPUS / name
    result = _convert(directory)

    assert result.is_successful, result.diagnostics
    assert result.xml_bytes == (directory / "expected.xml").read_bytes()
    assert [asdict(diagnostic) for diagnostic in result.diagnostics] == _expected_diagnostics(directory)


@pytest.mark.parametrize("name", VALID_DOCUMENTS)
def test_valid_corpus_documents_validate_against_the_embedded_schema(name: str) -> None:
    result = _convert(CORPUS / name)
    assert result.xml_bytes is not None
    validation = validate_xml_bytes(result.xml_bytes)
    assert validation.valid, validation.issues


@pytest.mark.parametrize("name", VALID_DOCUMENTS)
def test_corpus_conversion_is_deterministic(name: str) -> None:
    directory = CORPUS / name
    first = _convert(directory)
    second = _convert(directory)
    assert first.xml_bytes == second.xml_bytes
    assert first.diagnostics == second.diagnostics


@pytest.mark.parametrize("name", BLOCKED_CASES)
def test_blocked_corpus_cases_produce_no_tei_and_stable_diagnostics(name: str) -> None:
    directory = CORPUS / name
    result = _convert(directory)

    assert not result.is_successful
    assert result.xml_bytes is None
    assert not (directory / "expected.xml").exists()
    assert [asdict(diagnostic) for diagnostic in result.diagnostics] == _expected_diagnostics(directory)
    assert any(diagnostic.severity == "error" for diagnostic in result.diagnostics)


def test_metopes_tei_quote_style_is_rejected_as_unknown_custom_style() -> None:
    """Périmètre : aucun style Métopes ``TEI_*`` n'est reconnu en entrée."""
    directory = CORPUS / "document-d" / "unknown-custom-style"
    result = _convert(directory)
    assert any(
        diagnostic.code == "unsupported_paragraph_style"
        and diagnostic.severity == "error"
        and diagnostic.style_id == "TEIquote"
        for diagnostic in result.diagnostics
    )


def test_heading_level_jump_is_currently_informative_only() -> None:
    directory = CORPUS / "document-d" / "heading-level-jump"
    result = _convert(directory)

    assert result.is_successful
    assert result.xml_bytes == (directory / "expected.xml").read_bytes()
    assert [asdict(diagnostic) for diagnostic in result.diagnostics] == _expected_diagnostics(directory)
    assert [d.code for d in result.diagnostics] == ["heading_level_jump"]


def test_malformed_package_raises_a_stable_inspection_error() -> None:
    directory = CORPUS / "document-d" / "malformed-package"
    expected = _expected_diagnostics(directory)
    loaded = load_metadata_file(directory / "metadata.json")
    assert loaded.metadata is not None

    with pytest.raises(DocxInspectionError) as excinfo:
        convert_docx_to_tei(directory / "source.docx", metadata=loaded.metadata)
    assert excinfo.value.code == expected["inspection_error"]
