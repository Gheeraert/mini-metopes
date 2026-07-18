from dataclasses import replace
from pathlib import Path

from lxml import etree

from mini_metopes.cli import main
from mini_metopes.docx import inspect_docx_file
from mini_metopes.metadata import (
    Affiliation,
    Contributor,
    DocumentMetadata,
    METADATA_SCHEMA_VERSION,
    SourceDocument,
    compute_file_sha256,
    load_metadata_file,
)
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
    assert tree.xpath("count(//tei:idno[@type='ROR'])", namespaces=NS) == 0.0
    assert tree.xpath("string(tei:teiHeader/tei:profileDesc/tei:langUsage/tei:language/@ident)", namespaces=NS) == "fr"
    keywords = tree.xpath("tei:teiHeader/tei:profileDesc/tei:textClass/tei:keywords", namespaces=NS)
    assert len(keywords) == 1
    assert keywords[0].get("scheme") == "keywords"
    assert keywords[0].get("{http://www.w3.org/XML/1998/namespace}lang") == "fr"
    assert tree.xpath("count(tei:teiHeader/tei:profileDesc/tei:textClass/tei:keywords/tei:list/tei:item)", namespaces=NS) == 3.0
    assert tree.xpath("count(tei:text/tei:front/tei:div[@type='abstract'])", namespaces=NS) == 1.0
    assert tree.xpath("string(tei:text/tei:front/tei:div[@type='abstract']/tei:p)", namespaces=NS) == "Resume synthetique pour la fixture."
    assert tree.xpath("count(tei:text/tei:body/tei:p[text()='Une conversion synthetique'])", namespaces=NS) == 0.0
    assert tree.xpath("contains(string(tei:teiHeader/tei:fileDesc/tei:sourceDesc), 'native-tei-conversion.docx')", namespaces=NS)
    assert "ror_not_serialized" in [item.code for item in result.diagnostics]


def test_literal_contributor_orcid_is_normalized_in_tei() -> None:
    metadata = load_metadata_file(JSON).metadata
    assert metadata is not None
    literal = Contributor(
        contributor_id="person-literal",
        role="author",
        literal_name="Nom non decompose",
        orcid="https://orcid.org/0000-0002-1825-0097",
    )
    metadata = replace(metadata, contributors=(literal,), affiliations=())
    result = convert_docx_to_tei(DOCX, metadata=metadata)

    assert result.is_successful
    assert result.xml_bytes is not None
    tree = etree.fromstring(result.xml_bytes)
    assert tree.xpath("string(//tei:author/tei:persName)", namespaces=NS) == "Nom non decompose"
    assert tree.xpath("string(//tei:author/tei:idno[@type='ORCID'])", namespaces=NS) == "0000-0002-1825-0097"


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
        SourceDocument(docx_with_late_title.name, compute_file_sha256(docx_with_late_title)),
        "chapter", "fr", "Titre JSON",
    )
    late = convert_docx_to_tei(docx_with_late_title, metadata=late_metadata)
    assert late.xml_bytes is None
    assert "metadata_style_not_initial" in [item.code for item in late.diagnostics]
    matching = [item for item in late.diagnostics if item.code == "metadata_style_not_initial"]
    assert len(matching) == 1
    assert matching[0].origin == "metadata"
    assert matching[0].metadata_path and matching[0].metadata_path.startswith("paragraphs[")


def test_cli_validates_metadata_and_requires_it_for_conversion(tmp_path: Path, capsys) -> None:
    assert main(["validate-metadata", str(JSON)]) == 0
    output = tmp_path / "output.xml"
    assert main(["convert-docx", str(DOCX), str(output)]) == 1
    assert not output.exists()
    assert main(["convert-docx", str(DOCX), str(output), "--metadata", str(JSON)]) == 0
    assert output.exists()
    captured = capsys.readouterr()
    assert "missing_metadata" in captured.out


