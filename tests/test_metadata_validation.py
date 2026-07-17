from dataclasses import replace

import pytest

from mini_metopes.metadata import Affiliation, Contributor, DocumentMetadata, METADATA_SCHEMA_VERSION, MetadataSource, validate_metadata


@pytest.fixture()
def metadata() -> DocumentMetadata:
    return DocumentMetadata(METADATA_SCHEMA_VERSION, MetadataSource("x.docx", "a" * 64), "chapter", "fr", "Titre", contributors=(Contributor("person-1", "author", given_name="A", family_name="B", affiliation_ids=("affiliation-1",)),), affiliations=(Affiliation("affiliation-1", "Universite"),))


@pytest.mark.parametrize("changed,code", [
    (lambda item: replace(item, title=" "), "missing_title"),
    (lambda item: replace(item, language="français"), "invalid_language"),
    (lambda item: replace(item, document_type="invalid"), "invalid_document_type"),
    (lambda item: replace(item, source=MetadataSource("x.docx", "short")), "invalid_source_sha256"),
    (lambda item: replace(item, schema_version="9"), "unsupported_schema_version"),
])
def test_validation_codes(metadata, changed, code: str) -> None:
    assert code in [issue.code for issue in validate_metadata(changed(metadata)).issues]


def test_people_affiliations_orcid_and_ror_are_validated(metadata) -> None:
    duplicate = replace(metadata, contributors=metadata.contributors + metadata.contributors)
    assert "duplicate_contributor_id" in [issue.code for issue in validate_metadata(duplicate).issues]
    missing = replace(metadata, contributors=(replace(metadata.contributors[0], affiliation_ids=("unknown",)),))
    assert "unknown_affiliation_reference" in [issue.code for issue in validate_metadata(missing).issues]
    invalid = replace(metadata, contributors=(replace(metadata.contributors[0], literal_name="Collectif"),))
    assert "invalid_contributor_name" in [issue.code for issue in validate_metadata(invalid).issues]
    invalid_orcid = replace(metadata, contributors=(replace(metadata.contributors[0], orcid="0000-0000-0000-0000"),))
    assert "invalid_orcid" in [issue.code for issue in validate_metadata(invalid_orcid).issues]
    invalid_ror = replace(metadata, affiliations=(replace(metadata.affiliations[0], ror="ror.org/x"),))
    assert "invalid_ror" in [issue.code for issue in validate_metadata(invalid_ror).issues]
