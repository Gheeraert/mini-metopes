"""Lecture structurée, sûre et non destructive des paquets DOCX."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from zipfile import BadZipFile, ZipFile, ZipInfo

from lxml import etree

from .model import (
    DocxInspection,
    DocxInspectionError,
    InspectionIssue,
    MediaInfo,
    NoteInfo,
    ParagraphInfo,
    RelationshipInfo,
    RunContentInfo,
    RunInfo,
    StyleInfo,
)
from .namespaces import CONTENT_TYPES, NS, PACKAGE_RELATIONSHIPS, r_tag, w_tag


DOCUMENT_PART = "word/document.xml"
STYLES_PART = "word/styles.xml"
NUMBERING_PART = "word/numbering.xml"
FOOTNOTES_PART = "word/footnotes.xml"
ENDNOTES_PART = "word/endnotes.xml"
RELATIONSHIPS_PART = "word/_rels/document.xml.rels"
FOOTNOTE_RELATIONSHIPS_PART = "word/_rels/footnotes.xml.rels"
ENDNOTE_RELATIONSHIPS_PART = "word/_rels/endnotes.xml.rels"
CONTENT_TYPES_PART = "[Content_Types].xml"
MAX_XML_PART_BYTES = 16 * 1024 * 1024
DRAWING_MARKER = "[drawing]"


def inspect_docx_file(
    path: Path,
    *,
    max_xml_part_bytes: int = MAX_XML_PART_BYTES,
) -> DocxInspection:
    """Inspecter un fichier DOCX sans extraire son archive sur le disque.

    Les propriétés de mise en forme sont celles déclarées directement sur les
    runs et les paragraphes. La cascade complète de styles Word n'est pas
    résolue dans cette couche.

    Raises:
        DocxInspectionError: si le fichier ne peut pas être lu comme DOCX ou
            si sa partie principale n'est pas exploitable.
    """
    if max_xml_part_bytes <= 0:
        raise ValueError("max_xml_part_bytes doit être strictement positif")
    source = Path(path)
    if not source.exists():
        raise DocxInspectionError("missing_file", f"fichier introuvable : {source}")
    if not source.is_file():
        raise DocxInspectionError("not_a_file", f"ce chemin n'est pas un fichier : {source}")

    try:
        archive = ZipFile(source)
    except BadZipFile as error:
        raise DocxInspectionError("not_zip", f"archive ZIP invalide : {source}") from error
    except OSError as error:
        raise DocxInspectionError("unreadable_file", f"fichier illisible : {source}") from error

    with archive:
        infos = _archive_infos(archive)
        parts = tuple(sorted(info.filename for info in infos if not info.is_dir()))
        available_parts = frozenset(parts)
        if DOCUMENT_PART not in parts:
            raise DocxInspectionError(
                "missing_document_part",
                "le paquet ne contient pas word/document.xml",
                part=DOCUMENT_PART,
            )

        document = _read_xml_part(archive, DOCUMENT_PART, max_xml_part_bytes)
        issues: list[InspectionIssue] = []
        styles_root = _read_optional_xml(archive, STYLES_PART, available_parts, max_xml_part_bytes, issues)
        numbering_root = _read_optional_xml(
            archive, NUMBERING_PART, available_parts, max_xml_part_bytes, issues
        )
        footnotes_root = _read_optional_xml(
            archive, FOOTNOTES_PART, available_parts, max_xml_part_bytes, issues
        )
        endnotes_root = _read_optional_xml(
            archive, ENDNOTES_PART, available_parts, max_xml_part_bytes, issues
        )
        relationships_root = _read_optional_xml(
            archive, RELATIONSHIPS_PART, available_parts, max_xml_part_bytes, issues
        )
        footnote_relationships_root = _read_optional_xml(
            archive, FOOTNOTE_RELATIONSHIPS_PART, available_parts, max_xml_part_bytes, issues
        )
        endnote_relationships_root = _read_optional_xml(
            archive, ENDNOTE_RELATIONSHIPS_PART, available_parts, max_xml_part_bytes, issues
        )
        content_types_root = _read_optional_xml(
            archive, CONTENT_TYPES_PART, available_parts, max_xml_part_bytes, issues
        )

        styles = _read_styles(styles_root)
        styles_by_id = {style.style_id: style for style in styles}
        paragraphs = _read_paragraphs(document, styles_by_id)
        footnotes = _read_notes(footnotes_root, "footnote", styles_by_id)
        endnotes = _read_notes(endnotes_root, "endnote", styles_by_id)
        relationships = _read_relationships(relationships_root)
        footnote_relationships = _read_relationships(footnote_relationships_root)
        endnote_relationships = _read_relationships(endnote_relationships_root)
        media = _read_media(infos, content_types_root)
        issues.extend(_document_observation_issues(document, parts))
        if numbering_root is None and any(paragraph.numbering_id for paragraph in paragraphs):
            issues.append(
                InspectionIssue(
                    code="missing_numbering_part",
                    message="des paragraphes référencent une numérotation sans word/numbering.xml",
                    severity="warning",
                    part=NUMBERING_PART,
                )
            )

    return DocxInspection(
        source=source,
        parts=parts,
        styles=styles,
        paragraphs=paragraphs,
        footnotes=footnotes,
        endnotes=endnotes,
        relationships=relationships,
        footnote_relationships=footnote_relationships,
        endnote_relationships=endnote_relationships,
        media=media,
        issues=tuple(issues),
    )


def _secure_xml_parser() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        recover=False,
        huge_tree=False,
        remove_blank_text=False,
    )


def _archive_infos(archive: ZipFile) -> tuple[ZipInfo, ...]:
    try:
        return tuple(archive.infolist())
    except (BadZipFile, OSError, RuntimeError, NotImplementedError) as error:
        raise DocxInspectionError(
            "unreadable_file",
            "l'index du paquet DOCX ne peut pas etre lu",
        ) from error


def _read_optional_xml(
    archive: ZipFile,
    part: str,
    available_parts: frozenset[str],
    maximum: int,
    issues: list[InspectionIssue],
) -> etree._Element | None:
    if part not in available_parts:
        return None
    try:
        return _read_xml_part(archive, part, maximum)
    except DocxInspectionError as error:
        issues.append(
            InspectionIssue(
                code=error.code,
                message=str(error),
                severity="warning",
                part=part,
            )
        )
        return None


def _read_xml_part(archive: ZipFile, part: str, maximum: int) -> etree._Element:
    try:
        info = archive.getinfo(part)
    except (KeyError, BadZipFile, OSError, RuntimeError, NotImplementedError) as error:
        raise DocxInspectionError("unreadable_part", f"partie illisible : {part}", part=part) from error
    if info.file_size > maximum:
        raise DocxInspectionError(
            "xml_part_too_large",
            f"partie XML trop volumineuse ({info.file_size} octets) : {part}",
            part=part,
        )
    try:
        data = archive.read(part)
    except (BadZipFile, OSError, RuntimeError, NotImplementedError) as error:
        raise DocxInspectionError("unreadable_part", f"partie illisible : {part}", part=part) from error
    try:
        return etree.fromstring(data, parser=_secure_xml_parser())
    except etree.XMLSyntaxError as error:
        raise DocxInspectionError(
            "malformed_xml_part",
            f"XML mal formé dans {part} (ligne {error.lineno})",
            part=part,
        ) from error


def _read_styles(root: etree._Element | None) -> tuple[StyleInfo, ...]:
    if root is None:
        return ()
    styles: list[StyleInfo] = []
    for element in root.xpath("./w:style", namespaces=NS):
        style_id = element.get(w_tag("styleId"))
        if style_id is None:
            continue
        styles.append(
            StyleInfo(
                style_id=style_id,
                name=_child_value(element, "name"),
                style_type=element.get(w_tag("type")),
                based_on=_child_value(element, "basedOn"),
                linked_style=_child_value(element, "link"),
                is_default=_xml_bool(element.get(w_tag("default"))) is True,
                is_custom=_xml_bool(element.get(w_tag("customStyle"))),
                outline_level=_integer_child_value(element, "./w:pPr/w:outlineLvl"),
                quick_format=_element_bool(element, "qFormat"),
                ui_priority=_integer_child_value(element, "./w:uiPriority"),
            )
        )
    return tuple(styles)


def _read_paragraphs(
    root: etree._Element,
    styles_by_id: dict[str, StyleInfo],
) -> tuple[ParagraphInfo, ...]:
    body = root.find(".//w:body", namespaces=NS)
    if body is None:
        return ()
    return _read_paragraphs_from_container(body, styles_by_id)


def _read_paragraphs_from_container(
    container: etree._Element,
    styles_by_id: dict[str, StyleInfo],
) -> tuple[ParagraphInfo, ...]:
    return tuple(
        _read_paragraph(element, index, styles_by_id)
        for index, element in enumerate(_paragraph_elements(container))
    )


def _read_paragraph(
    element: etree._Element,
    index: int,
    styles_by_id: dict[str, StyleInfo],
) -> ParagraphInfo:
    style_id = _child_value(element, "./w:pPr/w:pStyle")
    direct_outline = _integer_child_value(element, "./w:pPr/w:outlineLvl")
    style = styles_by_id.get(style_id) if style_id else None
    runs = tuple(_read_run(run) for run in _paragraph_runs(element))
    hyperlinks = _paragraph_descendants(element, w_tag("hyperlink"))
    bookmark_starts = _paragraph_descendants(element, w_tag("bookmarkStart"))
    return ParagraphInfo(
        index=index,
        text="".join(run.text for run in runs),
        style_id=style_id,
        style_name=style.name if style else None,
        outline_level=direct_outline if direct_outline is not None else (style.outline_level if style else None),
        numbering_id=_child_value(element, "./w:pPr/w:numPr/w:numId"),
        numbering_level=_integer_child_value(element, "./w:pPr/w:numPr/w:ilvl"),
        manual_breaks=sum(run.manual_breaks for run in runs),
        footnote_reference_ids=tuple(
            note_id for run in runs for note_id in run.footnote_reference_ids
        ),
        endnote_reference_ids=tuple(
            note_id for run in runs for note_id in run.endnote_reference_ids
        ),
        hyperlink_count=len(hyperlinks),
        hyperlink_relationship_ids=tuple(
            hyperlink.get(r_tag("id"), "")
            for hyperlink in hyperlinks
            if hyperlink.get(r_tag("id")) is not None
        ),
        bookmark_start_ids=tuple(
            bookmark.get(w_tag("id"), "")
            for bookmark in bookmark_starts
            if bookmark.get(w_tag("id")) is not None
        ),
        drawing_count=sum(run.drawing_count for run in runs),
        drawing_relationship_ids=tuple(
            relationship_id for run in runs for relationship_id in run.drawing_relationship_ids
        ),
        runs=runs,
    )


def _paragraph_elements(element: etree._Element) -> tuple[etree._Element, ...]:
    return tuple(
        paragraph
        for paragraph in element.xpath(".//w:p", namespaces=NS)
        if _nearest_paragraph_parent(paragraph) is None
    )


def _paragraph_runs(element: etree._Element) -> tuple[etree._Element, ...]:
    return tuple(
        run
        for run in element.xpath(".//w:r", namespaces=NS)
        if _nearest_paragraph_parent(run) is element
    )


def _paragraph_descendants(element: etree._Element, tag: str) -> tuple[etree._Element, ...]:
    return tuple(
        descendant
        for descendant in element.iter(tag)
        if _nearest_paragraph_parent(descendant) is element
    )


def _nearest_paragraph_parent(element: etree._Element) -> etree._Element | None:
    for ancestor in element.iterancestors(w_tag("p")):
        return ancestor
    return None


def _nearest_run_parent(element: etree._Element) -> etree._Element | None:
    for ancestor in element.iterancestors(w_tag("r")):
        return ancestor
    return None


def _read_run(element: etree._Element) -> RunInfo:
    contents = _read_run_contents(element)
    text, footnote_ids, endnote_ids, break_types, drawing_relationship_ids = _run_convenience_values(
        contents
    )
    hyperlink_relationship_id, hyperlink_anchor = _run_hyperlink_context(element)
    properties = element.find("w:rPr", namespaces=NS)
    vertical_alignment = _child_value(properties, "vertAlign") if properties is not None else None
    return RunInfo(
        text=text,
        style_id=_child_value(properties, "rStyle") if properties is not None else None,
        bold=_property_bool(properties, "b"),
        italic=_property_bool(properties, "i"),
        small_caps=_property_bool(properties, "smallCaps"),
        caps=_property_bool(properties, "caps"),
        superscript=vertical_alignment == "superscript",
        subscript=vertical_alignment == "subscript",
        manual_breaks=sum(kind == "line" for kind in break_types),
        tabs=sum(content.kind == "tab" for content in contents),
        footnote_reference_ids=footnote_ids,
        endnote_reference_ids=endnote_ids,
        break_types=break_types,
        drawing_count=sum(content.kind == "drawing" for content in contents),
        drawing_relationship_ids=drawing_relationship_ids,
        contents=contents,
        hyperlink_relationship_id=hyperlink_relationship_id,
        hyperlink_anchor=hyperlink_anchor,
    )


def _read_run_contents(element: etree._Element) -> tuple[RunContentInfo, ...]:
    contents: list[RunContentInfo] = []
    for child in element.iter():
        if child is not element and _nearest_run_parent(child) is not element:
            continue
        tag = child.tag
        if tag == w_tag("t"):
            contents.append(RunContentInfo(kind="text", text=child.text or ""))
        elif tag == w_tag("tab"):
            contents.append(RunContentInfo(kind="tab"))
        elif tag == w_tag("br"):
            kind = child.get(w_tag("type"), "textWrapping")
            kind = "line" if kind == "textWrapping" else kind
            contents.append(RunContentInfo(kind="break", break_type=kind))
        elif tag == w_tag("cr"):
            contents.append(RunContentInfo(kind="break", break_type="line"))
        elif tag == w_tag("footnoteReference"):
            note_id = child.get(w_tag("id"))
            if note_id is not None:
                contents.append(RunContentInfo(kind="footnote_reference", reference_id=note_id))
        elif tag == w_tag("endnoteReference"):
            note_id = child.get(w_tag("id"))
            if note_id is not None:
                contents.append(RunContentInfo(kind="endnote_reference", reference_id=note_id))
        elif tag == w_tag("drawing"):
            relationship_ids = tuple(
                embedded.get(r_tag("embed"), "")
                for embedded in child.xpath(".//*[@r:embed]", namespaces=NS)
                if embedded.get(r_tag("embed")) is not None
            )
            contents.append(RunContentInfo(kind="drawing", relationship_ids=relationship_ids))

    return tuple(contents)


def _run_convenience_values(
    contents: tuple[RunContentInfo, ...],
) -> tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Construire les vues textuelles et compteurs depuis le flux inline."""
    text: list[str] = []
    footnote_ids: list[str] = []
    endnote_ids: list[str] = []
    break_types: list[str] = []
    drawing_relationship_ids: list[str] = []
    for content in contents:
        if content.kind == "text":
            text.append(content.text or "")
        elif content.kind == "tab":
            text.append("\t")
        elif content.kind == "break":
            break_type = content.break_type or "line"
            break_types.append(break_type)
            if break_type == "line":
                text.append("\n")
        elif content.kind == "footnote_reference" and content.reference_id is not None:
            footnote_ids.append(content.reference_id)
            text.append(f"[footnote:{content.reference_id}]")
        elif content.kind == "endnote_reference" and content.reference_id is not None:
            endnote_ids.append(content.reference_id)
            text.append(f"[endnote:{content.reference_id}]")
        elif content.kind == "drawing":
            text.append(DRAWING_MARKER)
            drawing_relationship_ids.extend(content.relationship_ids)

    return (
        "".join(text),
        tuple(footnote_ids),
        tuple(endnote_ids),
        tuple(break_types),
        tuple(drawing_relationship_ids),
    )


