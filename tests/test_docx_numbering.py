"""Resolution conservative des definitions de numerotation Word."""

from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from mini_metopes.docx import inspect_docx_file
from mini_metopes.cli import main
from mini_metopes.tei import convert_docx_to_tei
from mini_metopes.metadata import load_metadata_file


FIXTURES = Path(__file__).parent / "fixtures"
RUNTIME = Path(__file__).parents[1] / "build" / "test-runtime" / "numbering"


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
  <Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>
  <Override PartName="/word/endnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml"/>
</Types>
"""


MINIMAL_STYLES = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="Liste"/></w:style>
</w:styles>
"""


def write_docx(
    path: Path,
    body: str,
    *,
    styles: str = MINIMAL_STYLES,
    numbering: str | None = None,
    footnotes: str | None = None,
    endnotes: str | None = None,
) -> None:
    document = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>{body}<w:sectPr/></w:body>
</w:document>
"""
    files: dict[str, str] = {
        "[Content_Types].xml": CONTENT_TYPES,
        "word/document.xml": document,
        "word/styles.xml": styles,
    }
    if numbering is not None:
        files["word/numbering.xml"] = numbering
    if footnotes is not None:
        files["word/footnotes.xml"] = footnotes
    if endnotes is not None:
        files["word/endnotes.xml"] = endnotes
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in files.items():
            info = ZipInfo(name, date_time=(2024, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, content.encode("utf-8"))


def runtime_docx(name: str) -> Path:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    return RUNTIME / name


def paragraph(text: str, *, num_id: str | None = None, ilvl: str | None = None, style: str | None = None) -> str:
    style_xml = f'<w:pStyle w:val="{style}"/>' if style else ""
    level_xml = f'<w:ilvl w:val="{ilvl}"/>' if ilvl is not None else ""
    num_xml = f"<w:numPr>{level_xml}<w:numId w:val=\"{num_id}\"/></w:numPr>" if num_id is not None else ""
    props = f"<w:pPr>{style_xml}{num_xml}</w:pPr>" if style_xml or num_xml else ""
    return f"<w:p>{props}<w:r><w:t>{text}</w:t></w:r></w:p>"


def numbering_xml(inner: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
{inner}
</w:numbering>
"""


def basic_numbering(level_inner: str = '<w:numFmt w:val="decimal"/>') -> str:
    return numbering_xml(
        f'<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0">{level_inner}</w:lvl></w:abstractNum>'
        '<w:num w:numId="42"><w:abstractNumId w:val="1"/></w:num>'
    )


def issue_codes(path: Path) -> list[str]:
    return [issue.code for issue in inspect_docx_file(path).issues]


def test_native_lists_resolve_definitions_overrides_and_notes() -> None:
    inspection = inspect_docx_file(FIXTURES / "docx" / "native-lists.docx")

    definition = inspection.numbering_definitions.abstract_definitions[0]
    assert definition.abstract_numbering_id == "10"
    assert [level.num_format for level in definition.levels] == ["decimal", "bullet", "lowerLetter"]
    assert [instance.numbering_id for instance in inspection.numbering_definitions.instances] == ["42", "43"]
    assert inspection.numbering_definitions.instances[1].level_overrides[0].start_override == 5

    assert inspection.paragraphs[1].numbering is not None
    assert inspection.paragraphs[1].numbering.list_kind == "ordered"
    assert inspection.paragraphs[2].numbering is not None
    assert inspection.paragraphs[2].numbering.list_kind == "bulleted"
    assert inspection.paragraphs[6].numbering is not None
    assert inspection.paragraphs[6].numbering.start == 5
    assert inspection.paragraphs[7].numbering is not None
    assert inspection.paragraphs[7].numbering.num_format == "lowerLetter"
    assert inspection.footnotes[0].paragraphs[0].numbering is not None
    assert inspection.endnotes[0].paragraphs[0].numbering is not None


def test_numid_zero_is_explicitly_removed_and_does_not_block_alone() -> None:
    inspection = inspect_docx_file(FIXTURES / "docx" / "native-lists.docx")
    removed = inspection.paragraphs[-1]
    assert removed.numbering_id == "0"
    assert removed.numbering is not None
    assert removed.numbering.status == "removed"


