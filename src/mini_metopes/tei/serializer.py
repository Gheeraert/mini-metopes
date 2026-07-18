"""Serialisation deterministe du modele editorial vers la TEI Commons Publishing."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import os
import tempfile

from lxml import etree

from mini_metopes.editorial import (
    ColumnBreak,
    DrawingReference,
    EditorialBlock,
    EditorialDocument,
    EditorialFigure,
    EditorialGraphic,
    EditorialInline,
    EditorialList,
    EditorialListItem,
    EditorialLink,
    EditorialNote,
    EditorialTable,
    EditorialTableCell,
    EditorialTableRow,
    Heading,
    LineBreak,
    NoteReference,
    PageBreak,
    Paragraph,
    ProseQuote,
    Tab,
    TextSpan,
    VerseQuote,
)
from mini_metopes.validation import validate_xml_tree
from mini_metopes.metadata import DocumentMetadata, normalize_orcid

from .model import TeiAsset, TeiConversionDiagnostic, TeiConversionResult, TeiWriteResult


TEI_NS = "http://www.tei-c.org/ns/1.0"
_NSMAP = {None: TEI_NS}
_REND_VALUES = {
    "bold": "bold",
    "italic": "italic",
    "small_caps": "small-caps",
    "caps": "uppercase",
    "superscript": "sup",
    "subscript": "sub",
}


def _tag(name: str) -> str:
    return f"{{{TEI_NS}}}{name}"


@dataclass
class _SerializationState:
    document: EditorialDocument
    diagnostics: list[TeiConversionDiagnostic]
    notes: dict[tuple[str, str], EditorialNote]
    active_notes: set[tuple[str, str]]
    referenced_notes: set[tuple[str, str]]

    def error(
        self,
        code: str,
        message: str,
        *,
        source_paragraph_index: int | None = None,
        note_id: str | None = None,
    ) -> None:
        self.diagnostics.append(
            TeiConversionDiagnostic(
                code=code,
                severity="error",
                message=message,
                source_paragraph_index=source_paragraph_index,
                note_id=note_id,
            )
        )


def serialize_editorial_document_to_tei(
    document: EditorialDocument,
    *,
    metadata: DocumentMetadata | None = None,
    initial_diagnostics: tuple[TeiConversionDiagnostic, ...] = (),
) -> TeiConversionResult:
    """Serialiser un modele editorial et valider le resultat contre le RNG embarque."""
    diagnostics: list[TeiConversionDiagnostic] = list(initial_diagnostics)
    notes: dict[tuple[str, str], EditorialNote] = {}
    for note in document.notes:
        key = (note.note_kind, note.note_id)
        if key in notes:
            diagnostics.append(
                TeiConversionDiagnostic(
                    code="duplicate_note_target_not_serializable",
                    severity="error",
                    message=f"cible de note dupliquee : {note.note_kind}:{note.note_id}",
                    note_id=note.note_id,
                )
            )
        else:
            notes[key] = note
    state = _SerializationState(document, diagnostics, notes, set(), set())
    root = etree.Element(_tag("TEI"), nsmap=_NSMAP)
    _append_header(root, document.source_name, metadata, state)
    body = etree.SubElement(etree.SubElement(root, _tag("text")), _tag("body"))
    _append_body_blocks(body, document.blocks, state)
    _diagnose_unreferenced_notes(state)
    if _has_errors(state):
        return TeiConversionResult(None, tuple(state.diagnostics), ())

    tree = etree.ElementTree(root)
    validation = validate_xml_tree(tree)
    if not validation.valid:
        state.error("tei_validation_failed", "la TEI produite ne satisfait pas le RNG Commons Publishing")
        return TeiConversionResult(None, tuple(state.diagnostics), validation.issues)
    xml_bytes = etree.tostring(tree, encoding="UTF-8", xml_declaration=True, pretty_print=True) + b"\n"
    return TeiConversionResult(xml_bytes, tuple(state.diagnostics), ())


def write_tei_conversion_result(result: TeiConversionResult, output_path: Path) -> TeiWriteResult:
    """Ecrire atomiquement une conversion valide sans ecraser de cible en cas d'echec."""
    if not result.is_successful or result.xml_bytes is None:
        raise ValueError("une conversion TEI invalide ne peut pas etre ecrite")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    written, reused = _write_assets(result.assets, output_path)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=output_path.parent, prefix=f".{output_path.name}.", delete=False
        ) as temporary:
            temporary.write(result.xml_bytes)
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, output_path)
    except OSError:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    return TeiWriteResult(
        media_written=written,
        media_reused=reused,
        media_directory=str(output_path.parent / "media") if result.assets else None,
    )


