"""Paragraphes de suite issus du style Word natif BodyText."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from lxml import etree

from mini_metopes.cli import main
from mini_metopes.docx import inspect_docx_file
from mini_metopes.editorial import (
    EditorialDocument,
    NATIVE_WORD_CONVENTION,
    Paragraph,
    TextSpan,
    build_editorial_document,
    build_editorial_document_from_file,
    editorial_build_result_to_json,
)
from mini_metopes.metadata import load_metadata_file
from mini_metopes.tei import convert_docx_to_tei, serialize_editorial_document_to_tei
from mini_metopes.validation import validate_xml_bytes
from test_docx_numbering import basic_numbering, paragraph, runtime_docx, write_docx


FIXTURES = Path(__file__).parent / "fixtures"
DOCX = FIXTURES / "docx" / "native-consecutive-paragraphs.docx"
METADATA = FIXTURES / "metadata" / "native-consecutive-paragraphs.metadata.json"
NS = {"tei": "http://www.tei-c.org/ns/1.0"}


CONSECUTIVE_TEST_STYLES = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="BodyText"><w:name w:val="Corps de texte"/></w:style>
  <w:style w:type="paragraph" w:styleId="BodyText2"><w:name w:val="Corps de texte 2"/></w:style>
  <w:style w:type="paragraph" w:styleId="BodyText3"><w:name w:val="Corps de texte 3"/></w:style>
  <w:style w:type="paragraph" w:customStyle="1" w:styleId="CustomBodyText"><w:name w:val="Corps de texte"/></w:style>
  <w:style w:type="paragraph" w:styleId="LocalizedBodyText"><w:name w:val="Corps de texte"/></w:style>
  <w:style w:type="paragraph" w:styleId="EnglishBodyText"><w:name w:val="Body Text"/></w:style>
</w:styles>
"""


def _metadata():
    loaded = load_metadata_file(METADATA)
    assert loaded.metadata is not None
    return loaded.metadata


def _tree(result):
    assert result.xml_bytes is not None
    return etree.fromstring(result.xml_bytes)


def _runtime_docx_for_style(style_id: str, name: str, *, custom: bool = False) -> Path:
    custom_attr = ' w:customStyle="1"' if custom else ""
    path = runtime_docx(f"consecutive-{style_id}.docx")
    styles = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph"{custom_attr} w:styleId="{style_id}"><w:name w:val="{name}"/></w:style>
