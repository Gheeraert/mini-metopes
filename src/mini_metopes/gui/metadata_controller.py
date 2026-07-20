"""Operations testables de l'editeur de metadonnees, sans widget Tkinter."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from mini_metopes.docx import inspect_docx_file
from mini_metopes.metadata import (
    METADATA_SCHEMA_VERSION,
    Affiliation,
    Contributor,
    DocumentMetadata,
    InstitutionalProfile,
    MetadataIssue,
    MetadataSuggestions,
    MetadataValidationResult,
    SourceDocument,
    apply_institutional_profile,
    compute_file_sha256,
    default_metadata_path,
    extract_metadata_suggestions,
    load_institutional_profile,
    load_metadata_file,
    metadata_consistency_issues,
    resolve_source_document_path,
    source_document_reference,
    validate_metadata,
    write_metadata_file,
)
from mini_metopes.tei import (
    TeiConversionResult,
    TeiWriteResult,
    convert_docx_to_tei,
    write_tei_conversion_result,
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
    metadata_file_exists: bool = False


def create_initial_metadata_state(docx_path: Path, metadata_path: Path | None = None) -> MetadataEditorState:
    """Creer le pre-remplissage depuis le DOCX lorsqu'aucun JSON n'existe."""
    inspection = inspect_docx_file(docx_path)
    suggestions = extract_metadata_suggestions(inspection)
    path = metadata_path or default_metadata_path(docx_path)
    metadata = DocumentMetadata(
        schema_version=METADATA_SCHEMA_VERSION,
        source=SourceDocument(source_document_reference(docx_path, path), compute_file_sha256(docx_path)),
        document_type="chapter", language="fr", title=suggestions.title or "", subtitle=suggestions.subtitle,
    )
    return MetadataEditorState(
        docx_path,
        path,
        metadata,
        suggestions,
        _deduplicate_issues(suggestions.diagnostics),
        saved_metadata=metadata,
        metadata_file_exists=False,
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
            metadata_file_exists=True,
        )
    issues = loaded.issues + suggestions.diagnostics + metadata_consistency_issues(loaded.metadata, docx_path, suggestions)
    return MetadataEditorState(
        docx_path,
        path,
        loaded.metadata,
        suggestions,
        _deduplicate_issues(issues),
        saved_metadata=loaded.metadata,
        metadata_file_exists=True,
    )


def locate_source_document(metadata_path: Path) -> tuple[Path | None, tuple[MetadataIssue, ...]]:
    """Resoudre le DOCX designe par un JSON ; None s'il est introuvable.

    Le chemin relatif du JSON est resolu par rapport a son emplacement.
    L'appelant (GUI) peut proposer une relocalisation quand le resultat est
    ``None`` ; aucune recherche heuristique n'est faite.
    """
    loaded = load_metadata_file(metadata_path)
    if loaded.metadata is None:
        return None, loaded.issues
    candidate = resolve_source_document_path(loaded.metadata.source.path, metadata_path)
    if candidate.is_file():
        return candidate, ()
    return None, (
        MetadataIssue(
            "source_document_not_found",
            "warning",
            f"DOCX introuvable : {candidate}",
            "source_document.path",
        ),
    )


def relocate_source_document(state: MetadataEditorState, docx_path: Path) -> MetadataEditorState:
    """Pointer l'etat vers un DOCX relocalise sans toucher au JSON sur disque."""
    inspection = inspect_docx_file(docx_path)
    suggestions = extract_metadata_suggestions(inspection)
    metadata = replace(
        state.metadata,
        source=SourceDocument(
            source_document_reference(docx_path, state.metadata_path),
            compute_file_sha256(docx_path),
        ),
    )
    return replace(state, docx_path=docx_path, metadata=metadata, suggestions=suggestions, dirty=True)


def apply_profile_to_state(state: MetadataEditorState, profile_path: Path) -> MetadataEditorState:
    """Completer l'etat avec un profil institutionnel, sans ecraser le document."""
    profile, issues = load_institutional_profile(profile_path)
    if profile is None:
        return replace(state, issues=_deduplicate_issues(state.issues + issues))
    merged = apply_institutional_profile(state.metadata, profile)
    return replace(state, metadata=merged, dirty=merged != state.metadata or state.dirty)


def validate_metadata_editor_state(state: MetadataEditorState) -> MetadataValidationResult:
    """Valider les valeurs du formulaire sans ecrire de JSON."""
    return validate_metadata(state.metadata)


def save_metadata_editor_state(state: MetadataEditorState) -> MetadataEditorState:
    """Mettre a jour volontairement le lien source puis ecrire atomiquement."""
    metadata = replace(
        state.metadata,
        source=SourceDocument(
            source_document_reference(state.docx_path, state.metadata_path),
            compute_file_sha256(state.docx_path),
        ),
    )
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
        metadata_file_exists=True,
    )


def requires_save_as(state: MetadataEditorState) -> bool:
    """Indiquer si l'action principale doit ouvrir « Enregistrer sous… »."""
    return not state.metadata_file_exists


