"""Figures enrichies et tables Word simples de la passe 11."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from lxml import etree

from mini_metopes.cli import main
from mini_metopes.docx import TableInfo, inspect_docx_file
from mini_metopes.editorial import (
    EditorialFigure,
    EditorialList,
    EditorialTable,
    Paragraph,
    ProseQuote,
    VerseQuote,
    build_editorial_document,
)
from mini_metopes.editorial import NATIVE_WORD_CONVENTION
from mini_metopes.metadata import load_metadata_file
from mini_metopes.tei import convert_docx_to_tei
from mini_metopes.validation import validate_xml_bytes
from test_docx_numbering import basic_numbering


FIXTURES = Path(__file__).parent / "fixtures"
DOCX = FIXTURES / "docx" / "native-figure-details-and-tables.docx"
METADATA = FIXTURES / "metadata" / "native-figure-details-and-tables.metadata.json"
TEI = {"tei": "http://www.tei-c.org/ns/1.0"}


def _metadata():
    result = load_metadata_file(METADATA)
    assert result.metadata is not None
    return result.metadata


def _write_document_variant(path: Path, document: str, *, add: dict[str, str] | None = None) -> None:
    replacements = {"word/document.xml": document, **(add or {})}
    with ZipFile(DOCX) as source, ZipFile(path, "w", compression=ZIP_DEFLATED) as target:
        for entry in source.infolist():
            data = (
                replacements[entry.filename].encode("utf-8")
                if entry.filename in replacements
                else source.read(entry.filename)
            )
            info = ZipInfo(entry.filename, date_time=(2024, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            target.writestr(info, data)
        for name, content in replacements.items():
            if name in source.namelist():
                continue
            info = ZipInfo(name, date_time=(2024, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            target.writestr(info, content.encode("utf-8"))


def _codes(path: Path) -> set[str]:
    return {item.code for item in convert_docx_to_tei(path, metadata=_metadata()).diagnostics}


def _xml_fragment(xml: str, start_marker: str, end_marker: str, *, start_at: int = 0) -> str:
    start = xml.index(start_marker, start_at)
    end = xml.index(end_marker, start) + len(end_marker)
    return xml[start:end]


def _document_with_body(body: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
            xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
  <w:body>
    {body}
    <w:sectPr/>
  </w:body>
</w:document>
"""


def _paragraph(text: str, style_id: str = "Normal") -> str:
    return f'<w:p><w:pPr><w:pStyle w:val="{style_id}"/></w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>'


def _numbered_paragraph(text: str, *, style_id: str = "Normal") -> str:
    return (
        f'<w:p><w:pPr><w:pStyle w:val="{style_id}"/>'
        '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="42"/></w:numPr>'
        f'</w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>'
    )


def _table_xml() -> str:
    return _xml_fragment(_zip_document(), "<w:tbl>", "</w:tbl>")


def _style_paragraph_xml(document: str, style_id: str) -> str:
    style_position = document.index(f'<w:pStyle w:val="{style_id}"/>')
    return _xml_fragment(document, "<w:p>", "</w:p>", start_at=document.rfind("<w:p>", 0, style_position))


def _first_figure_paragraph() -> str:
    document = _zip_document()
    drawing_position = document.index("<w:drawing>")
    return _xml_fragment(document, "<w:p>", "</w:p>", start_at=document.rfind("<w:p>", 0, drawing_position))


def _conversion_result_for_body(tmp_path: Path, name: str, body: str, *, add_numbering: bool = False):
    path = tmp_path / name
    additions = {"word/numbering.xml": basic_numbering()} if add_numbering else None
    _write_document_variant(path, _document_with_body(body), add=additions)
    result = convert_docx_to_tei(path, metadata=_metadata())
    assert result.is_successful
    assert result.xml_bytes is not None
    assert validate_xml_bytes(result.xml_bytes).valid
    return build_editorial_document(inspect_docx_file(path)), etree.fromstring(result.xml_bytes)