def _run_hyperlink_context(element: etree._Element) -> tuple[str | None, str | None]:
    for hyperlink in element.iterancestors(w_tag("hyperlink")):
        return hyperlink.get(r_tag("id")), hyperlink.get(w_tag("anchor"))
    return None, None


def _read_notes(
    root: etree._Element | None,
    kind: str,
    styles_by_id: dict[str, StyleInfo],
) -> tuple[NoteInfo, ...]:
    if root is None:
        return ()
    notes: list[NoteInfo] = []
    note_tag = w_tag(kind)
    for note in root.findall(note_tag):
        note_type = note.get(w_tag("type"))
        if note_type in {"separator", "continuationSeparator", "continuationNotice"}:
            continue
        note_id = note.get(w_tag("id"))
        if note_id is None:
            continue
        paragraphs = _read_paragraphs_from_container(note, styles_by_id)
        notes.append(
            NoteInfo(
                note_id=note_id,
                kind=kind,
                text="\n".join(paragraph.text for paragraph in paragraphs),
                paragraphs=paragraphs,
                note_type=note_type,
            )
        )
    return tuple(notes)


def _read_relationships(root: etree._Element | None) -> tuple[RelationshipInfo, ...]:
    if root is None:
        return ()
    relationships: list[RelationshipInfo] = []
    relationship_tag = f"{{{PACKAGE_RELATIONSHIPS}}}Relationship"
    for relation in root.findall(relationship_tag):
        relation_id = relation.get("Id")
        relation_type = relation.get("Type")
        target = relation.get("Target")
        if relation_id is None or relation_type is None or target is None:
            continue
        relationships.append(
            RelationshipInfo(
                relationship_id=relation_id,
                relationship_type=relation_type,
                target=target,
                target_mode=relation.get("TargetMode"),
            )
        )
    return tuple(relationships)


