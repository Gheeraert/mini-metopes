"""Interface optionnelle, isolee des regles metier."""

from .metadata_editor import open_metadata_editor, run_metadata_editor
from .metadata_editor_api import MetadataEditorResult

__all__ = ["MetadataEditorResult", "open_metadata_editor", "run_metadata_editor"]