def test_lists_remain_conservatively_blocking_for_tei_conversion() -> None:
    metadata = load_metadata_file(
        FIXTURES / "metadata" / "native-tei-conversion.metadata.json"
    ).metadata
    assert metadata is not None
    result = convert_docx_to_tei(FIXTURES / "docx" / "native-lists.docx", metadata=metadata)
    assert result.xml_bytes is None
    diagnostics = [item for item in result.diagnostics if item.code == "numbered_paragraph_not_serializable"]
    assert diagnostics
    assert any("kind=ordered" in item.message for item in diagnostics)
    assert any("kind=bulleted" in item.message for item in diagnostics)


def test_numbering_defaults_are_applied_only_to_effective_resolution() -> None:
    path = runtime_docx("defaults.docx")
    numbering = numbering_xml(
        '<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"/></w:abstractNum>'
        '<w:num w:numId="42"><w:abstractNumId w:val="1"/></w:num>'
        '<w:num w:numId="43"><w:abstractNumId w:val="1"/>'
        '<w:lvlOverride w:ilvl="0"><w:lvl/></w:lvlOverride></w:num>'
    )
    write_docx(
        path,
        paragraph("Base", num_id="42", ilvl="0") + paragraph("Override", num_id="43", ilvl="0"),
        numbering=numbering,
    )

    inspection = inspect_docx_file(path)
    raw_level = inspection.numbering_definitions.abstract_definitions[0].levels[0]
    assert raw_level.num_format is None
    assert raw_level.start is None
    assert raw_level.suffix is None
    for item in inspection.paragraphs:
        assert item.numbering is not None
        assert item.numbering.status == "resolved"
        assert item.numbering.num_format == "decimal"
        assert item.numbering.start == 0
        assert item.numbering.suffix == "tab"
        assert item.numbering.list_kind == "ordered"
    assert "unsupported_numbering_format" not in [issue.code for issue in inspection.issues]


def test_invalid_paragraph_numbering_values_are_not_treated_as_absent() -> None:
    invalid_num = runtime_docx("invalid-num.docx")
    write_docx(invalid_num, paragraph("Bad", num_id="abc", ilvl="0"), numbering=basic_numbering())
    inspection = inspect_docx_file(invalid_num)
    codes = [issue.code for issue in inspection.issues]
    assert "invalid_numbering_identifier" in codes
    assert "missing_numbering_instance" not in codes
    assert inspection.paragraphs[0].numbering is not None
    assert inspection.paragraphs[0].numbering.status == "unresolved"

    invalid_level = runtime_docx("invalid-level.docx")
    write_docx(invalid_level, paragraph("Bad", num_id="42", ilvl="abc"), numbering=basic_numbering())
    inspection = inspect_docx_file(invalid_level)
    codes = [issue.code for issue in inspection.issues]
    assert "invalid_numbering_level" in codes
    assert "missing_numbering_level_assumed_zero" not in codes
    assert inspection.paragraphs[0].numbering is not None
    assert inspection.paragraphs[0].numbering.status == "unresolved"

    too_deep = runtime_docx("too-deep.docx")
    write_docx(too_deep, paragraph("Deep", num_id="42", ilvl="9"), numbering=basic_numbering())
    inspection = inspect_docx_file(too_deep)
    assert "invalid_numbering_level" in [issue.code for issue in inspection.issues]
    assert inspection.paragraphs[0].numbering is not None
    assert inspection.paragraphs[0].numbering.status == "unresolved"