def _read_media(
    infos: Iterable[ZipInfo],
    content_types_root: etree._Element | None,
) -> tuple[MediaInfo, ...]:
    content_types = _content_types(content_types_root)
    media: list[MediaInfo] = []
    for info in sorted(infos, key=lambda item: item.filename):
        if info.is_dir() or not info.filename.startswith("word/media/"):
            continue
        media.append(
            MediaInfo(
                path=info.filename,
                compressed_size=info.compress_size,
                uncompressed_size=info.file_size,
                content_type=content_types.get(info.filename)
                or content_types.get(Path(info.filename).suffix.lower()),
            )
        )
    return tuple(media)


def _content_types(root: etree._Element | None) -> dict[str, str]:
    if root is None:
        return {}
    result: dict[str, str] = {}
    default_tag = f"{{{CONTENT_TYPES}}}Default"
    override_tag = f"{{{CONTENT_TYPES}}}Override"
    for default in root.findall(default_tag):
        extension = default.get("Extension")
        content_type = default.get("ContentType")
        if extension and content_type:
            result[f".{extension.lower()}"] = content_type
    for override in root.findall(override_tag):
        part_name = override.get("PartName")
        content_type = override.get("ContentType")
        if part_name and content_type:
            result[part_name.lstrip("/")] = content_type
    return result


