"""Espaces de noms OOXML utilisés par l'inspecteur DOCX."""

from __future__ import annotations

WORDPROCESSINGML = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
OFFICE_DOCUMENT_RELATIONSHIPS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)
PACKAGE_RELATIONSHIPS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
WORDPROCESSING_DRAWING = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
DRAWINGML = "http://schemas.openxmlformats.org/drawingml/2006/main"
DRAWINGML_PICTURE = "http://schemas.openxmlformats.org/drawingml/2006/picture"
MARKUP_COMPATIBILITY = "http://schemas.openxmlformats.org/markup-compatibility/2006"
VML = "urn:schemas-microsoft-com:vml"

NS = {
    "w": WORDPROCESSINGML,
    "r": OFFICE_DOCUMENT_RELATIONSHIPS,
    "pr": PACKAGE_RELATIONSHIPS,
    "ct": CONTENT_TYPES,
    "wp": WORDPROCESSING_DRAWING,
    "a": DRAWINGML,
    "pic": DRAWINGML_PICTURE,
    "mc": MARKUP_COMPATIBILITY,
    "v": VML,
}


def w_tag(local_name: str) -> str:
    """Retourner un nom qualifié WordprocessingML."""
    return f"{{{WORDPROCESSINGML}}}{local_name}"


def r_tag(local_name: str) -> str:
    """Retourner un nom qualifié de relations Office."""
    return f"{{{OFFICE_DOCUMENT_RELATIONSHIPS}}}{local_name}"
