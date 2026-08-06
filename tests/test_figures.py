"""Figures Word simples, légendes et médias embarqués."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from lxml import etree

from mini_metopes.cli import main
from mini_metopes.docx import inspect_docx_file
from mini_metopes.editorial import EditorialFigure, build_editorial_document, editorial_build_result_to_json
from mini_metopes.metadata import load_metadata_file
from mini_metopes.tei import conversion as tei_conversion
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
IMAGE_RELATIONSHIP_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
TEI = {"tei": "http://www.tei-c.org/ns/1.0"}


def _metadata():
    loaded = load_metadata_file(METADATA)
    assert loaded.metadata is not None
    return loaded.metadata


def _zip_bytes(path: Path, name: str) -> bytes:
    with ZipFile(path) as archive:
        return archive.read(name)


def _write_variant(
    path: Path,
    replacements: dict[str, str | bytes],
    *,
    remove: tuple[str, ...] = (),
    add: dict[str, str | bytes] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(DOCX) as source, ZipFile(path, "w", compression=ZIP_DEFLATED) as target:
        for item in source.infolist():
            if item.filename in remove:
                continue
            content = source.read(item.filename)
            if item.filename in replacements:
                replacement = replacements[item.filename]
                content = replacement.encode("utf-8") if isinstance(replacement, str) else replacement
            info = ZipInfo(item.filename, date_time=(2024, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            target.writestr(info, content)
        for name, content in (add or {}).items():
            info = ZipInfo(name, date_time=(2024, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            target.writestr(info, content.encode("utf-8") if isinstance(content, str) else content)


def _conversion_codes(path: Path) -> list[str]:
    return [diagnostic.code for diagnostic in convert_docx_to_tei(path, metadata=_metadata()).diagnostics]


def _first_drawing_xml(document: str) -> str:
    start = document.index("<w:drawing>")
    end = document.index("</w:drawing>", start) + len("</w:drawing>")
    return document[start:end]


def _replace_first_caption(document: str, replacement: str) -> str:
    start = document.index('<w:p><w:pPr><w:pStyle w:val="Caption"/></w:pPr>')
    end = document.index("</w:p>", start) + len("</w:p>")
    return document[:start] + replacement + document[end:]


def _assert_cli_refuses_without_writing(path: Path, destination: Path, code: str) -> None:
    destination.write_text("ancienne TEI", encoding="utf-8")
    media_dir = destination.parent / "media"
    assert code in _conversion_codes(path)
    assert main(["convert-docx", str(path), str(destination), "--metadata", str(METADATA)]) == 1
    assert destination.read_text(encoding="utf-8") == "ancienne TEI"
    assert not media_dir.exists() or not any(media_dir.iterdir())


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
    assert first_drawing.invalid_properties == ()
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


def test_two_consecutive_native_captions_become_figure_title_and_caption(tmp_path: Path) -> None:
    """Protocole Caption a deux paragraphes (decision 0033), calque sur
    Signature : le premier paragraphe Caption devient le titre de la
    figure, le second sa legende."""
    document = _zip_bytes(DOCX, "word/document.xml").decode("utf-8")
    two_captions = (
        '<w:p><w:pPr><w:pStyle w:val="Caption"/></w:pPr><w:r><w:t>Titre de la figure</w:t></w:r></w:p>'
        '<w:p><w:pPr><w:pStyle w:val="Caption"/></w:pPr><w:r><w:t>Legende de la figure</w:t></w:r></w:p>'
    )
    path = tmp_path / "two-captions.docx"
    _write_variant(path, {"word/document.xml": _replace_first_caption(document, two_captions)})

    result = convert_docx_to_tei(path, metadata=_metadata())

    assert result.is_successful, result.diagnostics
    root = etree.fromstring(result.xml_bytes)
    titled_figures = root.xpath(".//tei:figure[tei:head]", namespaces=TEI)
    assert len(titled_figures) == 1
    figure = titled_figures[0]
    assert figure.findtext("tei:head", namespaces=TEI) == "Titre de la figure"
    caption_paragraphs = figure.xpath("./tei:p[@rend='caption']", namespaces=TEI)
    assert [p.text for p in caption_paragraphs] == ["Legende de la figure"]


def test_single_native_caption_still_becomes_a_caption_only(tmp_path: Path) -> None:
    """Retro-compatibilite explicite : un seul paragraphe Caption apres
    l'image reste une legende seule, sans titre (comportement d'origine)."""
    result = build_editorial_document(inspect_docx_file(DOCX), excluded_body_paragraph_indexes=frozenset({0, 1}))
    body_figures = [block for block in result.document.blocks if isinstance(block, EditorialFigure)]

    assert body_figures[0].title is None
    assert body_figures[0].caption is not None
    assert body_figures[0].caption.rendition == "caption"


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


def test_hyperlinked_images_are_refused_and_preserve_outputs(tmp_path: Path) -> None:
    document = _zip_bytes(DOCX, "word/document.xml").decode("utf-8")
    drawing = _first_drawing_xml(document)
    cases = [
        ("hyperlink-external.docx", f'<w:hyperlink r:id="rIdHyper"><w:r>{drawing}</w:r></w:hyperlink>'),
        ("hyperlink-anchor.docx", f'<w:hyperlink w:anchor="figure-anchor"><w:r>{drawing}</w:r></w:hyperlink>'),
    ]
    for name, replacement in cases:
        path = tmp_path / name
        _write_variant(path, {"word/document.xml": document.replace(f"<w:r>\n        {drawing}\n      </w:r>", replacement, 1)})
        _assert_cli_refuses_without_writing(path, tmp_path / f"{name}.xml", "hyperlinked_image_not_serializable")


def test_unsafe_relationship_targets_are_refused(tmp_path: Path) -> None:
    relationships = _zip_bytes(DOCX, "word/_rels/document.xml.rels").decode("utf-8")
    targets = [
        "",
        "media/../media/image.png",
        "../media/image.png",
        "media/sub/../../media/image.png",
        r"media\image.png",
    ]
    for index, target in enumerate(targets):
        path = tmp_path / f"unsafe-{index}.docx"
        _write_variant(
            path,
            {"word/_rels/document.xml.rels": relationships.replace('Target="media/figure.png"', f'Target="{target}"', 1)},
        )
        assert "unsafe_image_target" in _conversion_codes(path)

    safe_path = tmp_path / "safe-dot.docx"
    _write_variant(
        safe_path,
        {"word/_rels/document.xml.rels": relationships.replace('Target="media/figure.png"', 'Target="./media/figure.png"', 1)},
    )
    assert "unsafe_image_target" not in _conversion_codes(safe_path)


def test_duplicate_image_relationships_are_refused_only_when_used(tmp_path: Path) -> None:
    relationships = _zip_bytes(DOCX, "word/_rels/document.xml.rels").decode("utf-8")
    duplicate_internal = relationships.replace(
        "</Relationships>",
        '  <Relationship Id="rIdPng" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/photo.jpeg"/>\n</Relationships>',
    )
    duplicate_external = relationships.replace(
        "</Relationships>",
        '  <Relationship Id="rIdPng" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="https://example.test/image.png" TargetMode="External"/>\n</Relationships>',
    )
    unused_duplicate = relationships.replace(
        "</Relationships>",
        '  <Relationship Id="rIdUnused" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/figure.png"/>\n'
        '  <Relationship Id="rIdUnused" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/photo.jpeg"/>\n</Relationships>',
    )
    for name, rels, code in [
        ("duplicate-internal.docx", duplicate_internal, "duplicate_image_relationship_not_serializable"),
        ("duplicate-external.docx", duplicate_external, "duplicate_image_relationship_not_serializable"),
        ("duplicate-unused.docx", unused_duplicate, "duplicate_image_relationship_not_serializable"),
    ]:
        path = tmp_path / name
        _write_variant(path, {"word/_rels/document.xml.rels": rels})
        codes = _conversion_codes(path)
        if "unused" in name:
            assert code not in codes
            assert convert_docx_to_tei(path, metadata=_metadata()).is_successful
        else:
            assert code in codes

    footnote_relationships = _zip_bytes(DOCX, "word/_rels/footnotes.xml.rels").decode("utf-8")
    footnote_duplicate = footnote_relationships.replace(
        "</Relationships>",
        '  <Relationship Id="rIdNotePng" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/photo.jpeg"/>\n</Relationships>',
    )
    note_path = tmp_path / "duplicate-note.docx"
    _write_variant(note_path, {"word/_rels/footnotes.xml.rels": footnote_duplicate})
    assert "duplicate_image_relationship_not_serializable" in _conversion_codes(note_path)


def test_drawing_properties_distinguish_absent_and_invalid_values(tmp_path: Path) -> None:
    document = _zip_bytes(DOCX, "word/document.xml").decode("utf-8")
    cases = [
        ("bad-cx.docx", document.replace('cx="914400"', 'cx="abc"', 1), "extent.cx"),
        ("bad-cy.docx", document.replace('cy="914400"', 'cy="0"', 1), "extent.cy"),
        ("bad-rot.docx", document.replace("<a:xfrm/>", '<a:xfrm rot="abc"/>', 1), "xfrm.rot"),
        ("bad-flip.docx", document.replace("<a:xfrm/>", '<a:xfrm flipH="maybe" flipV="2"/>', 1), "xfrm.flipH"),
        ("bad-crop.docx", document.replace("<a:xfrm/>", '<a:xfrm/><a:srcRect l="abc"/>', 1), "srcRect.l"),
        ("bad-placement.docx", document.replace("<wp:inline>", "<wp:inline><wp:anchor></wp:anchor>", 1), "placement"),
    ]
    for name, content, property_name in cases:
        path = tmp_path / name
        _write_variant(path, {"word/document.xml": content})
        result = convert_docx_to_tei(path, metadata=_metadata())
        messages = "\n".join(diagnostic.message for diagnostic in result.diagnostics)
        assert "invalid_drawing_property_not_serializable" in [diagnostic.code for diagnostic in result.diagnostics]
        assert property_name in messages


def test_negative_figure_diagnostics_are_exhaustive_enough(tmp_path: Path) -> None:
    document = _zip_bytes(DOCX, "word/document.xml").decode("utf-8")
    relationships = _zip_bytes(DOCX, "word/_rels/document.xml.rels").decode("utf-8")
    content_types = _zip_bytes(DOCX, "[Content_Types].xml").decode("utf-8")
    drawing = _first_drawing_xml(document)
    caption_with_image = f'<w:p><w:pPr><w:pStyle w:val="Caption"/></w:pPr><w:r>{drawing}</w:r></w:p>'
    numbering = """<?xml version="1.0" encoding="UTF-8"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="10">
    <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl>
  </w:abstractNum>
  <w:num w:numId="42"><w:abstractNumId w:val="10"/></w:num>
