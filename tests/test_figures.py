"""Figures Word simples, légendes et médias embarqués."""

from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from lxml import etree

from mini_metopes.cli import main
from mini_metopes.docx import inspect_docx_file
from mini_metopes.editorial import EditorialFigure, build_editorial_document, editorial_build_result_to_json
from mini_metopes.metadata import load_metadata_file
from mini_metopes.tei import (
    TeiAsset,
    TeiConversionResult,
    convert_docx_to_tei,
    write_tei_conversion_result,
)
from mini_metopes.validation import validate_xml_bytes


FIXTURES = Path(__file__).parent / "fixtures"
DOCX = FIXTURES / "docx" / "native-figures.docx"
METADATA = FIXTURES / "metadata" / "native-figures.metadata.json"
TEI = {"tei": "http://www.tei-c.org/ns/1.0"}


def _metadata():
    loaded = load_metadata_file(METADATA)
    assert loaded.metadata is not None
    return loaded.metadata


def _zip_bytes(path: Path, name: str) -> bytes:
    with ZipFile(path) as archive:
        return archive.read(name)


def _write_variant(path: Path, replacements: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(DOCX) as source, ZipFile(path, "w", compression=ZIP_DEFLATED) as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename in replacements:
                content = replacements[item.filename].encode("utf-8")
            info = ZipInfo(item.filename, date_time=(2024, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            target.writestr(info, content)


def _conversion_codes(path: Path) -> list[str]:
    return [diagnostic.code for diagnostic in convert_docx_to_tei(path, metadata=_metadata()).diagnostics]


def test_inspection_exposes_structured_drawing_and_media_information() -> None:
    inspection = inspect_docx_file(DOCX)
    first_drawing = next(
        content.drawing
        for paragraph in inspection.paragraphs
        for run in paragraph.runs
        for content in run.contents
        if content.kind == "drawing" and content.drawing is not None
    )
    media = {item.path: item for item in inspection.media}

    assert first_drawing.placement == "inline"
    assert first_drawing.embedded_relationship_ids == ("rIdPng",)
    assert first_drawing.linked_relationship_ids == ()
    assert first_drawing.name == "Picture PNG"
    assert first_drawing.title == "Titre Word ignore"
    assert first_drawing.description == "Description accessible du carré PNG."
    assert first_drawing.width_emu == 914400
    assert first_drawing.height_emu == 914400
    assert not first_drawing.is_cropped
    assert first_drawing.rotation is None
    assert not first_drawing.flip_horizontal
    assert not first_drawing.flip_vertical
    assert media["word/media/figure.png"].content_type == "image/png"
    assert media["word/media/figure.png"].sha256 is not None
    assert media["word/media/photo.jpeg"].content_type == "image/jpeg"
    assert media["word/media/unused.gif"].content_type == "image/gif"
    assert json.loads(json.dumps(inspection.media[0].__dict__, sort_keys=True))


def test_editorial_model_builds_figures_captions_and_content_addressed_urls() -> None:
    result = build_editorial_document(inspect_docx_file(DOCX), excluded_body_paragraph_indexes=frozenset({0, 1}))
    body_figures = [block for block in result.document.blocks if isinstance(block, EditorialFigure)]
    note_figures = [
        block
        for note in result.document.notes
        for block in note.blocks
        if isinstance(block, EditorialFigure)
    ]
    data = json.loads(editorial_build_result_to_json(result))

    assert len(body_figures) == 4
    assert len(note_figures) == 2
    assert body_figures[0].caption is not None
    assert body_figures[1].caption is None
    assert body_figures[0].graphic.media_url == body_figures[2].graphic.media_url
    assert body_figures[0].graphic.media_url.startswith("media/")
    assert body_figures[0].graphic.media_url.endswith(".png")
    assert body_figures[1].graphic.media_url.endswith(".jpg")
    assert body_figures[0].caption.rendition == "caption"
    assert data["document"]["blocks"][1]["kind"] == "figure"
    assert data["document"]["blocks"][1]["graphic"]["sha256"] == body_figures[0].graphic.sha256


def test_tei_serializes_figures_and_assets_are_written_once(tmp_path: Path) -> None:
    result = convert_docx_to_tei(DOCX, metadata=_metadata())
    assert result.is_successful
    assert result.xml_bytes is not None
    assert validate_xml_bytes(result.xml_bytes).valid
    assert len(result.assets) == 2
    root = etree.fromstring(result.xml_bytes)

    assert root.xpath("count(.//tei:figure)", namespaces=TEI) == 6.0
    assert root.xpath("count(.//tei:figure/tei:graphic)", namespaces=TEI) == 6.0
    assert root.xpath("count(.//tei:figure/tei:figDesc)", namespaces=TEI) == 6.0
    assert root.xpath("count(.//tei:figure/tei:p[@rend='caption'])", namespaces=TEI) == 2.0
    assert root.xpath("count(.//tei:figure/tei:head)", namespaces=TEI) == 0.0
    assert root.xpath("count(.//tei:figure[@rend])", namespaces=TEI) == 0.0
    assert root.xpath("count(.//tei:note[@place='foot']//tei:figure)", namespaces=TEI) == 1.0
    assert root.xpath("count(.//tei:note[@place='end']//tei:figure)", namespaces=TEI) == 1.0

    destination = tmp_path / "book.xml"
    write_result = write_tei_conversion_result(result, destination)
    assert destination.exists()
    assert write_result.media_written == 2
    assert write_result.media_reused == 0
    media_files = sorted((tmp_path / "media").iterdir())
    assert [path.suffix for path in media_files] == [".jpg", ".png"]
    assert _zip_bytes(DOCX, "word/media/unused.gif") not in [path.read_bytes() for path in media_files]
    assert any(path.read_bytes() == _zip_bytes(DOCX, "word/media/figure.png") for path in media_files)
    assert any(path.read_bytes() == _zip_bytes(DOCX, "word/media/photo.jpeg") for path in media_files)
    second = write_tei_conversion_result(result, destination)
    assert second.media_written == 0
    assert second.media_reused == 2


def test_existing_corrupted_content_addressed_media_is_preserved(tmp_path: Path) -> None:
    result = convert_docx_to_tei(DOCX, metadata=_metadata())
    assert result.assets
    destination = tmp_path / "book.xml"
    destination.write_text("ancienne TEI", encoding="utf-8")
    corrupted = tmp_path / result.assets[0].relative_path
    corrupted.parent.mkdir(parents=True)
    corrupted.write_bytes(b"corrompu")

    try:
        write_tei_conversion_result(result, destination)
    except ValueError as error:
        assert "existing_media_hash_mismatch" in str(error)
    else:
        raise AssertionError("l'ecriture aurait dû refuser le média corrompu")

    assert destination.read_text(encoding="utf-8") == "ancienne TEI"
    assert corrupted.read_bytes() == b"corrompu"


def test_conversion_without_figures_has_no_assets() -> None:
    result = convert_docx_to_tei(FIXTURES / "docx" / "native-consecutive-paragraphs.docx", metadata=load_metadata_file(FIXTURES / "metadata" / "native-consecutive-paragraphs.metadata.json").metadata)
    assert result.is_successful
    assert result.assets == ()


def test_negative_figure_cases_are_blocking(tmp_path: Path) -> None:
    document = _zip_bytes(DOCX, "word/document.xml").decode("utf-8")
    relationships = _zip_bytes(DOCX, "word/_rels/document.xml.rels").decode("utf-8")
    cases = [
        ("missing-description.docx", { "word/document.xml": document.replace(' descr="Description accessible du carré PNG."', "") }, "missing_figure_description"),
        ("floating.docx", { "word/document.xml": document.replace("<wp:inline>", "<wp:anchor>").replace("</wp:inline>", "</wp:anchor>") }, "floating_image_not_serializable"),
        ("mixed.docx", { "word/document.xml": document.replace("<w:drawing>", "<w:t>texte</w:t><w:drawing>", 1) }, "mixed_text_and_image_not_serializable"),
        ("external.docx", { "word/document.xml": document.replace('r:embed="rIdPng"', 'r:link="rIdPng"', 1), "word/_rels/document.xml.rels": relationships.replace('Target="media/figure.png"', 'Target="https://example.test/image.png" TargetMode="External"', 1) }, "external_image_not_serializable"),
        ("caption-orphan.docx", { "word/document.xml": document.replace("<wp:inline>", "<wp:anchor>", 1).replace("</wp:inline>", "</wp:anchor>", 1) }, "orphan_figure_caption_not_serializable"),
    ]
    for name, replacements, code in cases:
        path = tmp_path / name
        _write_variant(path, replacements)
        destination = tmp_path / f"{name}.xml"
        assert code in _conversion_codes(path)
        assert main(["convert-docx", str(path), str(destination), "--metadata", str(METADATA)]) == 1
        assert not destination.exists()


def test_manual_asset_path_validation() -> None:
    failed = TeiConversionResult(
        b"<?xml version='1.0'?><TEI/>",
        (),
        (),
        assets=(TeiAsset("../bad.png", "image/png", "0" * 64, b"x"),),
    )
    try:
        write_tei_conversion_result(failed, Path("ignored.xml"))
    except ValueError as error:
        assert "invalid_figure_media_url" in str(error)
    else:
        raise AssertionError("chemin d'asset dangereux accepté")
