"""Association locale et empreinte des fichiers de metadonnees."""

from __future__ import annotations

import hashlib
from pathlib import Path


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
