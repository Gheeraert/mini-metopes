"""Tests hors Tkinter de la generation TEI Commons declenchee depuis la GUI.

``generate_tei_commons`` est la fonction testable extraite pour le bouton
« Generer la TEI Commons... » : elle ne fait qu'orchestrer le coeur de
conversion/ecriture deja couvert par ``test_metadata_cli_and_tei.py`` et
``test_figures.py``, donc ces tests se concentrent sur son contrat propre
(bilan structure, aucune ecriture en cas d'echec, metadonnees courantes).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from mini_metopes.gui.metadata_controller import TeiGenerationOutcome, generate_tei_commons, parse_pagination_field
from mini_metopes.metadata import (
    METADATA_SCHEMA_VERSION,
    DocumentMetadata,
    SourceDocument,
    compute_file_sha256,
    load_metadata_file,
)
from mini_metopes.validation import validate_xml_file

FIXTURES = Path(__file__).parent / "fixtures"
DOCX = FIXTURES / "docx" / "native-tei-conversion.docx"
JSON = FIXTURES / "metadata" / "native-tei-conversion.metadata.json"
FIGURES_DOCX = FIXTURES / "docx" / "native-figures.docx"
FIGURES_JSON = FIXTURES / "metadata" / "native-figures.metadata.json"
LATE_TITLE_DOCX = FIXTURES / "docx" / "native-editorial.docx"


def _metadata(path: Path = JSON) -> DocumentMetadata:
    loaded = load_metadata_file(path)
    assert loaded.metadata is not None
    return loaded.metadata


def test_generate_tei_commons_success_writes_valid_xml(tmp_path: Path) -> None:
    output = tmp_path / "article.xml"

    outcome = generate_tei_commons(DOCX, _metadata(), output)

    assert isinstance(outcome, TeiGenerationOutcome)
    assert outcome.is_successful
    assert outcome.output_path == output
    assert output.exists()
    validation = validate_xml_file(output)
    assert validation.valid


def test_generate_tei_commons_writes_media(tmp_path: Path) -> None:
    output = tmp_path / "book.xml"

    outcome = generate_tei_commons(FIGURES_DOCX, _metadata(FIGURES_JSON), output)

    assert outcome.is_successful
    assert outcome.write_result is not None
    assert outcome.write_result.media_written == 2
    assert outcome.write_result.media_reused == 0
    media_directory = tmp_path / "media"
    assert media_directory.is_dir()
    assert len(list(media_directory.iterdir())) == 2

    second = generate_tei_commons(FIGURES_DOCX, _metadata(FIGURES_JSON), output)
    assert second.write_result is not None
    assert second.write_result.media_written == 0
    assert second.write_result.media_reused == 2


def test_generate_tei_commons_failure_writes_nothing(tmp_path: Path) -> None:
    output = tmp_path / "article.xml"
    metadata = DocumentMetadata(
        METADATA_SCHEMA_VERSION,
        SourceDocument(LATE_TITLE_DOCX.name, compute_file_sha256(LATE_TITLE_DOCX)),
        "chapter",
        "fr",
        "Titre JSON",
    )

    outcome = generate_tei_commons(LATE_TITLE_DOCX, metadata, output)

    assert not outcome.is_successful
    assert outcome.write_result is None
    assert not output.exists()
    assert any(diagnostic.severity == "error" for diagnostic in outcome.result.diagnostics)


def test_generate_tei_commons_uses_the_metadata_passed_in_not_a_stale_json(tmp_path: Path) -> None:
    """Le titre effectivement passe en argument doit apparaitre dans la TEI, meme
    s'il ne correspond plus au JSON enregistre sur disque."""
    output = tmp_path / "article.xml"
    current = replace(_metadata(), title="Titre courant du formulaire")

    outcome = generate_tei_commons(DOCX, current, output)

    assert outcome.is_successful
    assert outcome.result.xml_bytes is not None
    assert b"Titre courant du formulaire" in outcome.result.xml_bytes


def test_generate_tei_commons_propagates_write_errors_without_faking_success(tmp_path: Path) -> None:
    """Une ecriture impossible (destination = repertoire) doit lever, pas produire un faux succes."""
    output = tmp_path / "as-directory.xml"
    output.mkdir()

    with pytest.raises(OSError):
        generate_tei_commons(DOCX, _metadata(), output)


def test_parse_pagination_field_accepts_empty_value() -> None:
    assert parse_pagination_field("") is None
    assert parse_pagination_field("   ") is None


def test_parse_pagination_field_accepts_digits() -> None:
    assert parse_pagination_field("12") == 12
    assert parse_pagination_field("  42  ") == 42


@pytest.mark.parametrize("value", ["12.5", "p.12", "-3", "douze"])
def test_parse_pagination_field_rejects_non_integer_input(value: str) -> None:
    """Une saisie non numerique doit lever, jamais produire une valeur fabriquee."""
    with pytest.raises(ValueError):
        parse_pagination_field(value)
