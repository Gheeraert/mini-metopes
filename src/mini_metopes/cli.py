"""Interface en ligne de commande minimale."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Exécuter la CLI et retourner son code de sortie."""
    arguments = build_parser().parse_args(argv)
    path: Path = arguments.path
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

