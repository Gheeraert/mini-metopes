"""Interface en ligne de commande minimale."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Sequence

from .docx import DocxInspection, DocxInspectionError, inspect_docx_file
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Exécuter la CLI et retourner son code de sortie."""
    arguments = build_parser().parse_args(argv)
    path: Path = arguments.path
    if arguments.command == "inspect-docx":
        return _inspect_docx(path, as_json=arguments.json)

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
