"""Interface en ligne de commande minimale."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Iterator, Sequence

from .docx import DocxInspection, DocxInspectionError, inspect_docx_file
from .editorial import (
    BibliographicReference,
    BibliographicReferenceInline,
    EditorialBuildResult,
    EditorialFigure,
    EditorialList,
    EditorialTable,
    Paragraph,
    ProseQuote,
    VerseQuote,
    build_editorial_document_from_file,
    editorial_build_result_to_json,
)
from .tei import convert_docx_to_tei, write_tei_conversion_result
from .tei.model import TeiConversionDiagnostic
from .metadata import default_metadata_path, extract_metadata_suggestions, load_metadata_file, metadata_consistency_issues
from .validation import ValidationIssue, validate_xml_file


def _format_issue(issue: ValidationIssue) -> str:
    position: list[str] = []
    if issue.line is not None:
        position.append(f"ligne {issue.line}")
    if issue.column is not None:
        position.append(f"colonne {issue.column}")
    prefix = ", ".join(position)
    return f"{prefix} : {issue.message}" if prefix else issue.message


def _format_conversion_diagnostic(diagnostic: TeiConversionDiagnostic) -> str:
    path = diagnostic.metadata_path or diagnostic.source_part or ""
    prefix = f"{path} : " if path else ""
    return f"{diagnostic.severity.upper()} [{diagnostic.code}] {prefix}{diagnostic.message}"


def build_parser() -> argparse.ArgumentParser:
    """Construire le parseur d'arguments de la CLI."""
    parser = argparse.ArgumentParser(prog="mini-metopes")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate", help="valider un fichier XML TEI")
    validate_parser.add_argument("path", type=Path, help="fichier XML à valider")
    inspect_parser = subparsers.add_parser(
        "inspect-docx", help="inspecter la structure OOXML d'un fichier DOCX"
    )
    inspect_parser.add_argument("path", type=Path, help="fichier DOCX à inspecter")
    inspect_parser.add_argument(
        "--json",
        action="store_true",
        help="produire un résultat JSON structuré",
    )
    model_parser = subparsers.add_parser(
        "model-docx", help="construire le modèle éditorial d'un fichier DOCX"
    )
    model_parser.add_argument("path", type=Path, help="fichier DOCX à modéliser")
    model_parser.add_argument(
        "--json",
        action="store_true",
        help="produire un résultat JSON structuré",
    )
    convert_parser = subparsers.add_parser(
        "convert-docx", help="convertir un fichier DOCX en TEI Commons Publishing"
    )
    convert_parser.add_argument("source", type=Path, help="fichier DOCX source")
    convert_parser.add_argument("output", type=Path, help="fichier TEI de sortie")
    convert_parser.add_argument("--metadata", type=Path, help="fichier JSON de metadonnees")
    convert_parser.add_argument("--profile", type=Path, help="profil institutionnel JSON (valeurs par defaut)")
    metadata_validate_parser = subparsers.add_parser("validate-metadata", help="valider un fichier JSON de metadonnees")
    metadata_validate_parser.add_argument("path", type=Path, help="fichier JSON de metadonnees")
    metadata_validate_parser.add_argument("--source", type=Path, help="DOCX associe a verifier")
    editor_parser = subparsers.add_parser("edit-metadata", help="editer les metadonnees associees a un DOCX")
    editor_parser.add_argument("path", type=Path, nargs="?", help="fichier DOCX a editer")
    editor_parser.add_argument("--metadata", type=Path, help="fichier JSON de metadonnees")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Exécuter la CLI et retourner son code de sortie."""
    arguments = build_parser().parse_args(argv)
    if arguments.command == "convert-docx":
        return _convert_docx(arguments.source, arguments.output, arguments.metadata, arguments.profile)
    if arguments.command == "validate-metadata":
        return _validate_metadata(arguments.path, arguments.source)
    if arguments.command == "edit-metadata":
        from .gui import run_metadata_editor
        try:
            return run_metadata_editor(arguments.path, arguments.metadata)
        except DocxInspectionError as error:
            print(f"ERREUR - {arguments.path}: {error}")
            return 2
        except OSError as error:
            print(f"ERREUR — {arguments.path}: {error.strerror or error}")
            return 2
    path: Path = arguments.path
    if arguments.command == "inspect-docx":
        return _inspect_docx(path, as_json=arguments.json)
    if arguments.command == "model-docx":
        return _model_docx(path, as_json=arguments.json)

    try:
        result = validate_xml_file(path)
    except OSError as error:
        print(f"ERREUR — {path}: {error.strerror or error}")
        return 2

    if result.valid:
        print(f"VALIDE — {path.name}")
        return 0

    print(f"INVALIDE — {path.name}")
    for issue in result.issues:
        print(_format_issue(issue))
    return 1


def _inspect_docx(path: Path, *, as_json: bool) -> int:
    try:
        inspection = inspect_docx_file(path)
    except DocxInspectionError as error:
        print(f"ERREUR — {path}: {error}")
        return 2

    if as_json:
        sys.stdout.buffer.write((_inspection_as_json(inspection) + "\n").encode("utf-8"))
    else:
        _print_inspection_summary(inspection)
    return 0


def _inspection_as_json(inspection: DocxInspection) -> str:
    result = asdict(inspection)
    result["source"] = inspection.source.name
    return json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)


def _model_docx(path: Path, *, as_json: bool) -> int:
    try:
        result = build_editorial_document_from_file(path)
    except DocxInspectionError as error:
        print(f"ERREUR — {path}: {error}")
        return 2

    if as_json:
        sys.stdout.buffer.write((editorial_build_result_to_json(result) + "\n").encode("utf-8"))
    else:
        _print_editorial_summary(result)
    return 0


def _convert_docx(source: Path, output: Path, metadata_path: Path | None, profile_path: Path | None = None) -> int:
    if not source.exists():
        print(f"ERREUR - {source}: fichier introuvable")
        return 2
    selected_metadata = metadata_path or default_metadata_path(source)
    if not selected_metadata.exists():
        print(f"ECHEC [missing_metadata] — {source.name}")
        print("Aucune metadonnee associee. Lancez :")
        print(f"python -m mini_metopes edit-metadata {source}")
        return 1
    loaded = load_metadata_file(selected_metadata)
    if not loaded.valid or loaded.metadata is None:
        print(f"ECHEC [invalid_metadata] — {selected_metadata.name}")
        for issue in loaded.issues:
            print(f"{issue.severity.upper()} [{issue.code}] {issue.path or ''} : {issue.message}")
        return 1
    metadata = loaded.metadata
    if profile_path is not None:
        from .metadata import apply_institutional_profile, load_institutional_profile

        profile, profile_issues = load_institutional_profile(profile_path)
        if profile is None:
            print(f"ECHEC [invalid_profile] — {profile_path.name}")
            for issue in profile_issues:
                print(f"{issue.severity.upper()} [{issue.code}] {issue.path or ''} : {issue.message}")
            return 1
        metadata = apply_institutional_profile(metadata, profile)
    try:
        result = convert_docx_to_tei(source, metadata=metadata)
    except DocxInspectionError as error:
        print(f"ERREUR — {source}: {error}")
        return 2
    if not result.is_successful:
        print(f"ECHEC — {source.name}")
        for diagnostic in result.diagnostics:
            print(_format_conversion_diagnostic(diagnostic))
        for issue in result.validation_issues:
            print(_format_issue(issue))
        return 1
    try:
        write_result = write_tei_conversion_result(result, output)
    except OSError as error:
        print(f"ERREUR — {output}: {error.strerror or error}")
        return 2
    except ValueError as error:
        print(f"ECHEC — {output}")
        print(f"ERROR [{str(error).split(':', 1)[0]}] : {error}")
        return 1
    print(f"TEI ECRITE — {output}")
    if result.assets:
        print(f"Médias écrits : {write_result.media_written}")
        print(f"Médias réutilisés : {write_result.media_reused}")
        print(f"Répertoire médias : {write_result.media_directory}")
    print("Validation Commons Publishing : réussie")
    for diagnostic in result.diagnostics:
        print(_format_conversion_diagnostic(diagnostic))
    print(f"Diagnostics non bloquants : {len(result.diagnostics)}")
    return 0


def _validate_metadata(path: Path, source: Path | None) -> int:
    if not path.exists():
        print(f"ERREUR — {path}: fichier introuvable")
        return 2
    loaded = load_metadata_file(path)
    if not loaded.valid or loaded.metadata is None:
        print(f"INVALIDES — {path.name}")
        for issue in loaded.issues:
            print(f"{issue.severity.upper()} [{issue.code}] {issue.path or ''} : {issue.message}")
        return 2 if any(issue.code in {"invalid_json", "metadata_file_unreadable"} for issue in loaded.issues) else 1
    if source is not None and not source.exists():
        print(f"ERREUR — {source}: fichier introuvable")
        return 2
    if source is not None:
        try:
            suggestions = extract_metadata_suggestions(inspect_docx_file(source))
        except DocxInspectionError as error:
            print(f"ERREUR - {source}: {error}")
            return 2
        for issue in suggestions.diagnostics + metadata_consistency_issues(loaded.metadata, source, suggestions):
            print(f"{issue.severity.upper()} [{issue.code}] {issue.path or ''} : {issue.message}")
    print(f"VALIDES — {path.name}")
    return 0


def _print_inspection_summary(inspection: DocxInspection) -> None:
    style_counts: dict[str, int] = {}
    for paragraph in inspection.paragraphs:
        if paragraph.style_id is not None:
            style_counts[paragraph.style_id] = style_counts.get(paragraph.style_id, 0) + 1
    manual_breaks = sum(paragraph.manual_breaks for paragraph in inspection.paragraphs)
    all_paragraphs = [
        *inspection.paragraphs,
        *(paragraph for note in inspection.footnotes for paragraph in note.paragraphs),
        *(paragraph for note in inspection.endnotes for paragraph in note.paragraphs),
    ]
    active_numbering = [
        paragraph.numbering
        for paragraph in all_paragraphs
        if paragraph.numbering is not None and paragraph.numbering.status != "removed"
    ]
    numbered = len(active_numbering)
    ordered_lists = sum(item.list_kind == "ordered" for item in active_numbering)
    bulleted_lists = sum(item.list_kind == "bulleted" for item in active_numbering)
    unresolved_lists = sum(item.status in {"unresolved", "unsupported"} for item in active_numbering)
    hyperlinks = sum(paragraph.hyperlink_count for paragraph in inspection.paragraphs)
    drawings = sum(paragraph.drawing_count for paragraph in inspection.paragraphs)
    all_drawings = [
        content.drawing
        for paragraph in all_paragraphs
        for run in paragraph.runs
        for content in run.contents
        if content.kind == "drawing" and content.drawing is not None
    ]
    inline_drawings = sum(drawing.placement == "inline" for drawing in all_drawings)
    floating_drawings = sum(drawing.placement == "anchor" for drawing in all_drawings)
    png_media = sum(media.content_type == "image/png" for media in inspection.media)
    jpeg_media = sum(media.content_type == "image/jpeg" for media in inspection.media)
    unsupported_media = sum(
        media.content_type not in {"image/png", "image/jpeg"} for media in inspection.media
    )
    body_tables = [block for block in inspection.body_blocks if getattr(block, "kind", None) == "table"]
    complex_tables = sum(
        not table.rows
        or any(not row.cells for row in table.rows)
        or any(
            cell.has_grid_span or cell.has_vertical_merge or cell.has_horizontal_merge or cell.has_nested_table
            for row in table.rows for cell in row.cells
        )
        or any(len(row.cells) != len(table.rows[0].cells) for row in table.rows)
        or (table.declared_column_count is not None and table.rows and table.declared_column_count != len(table.rows[0].cells))
        or any(row.is_header for row in table.rows[1:])
        for table in body_tables
    )

    print(f"DOCX — {inspection.source.name}")
    print(f"Paragraphes : {len(inspection.paragraphs)}")
    print(f"Styles : {len(inspection.styles)}")
    if style_counts:
        used_styles = ", ".join(
            f"{style_id} ({count})" for style_id, count in sorted(style_counts.items())
        )
        print(f"Styles de paragraphe employés : {used_styles}")
    print(f"Notes de bas de page : {len(inspection.footnotes)}")
    print(f"Notes de fin : {len(inspection.endnotes)}")
    print(f"Sauts manuels : {manual_breaks}")
    print(f"Paragraphes numérotés actifs : {numbered}")
    print(f"Listes ordonnées observées : {ordered_lists}")
    print(f"Listes à puces observées : {bulleted_lists}")
    print(f"Numérotations non résolues : {unresolved_lists}")
    print(f"Hyperliens : {hyperlinks}")
    print(f"Dessins : {drawings}")
    print(f"Images DrawingML inline : {inline_drawings}")
    print(f"Images DrawingML flottantes : {floating_drawings}")
    print(f"Images VML : {sum(issue.code == 'vml_image_not_supported' for issue in inspection.issues)}")
    print(f"Médias PNG : {png_media}")
    print(f"Médias JPEG : {jpeg_media}")
    print(f"Médias non pris en charge : {unsupported_media}")
    print(f"Médias : {len(inspection.media)}")
    print(f"Tableaux du corps : {len(body_tables)}")
    print(f"Lignes de tableaux : {sum(len(table.rows) for table in body_tables)}")
    print(f"Cellules de tableaux : {sum(len(row.cells) for table in body_tables for row in table.rows)}")
    print(f"Tableaux complexes refuses : {complex_tables}")
    for issue in inspection.issues:
        print(f"{issue.severity.upper()} [{issue.code}] : {issue.message}")


def _print_editorial_summary(result: EditorialBuildResult) -> None:
    document = result.document
    headings = [block for block in document.blocks if block.kind == "heading"]
    paragraphs = [block for block in document.blocks if block.kind == "paragraph"]
    consecutive_body_paragraphs = [
        block for block in document.blocks if isinstance(block, Paragraph) and block.rendition == "consecutive"
    ]
    consecutive_note_paragraphs = [
        block
        for note in document.notes
        for block in note.blocks
        if isinstance(block, Paragraph) and block.rendition == "consecutive"
    ]
    prose_quotes = [block for block in document.blocks if isinstance(block, ProseQuote)]
    verse_quotes = [block for block in document.blocks if isinstance(block, VerseQuote)]
    body_root_lists = [block for block in document.blocks if isinstance(block, EditorialList)]
    body_figures = [block for block in document.blocks if isinstance(block, EditorialFigure)]
    body_tables = [block for block in document.blocks if isinstance(block, EditorialTable)]
    note_figures = [
        block
        for note in document.notes
        for block in note.blocks
        if isinstance(block, EditorialFigure)
    ]
    note_root_lists = [
        block
        for note in document.notes
        for block in note.blocks
        if isinstance(block, EditorialList)
    ]
    body_lists = list(_iter_editorial_lists(document.blocks))
    note_lists = [
        editorial_list
        for note in document.notes
        for editorial_list in _iter_editorial_lists(note.blocks)
    ]
    editorial_lists = [*body_lists, *note_lists]
    body_items = [item for root in body_root_lists for item in _iter_list_items(root)]
    note_items = [item for root in note_root_lists for item in _iter_list_items(root)]
    all_list_items = [*body_items, *note_items]
    body_continuations = sum(len(item.continuation_paragraphs) for item in body_items)
    note_continuations = sum(len(item.continuation_paragraphs) for item in note_items)
    multiparagraph_items = sum(1 for item in all_list_items if item.continuation_paragraphs)
    figures = [*body_figures, *note_figures]
    standalone_bibliography_references = [block for block in document.blocks if isinstance(block, BibliographicReference)]
    inline_bibliographic_references = sum(
        1
        for block in (*document.blocks, *(item for note in document.notes for item in note.blocks))
        for inline in _object_inlines(block)
        if isinstance(inline, BibliographicReferenceInline)
    )
    citations_with_source = sum(
        isinstance(block, (ProseQuote, VerseQuote)) and block.source is not None
        for block in (*document.blocks, *(item for note in document.notes for item in note.blocks))
    )
    figure_media_urls = {figure.graphic.media_url for figure in figures}
    levels: dict[int, int] = {}
    for heading in headings:
        levels[heading.level] = levels.get(heading.level, 0) + 1
    codes: dict[str, int] = {}
    for diagnostic in result.diagnostics:
        codes[diagnostic.code] = codes.get(diagnostic.code, 0) + 1

    print(f"MODÈLE DOCX — {document.source_name}")
    print(f"Blocs : {len(document.blocks)}")
    print(f"Titres : {len(headings)}")
    print(f"Paragraphes : {len(paragraphs)}")
    print(f"Paragraphes de suite du corps : {len(consecutive_body_paragraphs)}")
    print(f"Paragraphes de suite dans les notes : {len(consecutive_note_paragraphs)}")
    print(f"Paragraphes de suite totaux : {len(consecutive_body_paragraphs) + len(consecutive_note_paragraphs)}")
    print(f"Citations en prose : {len(prose_quotes)}")
    print(f"Paragraphes de citation : {sum(len(quote.paragraphs) for quote in prose_quotes)}")
    print(f"Citations poetiques : {len(verse_quotes)}")
    print(f"Strophes : {sum(len(quote.stanzas) for quote in verse_quotes)}")
    print(f"Vers : {sum(len(stanza.lines) for quote in verse_quotes for stanza in quote.stanzas)}")
    print(f"Listes du corps : {len(body_lists)}")
    print(f"Listes des notes : {len(note_lists)}")
    print(f"Listes totales : {len(editorial_lists)}")
    print(f"Items de listes : {len(all_list_items)}")
    print(f"Paragraphes de continuation de liste du corps : {body_continuations}")
    print(f"Paragraphes de continuation de liste dans les notes : {note_continuations}")
    print(f"Paragraphes de continuation de liste totaux : {body_continuations + note_continuations}")
    print(f"Items de liste multiparagraphe : {multiparagraph_items}")
    print(f"Figures du corps : {len(body_figures)}")
    print(f"Figures dans les notes : {len(note_figures)}")
    print(f"Figures totales : {len(figures)}")
    print(f"Figures avec légende : {sum(figure.caption is not None for figure in figures)}")
    print(f"Figures sans légende : {sum(figure.caption is None for figure in figures)}")
    print(f"Médias uniques référencés : {len(figure_media_urls)}")
    print(f"Figures avec titre : {sum(figure.title is not None for figure in figures)}")
    print(f"Figures avec credits : {sum(figure.credits is not None for figure in figures)}")
    print(f"Tableaux editoriaux : {len(body_tables)}")
    print(f"Lignes de tableaux : {sum(len(table.rows) for table in body_tables)}")
    print(f"Cellules de tableaux : {sum(len(row.cells) for table in body_tables for row in table.rows)}")
    print(f"Tableaux avec ligne d'en-tete : {sum(bool(table.rows and table.rows[0].role == 'label') for table in body_tables)}")
    print(f"References bibliographiques autonomes : {len(standalone_bibliography_references)}")
    print(f"References bibliographiques inline : {inline_bibliographic_references}")
    print(f"Citations avec source : {citations_with_source}")
    print(f"Bibliographies : {int(document.bibliography is not None)}")
    print(f"Entrees bibliographiques : {len(document.bibliography.entries) if document.bibliography else 0}")
    if levels:
        print("Titres par niveau : " + ", ".join(f"{level} ({count})" for level, count in sorted(levels.items())))
    print(f"Notes de bas de page : {sum(note.note_kind == 'footnote' for note in document.notes)}")
    print(f"Notes de fin : {sum(note.note_kind == 'endnote' for note in document.notes)}")
    print(f"Diagnostics : {len(result.diagnostics)}")
    if codes:
        print("Diagnostics par code : " + ", ".join(f"{code} ({count})" for code, count in sorted(codes.items())))


def _iter_editorial_lists(blocks: tuple[object, ...]) -> Iterator[EditorialList]:
    for block in blocks:
        if isinstance(block, EditorialList):
            yield block
            for item in block.items:
                yield from _iter_editorial_lists(item.child_lists)


def _iter_list_items(editorial_list: EditorialList) -> Iterator[object]:
    for item in editorial_list.items:
        yield item
        for child in item.child_lists:
            yield from _iter_list_items(child)


def _object_inlines(block: object) -> Iterator[object]:
    content = getattr(block, "content", None)
    if isinstance(content, tuple):
        yield from _inline_objects(content)
    for paragraph in getattr(block, "paragraphs", ()):
        yield from _inline_objects(paragraph.content)
    for stanza in getattr(block, "stanzas", ()):
        for line in stanza.lines:
            yield from _inline_objects(line.content)
    source = getattr(block, "source", None)
    if source is not None:
        yield from _object_inlines(source)
    for item in getattr(block, "items", ()):
        yield from _object_inlines(item)
    for paragraph in getattr(block, "continuation_paragraphs", ()):
        yield from _object_inlines(paragraph)
    for child in getattr(block, "child_lists", ()):
        yield from _object_inlines(child)
    for paragraph_name in ("title", "caption", "credits"):
        paragraph = getattr(block, paragraph_name, None)
        if paragraph is not None:
            yield from _object_inlines(paragraph)
    for row in getattr(block, "rows", ()):
        for cell in row.cells:
            yield from _object_inlines(cell)
    bibliography = getattr(block, "bibliography", None)
    if bibliography is not None:
        yield from _object_inlines(bibliography)
    title = getattr(block, "title", None)
    if isinstance(title, tuple):
        yield from _inline_objects(title)
    for entry in getattr(block, "entries", ()):
        yield from _object_inlines(entry)


def _inline_objects(items: tuple[object, ...]) -> Iterator[object]:
    for item in items:
        yield item
        nested = getattr(item, "content", None)
        if isinstance(nested, tuple):
            yield from _inline_objects(nested)