def test_cli_prints_non_blocking_diagnostics_on_success(tmp_path: Path, capsys) -> None:
    output = tmp_path / "output.xml"

    assert main(["convert-docx", str(DOCX), str(output), "--metadata", str(JSON)]) == 0
    captured = capsys.readouterr()
    assert output.exists()
    assert "ror_not_serialized" in captured.out
    assert "affiliations[0].ror" in captured.out


def test_cli_reports_missing_docx_before_missing_metadata(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "missing.docx"
    output = tmp_path / "output.xml"

    assert main(["convert-docx", str(missing), str(output)]) == 2
    captured = capsys.readouterr()
    assert "missing_metadata" not in captured.out
    assert "fichier introuvable" in captured.out


def test_cli_handles_badly_typed_metadata_without_traceback(tmp_path: Path, capsys) -> None:
    invalid = tmp_path / "bad.metadata.json"
    invalid.write_text('{"schema_version":"1.0","source_document":{"path":"x.docx","sha256":"a"},"document":{"type":"chapter","language":3,"title":7},"contributors":[],"affiliations":[]}', encoding="utf-8")
    output = tmp_path / "output.xml"

    assert main(["validate-metadata", str(invalid)]) == 1
    assert main(["convert-docx", str(DOCX), str(output), "--metadata", str(invalid)]) == 1
    assert not output.exists()
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out
    assert "document.language" in captured.out


def test_validate_metadata_source_reports_word_divergences(tmp_path: Path, capsys) -> None:
    metadata = load_metadata_file(JSON).metadata
    assert metadata is not None
    changed = replace(metadata, title="Titre JSON different", source=replace(metadata.source, sha256="b" * 64))
    path = tmp_path / "changed.metadata.json"
    from mini_metopes.metadata import metadata_to_json

    path.write_text(metadata_to_json(changed), encoding="utf-8")

    assert main(["validate-metadata", str(path), "--source", str(DOCX)]) == 0
    captured = capsys.readouterr()
    assert "metadata_source_changed" in captured.out
    assert "metadata_title_differs_from_docx" in captured.out


def test_public_docx_conversion_requires_metadata() -> None:
    result = convert_docx_to_tei(DOCX)
    assert result.xml_bytes is None
    assert [item.code for item in result.diagnostics] == ["missing_metadata"]


def test_shared_ror_affiliation_warns_once_with_metadata_path() -> None:
    metadata = load_metadata_file(JSON).metadata
    assert metadata is not None
    shared = Affiliation("affiliation-ror", "Institution ROR", ror="https://ror.org/03yrm5c26")
    first = replace(metadata.contributors[0], affiliation_ids=("affiliation-ror",))
    second = Contributor("person-2", "editor", literal_name="Collectif", affiliation_ids=("affiliation-ror",))
    metadata = replace(metadata, contributors=(first, second), affiliations=(shared,))

    result = convert_docx_to_tei(DOCX, metadata=metadata)

    assert result.is_successful
    assert result.xml_bytes is not None
    diagnostics = [item for item in result.diagnostics if item.code == "ror_not_serialized"]
    assert len(diagnostics) == 1
    assert diagnostics[0].origin == "metadata"
    assert diagnostics[0].metadata_path == "affiliations[0].ror"
    tree = etree.fromstring(result.xml_bytes)
    assert tree.xpath("count(//tei:affiliation[contains(., 'Institution ROR')])", namespaces=NS) == 2.0


def test_edit_metadata_invalid_docx_returns_2_without_traceback(capsys) -> None:
    assert main(["edit-metadata", str(ROOT / "docx" / "not-a-zip.docx")]) == 2
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out


def test_edit_metadata_tk_initialization_failure_returns_2(monkeypatch, capsys) -> None:
    import tkinter as tk

    def fail_tk():
        raise tk.TclError("pas de display")

    monkeypatch.setattr(tk, "Tk", fail_tk)

    assert main(["edit-metadata"]) == 2
    captured = capsys.readouterr()
    assert "impossible d'initialiser l'interface graphique" in captured.out
    assert "Traceback" not in captured.out


def test_gui_module_import_does_not_open_a_window() -> None:
    import mini_metopes.gui.metadata_editor as editor

    assert callable(editor.run_metadata_editor)
