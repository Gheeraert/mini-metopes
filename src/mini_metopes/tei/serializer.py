"""Serialisation deterministe du modele editorial vers la TEI Commons Publishing."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import os
import tempfile

from lxml import etree

from mini_metopes.editorial import (
    BibliographicReference,
    BibliographicReferenceInline,
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
from mini_metopes.metadata import (
    DocumentMetadata,
    normalize_doi,
    normalize_issn,
    normalize_orcid,
    resolved_license,
)

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
    document_language: str | None = None

    def error(
        self,
        code: str,
        message: str,
        *,
        source_paragraph_index: int | None = None,
        note_id: str | None = None,
        metadata_path: str | None = None,
    ) -> None:
        self.diagnostics.append(
            TeiConversionDiagnostic(
                code=code,
                severity="error",
                message=message,
                source_paragraph_index=source_paragraph_index,
                note_id=note_id,
                origin="metadata" if metadata_path is not None else "serialization",
                metadata_path=metadata_path,
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
    state = _SerializationState(
        document, diagnostics, notes, set(), set(),
        document_language=metadata.language if metadata is not None else None,
    )
    root = etree.Element(_tag("TEI"), nsmap=_NSMAP)
    _append_header(root, document.source_name, metadata, state)
    text_element = etree.SubElement(root, _tag("text"))
    if metadata is not None and metadata.abstracts:
        _append_front_abstracts(text_element, metadata)
    body = etree.SubElement(text_element, _tag("body"))
    _append_body_blocks(body, document.blocks, state)
    if document.bibliography is not None:
        _append_bibliography(root.find(_tag("text")), document.bibliography, state)
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
            role_attribute = _TEI_CONTRIBUTOR_ROLES.get(contributor.role, "ctb")
            person = etree.SubElement(title_stmt, _tag(element_name), role=role_attribute)
            if contributor.role == "other":
                state.diagnostics.append(TeiConversionDiagnostic(
                    code="contributor_role_serialized_as_contributor", severity="info",
                    message="role other serialise comme editor role=ctb ; le libelle reste dans le JSON",
                    origin="metadata",
                    metadata_path=f"contributors[{contributor_index}].role",
                ))
            if contributor.email:
                state.diagnostics.append(TeiConversionDiagnostic(
                    code="contributor_email_not_serialized", severity="info",
                    message="adresse electronique non serialisee par le profil Commons Publishing",
                    origin="metadata",
                    metadata_path=f"contributors[{contributor_index}].email",
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
        for funding in metadata.funding:
            funder = etree.SubElement(title_stmt, _tag("funder"))
            etree.SubElement(funder, _tag("orgName")).text = funding.funder
            if funding.grant_number:
                etree.SubElement(funder, _tag("idno"), type="funder_registry").text = funding.grant_number
    _append_publication_statement(file_desc, metadata, state)
    source_desc = etree.SubElement(file_desc, _tag("sourceDesc"))
    etree.SubElement(source_desc, _tag("p")).text = f"Conversion du fichier DOCX {source_name}."
    if metadata is not None:
        _append_bibliographic_source_desc(file_desc, metadata, state)
        profile = etree.SubElement(header, _tag("profileDesc"))
        lang_usage = etree.SubElement(profile, _tag("langUsage"))
        etree.SubElement(lang_usage, _tag("language"), ident=metadata.language).text = metadata.language
        if metadata.keywords:
            text_class = etree.SubElement(profile, _tag("textClass"))
            for group in metadata.keywords:
                keywords = etree.SubElement(text_class, _tag("keywords"), scheme=group.scheme)
                keywords.set(_XML_LANG, group.language)
                listing = etree.SubElement(keywords, _tag("list"))
                for keyword in group.items:
                    etree.SubElement(listing, _tag("item")).text = keyword
        if metadata.editorial_responsibility:
            state.diagnostics.append(TeiConversionDiagnostic(
                code="editorial_responsibility_not_serialized", severity="info",
                message="responsable d'edition non serialisable : le profil embarque n'admet ni editionStmt ni respStmt",
                origin="metadata",
                metadata_path="editorial_responsibility",
            ))


_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def _foreign_language_attribute(run_language: str | None, document_language: str | None) -> str | None:
    """Determiner s'il faut porter `xml:lang` sur `<hi>` pour un run en langue etrangere.

    Compare uniquement la sous-etiquette primaire (ex. `fr` dans `fr-FR`) :
    un run Word tague `fr-FR` dans un document declare `fr` n'est pas une
    exception a marquer. Sans langue de document connue (`metadata` absent),
    aucune supposition n'est faite.
    """
    if run_language is None or document_language is None:
        return None
    if _primary_language_subtag(run_language) == _primary_language_subtag(document_language):
        return None
    return run_language


def _primary_language_subtag(value: str) -> str:
    return value.strip().split("-", 1)[0].lower()
_TEI_CONTRIBUTOR_ROLES = {
    "author": "aut",
    "editor": "edt",
    "scientific_editor": "edt",
    "translator": "trl",
    "other": "ctb",
}
_TEI_IDNO_TYPES = {
    ("doi", None): "DOI",
    ("issn", None): "pISSN",
    ("eissn", None): "eISSN",
    ("local", None): "documentnumber",
}


def _append_publication_statement(
    file_desc: etree._Element,
    metadata: DocumentMetadata | None,
    state: _SerializationState,
) -> None:
    """Serialiser publicationStmt : agence puis details, jamais de placeholder."""
    publication = etree.SubElement(file_desc, _tag("publicationStmt"))
    if metadata is None:
        etree.SubElement(publication, _tag("p")).text = "Document généré par Mini-Métopes."
        return
    publisher = metadata.publication.publisher
    availability = _availability_content(metadata)
    has_details = bool(
        metadata.identifiers
        or metadata.publication.publication_date
        or publisher.url
        or availability
    )
    if publisher.name is None:
        if has_details:
            state.error(
                "missing_publisher_for_publication_details",
                "le profil exige un editeur avant les details de publication (date, identifiants, droits)",
            )
        etree.SubElement(publication, _tag("p")).text = "Document généré par Mini-Métopes."
        return
    etree.SubElement(publication, _tag("publisher")).text = publisher.name
    if publisher.place or publisher.address:
        state.diagnostics.append(TeiConversionDiagnostic(
            code="publisher_address_not_serialized", severity="info",
            message="lieu et adresse de l'editeur non serialisables dans publicationStmt (profil sans pubPlace/address)",
            origin="metadata",
            metadata_path="publication.publisher",
        ))
    if publisher.url:
        etree.SubElement(publication, _tag("ref"), target=publisher.url, type="site").text = publisher.url
    if metadata.publication.publication_date:
        date = etree.SubElement(publication, _tag("date"), when=metadata.publication.publication_date, type="publishing")
        date.text = metadata.publication.publication_date
    for index, identifier in enumerate(metadata.identifiers):
        idno_type, value = _tei_identifier(identifier, index, state)
        if idno_type is None or value is None:
            continue
        etree.SubElement(publication, _tag("idno"), type=idno_type).text = value
    if availability:
        element = etree.SubElement(publication, _tag("availability"))
        license_model = resolved_license(metadata.rights.license)
        if license_model.name:
            attributes = {"target": license_model.url} if license_model.url else {}
            etree.SubElement(element, _tag("licence"), **attributes).text = license_model.name
        if metadata.rights.statement:
            etree.SubElement(element, _tag("p")).text = metadata.rights.statement
        if metadata.rights.holder:
            etree.SubElement(element, _tag("p")).text = f"© {metadata.rights.holder}"


def _availability_content(metadata: DocumentMetadata) -> bool:
    rights = metadata.rights
    license_model = resolved_license(rights.license)
    return bool(license_model.name or rights.statement or rights.holder)


def _tei_identifier(identifier: object, index: int, state: _SerializationState) -> tuple[str | None, str | None]:
    """Traduire un identifiant JSON vers idno/@type du profil embarque."""
    from mini_metopes.metadata import Identifier, normalize_isbn

    assert isinstance(identifier, Identifier)
    path = f"identifiers[{index}]"
    if identifier.identifier_type == "doi":
        return "DOI", normalize_doi(identifier.value)
    if identifier.identifier_type in {"isbn-13", "isbn-10"}:
        if normalize_isbn(identifier.value) is None or identifier.identifier_format is None:
            state.error("invalid_isbn", "ISBN invalide ou format absent", metadata_path=f"{path}.value")
            return None, None
        return ("pISBN" if identifier.identifier_format == "print" else "eISBN"), identifier.value.strip()
    if identifier.identifier_type in {"issn", "eissn"}:
        return _TEI_IDNO_TYPES[(identifier.identifier_type, None)], normalize_issn(identifier.value)
    if identifier.identifier_type == "local":
        return "documentnumber", identifier.value.strip()
    state.error("invalid_identifier_type", f"type d'identifiant inconnu : {identifier.identifier_type}", metadata_path=f"{path}.type")
    return None, None


def _append_bibliographic_source_desc(
    file_desc: etree._Element,
    metadata: DocumentMetadata,
    state: _SerializationState,
) -> None:
    """Serialiser collection et pagination dans un sourceDesc bibliographique."""
    collection = metadata.collection
    pagination = metadata.pagination
    page_range = (
        pagination is not None and pagination.page_from is not None and pagination.page_to is not None
    )
    if pagination is not None and pagination.extent is not None:
        state.diagnostics.append(TeiConversionDiagnostic(
            code="pagination_extent_not_serialized", severity="warning",
            message="etendue de pagination non serialisable sans extent dans le profil embarque",
            origin="metadata",
            metadata_path="pagination.extent",
        ))
    if collection is None and not page_range:
        return
    source_desc = etree.SubElement(file_desc, _tag("sourceDesc"))
    bibl = etree.SubElement(source_desc, _tag("bibl"))
    if collection is not None:
        series = etree.SubElement(bibl, _tag("series"))
        etree.SubElement(series, _tag("title")).text = collection.title
        if collection.editor:
            etree.SubElement(series, _tag("editor")).text = collection.editor
        if collection.volume:
            etree.SubElement(series, _tag("biblScope"), unit="volume").text = collection.volume
        if collection.issn:
            etree.SubElement(series, _tag("idno"), type="pISSN").text = normalize_issn(collection.issn)
    if page_range:
        assert pagination is not None
        etree.SubElement(bibl, _tag("biblScope"), unit="page").text = f"{pagination.page_from}-{pagination.page_to}"


def _append_front_abstracts(text_element: etree._Element, metadata: DocumentMetadata) -> None:
    """Serialiser resumes et quatrieme de couverture dans text/front.

    Le profil embarque n'admet pas abstract dans profileDesc ; il admet en
    revanche des divisions front de type abstract. La quatrieme de couverture
    est distinguee par l'attribut libre n="back-cover".
    """
    front = etree.SubElement(text_element, _tag("front"))
    for abstract in metadata.abstracts:
        attributes = {"type": "abstract"}
        if abstract.abstract_type == "back-cover":
            attributes["n"] = "back-cover"
        division = etree.SubElement(front, _tag("div"), **attributes)
        division.set(_XML_LANG, abstract.language)
        for paragraph in abstract.text.splitlines():
            if paragraph.strip():
                etree.SubElement(division, _tag("p")).text = paragraph.strip()


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
        wrapper = etree.SubElement(parent, _tag("cit")) if block.source is not None else parent
        quote = etree.SubElement(wrapper, _tag("quote"))
        for paragraph in block.paragraphs:
            if not paragraph.content:
                state.error("empty_prose_quote_paragraph_not_serializable", "paragraphe de citation vide non serialisable", source_paragraph_index=paragraph.source_paragraph_index)
                continue
            element = etree.SubElement(quote, _tag("p"))
            _append_inline(element, paragraph.content, state)
        if block.source is not None:
            _append_bibliographic_reference(wrapper, block.source, state)
        return
    if isinstance(block, VerseQuote):
        if not block.stanzas:
            state.error("empty_verse_quote_not_serializable", "citation poetique vide non serialisable")
            return
        wrapper = etree.SubElement(parent, _tag("cit")) if block.source is not None else parent
        quote = etree.SubElement(wrapper, _tag("quote"))
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
        if block.source is not None:
            _append_bibliographic_reference(wrapper, block.source, state)
        return
    if isinstance(block, BibliographicReference):
        _append_bibliographic_reference(parent, block, state)
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


def _append_bibliographic_reference(
    parent: etree._Element, reference: BibliographicReference, state: _SerializationState
) -> None:
    if not reference.content:
        state.error("empty_bibliographic_reference_not_serializable", "reference bibliographique vide", source_paragraph_index=reference.source_paragraph_index)
        return
    if _contains_bibliographic_inline(reference.content):
        state.error(
            "nested_bibliographic_reference_not_serializable",
            "reference bibliographique inline dans une reference bibliographique",
            source_paragraph_index=reference.source_paragraph_index,
        )
        return
    element = etree.SubElement(parent, _tag("bibl"))
    _append_inline(element, reference.content, state, inside_bibl=True)


def _append_bibliography(parent: etree._Element | None, bibliography: object, state: _SerializationState) -> None:
    from mini_metopes.editorial import EditorialBibliography

    if parent is None or not isinstance(bibliography, EditorialBibliography):
        state.error("bibliography_not_serializable", "bibliographie editoriale invalide")
        return
    if not bibliography.title:
        state.error("empty_bibliography_title_not_serializable", "titre de bibliographie vide", source_paragraph_index=bibliography.source_paragraph_index)
        return
    if _contains_bibliographic_inline(bibliography.title):
        state.error(
            "nested_bibliographic_reference_not_serializable",
            "reference bibliographique inline dans un titre de bibliographie",
            source_paragraph_index=bibliography.source_paragraph_index,
        )
        return
    if not bibliography.entries:
        state.error("bibliography_without_entries_not_serializable", "bibliographie sans entree", source_paragraph_index=bibliography.source_paragraph_index)
        return
    back = etree.SubElement(parent, _tag("back"))
    division = etree.SubElement(back, _tag("div"), type="bibliography")
    head = etree.SubElement(division, _tag("head"))
    _append_inline(head, bibliography.title, state, inside_bibl=True)
    listing = etree.SubElement(division, _tag("listBibl"))
    for entry in bibliography.entries:
        _append_bibliographic_reference(listing, entry, state)


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


def _append_inline(
    parent: etree._Element,
    items: tuple[EditorialInline, ...],
    state: _SerializationState,
    *,
    inside_bibl: bool = False,
) -> None:
    previous: etree._Element | None = None
    for item in items:
        if isinstance(item, TextSpan):
            container = _text_container(parent, item.link, state)
            foreign_language = _foreign_language_attribute(item.language, state.document_language)
            if item.marks or foreign_language is not None:
                attributes = {"rend": " ".join(_REND_VALUES[mark] for mark in item.marks)} if item.marks else {}
                rendered = etree.SubElement(container, _tag("hi"), **attributes)
                if foreign_language is not None:
                    rendered.set(_XML_LANG, foreign_language)
                rendered.text = item.text
                previous = rendered
            else:
                _append_text(container, item.text)
                previous = container
        elif isinstance(item, BibliographicReferenceInline):
            if inside_bibl:
                state.error("nested_bibliographic_reference_not_serializable", "reference bibliographique inline imbriquee")
                continue
            if not item.content:
                state.error("empty_bibliographic_reference_inline_not_serializable", "reference bibliographique inline vide")
                continue
            if _contains_bibliographic_inline(item.content):
                state.error("nested_bibliographic_reference_not_serializable", "reference bibliographique inline imbriquee")
                continue
            previous = etree.SubElement(parent, _tag("bibl"))
            _append_inline(previous, item.content, state, inside_bibl=True)
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


def _contains_bibliographic_inline(items: tuple[EditorialInline, ...]) -> bool:
    for item in items:
        if isinstance(item, BibliographicReferenceInline):
            return True
    return False


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