def _assert_cli_refuses_atomically(path: Path, destination: Path, code: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("ancienne TEI", encoding="utf-8")
    before = {item.name for item in destination.parent.iterdir()}

    assert code in _codes(path)
    assert main(["convert-docx", str(path), str(destination), "--metadata", str(METADATA)]) == 1

    assert destination.read_text(encoding="utf-8") == "ancienne TEI"
    assert {item.name for item in destination.parent.iterdir()} == before
    media_dir = destination.parent / "media"
    assert not media_dir.exists() or not any(media_dir.iterdir())


def test_inspection_preserves_body_block_order_and_simple_table_shape() -> None:
    inspection = inspect_docx_file(DOCX)
    tables = [block for block in inspection.body_blocks if isinstance(block, TableInfo)]

    assert len(tables) == 2
    assert [table.source_block_index for table in tables] == sorted(table.source_block_index for table in tables)
    assert tables[0].declared_column_count == 3
    assert len(tables[0].rows) == 3
    assert tables[0].rows[0].is_header
    assert [len(row.cells) for row in tables[0].rows] == [3, 3, 3]
    assert tables[0].rows[1].cells[2].paragraphs[0].text == ""


def test_editorial_model_associates_figure_details_and_tables() -> None:
    result = build_editorial_document(
        inspect_docx_file(DOCX), excluded_body_paragraph_indexes=frozenset({0, 1})
    )
    figures = [block for block in result.document.blocks if isinstance(block, EditorialFigure)]
    tables = [block for block in result.document.blocks if isinstance(block, EditorialTable)]

    assert len(figures) == 3
    assert figures[0].title is not None and figures[0].title.rendition == "figure-title"
    assert figures[0].caption is not None and figures[0].caption.rendition == "caption"
    assert figures[0].credits is not None and figures[0].credits.rendition == "credits"
    assert any(getattr(inline, "note_id", None) == "1" for inline in figures[0].credits.content)
    assert figures[1].title is None and figures[1].caption is not None and figures[1].credits is None
    assert figures[2].title is not None and figures[2].caption is None and figures[2].credits is not None
    assert [table.column_count for table in tables] == [3, 2]
    assert tables[0].rows[0].role == "label"
    assert all(cell.role == "label" for cell in tables[0].rows[0].cells)
    assert tables[0].rows[1].cells[2].content == ()


def test_tei_serializes_figure_details_and_simple_tables_in_document_order() -> None:
    result = convert_docx_to_tei(DOCX, metadata=_metadata())
    assert result.is_successful
    assert result.xml_bytes is not None
    assert validate_xml_bytes(result.xml_bytes).valid
    root = etree.fromstring(result.xml_bytes)

    figures = root.xpath(".//tei:body/tei:figure", namespaces=TEI)
    tables = root.xpath(".//tei:body/tei:table", namespaces=TEI)
    assert len(figures) == 3
    assert len(tables) == 2
    assert [child.tag.rsplit("}", 1)[-1] for child in figures[0]] == ["head", "graphic", "figDesc", "p", "p"]
    assert figures[0].xpath("./tei:p[@rend='caption']", namespaces=TEI)
    assert figures[0].xpath("./tei:p[@rend='credits']", namespaces=TEI)
    assert figures[0].xpath("./tei:p[@rend='credits']/tei:note[@place='foot']", namespaces=TEI)
    assert tables[0].get("rows") == "3" and tables[0].get("cols") == "3"
    assert tables[0].xpath("./tei:row[1][@role='label']/tei:cell[@role='label']", namespaces=TEI)
    assert len(tables[0].xpath("./tei:row[2]/tei:cell[not(node())]", namespaces=TEI)) == 1
    assert tables[0].xpath("./tei:row[3]/tei:cell[1]/tei:note[@place='end']", namespaces=TEI)
    blocks = root.xpath(".//tei:body/*", namespaces=TEI)
    assert [block.tag.rsplit("}", 1)[-1] for block in blocks].count("table") == 2


def test_tables_after_prose_quote_verse_quote_list_and_figure_keep_block_order(tmp_path: Path) -> None:
    table = _table_xml()
    cases = [
        (
            "prose-table.docx",
            _paragraph("Citation.", "Quote") + table + _paragraph("Apres."),
            (ProseQuote, EditorialTable, Paragraph),
            ["quote", "table", "p"],
            False,
        ),
        (
            "verse-table.docx",
            _paragraph("Vers.", "IntenseQuote") + table + _paragraph("Apres."),
            (VerseQuote, EditorialTable, Paragraph),
            ["quote", "table", "p"],
            False,
        ),
        (
            "list-table.docx",
            _numbered_paragraph("Item.") + table + _paragraph("Apres."),
            (EditorialList, EditorialTable, Paragraph),
            ["list", "table", "p"],
            True,
        ),
        (
            "figure-table.docx",
            _first_figure_paragraph() + table + _paragraph("Apres."),
            (EditorialFigure, EditorialTable, Paragraph),
            ["figure", "table", "p"],
            False,
        ),
    ]
    for name, body, model_types, tei_tags, add_numbering in cases:
        model, root = _conversion_result_for_body(tmp_path, name, body, add_numbering=add_numbering)
        assert [type(block) for block in model.document.blocks[:3]] == list(model_types)
        body_children = root.xpath(".//tei:body/*", namespaces=TEI)
        assert [child.tag.rsplit("}", 1)[-1] for child in body_children[:3]] == tei_tags


def test_table_refusals_are_conservative(tmp_path: Path) -> None:
    document = _zip_document()
    table = _table_xml()
    first_row = _xml_fragment(table, "<w:tr>", "</w:tr>")
    first_cell = _xml_fragment(table, "<w:tc>", "</w:tc>")
    first_paragraph = _xml_fragment(first_cell, "<w:p>", "</w:p>")
    drawing = _first_figure_paragraph()
    drawing_run = _xml_fragment(drawing, "<w:r>", "</w:r>")
    variants = {
        "empty-table.docx": (document.replace(table, "<w:tbl/>", 1), "empty_table_not_serializable"),
        "empty-row.docx": (document.replace(first_row, "<w:tr/>", 1), "empty_table_row_not_serializable"),
        "irregular.docx": (document.replace(first_cell, "", 1), "irregular_table_not_serializable"),
        "merged.docx": (document.replace("<w:tc><w:p><w:r><w:rPr><w:b/>", "<w:tc><w:tcPr><w:gridSpan w:val=\"2\"/></w:tcPr><w:p><w:r><w:rPr><w:b/>", 1), "merged_table_cells_not_serializable"),
        "vmerge.docx": (document.replace("<w:tc><w:p><w:r><w:rPr><w:b/>", "<w:tc><w:tcPr><w:vMerge w:val=\"restart\"/></w:tcPr><w:p><w:r><w:rPr><w:b/>", 1), "merged_table_cells_not_serializable"),
        "hmerge.docx": (document.replace("<w:tc><w:p><w:r><w:rPr><w:b/>", "<w:tc><w:tcPr><w:hMerge w:val=\"restart\"/></w:tcPr><w:p><w:r><w:rPr><w:b/>", 1), "merged_table_cells_not_serializable"),
        "nested.docx": (document.replace("<w:tc><w:p><w:r><w:t>X", "<w:tc><w:tbl><w:tr><w:tc><w:p/></w:tc></w:tr></w:tbl><w:p><w:r><w:t>X", 1), "nested_table_not_serializable"),
        "bad-header.docx": (document.replace("<w:tr><w:tc><w:p><w:r><w:rPr><w:b/>", "<w:tr><w:trPr><w:tblHeader/></w:trPr><w:tc><w:p><w:r><w:rPr><w:b/>", 1), "invalid_table_header_not_serializable"),
        "bad-cell-style.docx": (document.replace('w:val="TEIcell"', 'w:val="UnknownParagraph"'), "unsupported_table_cell_style"),
        "multi-paragraph-cell.docx": (document.replace(first_paragraph, first_paragraph + _paragraph("Second."), 1), "multiple_paragraphs_in_table_cell_not_serializable"),
        "image-cell.docx": (document.replace(first_paragraph, f'<w:p>{drawing_run}</w:p>', 1), "image_in_table_cell_not_serializable"),
        "list-cell.docx": (document.replace(first_paragraph, _numbered_paragraph("Cellule liste."), 1), "numbered_table_cell_not_serializable"),
    }
    for name, (variant, code) in variants.items():
        path = tmp_path / name
        add = {"word/numbering.xml": basic_numbering()} if name == "list-cell.docx" else None
        _write_document_variant(path, variant, add=add)
        assert code in _codes(path)


def test_table_in_note_is_refused_with_precise_diagnostic(tmp_path: Path) -> None:
    path = tmp_path / "table-in-note.docx"
    footnotes = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:footnote w:id="1">{_table_xml()}</w:footnote>
</w:footnotes>
"""
    _write_document_variant(path, _document_with_body(_paragraph("Corps.")), add={"word/footnotes.xml": footnotes})
    assert "table_in_note_not_serializable" in _codes(path)


def test_controlled_figure_styles_are_strict_and_orphans_are_refused(tmp_path: Path) -> None:
    convention = NATIVE_WORD_CONVENTION
    assert convention.is_figure_title_style("TEIfiguretitle", "TEI_figure_title", True)
    assert convention.is_controlled_figure_caption_style("TEIfigurecaption", "TEI_figure_caption", True)
    assert convention.is_figure_credits_style("TEIfigurecredits", "TEI_figure_credits", True)
    assert not convention.is_figure_title_style("TEIfiguretitle", "TEI_figure_title", False)
    assert not convention.is_figure_title_style("LocalTitle", "TEI_figure_title", True)
    document = _zip_document()
    title = _style_paragraph_xml(document, "TEIfiguretitle")
    credits = _style_paragraph_xml(document, "TEIfigurecredits")
    drawing_run = _xml_fragment(_first_figure_paragraph(), "<w:r>", "</w:r>")
    numbered_title = title.replace(
        '<w:pPr><w:pStyle w:val="TEIfiguretitle"/></w:pPr>',
        '<w:pPr><w:pStyle w:val="TEIfiguretitle"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="42"/></w:numPr></w:pPr>',
        1,
    )
    numbered_credits = credits.replace(
        '<w:pPr><w:pStyle w:val="TEIfigurecredits"/></w:pPr>',
        '<w:pPr><w:pStyle w:val="TEIfigurecredits"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="42"/></w:numPr></w:pPr>',
        1,
    )
    variants = {
        "orphan-title.docx": (
            document.replace("<w:p><w:pPr><w:pStyle w:val=\"Normal\"/></w:pPr><w:r><w:t>Texte après.", "<w:p><w:pPr><w:pStyle w:val=\"TEIfiguretitle\"/></w:pPr><w:r><w:t>Orphelin</w:t></w:r></w:p><w:p><w:pPr><w:pStyle w:val=\"Normal\"/></w:pPr><w:r><w:t>Texte après."),
            "orphan_figure_title_not_serializable",
        ),
        "orphan-credits.docx": (
            document.replace("<w:p><w:pPr><w:pStyle w:val=\"Normal\"/></w:pPr><w:r><w:t>Texte après.", "<w:p><w:pPr><w:pStyle w:val=\"TEIfigurecredits\"/></w:pPr><w:r><w:t>Orphelin</w:t></w:r></w:p><w:p><w:pPr><w:pStyle w:val=\"Normal\"/></w:pPr><w:r><w:t>Texte après."),
            "orphan_figure_credits_not_serializable",
        ),
        "empty-title.docx": (
            document.replace(
                '<w:p><w:pPr><w:pStyle w:val="TEIfiguretitle"/></w:pPr><w:r><w:t>Titre de </w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>figure</w:t></w:r></w:p>',
                '<w:p><w:pPr><w:pStyle w:val="TEIfiguretitle"/></w:pPr><w:r/></w:p>',
            ),
            "empty_figure_title_not_serializable",
        ),
        "numbered-title.docx": (
            document.replace(title, numbered_title, 1),
            "numbered_figure_title_not_serializable",
        ),
        "image-title.docx": (
            document.replace(title, f'<w:p><w:pPr><w:pStyle w:val="TEIfiguretitle"/></w:pPr>{drawing_run}</w:p>', 1),
            "image_in_figure_title_not_serializable",
        ),
        "empty-credits.docx": (
            document.replace(credits, '<w:p><w:pPr><w:pStyle w:val="TEIfigurecredits"/></w:pPr></w:p>', 1),
            "empty_figure_credits_not_serializable",
        ),
        "numbered-credits.docx": (
            document.replace(credits, numbered_credits, 1),
            "numbered_figure_credits_not_serializable",
        ),
        "image-credits.docx": (
            document.replace(credits, f'<w:p><w:pPr><w:pStyle w:val="TEIfigurecredits"/></w:pPr>{drawing_run}</w:p>', 1),
            "image_in_figure_credits_not_serializable",
        ),
    }
    for name, (variant, code) in variants.items():
        path = tmp_path / name
        add = {"word/numbering.xml": basic_numbering()} if "numbered" in name else None
        _write_document_variant(path, variant, add=add)
        assert code in _codes(path)


def test_cli_refusals_preserve_existing_xml_and_do_not_write_media(tmp_path: Path) -> None:
    document = _zip_document()
    table_path = tmp_path / "table-refusal.docx"
    _write_document_variant(table_path, document.replace(_table_xml(), "<w:tbl/>", 1))
    _assert_cli_refuses_atomically(
        table_path,
        tmp_path / "table-output" / "book.xml",
        "empty_table_not_serializable",
    )

    credits = _style_paragraph_xml(document, "TEIfigurecredits")
    figure_path = tmp_path / "figure-refusal.docx"
    _write_document_variant(
        figure_path,
        document.replace(credits, '<w:p><w:pPr><w:pStyle w:val="TEIfigurecredits"/></w:pPr></w:p>', 1),
    )
    _assert_cli_refuses_atomically(
        figure_path,
        tmp_path / "figure-output" / "book.xml",
        "empty_figure_credits_not_serializable",
    )


def _zip_document() -> str:
    with ZipFile(DOCX) as archive:
        return archive.read("word/document.xml").decode("utf-8")
