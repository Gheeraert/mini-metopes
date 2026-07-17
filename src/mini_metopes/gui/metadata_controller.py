"""Operations testables de l'editeur de metadonnees, sans widget Tkinter."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from mini_metopes.docx import inspect_docx_file
from mini_metopes.metadata import (
    METADATA_SCHEMA_VERSION,
    Affiliation,
    Contributor,
    DocumentMetadata,
    MetadataIssue,
    MetadataSuggestions,
    MetadataValidationResult,
    MetadataSource,
    compute_file_sha256,
    default_metadata_path,
    extract_metadata_suggestions,
    load_metadata_file,
    validate_metadata,
    write_metadata_file,
)


@dataclass(frozen=True)
class MetadataEditorState:
    """Etat editable sans effets de bord de la fenetre de metadonnees."""

    docx_path: Path
    metadata_path: Path
    metadata: DocumentMetadata
    suggestions: MetadataSuggestions
    issues: tuple[MetadataIssue, ...] = ()
    dirty: bool = False


def create_initial_metadata_state(docx_path: Path, metadata_path: Path | None = None) -> MetadataEditorState:
    """Creer le pre-remplissage depuis le DOCX lorsqu'aucun JSON n'existe."""
    inspection = inspect_docx_file(docx_path)
    suggestions = extract_metadata_suggestions(inspection)
    metadata = DocumentMetadata(
        schema_version=METADATA_SCHEMA_VERSION,
        source=MetadataSource(docx_path.name, compute_file_sha256(docx_path)),
        document_type="chapter", language="fr", title=suggestions.title or "", subtitle=suggestions.subtitle,
    )
    return MetadataEditorState(docx_path, metadata_path or default_metadata_path(docx_path), metadata, suggestions, suggestions.diagnostics)


def load_metadata_editor_state(docx_path: Path, metadata_path: Path | None = None) -> MetadataEditorState:
    """Charger le JSON existant sans le remplacer par les suggestions Word."""
    path = metadata_path or default_metadata_path(docx_path)
    if not path.exists():
        return create_initial_metadata_state(docx_path, path)
    inspection = inspect_docx_file(docx_path)
    suggestions = extract_metadata_suggestions(inspection)
    loaded = load_metadata_file(path)
    if loaded.metadata is None:
        return MetadataEditorState(docx_path, path, create_initial_metadata_state(docx_path, path).metadata, suggestions, loaded.issues)
    return MetadataEditorState(docx_path, path, loaded.metadata, suggestions, loaded.issues)


def validate_metadata_editor_state(state: MetadataEditorState) -> MetadataValidationResult:
    """Valider les valeurs du formulaire sans ecrire de JSON."""
    return validate_metadata(state.metadata)


def save_metadata_editor_state(state: MetadataEditorState) -> MetadataEditorState:
    """Mettre a jour volontairement l'empreinte puis ecrire le JSON atomiquement."""
    metadata = replace(state.metadata, source=MetadataSource(state.docx_path.name, compute_file_sha256(state.docx_path)))
    validation = validate_metadata(metadata)
    if not validation.valid:
        return replace(state, metadata=metadata, issues=validation.issues)
    write_metadata_file(metadata, state.metadata_path)
    return replace(state, metadata=metadata, issues=(), dirty=False)


def next_identifier(prefix: str, identifiers: tuple[str, ...]) -> str:
    """Proposer le prochain identifiant stable sans UUID aleatoire."""
    number = 1
    known = set(identifiers)
    while f"{prefix}-{number}" in known:
        number += 1
    return f"{prefix}-{number}"


def add_contributor(state: MetadataEditorState, contributor: Contributor) -> MetadataEditorState:
    return replace(state, metadata=replace(state.metadata, contributors=state.metadata.contributors + (contributor,)), dirty=True)


def update_contributor(state: MetadataEditorState, contributor: Contributor) -> MetadataEditorState:
    return replace(state, metadata=replace(state.metadata, contributors=tuple(contributor if item.contributor_id == contributor.contributor_id else item for item in state.metadata.contributors)), dirty=True)


def remove_contributor(state: MetadataEditorState, contributor_id: str) -> MetadataEditorState:
    return replace(state, metadata=replace(state.metadata, contributors=tuple(item for item in state.metadata.contributors if item.contributor_id != contributor_id)), dirty=True)


def add_affiliation(state: MetadataEditorState, affiliation: Affiliation) -> MetadataEditorState:
    return replace(state, metadata=replace(state.metadata, affiliations=state.metadata.affiliations + (affiliation,)), dirty=True)


def update_affiliation(state: MetadataEditorState, affiliation: Affiliation) -> MetadataEditorState:
    return replace(state, metadata=replace(state.metadata, affiliations=tuple(affiliation if item.affiliation_id == affiliation.affiliation_id else item for item in state.metadata.affiliations)), dirty=True)


def remove_affiliation(state: MetadataEditorState, affiliation_id: str) -> MetadataEditorState:
    """Refuser une suppression qui laisserait une reference pendante."""
    if any(affiliation_id in item.affiliation_ids for item in state.metadata.contributors):
        raise ValueError("affiliation encore utilisee par un contributeur")
    return replace(state, metadata=replace(state.metadata, affiliations=tuple(item for item in state.metadata.affiliations if item.affiliation_id != affiliation_id)), dirty=True)