def _document_observation_issues(root: etree._Element, parts: tuple[str, ...]) -> list[InspectionIssue]:
    issues: list[InspectionIssue] = []
    if root.xpath(".//w:txbxContent", namespaces=NS):
        issues.append(
            InspectionIssue(
                code="textboxes_not_inspected",
                message=(
                    "des zones de texte Word sont presentes ; leur contenu n'est pas "
                    "encore integre a la sequence principale"
                ),
                severity="info",
                part=DOCUMENT_PART,
            )
        )
    if root.xpath(".//w:tbl", namespaces=NS):
        issues.append(
            InspectionIssue(
                code="table_not_modeled",
                message="des tableaux sont présents ; leur structure n'est pas encore modélisée",
                severity="info",
                part=DOCUMENT_PART,
            )
        )
    if "word/comments.xml" in parts:
        issues.append(
            InspectionIssue(
                code="comments_not_inspected",
                message="des commentaires Word sont présents mais ne sont pas encore inspectés",
                severity="info",
                part="word/comments.xml",
            )
        )
    if any(part.startswith("word/header") or part.startswith("word/footer") for part in parts):
        issues.append(
            InspectionIssue(
                code="headers_footers_not_inspected",
                message="des en-têtes ou pieds de page sont présents mais ne sont pas encore inspectés",
                severity="info",
            )
        )
    return issues


def _child_value(element: etree._Element | None, path: str) -> str | None:
    if element is None:
        return None
    qualified_path = path if path.startswith(".") else f"w:{path}"
    child = element.find(qualified_path, namespaces=NS)
    return child.get(w_tag("val")) if child is not None else None


def _integer_child_value(element: etree._Element | None, path: str) -> int | None:
    value = _child_value(element, path)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _property_bool(element: etree._Element | None, name: str) -> bool | None:
    if element is None:
        return None
    child = element.find(f"w:{name}", namespaces=NS)
    if child is None:
        return None
    value = child.get(w_tag("val"))
    return True if value is None else _xml_bool(value)


def _element_bool(element: etree._Element | None, name: str) -> bool | None:
    if element is None:
        return None
    child = element.find(f"w:{name}", namespaces=NS)
    if child is None:
        return None
    value = child.get(w_tag("val"))
    return True if value is None else _xml_bool(value)


def _xml_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.lower() not in {"0", "false", "off"}
