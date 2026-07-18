"""Serialisation TEI du modele de metadonnees v2 : teiHeader et front."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from lxml import etree

from mini_metopes.metadata import (
    Abstract,
    Collection,
    Contributor,
    EditorialResponsibility,
    Identifier,
    KeywordGroup,
    License,
    Pagination,
    Publication,
    Publisher,
    Rights,
    load_metadata_file,
)
from mini_metopes.tei import convert_docx_to_tei
from mini_metopes.validation import validate_xml_bytes


ROOT = Path(__file__).parent / "fixtures"
DOCX = ROOT / "docx" / "native-tei-conversion.docx"
JSON = ROOT / "metadata" / "native-tei-conversion.metadata.json"
NS = {"tei": "http://www.tei-c.org/ns/1.0"}
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def _base_metadata():
    metadata = load_metadata_file(JSON).metadata
    assert metadata is not None
    return metadata


def _convert(metadata):
    result = convert_docx_to_tei(DOCX, metadata=metadata)
    assert result.is_successful, result.diagnostics
    assert result.xml_bytes is not None
    assert validate_xml_bytes(result.xml_bytes).valid
    return result


def _rich_metadata():
    return replace(
        _base_metadata(),
        editorial_responsibility=(EditorialResponsibility("éditrice", "Anaïs Monchy"),),
        publication=Publication(
            publisher=Publisher(
                name="Presses universitaires de Rouen et du Havre",
                place="Mont-Saint-Aignan",
                url="https://purh.univ-rouen.fr",
            ),
            publication_date="2026",
        ),
        identifiers=(
            Identifier("doi", "https://doi.org/10.4000/books.purh.12345"),
            Identifier("isbn-13", "979-10-240-1755-6", "print"),
            Identifier("isbn-13", "978-2-87775-994-6", "pdf"),
            Identifier("issn", "0000-0019"),
            Identifier("local", "PURH-2026-07"),
        ),
        rights=Rights(
            holder="Presses universitaires de Rouen et du Havre",
            statement="Tous droits réservés.",
            license=License("CC BY-NC-ND 4.0", "https://creativecommons.org/licenses/by-nc-nd/4.0/"),
        ),
        abstracts=(
            Abstract("summary", "fr", "Résumé français."),
            Abstract("abstract", "en", "English abstract."),
            Abstract("abstract", "grc", "Περὶ ποιητικῆς."),
            Abstract("back-cover", "fr", "Quatrième de couverture."),
        ),
        keywords=(
            KeywordGroup("fr", ("Racine", "tragédie")),
            KeywordGroup("grc", ("τραγῳδία",)),
        ),
        collection=Collection(title="Cours de littérature", issn="0000-0019", volume="7"),
        pagination=Pagination(page_from=125, page_to=148),
    )


def test_full_metadata_produce_a_complete_and_valid_header() -> None:
    result = _convert(_rich_metadata())
    tree = etree.fromstring(result.xml_bytes)

    publication = tree.xpath("tei:teiHeader/tei:fileDesc/tei:publicationStmt", namespaces=NS)[0]
    children = [etree.QName(child).localname for child in publication]
    assert children[0] == "publisher"
    assert publication[0].text == "Presses universitaires de Rouen et du Havre"
    idnos = {(item.get("type"), item.text) for item in publication.findall("tei:idno", NS)}
    assert idnos == {
        ("DOI", "10.4000/books.purh.12345"),
        ("pISBN", "979-10-240-1755-6"),
        ("eISBN", "978-2-87775-994-6"),
        ("pISSN", "0000-0019"),
        ("documentnumber", "PURH-2026-07"),
    }
    date = publication.find("tei:date", NS)
    assert date.get("when") == "2026" and date.text == "2026"
    licence = publication.find("tei:availability/tei:licence", NS)
    assert licence.get("target") == "https://creativecommons.org/licenses/by-nc-nd/4.0/"
    assert licence.text == "CC BY-NC-ND 4.0"
    statements = [item.text for item in publication.findall("tei:availability/tei:p", NS)]
    assert statements == ["Tous droits réservés.", "© Presses universitaires de Rouen et du Havre"]

    series = tree.xpath("//tei:sourceDesc/tei:bibl/tei:series", namespaces=NS)[0]
    assert series.find("tei:title", NS).text == "Cours de littérature"
    assert series.find("tei:biblScope", NS).get("unit") == "volume"
    assert tree.xpath("string(//tei:sourceDesc/tei:bibl/tei:biblScope[@unit='page'])", namespaces=NS) == "125-148"

    fronts = tree.xpath("tei:text/tei:front/tei:div", namespaces=NS)
    assert [item.get(XML_LANG) for item in fronts] == ["fr", "en", "grc", "fr"]
    assert [item.get("n") for item in fronts] == [None, None, None, "back-cover"]
    assert all(item.get("type") == "abstract" for item in fronts)

    keyword_groups = tree.xpath("//tei:textClass/tei:keywords", namespaces=NS)
    assert [group.get(XML_LANG) for group in keyword_groups] == ["fr", "grc"]
    assert tree.xpath("string(//tei:keywords[2]/tei:list/tei:item)", namespaces=NS) == "τραγῳδία"

    assert "editorial_responsibility_not_serialized" in {item.code for item in result.diagnostics}
    assert "publisher_address_not_serialized" in {item.code for item in result.diagnostics}


def test_serialization_is_deterministic_byte_for_byte() -> None:
    metadata = _rich_metadata()
    first = _convert(metadata)
    second = _convert(metadata)
    assert first.xml_bytes == second.xml_bytes


def test_absent_optional_metadata_produce_no_empty_structures() -> None:
    metadata = replace(
        _base_metadata(),
        abstracts=(), keywords=(), identifiers=(), collection=None, pagination=None,
        rights=Rights(), publication=Publication(),
    )
    result = _convert(metadata)
    tree = etree.fromstring(result.xml_bytes)

    assert tree.xpath("count(tei:text/tei:front)", namespaces=NS) == 0.0
    assert tree.xpath("count(//tei:textClass)", namespaces=NS) == 0.0
    assert tree.xpath("count(//tei:availability)", namespaces=NS) == 0.0
    assert tree.xpath("count(//tei:sourceDesc)", namespaces=NS) == 1.0
    assert tree.xpath("count(//tei:publicationStmt/tei:p)", namespaces=NS) == 1.0
    assert tree.xpath("count(//tei:licence)", namespaces=NS) == 0.0


def test_publication_details_without_publisher_block_conversion() -> None:
    metadata = replace(
        _base_metadata(),
        abstracts=(), keywords=(),
        identifiers=(Identifier("doi", "10.4000/books.purh.12345"),),
    )
    result = convert_docx_to_tei(DOCX, metadata=metadata)
    assert not result.is_successful
    assert result.xml_bytes is None
    assert "missing_publisher_for_publication_details" in {item.code for item in result.diagnostics}


def test_contributor_roles_map_to_tei_role_attributes() -> None:
    metadata = replace(
        _base_metadata(),
        abstracts=(), keywords=(), affiliations=(),
        contributors=(
            Contributor("person-1", "author", given_name="A", family_name="Auteur"),
            Contributor("person-2", "scientific_editor", given_name="B", family_name="Directrice"),
            Contributor("person-3", "translator", given_name="C", family_name="Traductrice"),
            Contributor("person-4", "other", literal_name="Collectif", role_label="préfacier"),
        ),
    )
    result = _convert(metadata)
    tree = etree.fromstring(result.xml_bytes)
    assert tree.xpath("//tei:titleStmt/tei:author/@role", namespaces=NS) == ["aut"]
    assert tree.xpath("//tei:titleStmt/tei:editor/@role", namespaces=NS) == ["edt", "trl", "ctb"]
    assert "contributor_role_serialized_as_contributor" in {item.code for item in result.diagnostics}


def test_pagination_extent_is_kept_in_json_only() -> None:
    metadata = replace(_base_metadata(), abstracts=(), keywords=(), pagination=Pagination(extent=320))
    result = _convert(metadata)
    tree = etree.fromstring(result.xml_bytes)
    assert tree.xpath("count(//tei:biblScope)", namespaces=NS) == 0.0
    assert "pagination_extent_not_serialized" in {item.code for item in result.diagnostics}