def test_invalid_level_properties_make_resolution_unresolved() -> None:
    invalid_start = runtime_docx("invalid-start.docx")
    write_docx(
        invalid_start,
        paragraph("Start", num_id="42", ilvl="0"),
        numbering=basic_numbering('<w:start w:val="abc"/><w:numFmt w:val="decimal"/>'),
    )
    inspection = inspect_docx_file(invalid_start)
    assert "invalid_numbering_level" in [issue.code for issue in inspection.issues]
    assert inspection.paragraphs[0].numbering is not None
    assert inspection.paragraphs[0].numbering.status == "unresolved"
    assert inspection.paragraphs[0].numbering.start is None
    assert inspection.paragraphs[0].numbering.restart_after_level is None

    invalid_override = runtime_docx("invalid-override.docx")
    numbering = numbering_xml(
        '<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"><w:numFmt w:val="decimal"/></w:lvl></w:abstractNum>'
        '<w:num w:numId="42"><w:abstractNumId w:val="1"/>'
        '<w:lvlOverride w:ilvl="0"><w:startOverride w:val="abc"/></w:lvlOverride></w:num>'
    )
    write_docx(invalid_override, paragraph("Override", num_id="42", ilvl="0"), numbering=numbering)
    inspection = inspect_docx_file(invalid_override)
    assert "invalid_numbering_level" in [issue.code for issue in inspection.issues]
    assert inspection.paragraphs[0].numbering is not None
    assert inspection.paragraphs[0].numbering.status == "unresolved"
    assert inspection.paragraphs[0].numbering.start is None


def test_missing_required_numbering_identifiers_are_diagnosed_without_partial_definitions() -> None:
    missing_abstract_id = runtime_docx("missing-abstract-id.docx")
    write_docx(
        missing_abstract_id,
        paragraph("Bad", num_id="42", ilvl="0"),
        numbering=numbering_xml(
            '<w:abstractNum><w:lvl w:ilvl="0"/></w:abstractNum>'
            '<w:num w:numId="42"><w:abstractNumId w:val="1"/></w:num>'
        ),
    )
    inspection = inspect_docx_file(missing_abstract_id)
    assert "invalid_numbering_identifier" in [issue.code for issue in inspection.issues]
    assert inspection.numbering_definitions.abstract_definitions == ()
    assert inspection.paragraphs[0].numbering is not None
    assert inspection.paragraphs[0].numbering.status == "unresolved"

    missing_num_id = runtime_docx("missing-num-id.docx")
    write_docx(
        missing_num_id,
        paragraph("Bad", num_id="42", ilvl="0"),
        numbering=numbering_xml(
            '<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"/></w:abstractNum>'
            '<w:num><w:abstractNumId w:val="1"/></w:num>'
        ),
    )
    inspection = inspect_docx_file(missing_num_id)
    assert "invalid_numbering_identifier" in [issue.code for issue in inspection.issues]
    assert inspection.numbering_definitions.instances == ()


def test_incomplete_direct_numpr_values_are_not_ignored_or_replaced_by_style() -> None:
    styles = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Active"><w:pPr><w:numPr><w:numId w:val="42"/></w:numPr></w:pPr></w:style>
