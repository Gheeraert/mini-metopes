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
    EditorialBuildResult,
    EditorialList,
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
        return _convert_docx(arguments.source, arguments.output, arguments.metadata)
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


def _convert_docx(source: Path, output: Path, metadata_path: Path | None) -> int:
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
    try:
        result = convert_docx_to_tei(source, metadata=loaded.metadata)
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
        write_tei_conversion_result(result, output)
    except OSError as error:
        print(f"ERREUR — {output}: {error.strerror or error}")
        return 2
    print(f"TEI ECRITE — {output}")
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
    print(f"Médias : {len(inspection.media)}")
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
    print(f"Items de listes : {sum(1 for editorial_list in [*body_root_lists, *note_root_lists] for _ in _iter_list_items(editorial_list))}")
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
