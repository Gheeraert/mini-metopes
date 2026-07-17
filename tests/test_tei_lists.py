"""Tests de serialisation TEI des listes editoriales imbriquees."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from lxml import etree

from mini_metopes.docx import inspect_docx_file
from mini_metopes.editorial import EditorialDocument, EditorialList, build_editorial_document
from mini_metopes.metadata import load_metadata_file
from mini_metopes.tei import convert_docx_to_tei, serialize_editorial_document_to_tei
from mini_metopes.validation import validate_xml_bytes


FIXTURES = Path(__file__).parent / "fixtures"
TEI = {"tei": "http://www.tei-c.org/ns/1.0"}


def _metadata():
    result = load_metadata_file(FIXTURES / "metadata" / "native-lists-tei.metadata.json")
    assert result.metadata is not None
    return result.metadata


def test_native_lists_convert_to_valid_nested_tei() -> None:
    source = FIXTURES / "docx" / "native-lists-tei.docx"
    first = convert_docx_to_tei(source, metadata=_metadata())
    second = convert_docx_to_tei(source, metadata=_metadata())
    assert first.is_successful
    assert first.xml_bytes == second.xml_bytes
    assert first.xml_bytes is not None and validate_xml_bytes(first.xml_bytes).valid

    root = etree.fromstring(first.xml_bytes)
    lists = root.xpath("./tei:text/tei:body/tei:list", namespaces=TEI)
    assert [(item.get("type"), item.get("n")) for item in lists] == [
        ("decimal", "1"),
        ("bulleted", None),
        ("decimal", "5"),
    ]
    assert root.xpath("count(.//tei:list[@type='lowerLetter'])", namespaces=TEI) == 1.0
    assert root.xpath("count(.//tei:item/tei:list)", namespaces=TEI) >= 2.0
    assert root.xpath("string(.//tei:list[@type='decimal']/tei:item[1])", namespaces=TEI).startswith("Premier item gras lien")
    assert root.xpath("count(.//tei:list//tei:p)", namespaces=TEI) == 0.0
    assert root.xpath("count(.//tei:note[@place='foot']/tei:list)", namespaces=TEI) == 1.0
    assert root.xpath("count(.//tei:note[@place='end']/tei:list)", namespaces=TEI) == 1.0
    assert any(item.code == "list_root_level_normalized" for item in first.diagnostics)


def test_manual_empty_editorial_lists_fail_without_xml() -> None:
    document = EditorialDocument(
        source_name="manual.docx",
        blocks=(
            EditorialList(
                list_kind="ordered",
                num_format="decimal",
                start=1,
                source_numbering_id="42",
                source_level=0,
                level_text=None,
                suffix=None,
                restart_after_level=None,
                items=(),
            ),
        ),
        notes=(),
    )
    result = serialize_editorial_document_to_tei(document)
    assert result.xml_bytes is None
    assert [item.code for item in result.diagnostics] == ["empty_list_not_serializable"]


def test_ambiguous_list_fixture_remains_refused_for_its_structural_error(tmp_path: Path) -> None:
    source = FIXTURES / "docx" / "native-lists.docx"
    metadata = _metadata()
    result = convert_docx_to_tei(source, metadata=metadata)
    assert result.xml_bytes is None
    assert any(item.code == "list_level_jump_not_serializable" for item in result.diagnostics)
    target = tmp_path / "preserved.xml"
    target.write_text("ancienne sortie", encoding="utf-8")
    assert target.read_text(encoding="utf-8") == "ancienne sortie"