</w:styles>
"""
    missing_value = runtime_docx("direct-numid-without-value.docx")
    body = (
        '<w:p><w:pPr><w:pStyle w:val="Active"/><w:numPr><w:numId/></w:numPr></w:pPr>'
        '<w:r><w:t>Direct incomplet</w:t></w:r></w:p>'
    )
    write_docx(missing_value, body, styles=styles, numbering=basic_numbering())
    inspection = inspect_docx_file(missing_value)
    assert "invalid_numbering_identifier" in [issue.code for issue in inspection.issues]
    assert "style_based_numbering_not_resolved" not in [issue.code for issue in inspection.issues]
    assert inspection.paragraphs[0].numbering is not None
    assert inspection.paragraphs[0].numbering.origin == "direct"
    assert inspection.paragraphs[0].numbering.status == "unresolved"

    missing_level_value = runtime_docx("direct-ilvl-without-value.docx")
    body = (
        '<w:p><w:pPr><w:numPr><w:ilvl/><w:numId w:val="42"/></w:numPr></w:pPr>'
        '<w:r><w:t>Niveau incomplet</w:t></w:r></w:p>'
    )
    write_docx(missing_level_value, body, numbering=basic_numbering())
    inspection = inspect_docx_file(missing_level_value)
    codes = [issue.code for issue in inspection.issues]
    assert "invalid_numbering_level" in codes
    assert "missing_numbering_level_assumed_zero" not in codes
    assert inspection.paragraphs[0].numbering is not None
    assert inspection.paragraphs[0].numbering.status == "unresolved"


def test_incomplete_abstract_reference_child_is_invalid_not_missing() -> None:
    incomplete_reference = runtime_docx("abstract-reference-without-value.docx")
    write_docx(
        incomplete_reference,
        paragraph("Bad", num_id="42", ilvl="0"),
        numbering=numbering_xml(
            '<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"/></w:abstractNum>'
            '<w:num w:numId="42"><w:abstractNumId/></w:num>'
        ),
    )
    inspection = inspect_docx_file(incomplete_reference)
    codes = [issue.code for issue in inspection.issues]
    assert "invalid_numbering_identifier" in codes
    assert inspection.paragraphs[0].numbering is not None
    assert inspection.paragraphs[0].numbering.status == "unresolved"

    absent_reference = runtime_docx("abstract-reference-absent.docx")
    write_docx(
        absent_reference,
        paragraph("Bad", num_id="42", ilvl="0"),
        numbering=numbering_xml(
            '<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"/></w:abstractNum>'
            '<w:num w:numId="42"/>'
        ),
    )
    assert "missing_abstract_numbering_definition" in issue_codes(absent_reference)


def test_incomplete_numbering_level_properties_are_not_defaulted() -> None:
    path = runtime_docx("incomplete-level-properties.docx")
    write_docx(
        path,
        paragraph("Bad", num_id="42", ilvl="0"),
        numbering=basic_numbering("<w:numFmt/><w:suff/><w:start/><w:lvlRestart/>"),
    )
    inspection = inspect_docx_file(path)
    codes = [issue.code for issue in inspection.issues]
    assert "invalid_numbering_property" in codes
    assert "invalid_numbering_level" in codes
    assert "unsupported_numbering_format" not in codes
    assert inspection.paragraphs[0].numbering is not None
    assert inspection.paragraphs[0].numbering.status == "unresolved"
    assert inspection.paragraphs[0].numbering.num_format is None
    assert inspection.paragraphs[0].numbering.suffix is None
    assert inspection.paragraphs[0].numbering.start is None
    assert inspection.paragraphs[0].numbering.restart_after_level is None

    override = runtime_docx("incomplete-start-override.docx")
    write_docx(
        override,
        paragraph("Bad", num_id="42", ilvl="0"),
        numbering=numbering_xml(
            '<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"/></w:abstractNum>'
            '<w:num w:numId="42"><w:abstractNumId w:val="1"/>'
            '<w:lvlOverride w:ilvl="0"><w:startOverride/></w:lvlOverride></w:num>'
        ),
    )
    inspection = inspect_docx_file(override)
    assert "invalid_numbering_level" in [issue.code for issue in inspection.issues]
    assert inspection.paragraphs[0].numbering is not None
    assert inspection.paragraphs[0].numbering.status == "unresolved"
    assert inspection.paragraphs[0].numbering.start is None

    override_with_abstract_start = runtime_docx("incomplete-start-override-no-fallback.docx")
    write_docx(
        override_with_abstract_start,
        paragraph("Bad", num_id="42", ilvl="0"),
        numbering=numbering_xml(
            '<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0">'
            '<w:start w:val="3"/></w:lvl></w:abstractNum>'
            '<w:num w:numId="42"><w:abstractNumId w:val="1"/>'
            '<w:lvlOverride w:ilvl="0"><w:startOverride/></w:lvlOverride></w:num>'
        ),
    )
    inspection = inspect_docx_file(override_with_abstract_start)
    assert "invalid_numbering_level" in [issue.code for issue in inspection.issues]
    assert inspection.paragraphs[0].numbering is not None
    assert inspection.paragraphs[0].numbering.status == "unresolved"
    assert inspection.paragraphs[0].numbering.start is None


def test_numbering_definition_identifiers_are_canonicalized_for_duplicates() -> None:
    path = runtime_docx("duplicates.docx")
    numbering = numbering_xml(
        '<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"><w:numFmt w:val="decimal"/></w:lvl></w:abstractNum>'
        '<w:abstractNum w:abstractNumId="01"><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/></w:lvl></w:abstractNum>'
        '<w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>'
        '<w:num w:numId="02"><w:abstractNumId w:val="1"/></w:num>'
    )
    write_docx(path, paragraph("Ambiguous", num_id="2", ilvl="0"), numbering=numbering)
    codes = issue_codes(path)
    assert "duplicate_abstract_numbering_id" in codes
    assert "duplicate_numbering_instance_id" in codes


def test_missing_definitions_and_assumed_zero_are_diagnosed_distinctly() -> None:
    path = runtime_docx("missing-definitions.docx")
    numbering = numbering_xml(
        '<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"><w:numFmt w:val="decimal"/></w:lvl></w:abstractNum>'
        '<w:num w:numId="42"><w:abstractNumId w:val="1"/></w:num>'
        '<w:num w:numId="43"><w:abstractNumId w:val="99"/></w:num>'
    )
    body = (
        paragraph("Missing instance", num_id="99", ilvl="0")
        + paragraph("Missing abstract", num_id="43", ilvl="0")
        + paragraph("Missing level", num_id="42", ilvl="2")
        + paragraph("Assume zero", num_id="42")
    )
    write_docx(path, body, numbering=numbering)

    inspection = inspect_docx_file(path)
    codes = [issue.code for issue in inspection.issues]
    assert "missing_numbering_instance" in codes
    assert "missing_abstract_numbering_definition" in codes
    assert "missing_numbering_level_definition" in codes
    assert "missing_numbering_level_assumed_zero" in codes
    assert inspection.paragraphs[3].numbering is not None
    assert inspection.paragraphs[3].numbering.status == "resolved"


def test_supported_formats_none_unknown_and_picture_bullets() -> None:
    formats = [
        ("decimal", "ordered"),
        ("lowerLetter", "ordered"),
        ("upperLetter", "ordered"),
        ("lowerRoman", "ordered"),
        ("upperRoman", "ordered"),
        ("bullet", "bulleted"),
        ("none", "none"),
    ]
    levels = "".join(
        f'<w:lvl w:ilvl="{index}"><w:numFmt w:val="{fmt}"/></w:lvl>'
        for index, (fmt, _kind) in enumerate(formats)
    )
    numbering = numbering_xml(
        f'<w:abstractNum w:abstractNumId="1">{levels}'
        '<w:lvl w:ilvl="7"><w:numFmt w:val="custom"/></w:lvl>'
        '<w:lvl w:ilvl="8"><w:numFmt w:val="bullet"/><w:lvlPicBulletId w:val="4"/></w:lvl>'
        '</w:abstractNum><w:num w:numId="42"><w:abstractNumId w:val="1"/></w:num>'
        '<w:numPicBullet w:numPicBulletId="4"/>'
    )
    body = "".join(paragraph(fmt, num_id="42", ilvl=str(index)) for index, (fmt, _kind) in enumerate(formats))
    body += paragraph("Unknown", num_id="42", ilvl="7")
    body += paragraph("Picture", num_id="42", ilvl="8")
    path = runtime_docx("formats.docx")
    write_docx(path, body, numbering=numbering)

    inspection = inspect_docx_file(path)
    assert [paragraph.numbering.list_kind for paragraph in inspection.paragraphs[:7] if paragraph.numbering] == [
        kind for _fmt, kind in formats
    ]
    assert inspection.paragraphs[7].numbering is not None
    assert inspection.paragraphs[7].numbering.status == "unsupported"
    assert inspection.paragraphs[8].numbering is not None
    assert inspection.paragraphs[8].numbering.status == "unsupported"
    codes = [issue.code for issue in inspection.issues]
    assert "unsupported_numbering_format" in codes
    assert "picture_bullet_not_supported" in codes


def test_style_numbering_removed_active_inherited_and_cycles() -> None:
    styles = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Active"><w:pPr><w:numPr><w:numId w:val="42"/></w:numPr></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Inherited"><w:basedOn w:val="Active"/></w:style>
  <w:style w:type="paragraph" w:styleId="Parent"><w:pPr><w:numPr><w:numId w:val="42"/></w:numPr></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="ChildRemoved"><w:basedOn w:val="Parent"/><w:pPr><w:numPr><w:numId w:val="0"/></w:numPr></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="CycleA"><w:basedOn w:val="CycleB"/></w:style>
  <w:style w:type="paragraph" w:styleId="CycleB"><w:basedOn w:val="CycleA"/></w:style>
</w:styles>
"""
    body = (
        paragraph("Active", style="Active")
        + paragraph("Inherited", style="Inherited")
        + paragraph("Removed", style="ChildRemoved")
        + paragraph("Cycle", style="CycleA")
    )
    path = runtime_docx("style-numbering.docx")
    write_docx(path, body, styles=styles, numbering=basic_numbering())

    inspection = inspect_docx_file(path)
    assert inspection.paragraphs[0].numbering is not None
    assert inspection.paragraphs[0].numbering.status == "unresolved"
    assert inspection.paragraphs[0].numbering.origin == "style"
    assert inspection.paragraphs[1].numbering is not None
    assert inspection.paragraphs[1].numbering.status == "unresolved"
    assert inspection.paragraphs[2].numbering is not None
    assert inspection.paragraphs[2].numbering.status == "removed"
    assert inspection.paragraphs[2].numbering.origin == "style"
    codes = [issue.code for issue in inspection.issues]
    assert "style_based_numbering_not_resolved" in codes
    assert "cyclic_style_inheritance" in codes


