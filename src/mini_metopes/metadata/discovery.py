"""Association locale, empreinte et resolution du chemin du DOCX source."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath, PureWindowsPath


def default_metadata_path(docx_path: Path) -> Path:
    """Retourner le JSON associe, sans recherche hors du repertoire du DOCX."""
    return docx_path.with_suffix(".metadata.json")


def compute_file_sha256(path: Path) -> str:
    """Calculer l'empreinte SHA-256 par blocs sans charger le DOCX entier."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def source_document_reference(docx_path: Path, metadata_path: Path) -> str:
    """Choisir le chemin memorise dans le JSON pour retrouver le DOCX.

    Un chemin relatif au repertoire du JSON est prefere ; un chemin absolu
    n'est conserve que lorsque aucun chemin relatif n'est possible (autre
    lecteur Windows, par exemple). Les separateurs sont normalises en ``/``
    pour que le JSON reste portable. Le DOCX n'est jamais incorpore.
    """
    docx_resolved = docx_path.resolve()
    base = metadata_path.resolve().parent
    try:
        relative = docx_resolved.relative_to(base)
        return relative.as_posix()
    except ValueError:
        pass
    try:
        import os

        relative_text = os.path.relpath(docx_resolved, base)
    except ValueError:
        return docx_resolved.as_posix()
    return PureWindowsPath(relative_text).as_posix()


def resolve_source_document_path(source_path: str, metadata_path: Path) -> Path:
    """Resoudre le chemin du DOCX relativement a l'emplacement du JSON."""
    candidate = PurePosixPath(source_path)
    if Path(str(candidate)).is_absolute() or PureWindowsPath(source_path).is_absolute():
        return Path(source_path)
    return (metadata_path.resolve().parent / Path(str(candidate))).resolve()
