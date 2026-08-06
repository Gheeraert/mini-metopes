from dataclasses import replace

import pytest

from mini_metopes.metadata import (
    Abstract,
    Affiliation,
    Collection,
    Contributor,
    DocumentMetadata,
    Funding,
    Identifier,
    KeywordGroup,
    License,
    METADATA_SCHEMA_VERSION,
    Pagination,
    Publication,
    Rights,
    SourceDocument,
    normalize_doi,
    normalize_isbn,
    normalize_issn,
    validate_metadata,
)


@pytest.fixture()
def metadata() -> DocumentMetadata:
    return DocumentMetadata(METADATA_SCHEMA_VERSION, SourceDocument("x.docx", "a" * 64), "chapter", "fr", "Titre", contributors=(Contributor("person-1", "author", given_name="A", family_name="B", affiliation_ids=("affiliation-1",)),), affiliations=(Affiliation("affiliation-1", "Universite"),))


@pytest.mark.parametrize("changed,code", [
    (lambda item: replace(item, title=" "), "missing_title"),
    (lambda item: replace(item, language="français"), "invalid_language"),
    (lambda item: replace(item, document_type="invalid"), "invalid_document_type"),
    (lambda item: replace(item, source=SourceDocument("x.docx", "short")), "invalid_source_sha256"),
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


def test_identifiers_are_compared_after_stripping(metadata) -> None:
    spaced = replace(metadata, affiliations=metadata.affiliations + (Affiliation(" affiliation-1", "Autre"),))
    codes = [issue.code for issue in validate_metadata(spaced).issues]
    assert "invalid_affiliation_id" in codes
    assert "duplicate_affiliation_id" in codes


@pytest.mark.parametrize(
    ("ror", "valid"),
    [
        ("https://ror.org/03yrm5c26", True),
        ("https://example.org/03yrm5c26", False),
        ("http://ror.org/03yrm5c26", False),
        ("https://ror.org/", False),
    ],
)
def test_ror_must_be_a_ror_org_https_identifier(metadata, ror: str, valid: bool) -> None:
    changed = replace(metadata, affiliations=(replace(metadata.affiliations[0], ror=ror),))
    codes = [issue.code for issue in validate_metadata(changed).issues]

    assert ("invalid_ror" not in codes) is valid


@pytest.mark.parametrize("changed,code", [
    (lambda item: replace(item, identifiers=(Identifier("doi", "pas-un-doi"),)), "invalid_doi"),
    (lambda item: replace(item, identifiers=(Identifier("isbn-13", "979-10-240-0000-0", "print"),)), "invalid_isbn"),
    (lambda item: replace(item, identifiers=(Identifier("isbn-13", "979-10-240-1755-6"),)), "missing_identifier_format"),
    (lambda item: replace(item, identifiers=(Identifier("issn", "1234-5678"),)), "invalid_issn"),
    (lambda item: replace(item, identifiers=(Identifier("ark", "x"),)), "invalid_identifier_type"),
    (lambda item: replace(item, identifiers=(Identifier("doi", "10.4000/x.1", "papier"),)), "invalid_identifier_format"),
    (lambda item: replace(item, publication=Publication(publication_date="2026-13")), "invalid_publication_date"),
    (lambda item: replace(item, publication=Publication(publication_date="hier")), "invalid_publication_date"),
    (lambda item: replace(item, rights=Rights(license=License("CC", "creativecommons.org"))), "invalid_license_url"),
    (lambda item: replace(item, rights=Rights(license=License(url="https://x.org/l"))), "missing_license_name"),
    (lambda item: replace(item, abstracts=(Abstract("summary", "fr", "  "),)), "empty_abstract"),
    (lambda item: replace(item, abstracts=(Abstract("preface", "fr", "x"),)), "invalid_abstract_type"),
    (lambda item: replace(item, abstracts=(Abstract("summary", "français", "x"),)), "invalid_language"),
    (lambda item: replace(item, keywords=(KeywordGroup("fr", ()),)), "empty_keyword_group"),
    (lambda item: replace(item, keywords=(KeywordGroup("fr", ("", "x")),)), "invalid_keyword"),
    (lambda item: replace(item, collection=Collection(" ")), "invalid_collection_title"),
    (lambda item: replace(item, collection=Collection("C", issn="0000-0021")), "invalid_issn"),
    (lambda item: replace(item, collection=Collection("C", editor=" ")), "invalid_collection_editor"),
    (lambda item: replace(item, funding=(Funding(" "),)), "invalid_funder"),
    (lambda item: replace(item, funding=(Funding("ANR", " "),)), "invalid_grant_number"),
    (lambda item: replace(item, pagination=Pagination(page_from=10, page_to=5)), "invalid_pagination"),
    (lambda item: replace(item, pagination=Pagination(page_from=10)), "incomplete_pagination"),
    (lambda item: replace(item, pagination=Pagination(page_from=1, page_to=2, extent=10)), "conflicting_pagination"),
    (lambda item: replace(item, pagination=Pagination()), "incomplete_pagination"),
    (lambda item: replace(item, contributors=(replace(item.contributors[0], email="pas-un-mail"),)), "invalid_email"),
    (lambda item: replace(item, contributors=(replace(item.contributors[0], role="other"),)), "missing_contributor_role_label"),
])
def test_v2_validation_codes(metadata, changed, code: str) -> None:
    assert code in [issue.code for issue in validate_metadata(changed(metadata)).issues]


def test_funding_and_collection_editor_are_valid_when_well_formed(metadata) -> None:
    valid = replace(
        metadata,
        funding=(Funding("ANR", "ANR-23-CE38-0001"), Funding("ERC")),
        collection=Collection("Une collection", editor="Un directeur de collection"),
    )
    result = validate_metadata(valid)
    assert result.valid
    assert not [issue for issue in result.issues if issue.path and issue.path.startswith(("funding", "collection.editor"))]


def test_duplicate_identifier_value_is_reported(metadata) -> None:
    duplicated = replace(
        metadata,
        identifiers=(
            Identifier("doi", "10.4000/x.1"),
            Identifier("doi", "10.4000/x.1"),
        ),
    )
    codes = [issue.code for issue in validate_metadata(duplicated).issues]
    assert "duplicate_identifier_value" in codes


def test_duplicate_identifier_value_is_reported_after_case_and_space_normalization(metadata) -> None:
    duplicated = replace(
        metadata,
        identifiers=(
            Identifier("doi", "10.4000/X.1"),
            Identifier("doi", " 10.4000/x.1 "),
        ),
    )
    codes = [issue.code for issue in validate_metadata(duplicated).issues]
    assert "duplicate_identifier_value" in codes


def test_two_identifiers_with_the_same_type_and_format_are_reported(metadata) -> None:
    """Deux ISBN "print" distincts se serialiseraient tous les deux en
    idno[@type='pISBN'] sans qu'aucun attribut ne les distingue."""
    collision = replace(
        metadata,
        identifiers=(
            Identifier("isbn-13", "979-10-240-1755-6", "print"),
            Identifier("isbn-13", "978-2-07-036822-8", "print"),
        ),
    )
    codes = [issue.code for issue in validate_metadata(collision).issues]
    assert "duplicate_identifier_type_format" in codes


def test_different_identifier_formats_do_not_collide(metadata) -> None:
    distinct = replace(
        metadata,
        identifiers=(
            Identifier("isbn-13", "979-10-240-1755-6", "print"),
            Identifier("isbn-13", "979-10-240-1755-6", "pdf"),
        ),
    )
    codes = [issue.code for issue in validate_metadata(distinct).issues]
    assert "duplicate_identifier_type_format" not in codes


def test_similar_keywords_warn_without_deduplication(metadata) -> None:
    grouped = replace(metadata, keywords=(KeywordGroup("fr", ("Tragédie", "tragedie", "genre")),))
    result = validate_metadata(grouped)
    assert result.valid
    assert "similar_keywords" in [issue.code for issue in result.issues]


def test_normalizations_are_explicit_and_local() -> None:
    assert normalize_doi("https://doi.org/10.4000/books.purh.1") == "10.4000/books.purh.1"
    assert normalize_doi("doi:10.4000/x.1") == "10.4000/x.1"
    assert normalize_doi("11.4000/x") is None
    assert normalize_isbn("979-10-240-1755-6") == "9791024017556"
    assert normalize_isbn("2-87775-994-9") is None
    assert normalize_isbn("0-19-852663-6") == "0198526636"
    assert normalize_issn("0000-0019") == "0000-0019"
    assert normalize_issn("00000019") == "0000-0019"
    assert normalize_issn("0000-0018") is None


@pytest.mark.parametrize(("date", "valid"), [
    ("2026", True),
    ("2026-03", True),
    ("2026-03-15", True),
    ("2026-02-31", False),
    ("2026-13", False),
    ("2025-02-29", False),
    ("2024-02-29", True),
    ("2026-3", False),
    ("26", False),
])
def test_publication_dates_must_be_calendar_possible(metadata, date: str, valid: bool) -> None:
    changed = replace(metadata, publication=Publication(publication_date=date))
    codes = [issue.code for issue in validate_metadata(changed).issues]

    assert ("invalid_publication_date" not in codes) is valid