def test_list_paragraph_without_numbering_is_contextualized_in_all_parts() -> None:
    path = runtime_docx("list-paragraph-context.docx")
    footnotes = """<?xml version="1.0" encoding="UTF-8"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:footnote w:id="1"><w:p><w:pPr><w:pStyle w:val="ListParagraph"/></w:pPr><w:r><w:t>Note</w:t></w:r></w:p></w:footnote>
</w:footnotes>
"""
    endnotes = """<?xml version="1.0" encoding="UTF-8"?>
<w:endnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:endnote w:id="2"><w:p><w:pPr><w:pStyle w:val="ListParagraph"/></w:pPr><w:r><w:t>End</w:t></w:r></w:p></w:endnote>
</w:endnotes>
"""
    write_docx(
        path,
        paragraph("Body", style="ListParagraph"),
        numbering=basic_numbering(),
        footnotes=footnotes,
        endnotes=endnotes,
    )

    issues = [issue for issue in inspect_docx_file(path).issues if issue.code == "list_paragraph_without_numbering"]
    assert [(issue.part, issue.paragraph_index, issue.note_id) for issue in issues] == [
        ("word/document.xml", 0, None),
        ("word/footnotes.xml", 0, "1"),
        ("word/endnotes.xml", 0, "2"),
    ]


