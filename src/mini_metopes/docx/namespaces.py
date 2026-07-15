"""Espaces de noms OOXML utilisés par l'inspecteur DOCX."""

from __future__ import annotations

WORDPROCESSINGML = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
OFFICE_DOCUMENT_RELATIONSHIPS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)
PACKAGE_RELATIONSHIPS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"

NS = {
    "w": WORDPROCESSINGML,
    "r": OFFICE_DOCUMENT_RELATIONSHIPS,
    "pr": PACKAGE_RELATIONSHIPS,
    "ct": CONTENT_TYPES,
}


def w_tag(local_name: str) -> str:
    """Retourner un nom qualifié WordprocessingML."""
    return f"{{{WORDPROCESSINGML}}}{local_name}"


def r_tag(local_name: str) -> str:
    """Retourner un nom qualifié de relations Office."""
    return f"{{{OFFICE_DOCUMENT_RELATIONSHIPS}}}{local_name}"
