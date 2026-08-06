from dataclasses import replace
from pathlib import Path

import pytest

from mini_metopes.metadata import (
    Collection,
    Funding,
    load_metadata_file,
    metadata_from_json,
    metadata_to_json,
    write_metadata_file,
)


FIXTURE = Path(__file__).parent / "fixtures" / "metadata" / "native-tei-conversion.metadata.json"


def test_json_round_trip_is_deterministic_and_unicode() -> None:
    loaded = load_metadata_file(FIXTURE)
    assert loaded.valid and loaded.metadata is not None
    rendered = metadata_to_json(loaded.metadata)
    assert rendered.endswith("\n")
    assert metadata_from_json(rendered).metadata == loaded.metadata
    assert metadata_to_json(loaded.metadata) == rendered


def test_funding_and_collection_editor_round_trip() -> None:
    loaded = load_metadata_file(FIXTURE)
    assert loaded.metadata is not None
    enriched = replace(
        loaded.metadata,
        funding=(Funding("ANR", "ANR-23-CE38-0001"), Funding("ERC")),
        collection=Collection("Une collection", editor="Un directeur de collection"),
    )
    rendered = metadata_to_json(enriched)
    round_tripped = metadata_from_json(rendered)
    assert round_tripped.metadata == enriched


def test_invalid_json_and_atomic_write_preserve_target(tmp_path: Path) -> None:
    assert not metadata_from_json("{").valid
    loaded = load_metadata_file(FIXTURE)
    assert loaded.metadata is not None
    destination = tmp_path / "metadata.json"
    destination.write_text("ancienne", encoding="utf-8")
    with pytest.raises(ValueError):
        write_metadata_file(replace(loaded.metadata, title=""), destination)
    assert destination.read_text(encoding="utf-8") == "ancienne"
    write_metadata_file(loaded.metadata, destination)
    assert load_metadata_file(destination).valid


@pytest.mark.parametrize(
    ("payload", "code", "path"),
    [
        ("null", "invalid_metadata_structure", None),
        ("[]", "invalid_metadata_structure", None),
        ('{"schema_version":"1.0","source_document":[],"document":{},"contributors":[],"affiliations":[]}', "invalid_metadata_structure", "source_document"),
        ('{"schema_version":"1.0","source_document":{"path":"x.docx","sha256":"a"},"document":{"type":"chapter","language":"fr","title":null},"contributors":[],"affiliations":[]}', "invalid_field_type", "document.title"),
        ('{"schema_version":"1.0","source_document":{"path":"x.docx","sha256":"a"},"document":{"type":"chapter","language":3,"title":"T"},"contributors":[],"affiliations":[]}', "invalid_field_type", "document.language"),
        ('{"schema_version":"1.0","source_document":{"path":"x.docx","sha256":"a"},"document":{"type":"chapter","language":"fr","title":"T"},"contributors":[],"affiliations":[],"keywords":[{"language":"fr","items":[null]}]}', "invalid_field_type", "keywords[0].items[0]"),
        ('{"schema_version":"1.0","source_document":{"path":"x.docx","sha256":"a"},"document":{"type":"chapter","language":"fr","title":"T"},"contributors":["x"],"affiliations":[]}', "invalid_metadata_structure", "contributors[0]"),
        ('{"schema_version":"1.0","source_document":{"path":"x.docx","sha256":"a"},"document":{"type":"chapter","language":"fr","title":"T"},"contributors":[{"id":"p","role":[]}],"affiliations":[]}', "invalid_field_type", "contributors[0].role"),
        ('{"schema_version":"1.0","source_document":{"path":"x.docx","sha256":"a"},"document":{"type":"chapter","language":"fr","title":"T"},"contributors":[{"id":"p","role":"author","affiliations":true}],"affiliations":[]}', "invalid_field_type", "contributors[0].affiliations"),
        ('{"schema_version":"1.0","source_document":{"path":"x.docx","sha256":"a"},"document":{"type":"chapter","language":"fr","title":"T"},"contributors":[],"affiliations":[3]}', "invalid_metadata_structure", "affiliations[0]"),
        ('{"schema_version":"1.0","source_document":{"path":"x.docx","sha256":"a"},"document":{"type":"chapter","language":"fr","title":"T"},"contributors":[],"affiliations":[{"id":"a","name":"N","ror":7}]}', "invalid_field_type", "affiliations[0].ror"),
        ('{"schema_version":"1.0","source_document":{"path":"x.docx","sha256":"a"},"document":{"type":"chapter","language":"fr","title":"T"},"contributors":[],"affiliations":[],"identifiers":[{"type":"doi"}]}', "missing_metadata_field", "identifiers[0].value"),
        ('{"schema_version":"1.0","source_document":{"path":"x.docx","sha256":"a"},"document":{"type":"chapter","language":"fr","title":"T"},"contributors":[],"affiliations":[],"pagination":{"from":"a","to":2}}', "invalid_field_type", "pagination.from"),
        ('{"schema_version":"1.0","source_document":{"path":"x.docx","sha256":"a"},"document":{"type":"chapter","language":"fr","title":"T"},"contributors":[],"affiliations":[],"abstracts":[{"type":"summary","language":"fr"}]}', "missing_metadata_field", "abstracts[0].text"),
        ('{"schema_version":"1.0","source_document":{"path":"x.docx","sha256":"a"},"document":{"type":"chapter","language":"fr","title":"T"},"contributors":[],"affiliations":[],"funding":[{"grant_number":"X"}]}', "missing_metadata_field", "funding[0].funder"),
    ],
)
def test_badly_typed_json_never_raises(payload: str, code: str, path: str | None) -> None:
    result = metadata_from_json(payload)

    assert not result.valid
    assert code in [issue.code for issue in result.issues]
    if path is not None:
        assert path in [issue.path for issue in result.issues]