</w:styles>
"""
    write_docx(path, paragraph("Texte", style=style_id), styles=styles)
    return path


def test_inspection_exposes_style_custom_flag_and_json_is_deterministic() -> None:
    inspection = inspect_docx_file(DOCX)
    body_text = inspection.paragraphs[4]
    serialized = json.loads(main_json := _inspection_json(inspection))

    assert body_text.style_id == "BodyText"
    assert body_text.style_name == "Corps de texte"
    assert body_text.style_is_custom is None
    assert '"style_is_custom": null' in main_json
    assert serialized["paragraphs"][4]["style_is_custom"] is None
    assert _inspection_json(inspection) == _inspection_json(inspection)


def _inspection_json(inspection) -> str:
    from dataclasses import asdict

    data = asdict(inspection)
    data["source"] = inspection.source.name
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)


def test_convention_recognizes_only_integrated_body_text_semantics() -> None:
    convention = NATIVE_WORD_CONVENTION

    assert convention.paragraph_role("BodyText", None).paragraph_rendition == "consecutive"
    assert convention.paragraph_role("LocalizedBodyText", None, style_name="Corps de texte", style_is_custom=False).paragraph_rendition == "consecutive"
    assert convention.paragraph_role("EnglishBodyText", None, style_name="Body Text", style_is_custom=False).paragraph_rendition == "consecutive"
    assert convention.paragraph_role("Normal", None).paragraph_rendition is None

    assert convention.paragraph_role("CustomBodyText", None, style_name="Corps de texte", style_is_custom=True).kind == "unsupported"
    assert convention.paragraph_role("BodyText", None, style_name="Corps de texte", style_is_custom=True).kind == "unsupported"
    assert convention.paragraph_role("BodyText2", None, style_name="Corps de texte", style_is_custom=False).kind == "unsupported"
    assert convention.paragraph_role("BodyText2", None, style_name="Body Text", style_is_custom=False).kind == "unsupported"
    assert convention.paragraph_role("BodyText3", None, style_name="Corps de texte", style_is_custom=False).kind == "unsupported"
    assert convention.paragraph_role("BodyText3", None, style_name="Body Text", style_is_custom=False).kind == "unsupported"
    assert convention.paragraph_role("BodyText2", None, style_name="Corps de texte 2", style_is_custom=False).kind == "unsupported"
    assert convention.paragraph_role("BodyText3", None, style_name="Corps de texte 3", style_is_custom=False).kind == "unsupported"
    for name in ("Corps de texte 2", "Corps  de texte 2", "Corps de textes", "Retrait corps de texte", "Mon Corps de texte"):
        assert convention.paragraph_role("Local", None, style_name=name, style_is_custom=False).kind == "unsupported"


def test_editorial_model_marks_body_text_paragraphs_and_keeps_inline_content() -> None:
    result = build_editorial_document_from_file(DOCX)
    body_paragraphs = [
        block for block in result.document.blocks if isinstance(block, Paragraph) and block.rendition == "consecutive"
    ]
    footnote = result.document.notes[0]

    assert [block.source_paragraph_index for block in body_paragraphs] == [4, 6]
    assert isinstance(footnote.blocks[0], Paragraph)
    assert footnote.blocks[0].rendition == "consecutive"
    assert any(isinstance(item, TextSpan) and item.marks == ("bold",) for item in body_paragraphs[1].content)
    assert any(isinstance(item, TextSpan) and item.link is not None for item in body_paragraphs[1].content)
    assert editorial_build_result_to_json(result) == editorial_build_result_to_json(result)
    data = json.loads(editorial_build_result_to_json(result))
    assert data["document"]["blocks"][4]["rendition"] == "consecutive"


def test_tei_serializes_consecutive_paragraphs_in_body_and_notes() -> None:
    result = convert_docx_to_tei(DOCX, metadata=_metadata())
    tree = _tree(result)

    assert result.is_successful
    assert validate_xml_bytes(result.xml_bytes or b"").valid
    assert tree.xpath("count(.//tei:p[@rend='consecutive'])", namespaces=NS) == 3.0
    assert tree.xpath("count(tei:text/tei:body/tei:p[@rend='consecutive'])", namespaces=NS) == 1.0
    assert tree.xpath("count(tei:text/tei:body/tei:div/tei:p[@rend='consecutive'])", namespaces=NS) == 1.0
    assert tree.xpath("count(.//tei:note/tei:p[@rend='consecutive'])", namespaces=NS) == 1.0
    assert tree.xpath("count(tei:text/tei:body/tei:p[not(@rend)])", namespaces=NS) == 2.0
    assert tree.xpath("string(tei:text/tei:body/tei:p[2])", namespaces=NS) == "Paragraphe normal avec retrait direct ignore."
    assert tree.xpath(".//tei:p[@rend='consecutive']//tei:ref/@target", namespaces=NS) == ["https://example.test/body"]
    assert tree.xpath("count(.//tei:p[@rend='consecutive']/tei:note[@place='foot'])", namespaces=NS) == 1.0
    assert tree.xpath("count(.//tei:p[@rend='consecutive']/@type | .//tei:p[@rend='consecutive']/@style)", namespaces=NS) == 0.0


def test_localized_non_custom_name_fallback_is_exact() -> None:
    path = _runtime_docx_for_style("LocalizedBodyText", "Corps de texte")
    result = build_editorial_document_from_file(path)
    paragraph_block = result.document.blocks[0]

    assert isinstance(paragraph_block, Paragraph)
    assert paragraph_block.rendition == "consecutive"


def test_body_text_numbered_paragraph_stays_a_list_item() -> None:
    path = runtime_docx("consecutive-bodytext-list.docx")
    write_docx(
        path,
        paragraph("Item", style="BodyText", num_id="42", ilvl="0"),
        styles=CONSECUTIVE_TEST_STYLES,
        numbering=basic_numbering(),
    )

    result = build_editorial_document_from_file(path)

    assert result.document.blocks[0].kind == "list"
    assert "unsupported_paragraph_style" not in [diagnostic.code for diagnostic in result.diagnostics]


def test_unsupported_body_text_variants_refuse_conversion_and_preserve_output(tmp_path: Path) -> None:
    for style_id, name, custom in (
        ("BodyText2", "Corps de texte 2", False),
        ("BodyText3", "Corps de texte 3", False),
        ("CustomBodyText", "Corps de texte", True),
    ):
        path = _runtime_docx_for_style(style_id, name, custom=custom)
        destination = tmp_path / f"{style_id}.xml"
        destination.write_text("ancienne sortie", encoding="utf-8")

        result = convert_docx_to_tei(path, metadata=_metadata())

        assert result.xml_bytes is None
        assert "unsupported_paragraph_style" in [diagnostic.code for diagnostic in result.diagnostics]
        assert destination.read_text(encoding="utf-8") == "ancienne sortie"


def test_excluded_body_text_variants_ignore_exact_name_fallback(tmp_path: Path) -> None:
    for style_id, name in (
        ("BodyText2", "Corps de texte"),
        ("BodyText2", "Body Text"),
        ("BodyText3", "Corps de texte"),
        ("BodyText3", "Body Text"),
    ):
        path = _runtime_docx_for_style(style_id, name)
        missing_destination = tmp_path / f"{style_id}-{name.replace(' ', '-')}-missing.xml"
        preserved_destination = tmp_path / f"{style_id}-{name.replace(' ', '-')}-preserved.xml"
        preserved_destination.write_text("ancienne sortie", encoding="utf-8")

        result = convert_docx_to_tei(path, metadata=_metadata())
        missing_code = main(["convert-docx", str(path), str(missing_destination), "--metadata", str(METADATA)])
        preserved_code = main(["convert-docx", str(path), str(preserved_destination), "--metadata", str(METADATA)])

        assert result.xml_bytes is None
        assert "unsupported_paragraph_style" in [diagnostic.code for diagnostic in result.diagnostics]
        assert missing_code == 1
        assert preserved_code == 1
        assert not missing_destination.exists()
        assert preserved_destination.read_text(encoding="utf-8") == "ancienne sortie"


def test_unknown_manual_paragraph_rendition_is_rejected() -> None:
    document = EditorialDocument(
        source_name="manual.docx",
        blocks=(Paragraph((TextSpan("Texte"),), 0, "Normal", rendition="no-indent"),),  # type: ignore[arg-type]
        notes=(),
    )

    result = serialize_editorial_document_to_tei(document)

    assert result.xml_bytes is None
    assert "unsupported_paragraph_rendition" in [diagnostic.code for diagnostic in result.diagnostics]


def test_model_docx_reports_consecutive_paragraph_counts(capsys) -> None:
    assert main(["model-docx", str(DOCX)]) == 0
    captured = capsys.readouterr()

    assert "Paragraphes de suite du corps : 2" in captured.out
    assert "Paragraphes de suite dans les notes : 1" in captured.out
    assert "Paragraphes de suite totaux : 3" in captured.out


def test_normal_direct_indentation_does_not_create_consecutive_rendition() -> None:
    result = build_editorial_document_from_file(DOCX)
    normal = next(
        block
        for block in result.document.blocks
        if isinstance(block, Paragraph) and block.source_paragraph_index == 3
    )

    assert normal.rendition is None
