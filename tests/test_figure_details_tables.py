"""Figures enrichies et tables Word simples de la passe 11."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from lxml import etree

from mini_metopes.docx import TableInfo, inspect_docx_file
from mini_metopes.editorial import EditorialFigure, EditorialTable, build_editorial_document
from mini_metopes.editorial import NATIVE_WORD_CONVENTION
from mini_metopes.metadata import load_metadata_file
from mini_metopes.tei import convert_docx_to_tei
from mini_metopes.validation import validate_xml_bytes


FIXTURES = Path(__file__).parent / "fixtures"
DOCX = FIXTURES / "docx" / "native-figure-details-and-tables.docx"
METADATA = FIXTURES / "metadata" / "native-figure-details-and-tables.metadata.json"
TEI = {"tei": "http://www.tei-c.org/ns/1.0"}


def _metadata():
    result = load_metadata_file(METADATA)
    assert result.metadata is not None
    return result.metadata


def _write_document_variant(path: Path, document: str) -> None:
    with ZipFile(DOCX) as source, ZipFile(path, "w", compression=ZIP_DEFLATED) as target:
        for entry in source.infolist():
            data = document.encode("utf-8") if entry.filename == "word/document.xml" else source.read(entry.filename)
            info = ZipInfo(entry.filename, date_time=(2024, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            target.writestr(info, data)


def _codes(path: Path) -> set[str]:
    return {item.code for item in convert_docx_to_tei(path, metadata=_metadata()).diagnostics}


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


def test_table_refusals_are_conservative(tmp_path: Path) -> None:
    document = _zip_document()
    variants = {
        "merged.docx": (document.replace("<w:tc><w:p><w:r><w:rPr><w:b/>", "<w:tc><w:tcPr><w:gridSpan w:val=\"2\"/></w:tcPr><w:p><w:r><w:rPr><w:b/>", 1), "merged_table_cells_not_serializable"),
        "nested.docx": (document.replace("<w:tc><w:p><w:r><w:t>X", "<w:tc><w:tbl><w:tr><w:tc><w:p/></w:tc></w:tr></w:tbl><w:p><w:r><w:t>X", 1), "nested_table_not_serializable"),
        "bad-header.docx": (document.replace("<w:tr><w:tc><w:p><w:r><w:rPr><w:b/>", "<w:tr><w:trPr><w:tblHeader/></w:trPr><w:tc><w:p><w:r><w:rPr><w:b/>", 1), "invalid_table_header_not_serializable"),
        "bad-cell-style.docx": (document.replace('w:val="TEIcell"', 'w:val="UnknownParagraph"'), "unsupported_table_cell_style"),
    }
    for name, (variant, code) in variants.items():
        path = tmp_path / name
        _write_document_variant(path, variant)
        assert code in _codes(path)


def test_controlled_figure_styles_are_strict_and_orphans_are_refused(tmp_path: Path) -> None:
    convention = NATIVE_WORD_CONVENTION
    assert convention.is_figure_title_style("TEIfiguretitle", "TEI_figure_title", True)
    assert convention.is_controlled_figure_caption_style("TEIfigurecaption", "TEI_figure_caption", True)
    assert convention.is_figure_credits_style("TEIfigurecredits", "TEI_figure_credits", True)
    assert not convention.is_figure_title_style("TEIfiguretitle", "TEI_figure_title", False)
    assert not convention.is_figure_title_style("LocalTitle", "TEI_figure_title", True)
    document = _zip_document()
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
    }
    for name, (variant, code) in variants.items():
        path = tmp_path / name
        _write_document_variant(path, variant)
        assert code in _codes(path)


def _zip_document() -> str:
    with ZipFile(DOCX) as archive:
        return archive.read("word/document.xml").decode("utf-8")
