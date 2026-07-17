"""Serialisation deterministe du modele editorial vers la TEI Commons Publishing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import tempfile

from lxml import etree

from mini_metopes.editorial import (
    ColumnBreak,
    DrawingReference,
    EditorialBlock,
    EditorialDocument,
    EditorialInline,
    EditorialLink,
    EditorialNote,
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

from .model import TeiConversionDiagnostic, TeiConversionResult


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


def write_tei_conversion_result(result: TeiConversionResult, output_path: Path) -> None:
    """Ecrire atomiquement une conversion valide sans ecraser de cible en cas d'echec."""
    if not result.is_successful or result.xml_bytes is None:
        raise ValueError("une conversion TEI invalide ne peut pas etre ecrite")
    output_path.parent.mkdir(parents=True, exist_ok=True)
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
        for contributor in metadata.contributors:
            element_name = "author" if contributor.role == "author" else "editor"
            person = etree.SubElement(title_stmt, _tag(element_name))
            if contributor.role not in {"author", "editor"}:
                state.diagnostics.append(TeiConversionDiagnostic(
                    code="contributor_role_serialized_as_editor", severity="warning",
                    message=f"role {contributor.role} serialise comme editor, le profil n'admet pas respStmt ici",
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
            affiliations = {item.affiliation_id: item for item in metadata.affiliations}
            for affiliation_id in contributor.affiliation_ids:
                used_affiliations.add(affiliation_id)
                affiliation = affiliations[affiliation_id]
                # Commons Publishing permits an affiliation inline here, but no
                # shared affiliation registry at this header level. Do not
                # duplicate an xml:id when several people share one institution.
                rendered = etree.SubElement(person, _tag("affiliation"))
                rendered.text = _affiliation_text(affiliation)
                if affiliation.ror:
                    state.diagnostics.append(
                        TeiConversionDiagnostic(
                            code="ror_not_serialized",
                            severity="warning",
                            message=f"ROR non serialise par le profil Commons Publishing : {affiliation.affiliation_id}",
                        )
                    )
        for affiliation in metadata.affiliations:
            if affiliation.affiliation_id not in used_affiliations:
                state.diagnostics.append(TeiConversionDiagnostic(
                    code="unreferenced_affiliation_not_serialized", severity="warning",
                    message=f"affiliation non utilisee non serialisee : {affiliation.affiliation_id}",
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
        if not block.content:
            state.error("empty_paragraph_not_serializable", "paragraphe vide non serialisable", source_paragraph_index=block.source_paragraph_index)
            return
        element = etree.SubElement(parent, _tag("p"))
        _append_inline(element, block.content, state)
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
    raise TypeError(f"bloc editorial inconnu : {type(block)!r}")


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