def _write_assets(assets: tuple[TeiAsset, ...], output_path: Path) -> tuple[int, int]:
    if not assets:
        return 0, 0
    preflight = _preflight_assets(assets, output_path)
    media_directory = output_path.parent / "media"
    media_directory.mkdir(parents=True, exist_ok=True)
    written = 0
    reused = 0
    for asset, destination, exists in preflight:
        if exists:
            reused += 1
            continue
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=destination.parent, prefix=f".{destination.name}.", delete=False
            ) as temporary:
                temporary.write(asset.data)
                temporary_path = Path(temporary.name)
            if _file_sha256(temporary_path) != asset.sha256:
                raise ValueError(f"image_media_changed_during_conversion: {asset.relative_path}")
            os.replace(temporary_path, destination)
            written += 1
        except (OSError, ValueError):
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise
    return written, reused


def _preflight_assets(assets: tuple[TeiAsset, ...], output_path: Path) -> tuple[tuple[TeiAsset, Path, bool], ...]:
    seen: dict[str, TeiAsset] = {}
    planned: list[tuple[TeiAsset, Path, bool]] = []
    for asset in assets:
        previous = seen.get(asset.relative_path)
        if previous is not None and (
            previous.sha256 != asset.sha256
            or previous.content_type != asset.content_type
            or previous.data != asset.data
        ):
            raise ValueError(f"duplicate_figure_asset_conflict: {asset.relative_path}")
        if previous is not None:
            continue
        relative = _validate_asset(asset)
        destination = output_path.parent / relative
        exists = destination.exists()
        if exists and _file_sha256(destination) != asset.sha256:
            raise ValueError(f"existing_media_hash_mismatch: {asset.relative_path}")
        seen[asset.relative_path] = asset
        planned.append((asset, destination, exists))
    return tuple(planned)


def _validate_asset(asset: TeiAsset) -> Path:
    relative = _safe_asset_path(asset.relative_path)
    if len(asset.sha256) != 64 or any(character not in "0123456789abcdef" for character in asset.sha256):
        raise ValueError(f"invalid_figure_sha256: {asset.relative_path}")
    actual_sha256 = hashlib.sha256(asset.data).hexdigest()
    if actual_sha256 != asset.sha256:
        raise ValueError(f"invalid_figure_sha256: {asset.relative_path}")
    if asset.content_type not in {"image/png", "image/jpeg"}:
        raise ValueError(f"unsupported_figure_media_type: {asset.relative_path}")
    detected = _detect_asset_content_type(asset.data)
    if detected != asset.content_type:
        raise ValueError(f"image_content_type_mismatch: {asset.relative_path}")
    suffix = ".png" if asset.content_type == "image/png" else ".jpg"
    expected = f"media/{asset.sha256}{suffix}"
    if asset.relative_path != expected:
        raise ValueError(f"invalid_figure_media_url: {asset.relative_path}")
    return relative


def _safe_asset_path(relative_path: str) -> Path:
    path = Path(relative_path)
    if (
        not relative_path
        or "\\" in relative_path
        or path.is_absolute()
        or ".." in path.parts
        or Path(path.parts[0] if path.parts else "") != Path("media")
    ):
        raise ValueError(f"invalid_figure_media_url: {relative_path}")
    return path


