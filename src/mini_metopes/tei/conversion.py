"""Chainage DOCX -> modele editorial -> TEI validee."""

from __future__ import annotations

from pathlib import Path

from mini_metopes.editorial import NATIVE_WORD_CONVENTION, WordEditorialConvention, build_editorial_document_from_file

from .model import TeiConversionResult
from .serializer import serialize_editorial_document_to_tei


def convert_docx_to_tei(
    path: Path,
    *,
    convention: WordEditorialConvention = NATIVE_WORD_CONVENTION,
) -> TeiConversionResult:
    """Convertir un DOCX en TEI Commons Publishing sans ecrire de fichier."""
    editorial = build_editorial_document_from_file(path, convention=convention)
    return serialize_editorial_document_to_tei(editorial.document)
