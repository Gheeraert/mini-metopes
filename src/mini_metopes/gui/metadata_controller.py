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
    metadata_consistency_issues,
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
    loaded_from_invalid_json: bool = False
    saved_metadata: DocumentMetadata | None = None


def create_initial_metadata_state(docx_path: Path, metadata_path: Path | None = None) -> MetadataEditorState:
    """Creer le pre-remplissage depuis le DOCX lorsqu'aucun JSON n'existe."""
    inspection = inspect_docx_file(docx_path)
    suggestions = extract_metadata_suggestions(inspection)
    metadata = DocumentMetadata(
        schema_version=METADATA_SCHEMA_VERSION,
        source=MetadataSource(docx_path.name, compute_file_sha256(docx_path)),
        document_type="chapter", language="fr", title=suggestions.title or "", subtitle=suggestions.subtitle,
    )
    return MetadataEditorState(
        docx_path,
        metadata_path or default_metadata_path(docx_path),
        metadata,
        suggestions,
        _deduplicate_issues(suggestions.diagnostics),
        saved_metadata=metadata,
    )


def load_metadata_editor_state(docx_path: Path, metadata_path: Path | None = None) -> MetadataEditorState:
    """Charger le JSON existant sans le remplacer par les suggestions Word."""
    path = metadata_path or default_metadata_path(docx_path)
    if not path.exists():
        return create_initial_metadata_state(docx_path, path)
    inspection = inspect_docx_file(docx_path)
    suggestions = extract_metadata_suggestions(inspection)
    loaded = load_metadata_file(path)
    if loaded.metadata is None:
        fallback = create_initial_metadata_state(docx_path, path).metadata
        return MetadataEditorState(
            docx_path,
            path,
            fallback,
            suggestions,
            _deduplicate_issues(loaded.issues + suggestions.diagnostics),
            loaded_from_invalid_json=True,
            saved_metadata=None,
        )
    issues = loaded.issues + suggestions.diagnostics + metadata_consistency_issues(loaded.metadata, docx_path, suggestions)
    return MetadataEditorState(
        docx_path,
        path,
        loaded.metadata,
        suggestions,
        _deduplicate_issues(issues),
        saved_metadata=loaded.metadata,
    )


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
    issues = state.suggestions.diagnostics + metadata_consistency_issues(metadata, state.docx_path, state.suggestions)
    return replace(
        state,
        metadata=metadata,
        issues=_deduplicate_issues(issues),
        dirty=False,
        loaded_from_invalid_json=False,
        saved_metadata=metadata,
    )


def next_identifier(prefix: str, identifiers: tuple[str, ...]) -> str:
    """Proposer le prochain identifiant stable sans UUID aleatoire."""
    number = 1
    known = set(identifiers)
    while f"{prefix}-{number}" in known:
        number += 1
    return f"{prefix}-{number}"


def add_contributor(state: MetadataEditorState, contributor: Contributor) -> MetadataEditorState:
    return replace(state, metadata=replace(state.metadata, contributors=state.metadata.contributors + (contributor,)), dirty=True)


def update_contributor(state: MetadataEditorState, original_id: str, contributor: Contributor) -> MetadataEditorState:
    if contributor.contributor_id != original_id and any(
        item.contributor_id == contributor.contributor_id for item in state.metadata.contributors
    ):
        raise ValueError("identifiant de contributeur deja utilise")
    return replace(
        state,
        metadata=replace(
            state.metadata,
            contributors=tuple(contributor if item.contributor_id == original_id else item for item in state.metadata.contributors),
        ),
        dirty=True,
    )


def remove_contributor(state: MetadataEditorState, contributor_id: str) -> MetadataEditorState:
    return replace(state, metadata=replace(state.metadata, contributors=tuple(item for item in state.metadata.contributors if item.contributor_id != contributor_id)), dirty=True)


def add_affiliation(state: MetadataEditorState, affiliation: Affiliation) -> MetadataEditorState:
    return replace(state, metadata=replace(state.metadata, affiliations=state.metadata.affiliations + (affiliation,)), dirty=True)


def update_affiliation(state: MetadataEditorState, original_id: str, affiliation: Affiliation) -> MetadataEditorState:
    if affiliation.affiliation_id != original_id and any(
        item.affiliation_id == affiliation.affiliation_id for item in state.metadata.affiliations
    ):
        raise ValueError("identifiant d'affiliation deja utilise")
    contributors = state.metadata.contributors
    if affiliation.affiliation_id != original_id:
        contributors = tuple(
            replace(
                contributor,
                affiliation_ids=tuple(
                    affiliation.affiliation_id if value == original_id else value for value in contributor.affiliation_ids
                ),
            )
            for contributor in contributors
        )
    return replace(
        state,
        metadata=replace(
            state.metadata,
            contributors=contributors,
            affiliations=tuple(affiliation if item.affiliation_id == original_id else item for item in state.metadata.affiliations),
        ),
        dirty=True,
    )


def remove_affiliation(state: MetadataEditorState, affiliation_id: str) -> MetadataEditorState:
    """Refuser une suppression qui laisserait une reference pendante."""
    if any(affiliation_id in item.affiliation_ids for item in state.metadata.contributors):
        raise ValueError("affiliation encore utilisee par un contributeur")
    return replace(state, metadata=replace(state.metadata, affiliations=tuple(item for item in state.metadata.affiliations if item.affiliation_id != affiliation_id)), dirty=True)


def is_metadata_dirty(saved: DocumentMetadata | None, current: DocumentMetadata) -> bool:
    """Comparer deux etats pour piloter la fermeture de la fenetre."""
    return saved != current


def _deduplicate_issues(issues: tuple[MetadataIssue, ...]) -> tuple[MetadataIssue, ...]:
    seen: set[tuple[str, str | None]] = set()
    result: list[MetadataIssue] = []
    for issue in issues:
        key = (issue.code, issue.path)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return tuple(result)