def _detect_asset_content_type(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _append_header(root: etree._Element, source_name: str, metadata: DocumentMetadata | None, state: _SerializationState) -> None:
    header = etree.SubElement(root, _tag("teiHeader"))
    file_desc = etree.SubElement(header, _tag("fileDesc"))
    title_stmt = etree.SubElement(file_desc, _tag("titleStmt"))
    if metadata is None:
        etree.SubElement(title_stmt, _tag("title")).text = source_name
    else:
        etree.SubElement(title_stmt, _tag("title"), type="main").text = metadata.title
        if metadata.subtitle:
            etree.SubElement(title_stmt, _tag("title"), type="sub").text = metadata.subtitle
        used_affiliations: set[str] = set()
        reported_ror_affiliations: set[str] = set()
        affiliation_indexes = {item.affiliation_id: index for index, item in enumerate(metadata.affiliations)}
        affiliations = {item.affiliation_id: item for item in metadata.affiliations}
        for contributor_index, contributor in enumerate(metadata.contributors):
            element_name = "author" if contributor.role == "author" else "editor"
            person = etree.SubElement(title_stmt, _tag(element_name))
            if contributor.role not in {"author", "editor"}:
                state.diagnostics.append(TeiConversionDiagnostic(
                    code="contributor_role_serialized_as_editor", severity="warning",
                    message=f"role {contributor.role} serialise comme editor, le profil n'admet pas respStmt ici",
                    origin="metadata",
                    metadata_path=f"contributors[{contributor_index}].role",
                ))
            if contributor.literal_name:
                etree.SubElement(person, _tag("persName")).text = contributor.literal_name
            else:
                name = etree.SubElement(person, _tag("persName"))
                if contributor.given_name:
                    etree.SubElement(name, _tag("forename")).text = contributor.given_name
                if contributor.family_name:
                    etree.SubElement(name, _tag("surname")).text = contributor.family_name
            if contributor.orcid:
                normalized = normalize_orcid(contributor.orcid)
                if normalized:
                    etree.SubElement(person, _tag("idno"), type="ORCID").text = normalized
            for affiliation_id in contributor.affiliation_ids:
                used_affiliations.add(affiliation_id)
                affiliation = affiliations[affiliation_id]
                # Commons Publishing permits an affiliation inline here, but no
                # shared affiliation registry at this header level. Do not
                # duplicate an xml:id when several people share one institution.
                rendered = etree.SubElement(person, _tag("affiliation"))
                rendered.text = _affiliation_text(affiliation)
                if affiliation.ror and affiliation.affiliation_id not in reported_ror_affiliations:
                    reported_ror_affiliations.add(affiliation.affiliation_id)
                    state.diagnostics.append(
                        TeiConversionDiagnostic(
                            code="ror_not_serialized",
                            severity="warning",
                            message=f"ROR non serialise par le profil Commons Publishing : {affiliation.affiliation_id}",
                            origin="metadata",
                            metadata_path=f"affiliations[{affiliation_indexes[affiliation.affiliation_id]}].ror",
                        )
                    )
        for affiliation_index, affiliation in enumerate(metadata.affiliations):
            if affiliation.affiliation_id not in used_affiliations:
                state.diagnostics.append(TeiConversionDiagnostic(
                    code="unreferenced_affiliation_not_serialized", severity="warning",
                    message=f"affiliation non utilisee non serialisee : {affiliation.affiliation_id}",
                    origin="metadata",
                    metadata_path=f"affiliations[{affiliation_index}].id",
                ))
    publication = etree.SubElement(file_desc, _tag("publicationStmt"))
    etree.SubElement(publication, _tag("p")).text = "Document généré par Mini-Métopes."
    source_desc = etree.SubElement(file_desc, _tag("sourceDesc"))
    etree.SubElement(source_desc, _tag("p")).text = f"Conversion du fichier DOCX {source_name}."
    if metadata is not None:
        profile = etree.SubElement(header, _tag("profileDesc"))
        lang_usage = etree.SubElement(profile, _tag("langUsage"))
        etree.SubElement(lang_usage, _tag("language"), ident=metadata.language).text = metadata.language
        if metadata.abstract:
            state.diagnostics.append(TeiConversionDiagnostic(
                code="abstract_not_serialized", severity="warning",
                message="le profil Commons Publishing embarque n'admet pas le resume dans profileDesc",
                origin="metadata",
                metadata_path="document.abstract",
            ))
        if metadata.keywords:
            keywords = etree.SubElement(etree.SubElement(profile, _tag("textClass")), _tag("keywords"))
            for keyword in metadata.keywords:
                etree.SubElement(keywords, _tag("term")).text = keyword


def _affiliation_text(affiliation: object) -> str:
    """Rendre une affiliation en texte, format le plus simple admis par le RNG."""
    from mini_metopes.metadata import Affiliation

    assert isinstance(affiliation, Affiliation)
    return ", ".join(part for part in (affiliation.name, affiliation.unit, affiliation.city, affiliation.country) if part)


def _append_body_blocks(parent: etree._Element, blocks: tuple[EditorialBlock, ...], state: _SerializationState) -> None:
    divisions: list[etree._Element] = []
    for block in blocks:
        if isinstance(block, Heading):
            if not block.content:
                state.error("empty_heading_not_serializable", "titre vide non serialisable", source_paragraph_index=block.source_paragraph_index)
                continue
            while len(divisions) >= block.level:
                divisions.pop()
            while len(divisions) < block.level - 1:
                anonymous_parent = divisions[-1] if divisions else parent
                anonymous = etree.SubElement(anonymous_parent, _tag("div"))
                divisions.append(anonymous)
            container = divisions[-1] if divisions else parent
            division = etree.SubElement(container, _tag("div"))
            head = etree.SubElement(division, _tag("head"))
            _append_inline(head, block.content, state)
            divisions.append(division)
            continue
        target = divisions[-1] if divisions else parent
        _append_block(target, block, state)


def _append_block(parent: etree._Element, block: EditorialBlock, state: _SerializationState) -> None:
    if isinstance(block, Paragraph):
        _append_paragraph_element(
            parent,
            block.content,
            rendition=block.rendition,
            source_paragraph_index=block.source_paragraph_index,
            state=state,
            empty_code="empty_paragraph_not_serializable",
            empty_message="paragraphe vide non serialisable",
        )
        return
    if isinstance(block, ProseQuote):
        if not block.paragraphs:
            state.error("empty_prose_quote_not_serializable", "citation en prose vide non serialisable")
            return
        quote = etree.SubElement(parent, _tag("quote"))
        for paragraph in block.paragraphs:
            if not paragraph.content:
                state.error("empty_prose_quote_paragraph_not_serializable", "paragraphe de citation vide non serialisable", source_paragraph_index=paragraph.source_paragraph_index)
                continue
            element = etree.SubElement(quote, _tag("p"))
            _append_inline(element, paragraph.content, state)
        return
    if isinstance(block, VerseQuote):
        if not block.stanzas:
            state.error("empty_verse_quote_not_serializable", "citation poetique vide non serialisable")
            return
        quote = etree.SubElement(parent, _tag("quote"))
        for stanza in block.stanzas:
            if not stanza.lines or all(not line.content for line in stanza.lines):
                state.error("empty_verse_stanza_not_serializable", "strophe vide non serialisable", source_paragraph_index=stanza.source_paragraph_index)
                continue
            group = etree.SubElement(quote, _tag("lg"))
            for line in stanza.lines:
                if not line.content:
                    state.error("empty_verse_not_serializable", "vers vide non serialisable", source_paragraph_index=line.source_paragraph_index)
                    continue
                element = etree.SubElement(group, _tag("l"))
                _append_inline(element, line.content, state)
        return
    if isinstance(block, EditorialList):
        _append_editorial_list(parent, block, state)
        return
    if isinstance(block, EditorialFigure):
        _append_figure(parent, block, state)
        return
    if isinstance(block, EditorialTable):
        _append_editorial_table(parent, block, state)
        return
    raise TypeError(f"bloc editorial inconnu : {type(block)!r}")


def _append_figure(parent: etree._Element, figure: EditorialFigure, state: _SerializationState) -> None:
    diagnostic = _validate_graphic(figure.graphic)
    if diagnostic is not None:
        state.diagnostics.append(diagnostic)
        return
    element = etree.SubElement(parent, _tag("figure"))
    if figure.title is not None:
        if figure.title.rendition != "figure-title":
            state.error("unsupported_paragraph_rendition", "rendition de titre de figure non prise en charge", source_paragraph_index=figure.title.source_paragraph_index)
            return
        if not figure.title.content:
            state.error("empty_figure_title_not_serializable", "titre de figure vide non serialisable", source_paragraph_index=figure.title.source_paragraph_index)
            return
        head = etree.SubElement(element, _tag("head"))
        _append_inline(head, figure.title.content, state)
    etree.SubElement(element, _tag("graphic"), url=figure.graphic.media_url)
    etree.SubElement(element, _tag("figDesc")).text = figure.graphic.description
    if figure.caption is not None:
        if figure.caption.rendition != "caption":
            state.error(
                "unsupported_paragraph_rendition",
                "rendition de legende de figure non prise en charge",
                source_paragraph_index=figure.caption.source_paragraph_index,
            )
            return
        _append_paragraph_element(
            element,
            figure.caption.content,
            rendition="caption",
            source_paragraph_index=figure.caption.source_paragraph_index,
            state=state,
            empty_code="empty_figure_caption_not_serializable",
            empty_message="legende de figure vide non serialisable",
            allowed_renditions=frozenset({"caption"}),
        )
    if figure.credits is not None:
        _append_paragraph_element(
            element, figure.credits.content, rendition=figure.credits.rendition,
            source_paragraph_index=figure.credits.source_paragraph_index, state=state,
            empty_code="empty_figure_credits_not_serializable",
            empty_message="credits de figure vides non serialisables",
            allowed_renditions=frozenset({"credits"}),
        )


def _append_editorial_table(parent: etree._Element, table: EditorialTable, state: _SerializationState) -> None:
    if not table.rows:
        state.error("empty_table_not_serializable", "table editoriale vide non serialisable")
        return
    if table.column_count <= 0:
        state.error("invalid_table_column_count", "nombre de colonnes de table invalide")
        return
    element = etree.SubElement(parent, _tag("table"), rows=str(len(table.rows)), cols=str(table.column_count))
    for row_index, row in enumerate(table.rows):
        if len(row.cells) != table.column_count:
            state.error("irregular_table_not_serializable", "lignes de table editoriale de tailles differentes")
            return
        if row.role not in {None, "label"}:
            state.error("unsupported_table_role", "role de ligne de table inconnu")
            return
        if row.role == "label" and row_index != 0:
            state.error("invalid_table_header_not_serializable", "ligne d'en-tete editoriale hors premiere ligne")
            return
        row_element = etree.SubElement(element, _tag("row"), **({"role": "label"} if row.role == "label" else {}))
        for column_index, cell in enumerate(row.cells):
            if cell.role not in {None, "label"} or (row.role == "label" and cell.role != "label"):
                state.error("unsupported_table_role", "role de cellule de table inconnu")
                return
            if cell.source_column_index < 0 or cell.source_row_index < 0:
                state.error("invalid_table_source_index", "index source de cellule invalide")
                return
            cell_element = etree.SubElement(row_element, _tag("cell"), **({"role": "label"} if cell.role == "label" else {}))
            for inline in cell.content:
                if isinstance(inline, DrawingReference):
                    state.error("image_in_table_cell_not_serializable", "dessin dans une cellule de table")
                    return
            _append_inline(cell_element, cell.content, state)


def _validate_graphic(graphic: EditorialGraphic) -> TeiConversionDiagnostic | None:
    if (
        not graphic.media_url
        or graphic.media_url.startswith("/")
        or ".." in Path(graphic.media_url).parts
        or not graphic.media_url.startswith("media/")
    ):
        return TeiConversionDiagnostic("invalid_figure_media_url", "error", "URL de media de figure invalide")
    if len(graphic.sha256) != 64 or any(character not in "0123456789abcdef" for character in graphic.sha256):
        return TeiConversionDiagnostic("invalid_figure_sha256", "error", "empreinte de figure invalide")
    if graphic.content_type not in {"image/png", "image/jpeg"}:
        return TeiConversionDiagnostic("unsupported_figure_media_type", "error", "type de media de figure non pris en charge")
    if not graphic.description.strip():
        return TeiConversionDiagnostic("missing_figure_description", "error", "description de figure absente")
    return None


def _append_editorial_list(
    parent: etree._Element,
    editorial_list: EditorialList,
    state: _SerializationState,
) -> None:
    """Serialiser une liste deja construite par la couche editoriale."""
    if not editorial_list.items:
        state.error("empty_list_not_serializable", "liste editoriale vide non serialisable")
        return
    if editorial_list.list_kind not in {"ordered", "bulleted"}:
        state.error("unsupported_editorial_list_kind", "nature de liste editoriale inconnue")
        return
    if not editorial_list.num_format:
        state.error("missing_editorial_list_format", "format de liste editorial absent")
        return
    if editorial_list.restart_after_level is not None:
        state.error(
            "explicit_list_restart_not_serializable",
            "redemarrage explicite de liste Word non serialisable",
        )
        return
    attributes = {"type": "bulleted" if editorial_list.list_kind == "bulleted" else editorial_list.num_format}
    if editorial_list.list_kind == "ordered" and editorial_list.start is not None:
        attributes["n"] = str(editorial_list.start)
    element = etree.SubElement(parent, _tag("list"), **attributes)
    for item in editorial_list.items:
        _append_editorial_list_item(element, item, state)


def _append_editorial_list_item(
    parent: etree._Element,
    item: EditorialListItem,
    state: _SerializationState,
) -> None:
    if not item.content and not item.child_lists and not item.continuation_paragraphs:
        state.error(
            "empty_list_item_not_serializable",
            "item de liste vide non serialisable",
            source_paragraph_index=item.source_paragraph_index,
        )
        return
    if item.continuation_paragraphs and not item.content:
        state.error(
            "empty_list_item_not_serializable",
            "item de liste multiparagraphe sans paragraphe initial",
            source_paragraph_index=item.source_paragraph_index,
        )
        return
    element = etree.SubElement(parent, _tag("item"))
    if item.continuation_paragraphs:
        _append_paragraph_element(
            element,
            item.content,
            rendition=None,
            source_paragraph_index=item.source_paragraph_index,
            state=state,
            empty_code="empty_list_item_not_serializable",
            empty_message="paragraphe initial d'item de liste vide non serialisable",
        )
        for paragraph in item.continuation_paragraphs:
            _append_paragraph_element(
                element,
                paragraph.content,
                rendition=paragraph.rendition,
                source_paragraph_index=paragraph.source_paragraph_index,
                state=state,
                empty_code="empty_list_continuation_not_serializable",
                empty_message="paragraphe de continuation de liste vide non serialisable",
            )
    else:
        _append_inline(element, item.content, state)
    for child in item.child_lists:
        _append_editorial_list(element, child, state)


def _append_paragraph_element(
    parent: etree._Element,
    content: tuple[EditorialInline, ...],
    *,
    rendition: object,
    source_paragraph_index: int,
    state: _SerializationState,
    empty_code: str,
    empty_message: str,
    allowed_renditions: frozenset[object] = frozenset({None, "consecutive"}),
) -> None:
    if not content:
        state.error(empty_code, empty_message, source_paragraph_index=source_paragraph_index)
        return
    if rendition not in allowed_renditions:
        state.error(
            "unsupported_paragraph_rendition",
            f"rendition de paragraphe non prise en charge : {rendition}",
            source_paragraph_index=source_paragraph_index,
        )
        return
    attributes = {"rend": rendition} if rendition in {"consecutive", "caption", "credits"} else {}
    element = etree.SubElement(parent, _tag("p"), **attributes)
    _append_inline(element, content, state)


def _append_inline(parent: etree._Element, items: tuple[EditorialInline, ...], state: _SerializationState) -> None:
    previous: etree._Element | None = None
    for item in items:
        if isinstance(item, TextSpan):
            container = _text_container(parent, item.link, state)
            if item.marks:
                rendered = etree.SubElement(container, _tag("hi"), rend=" ".join(_REND_VALUES[mark] for mark in item.marks))
                rendered.text = item.text
                previous = rendered
            else:
                _append_text(container, item.text)
                previous = container
        elif isinstance(item, LineBreak):
            previous = etree.SubElement(parent, _tag("lb"))
        elif isinstance(item, NoteReference):
            previous = _append_note_reference(parent, item, state)
        elif isinstance(item, (PageBreak, ColumnBreak)):
            state.error("break_not_serializable", "saut de page ou de colonne non autorise par le profil", note_id=None)
        elif isinstance(item, Tab):
            state.error("tab_not_serializable", "tabulation non autorisee par le profil")
        elif isinstance(item, DrawingReference):
            state.error("drawing_reference_not_serializable", "dessin sans informations editoriales suffisantes")
        else:
            raise TypeError(f"contenu editorial inconnu : {type(item)!r}")


def _text_container(parent: etree._Element, link: EditorialLink | None, state: _SerializationState) -> etree._Element:
    if link is None:
        return parent
    if link.kind == "external" and link.target:
        return etree.SubElement(parent, _tag("ref"), target=link.target)
    if link.kind == "internal":
        state.error("internal_link_target_not_materialized", "cible de lien interne non materialisee")
    else:
        state.error("unresolved_link_not_serializable", "lien externe non resolu non serialisable")
    return parent


def _append_text(parent: etree._Element, text: str) -> None:
    if len(parent):
        last = parent[-1]
        last.tail = (last.tail or "") + text
    else:
        parent.text = (parent.text or "") + text


def _append_note_reference(parent: etree._Element, reference: NoteReference, state: _SerializationState) -> etree._Element:
    key = (reference.note_kind, reference.note_id)
    state.referenced_notes.add(key)
    note = state.notes.get(key)
    if note is None:
        state.error("missing_note_target_not_serializable", f"cible de note absente : {reference.note_kind}:{reference.note_id}", note_id=reference.note_id)
        return parent
    if key in state.active_notes:
        state.error("cyclic_note_reference", f"cycle de notes : {reference.note_kind}:{reference.note_id}", note_id=reference.note_id)
        return parent
    state.active_notes.add(key)
    element = etree.SubElement(parent, _tag("note"), place="foot" if reference.note_kind == "footnote" else "end")
    for block in note.blocks:
        if isinstance(block, Heading):
            state.error(
                "heading_in_note_not_serializable",
                "titre de section dans une note non serialisable dans cette passe",
                source_paragraph_index=block.source_paragraph_index,
                note_id=note.note_id,
            )
            continue
        _append_block(element, block, state)
    state.active_notes.remove(key)
    return element


def _diagnose_unreferenced_notes(state: _SerializationState) -> None:
    """Signaler les notes absentes du flux sans les injecter artificiellement."""
    for note_kind, note_id in sorted(set(state.notes) - state.referenced_notes):
        state.diagnostics.append(
            TeiConversionDiagnostic(
                code="unreferenced_note_not_serialized",
                severity="warning",
                message=f"note non appelee non serialisee : {note_kind}:{note_id}",
                note_id=note_id,
            )
        )


def _has_errors(state: _SerializationState) -> bool:
    return any(diagnostic.severity == "error" for diagnostic in state.diagnostics)
