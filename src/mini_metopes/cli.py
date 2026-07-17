"""Interface en ligne de commande minimale."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Sequence

from .docx import DocxInspection, DocxInspectionError, inspect_docx_file
from .editorial import (
    EditorialBuildResult,
    ProseQuote,
    VerseQuote,
    build_editorial_document_from_file,
    editorial_build_result_to_json,
)
from .tei import convert_docx_to_tei, write_tei_conversion_result
from .metadata import MetadataSuggestions, default_metadata_path, load_metadata_file, metadata_consistency_issues
from .validation import ValidationIssue, validate_xml_file


def _format_issue(issue: ValidationIssue) -> str:
    position: list[str] = []
    if issue.line is not None:
        position.append(f"ligne {issue.line}")
    if issue.column is not None:
        position.append(f"colonne {issue.column}")
    prefix = ", ".join(position)
    return f"{prefix} : {issue.message}" if prefix else issue.message


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
            print(f"{diagnostic.severity.upper()} [{diagnostic.code}] : {diagnostic.message}")
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
        for issue in metadata_consistency_issues(loaded.metadata, source, MetadataSuggestions(None, None, (), ())):
            print(f"{issue.severity.upper()} [{issue.code}] {issue.path or ''} : {issue.message}")
    print(f"VALIDES — {path.name}")
    return 0


def _print_inspection_summary(inspection: DocxInspection) -> None:
    style_counts: dict[str, int] = {}
    for paragraph in inspection.paragraphs:
        if paragraph.style_id is not None:
            style_counts[paragraph.style_id] = style_counts.get(paragraph.style_id, 0) + 1
    manual_breaks = sum(paragraph.manual_breaks for paragraph in inspection.paragraphs)
    numbered = sum(paragraph.numbering_id is not None for paragraph in inspection.paragraphs)
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
    print(f"Paragraphes numérotés : {numbered}")
    print(f"Hyperliens : {hyperlinks}")
    print(f"Dessins : {drawings}")
    print(f"Médias : {len(inspection.media)}")
    for issue in inspection.issues:
        print(f"{issue.severity.upper()} [{issue.code}] : {issue.message}")


def _print_editorial_summary(result: EditorialBuildResult) -> None:
    document = result.document
    headings = [block for block in document.blocks if block.kind == "heading"]
    paragraphs = [block for block in document.blocks if block.kind == "paragraph"]
    prose_quotes = [block for block in document.blocks if isinstance(block, ProseQuote)]
    verse_quotes = [block for block in document.blocks if isinstance(block, VerseQuote)]
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
    print(f"Citations en prose : {len(prose_quotes)}")
    print(f"Paragraphes de citation : {sum(len(quote.paragraphs) for quote in prose_quotes)}")
    print(f"Citations poetiques : {len(verse_quotes)}")
    print(f"Strophes : {sum(len(quote.stanzas) for quote in verse_quotes)}")
    print(f"Vers : {sum(len(stanza.lines) for quote in verse_quotes for stanza in quote.stanzas)}")
    if levels:
        print("Titres par niveau : " + ", ".join(f"{level} ({count})" for level, count in sorted(levels.items())))
    print(f"Notes de bas de page : {sum(note.note_kind == 'footnote' for note in document.notes)}")
    print(f"Notes de fin : {sum(note.note_kind == 'endnote' for note in document.notes)}")
    print(f"Diagnostics : {len(result.diagnostics)}")
    if codes:
        print("Diagnostics par code : " + ", ".join(f"{code} ({count})" for code, count in sorted(codes.items())))
