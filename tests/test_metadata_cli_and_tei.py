from dataclasses import replace
from pathlib import Path

from lxml import etree

from mini_metopes.cli import main
from mini_metopes.docx import inspect_docx_file
from mini_metopes.metadata import DocumentMetadata, METADATA_SCHEMA_VERSION, MetadataSource, compute_file_sha256, load_metadata_file
from mini_metopes.tei import convert_docx_to_tei


ROOT = Path(__file__).parent / "fixtures"
DOCX = ROOT / "docx" / "native-tei-conversion.docx"
JSON = ROOT / "metadata" / "native-tei-conversion.metadata.json"
NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def test_metadata_enriches_header_and_consumes_initial_word_suggestions() -> None:
    metadata = load_metadata_file(JSON).metadata
    assert metadata is not None
    result = convert_docx_to_tei(DOCX, metadata=metadata)
    assert result.is_successful
    assert result.xml_bytes is not None
    tree = etree.fromstring(result.xml_bytes)
    assert tree.xpath("string(tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:title[@type='main'])", namespaces=NS) == metadata.title
    assert tree.xpath("string(tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:title[@type='sub'])", namespaces=NS) == metadata.subtitle
    assert tree.xpath("count(tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:author)", namespaces=NS) == 1.0
    assert tree.xpath("string(//tei:author/tei:persName/tei:forename)", namespaces=NS) == "Tony"
    assert tree.xpath("string(//tei:idno[@type='ORCID'])", namespaces=NS) == "0000-0002-1825-0097"
    assert tree.xpath("string(tei:teiHeader/tei:profileDesc/tei:langUsage/tei:language/@ident)", namespaces=NS) == "fr"
    assert tree.xpath("count(tei:teiHeader/tei:profileDesc/tei:textClass/tei:keywords/tei:term)", namespaces=NS) == 3.0
    assert tree.xpath("count(tei:text/tei:body/tei:p[text()='Une conversion synthetique'])", namespaces=NS) == 0.0
    assert tree.xpath("contains(string(tei:teiHeader/tei:fileDesc/tei:sourceDesc), 'native-tei-conversion.docx')", namespaces=NS)


def test_json_has_priority_and_non_initial_title_refuses_conversion() -> None:
    metadata = load_metadata_file(JSON).metadata
    assert metadata is not None
    changed = replace(metadata, title="Titre JSON different")
    result = convert_docx_to_tei(DOCX, metadata=changed)
    assert result.is_successful
    assert "metadata_title_differs_from_docx" in [item.code for item in result.diagnostics]
    docx_with_late_title = ROOT / "docx" / "native-editorial.docx"
    late_metadata = DocumentMetadata(
        METADATA_SCHEMA_VERSION,
        MetadataSource(docx_with_late_title.name, compute_file_sha256(docx_with_late_title)),
        "chapter", "fr", "Titre JSON",
    )
    late = convert_docx_to_tei(docx_with_late_title, metadata=late_metadata)
    assert late.xml_bytes is None
    assert "metadata_style_not_initial" in [item.code for item in late.diagnostics]


def test_cli_validates_metadata_and_requires_it_for_conversion(tmp_path: Path, capsys) -> None:
    assert main(["validate-metadata", str(JSON)]) == 0
    output = tmp_path / "output.xml"
    assert main(["convert-docx", str(DOCX), str(output)]) == 1
    assert not output.exists()
    assert main(["convert-docx", str(DOCX), str(output), "--metadata", str(JSON)]) == 0
    assert output.exists()
    captured = capsys.readouterr()
    assert "missing_metadata" in captured.out


def test_public_docx_conversion_requires_metadata() -> None:
    result = convert_docx_to_tei(DOCX)
    assert result.xml_bytes is None
    assert [item.code for item in result.diagnostics] == ["missing_metadata"]


def test_gui_module_import_does_not_open_a_window() -> None:
    import mini_metopes.gui.metadata_editor as editor

    assert callable(editor.run_metadata_editor)
