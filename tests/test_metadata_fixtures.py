"""Fixtures du contrat JSON v2 : cas valides, invalides et determinisme."""

from __future__ import annotations

from pathlib import Path

import pytest

from mini_metopes.metadata import load_metadata_file, metadata_from_json, metadata_to_json


FIXTURES = Path(__file__).parent / "fixtures" / "metadata"
VALID = ("minimal-v0.1.json", "complete-purh-v0.2.json", "multilingual-v0.2.json")


@pytest.mark.parametrize("name", VALID)
def test_valid_fixtures_load_and_round_trip_byte_identical(name: str) -> None:
    content = (FIXTURES / name).read_text(encoding="utf-8")
    loaded = metadata_from_json(content)
    assert loaded.valid and loaded.metadata is not None, loaded.issues
    rendered = metadata_to_json(loaded.metadata)
    assert rendered == content
    assert metadata_to_json(loaded.metadata) == rendered


def test_complete_purh_fixture_covers_all_groups() -> None:
    metadata = load_metadata_file(FIXTURES / "complete-purh-v0.2.json").metadata
    assert metadata is not None
    assert metadata.language == "fr-FR"
    assert [item.role for item in metadata.contributors] == ["author", "translator"]
    assert metadata.contributors[0].orcid == "0000-0002-1825-0097"
    assert metadata.editorial_responsibility[0].name == "Anaïs Monchy"
    assert metadata.publication.publisher.place == "Mont-Saint-Aignan"
    assert [item.identifier_format for item in metadata.identifiers] == [None, "print", "epub"]
    assert metadata.rights.license.url == "https://creativecommons.org/licenses/by-nc-nd/4.0/"
    assert [item.abstract_type for item in metadata.abstracts] == ["summary", "back-cover"]
    assert metadata.collection is not None and metadata.collection.volume == "7"
    assert metadata.pagination is not None and metadata.pagination.page_from == 125


def test_multilingual_fixture_preserves_unicode_and_order() -> None:
    metadata = load_metadata_file(FIXTURES / "multilingual-v0.2.json").metadata
    assert metadata is not None
    assert metadata.title.startswith("Οἰδίπους")
    assert [item.language for item in metadata.abstracts] == ["fr", "en", "grc"]
    assert metadata.keywords[1].items == ("τραγῳδία", "Οἰδίπους")


@pytest.mark.parametrize(
    ("name", "codes"),
    [
        ("invalid-orcid.json", {"invalid_orcid"}),
        ("invalid-isbn.json", {"invalid_isbn"}),
        ("invalid-empty-fields.json", {"missing_title", "empty_abstract", "invalid_keyword", "invalid_affiliation_name"}),
    ],
)
def test_invalid_fixtures_produce_stable_codes(name: str, codes: set[str]) -> None:
    loaded = load_metadata_file(FIXTURES / name)
    assert loaded.metadata is None or not loaded.valid
    observed = {issue.code for issue in loaded.issues}
    assert codes <= observed