def change_metadata_destination(state: MetadataEditorState, new_path: Path) -> MetadataEditorState:
    """Deplacer la destination du JSON sans rien ecrire sur disque.

    Le SHA-256 du DOCX est preserve (seul le chemin memorise change) et l'etat
    est marque modifie ; l'appelant reste responsable de l'enregistrement.
    """
    metadata = replace(
        state.metadata,
        source=SourceDocument(
            source_document_reference(state.docx_path, new_path),
            state.metadata.source.sha256,
        ),
    )
    return replace(state, metadata_path=new_path, metadata=metadata, dirty=True)


def update_metadata(state: MetadataEditorState, **changes: Any) -> MetadataEditorState:
    """Appliquer des remplacements immuables au modele et marquer l'etat."""
    metadata = replace(state.metadata, **changes)
    return replace(state, metadata=metadata, dirty=is_metadata_dirty(state.saved_metadata, metadata))


def move_item(items: tuple, index: int, delta: int) -> tuple:
    """Deplacer un element d'une liste ordonnee, sans sortir des bornes."""
    target = index + delta
    if not (0 <= index < len(items)) or not (0 <= target < len(items)):
        return items
    values = list(items)
    values[index], values[target] = values[target], values[index]
    return tuple(values)


def next_identifier(prefix: str, identifiers: tuple[str, ...]) -> str:
    """Proposer le prochain identifiant stable sans UUID aleatoire."""
    number = 1
    known = set(identifiers)
    while f"{prefix}-{number}" in known:
        number += 1
    return f"{prefix}-{number}"


def add_contributor(state: MetadataEditorState, contributor: Contributor) -> MetadataEditorState:
    _ensure_new_identifier(
        contributor.contributor_id,
        tuple(item.contributor_id for item in state.metadata.contributors),
        duplicate_message="identifiant de contributeur deja utilise",
        invalid_message="identifiant de contributeur invalide",
    )
    return update_metadata(state, contributors=state.metadata.contributors + (contributor,))


def update_contributor(state: MetadataEditorState, original_id: str, contributor: Contributor) -> MetadataEditorState:
    if contributor.contributor_id != original_id and any(
        item.contributor_id == contributor.contributor_id for item in state.metadata.contributors
    ):
        raise ValueError("identifiant de contributeur deja utilise")
    return update_metadata(
        state,
        contributors=tuple(contributor if item.contributor_id == original_id else item for item in state.metadata.contributors),
    )


def remove_contributor(state: MetadataEditorState, contributor_id: str) -> MetadataEditorState:
    return update_metadata(state, contributors=tuple(item for item in state.metadata.contributors if item.contributor_id != contributor_id))


def add_affiliation(state: MetadataEditorState, affiliation: Affiliation) -> MetadataEditorState:
    _ensure_new_identifier(
        affiliation.affiliation_id,
        tuple(item.affiliation_id for item in state.metadata.affiliations),
        duplicate_message="identifiant d'affiliation deja utilise",
        invalid_message="identifiant d'affiliation invalide",
    )
    return update_metadata(state, affiliations=state.metadata.affiliations + (affiliation,))


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
    return update_metadata(
        state,
        contributors=contributors,
        affiliations=tuple(affiliation if item.affiliation_id == original_id else item for item in state.metadata.affiliations),
    )


def remove_affiliation(state: MetadataEditorState, affiliation_id: str) -> MetadataEditorState:
    """Refuser une suppression qui laisserait une reference pendante."""
    if any(affiliation_id in item.affiliation_ids for item in state.metadata.contributors):
        raise ValueError("affiliation encore utilisee par un contributeur")
    return update_metadata(state, affiliations=tuple(item for item in state.metadata.affiliations if item.affiliation_id != affiliation_id))


def is_metadata_dirty(saved: DocumentMetadata | None, current: DocumentMetadata) -> bool:
    """Comparer deux etats pour piloter la fermeture de la fenetre."""
    return saved != current


def _ensure_new_identifier(
    candidate: str,
    existing: tuple[str, ...],
    *,
    duplicate_message: str,
    invalid_message: str,
) -> None:
    normalized = candidate.strip()
    if not normalized or normalized != candidate:
        raise ValueError(invalid_message)
    if normalized in {value.strip() for value in existing}:
        raise ValueError(duplicate_message)


@dataclass(frozen=True)
class TeiGenerationOutcome:
    """Bilan structure d'une generation TEI Commons Publishing depuis la GUI."""

    result: TeiConversionResult
    write_result: TeiWriteResult | None
    output_path: Path

    @property
    def is_successful(self) -> bool:
        """Indiquer si un XML valide a effectivement ete ecrit au chemin demande."""
        return self.result.is_successful and self.write_result is not None


def generate_tei_commons(docx_path: Path, metadata: DocumentMetadata, output_path: Path) -> TeiGenerationOutcome:
    """Convertir un DOCX en TEI Commons Publishing puis ecrire le resultat s'il est valide.

    Reutilise directement ``convert_docx_to_tei`` et ``write_tei_conversion_result``
    (le meme coeur que la CLI ``convert-docx``) : aucun XML n'est ecrit lorsque
    la conversion echoue.
    """
    result = convert_docx_to_tei(docx_path, metadata=metadata)
    write_result: TeiWriteResult | None = None
    if result.is_successful:
        write_result = write_tei_conversion_result(result, output_path)
    return TeiGenerationOutcome(result=result, write_result=write_result, output_path=output_path)


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
