"""Tests normatifs de l'API de validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from lxml import etree

from mini_metopes import validate_xml_bytes, validate_xml_file
from mini_metopes.validation import validate_xml_tree


FIXTURES = Path(__file__).parent / "fixtures" / "xml"


@pytest.mark.parametrize(
    "name",
    ["minimal.xml", "prose-citation.xml", "poetic-citation.xml", "poetic-stanzas.xml"],
)
def test_valid_documents_are_accepted(name: str) -> None:
    result = validate_xml_file(FIXTURES / "valid" / name)
    assert result.valid
    assert result.issues == ()


def test_poetic_citation_with_empty_stanza_is_rejected() -> None:
    result = validate_xml_file(FIXTURES / "invalid" / "poetic-citation-with-empty-lg.xml")
    assert not result.valid
    assert result.issues
    assert all(issue.domain == "relaxng" for issue in result.issues)


def test_malformed_xml_is_distinguished_from_relax_ng_error() -> None:
    result = validate_xml_file(FIXTURES / "invalid" / "malformed.xml")
    assert not result.valid
    assert result.issues
    assert all(issue.domain == "xml" for issue in result.issues)


def test_validation_accepts_xml_bytes() -> None:
    data = (FIXTURES / "valid" / "minimal.xml").read_bytes()
    assert validate_xml_bytes(data).valid


def test_validation_accepts_an_lxml_tree() -> None:
    tree = etree.parse(str(FIXTURES / "valid" / "minimal.xml"))
    assert validate_xml_tree(tree).valid