</w:numbering>
"""
    content_types_with_numbering = content_types.replace(
        "</Types>",
        '  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>\n</Types>',
    )
    cases: list[tuple[str, dict[str, str | bytes], str, tuple[str, ...]]] = [
        ("multiple-images.docx", {"word/document.xml": document.replace(f"<w:r>\n        {drawing}\n      </w:r>", f"<w:r>{drawing}</w:r><w:r>{drawing}</w:r>", 1)}, "multiple_images_in_paragraph_not_serializable", ()),
        ("missing-relationship.docx", {"word/document.xml": document.replace('r:embed="rIdPng"', 'r:embed="rIdMissing"', 1)}, "missing_image_relationship", ()),
        ("unsupported-relationship.docx", {"word/_rels/document.xml.rels": relationships.replace(IMAGE_RELATIONSHIP_TYPE, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", 1)}, "unsupported_image_relationship", ()),
        ("missing-media.docx", {"word/_rels/document.xml.rels": relationships.replace("media/figure.png", "media/missing.png", 1)}, "missing_image_media_part", ()),
        ("unsupported-format.docx", {"word/_rels/document.xml.rels": relationships.replace("media/figure.png", "media/unused.gif", 1)}, "unsupported_image_format", ()),
        ("mismatch.docx", {"word/media/figure.png": _zip_bytes(DOCX, "word/media/photo.jpeg")}, "image_content_type_mismatch", ()),
        ("cropped.docx", {"word/document.xml": document.replace("<a:xfrm/>", '<a:xfrm/><a:srcRect l="1"/>', 1)}, "cropped_image_not_serializable", ()),
        ("transformed.docx", {"word/document.xml": document.replace("<a:xfrm/>", '<a:xfrm rot="1"/>', 1)}, "transformed_image_not_serializable", ()),
        ("image-list.docx", {"word/document.xml": document.replace('<w:pPr><w:pStyle w:val="Normal"/></w:pPr>\n      <w:r>\n        <w:drawing>', '<w:pPr><w:pStyle w:val="Normal"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="42"/></w:numPr></w:pPr>\n      <w:r>\n        <w:drawing>', 1), "word/numbering.xml": numbering, "[Content_Types].xml": content_types_with_numbering}, "image_in_list_item_not_serializable", ()),
        ("empty-caption.docx", {"word/document.xml": _replace_first_caption(document, '<w:p><w:pPr><w:pStyle w:val="Caption"/></w:pPr></w:p>')}, "empty_figure_caption_not_serializable", ()),
        ("image-caption.docx", {"word/document.xml": _replace_first_caption(document, caption_with_image)}, "image_in_figure_caption_not_serializable", ()),
        ("numbered-caption.docx", {"word/document.xml": document.replace('<w:p><w:pPr><w:pStyle w:val="Caption"/></w:pPr>', '<w:p><w:pPr><w:pStyle w:val="Caption"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="42"/></w:numPr></w:pPr>', 1)}, "numbered_figure_caption_not_serializable", ()),
        ("vml.docx", {"word/document.xml": document.replace("</w:body>", '<w:p xmlns:v="urn:schemas-microsoft-com:vml"><w:r><w:pict><v:shape><v:imagedata r:id="rIdPng"/></v:shape></w:pict></w:r></w:p></w:body>')}, "vml_image_not_supported", ()),
    ]
    for name, replacements, code, remove in cases:
        path = tmp_path / name
        extra_replacements = dict(replacements)
        if name == "unsupported-format.docx":
            extra_replacements["[Content_Types].xml"] = content_types
        extra_add: dict[str, str | bytes] = {}
        if name == "image-list.docx":
            extra_add["word/numbering.xml"] = numbering
        _write_variant(path, extra_replacements, remove=remove, add=extra_add)
        _assert_cli_refuses_without_writing(path, tmp_path / f"{name}.xml", code)


def test_total_media_limit_applies_only_to_used_unique_assets(tmp_path: Path, monkeypatch) -> None:
    document = _zip_bytes(DOCX, "word/document.xml").decode("utf-8")
    first_figure_start = document.index("<w:p>", document.index("<w:drawing>"))
    first_figure_end = document.index("</w:p>", first_figure_start) + len("</w:p>")
    body_end = document.index("</w:body>")
    one_png_document = document[: first_figure_end] + document[body_end:]
    one_png_document = one_png_document.replace('<w:r><w:rPr><w:rStyle w:val="EndnoteReference"/></w:rPr><w:endnoteReference w:id="2"/></w:r>', "")
    path = tmp_path / "one-used-with-unused-large.docx"
    _write_variant(path, {"word/document.xml": one_png_document}, add={"word/media/unused-large.bin": b"x" * 500})
    monkeypatch.setattr(tei_conversion, "MAX_TOTAL_MEDIA_BYTES", 80)
    result = convert_docx_to_tei(path, metadata=_metadata())
    assert result.is_successful

    monkeypatch.setattr(tei_conversion, "MAX_TOTAL_MEDIA_BYTES", 150)
    limited = convert_docx_to_tei(DOCX, metadata=_metadata())
    assert "total_image_media_too_large" in [diagnostic.code for diagnostic in limited.diagnostics]

    monkeypatch.setattr(tei_conversion, "MAX_TOTAL_MEDIA_BYTES", 80)
    reused = convert_docx_to_tei(path, metadata=_metadata())
    assert len(reused.assets) == 1
    assert "total_image_media_too_large" not in [diagnostic.code for diagnostic in reused.diagnostics]


def test_asset_preflight_rejects_all_before_writing(tmp_path: Path) -> None:
    png = _zip_bytes(DOCX, "word/media/figure.png")
    sha256 = hashlib.sha256(png).hexdigest()
    valid = TeiAsset(f"media/{sha256}.png", "image/png", sha256, png)
    bad_sha = TeiAsset("media/" + ("0" * 64) + ".png", "image/png", "0" * 64, png)
    destination = tmp_path / "book.xml"
    destination.write_text("ancienne TEI", encoding="utf-8")

    for bad_asset, code in [
        (bad_sha, "invalid_figure_sha256"),
        (TeiAsset(f"media/{sha256}.jpg", "image/png", sha256, png), "invalid_figure_media_url"),
        (TeiAsset(f"media/{sha256}.jpg", "image/jpeg", sha256, png), "image_content_type_mismatch"),
        (TeiAsset(f"media/{sha256}.gif", "image/gif", sha256, png), "unsupported_figure_media_type"),
    ]:
        try:
            write_tei_conversion_result(
                TeiConversionResult(b"<?xml version='1.0'?><TEI/>", (), (), assets=(valid, bad_asset)),
                destination,
            )
        except ValueError as error:
            assert code in str(error)
        else:
            raise AssertionError(f"asset invalide accepte : {code}")
        assert destination.read_text(encoding="utf-8") == "ancienne TEI"
        assert not (tmp_path / valid.relative_path).exists()

    conflict = tmp_path / valid.relative_path
    conflict.parent.mkdir(parents=True)
    conflict.write_bytes(b"corrompu")
    try:
        write_tei_conversion_result(
            TeiConversionResult(
                b"<?xml version='1.0'?><TEI/>",
                (),
                (),
                assets=(TeiAsset(f"media/{hashlib.sha256(_zip_bytes(DOCX, 'word/media/photo.jpeg')).hexdigest()}.jpg", "image/jpeg", hashlib.sha256(_zip_bytes(DOCX, "word/media/photo.jpeg")).hexdigest(), _zip_bytes(DOCX, "word/media/photo.jpeg")), valid),
            ),
            destination,
        )
    except ValueError as error:
        assert "existing_media_hash_mismatch" in str(error)
    else:
        raise AssertionError("conflit de media existant accepte")
    assert not (tmp_path / f"media/{hashlib.sha256(_zip_bytes(DOCX, 'word/media/photo.jpeg')).hexdigest()}.jpg").exists()

    try:
        write_tei_conversion_result(
            TeiConversionResult(
                b"<?xml version='1.0'?><TEI/>",
                (),
                (),
                assets=(valid, TeiAsset(valid.relative_path, "image/png", "1" * 64, png)),
            ),
            tmp_path / "duplicate" / "other.xml",
        )
    except ValueError as error:
        assert "duplicate_figure_asset_conflict" in str(error)
    else:
        raise AssertionError("assets incompatibles au meme chemin acceptes")


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