def test_missing_numbering_part_ignores_numid_zero() -> None:
    active = runtime_docx("missing-numbering-active.docx")
    write_docx(active, paragraph("Active", num_id="42", ilvl="0"), numbering=None)
    assert "missing_numbering_part" in issue_codes(active)

    removed = runtime_docx("missing-numbering-removed.docx")
    write_docx(removed, paragraph("Removed", num_id="0"), numbering=None)
    inspection = inspect_docx_file(removed)
    assert "missing_numbering_part" not in [issue.code for issue in inspection.issues]
    assert inspection.paragraphs[0].numbering is not None
    assert inspection.paragraphs[0].numbering.status == "removed"


def test_inspect_docx_counts_numbering_in_body_footnotes_and_endnotes(capsys) -> None:
    code = main(["inspect-docx", str(FIXTURES / "docx" / "native-lists.docx")])
    captured = capsys.readouterr()
    assert code == 0
    assert "Paragraphes num" in captured.out
    assert "8" in captured.out
    assert "Listes ordonn" in captured.out
    assert "5" in captured.out
    assert "Listes " in captured.out
    assert "3" in captured.out


def test_inspect_docx_numbering_json_is_deterministic_and_effective() -> None:
    path = FIXTURES / "docx" / "native-lists.docx"
    first = json.dumps(json.loads(_inspect_json(path)), sort_keys=True)
    second = json.dumps(json.loads(_inspect_json(path)), sort_keys=True)
    assert first == second
    data = json.loads(first)
    assert data["paragraphs"][-1]["numbering"]["status"] == "removed"
    assert data["footnotes"][0]["paragraphs"][0]["numbering"]["list_kind"] == "ordered"


def _inspect_json(path: Path) -> str:
    from mini_metopes.cli import _inspection_as_json

    return _inspection_as_json(inspect_docx_file(path))
