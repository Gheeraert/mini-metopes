"""Validation deterministe des metadonnees Mini-Metopes."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from .model import (
    METADATA_SCHEMA_VERSION,
    Affiliation,
    Contributor,
    DocumentMetadata,
    MetadataIssue,
    MetadataValidationResult,
)

_DOCUMENT_TYPES = frozenset({"book", "chapter", "article", "front_matter", "back_matter", "other"})
_ROLES = frozenset({"author", "editor", "translator", "compiler", "contributor"})
_LANGUAGE_RE = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_ORCID_RE = re.compile(r"^(?:https://orcid\.org/)?(\d{4}-\d{4}-\d{4}-\d{3}[\dX])$")


def validate_metadata(metadata: DocumentMetadata) -> MetadataValidationResult:
    """Valider les contraintes que le JSON Schema ne peut pas exprimer seul."""
    issues: list[MetadataIssue] = []
    if metadata.schema_version != METADATA_SCHEMA_VERSION:
        issues.append(_error("unsupported_schema_version", "version de schema non prise en charge", "schema_version"))
    if not metadata.title.strip():
        issues.append(_error("missing_title", "titre obligatoire", "document.title"))
    if not metadata.language.strip():
        issues.append(_error("missing_language", "langue obligatoire", "document.language"))
    elif not _LANGUAGE_RE.fullmatch(metadata.language):
        issues.append(_error("invalid_language", "langue BCP 47 invalide", "document.language"))
    if metadata.document_type not in _DOCUMENT_TYPES:
        issues.append(_error("invalid_document_type", "type de document invalide", "document.type"))
    if not metadata.source.filename.strip():
        issues.append(_error("invalid_source_filename", "nom de fichier source obligatoire", "source.filename"))
    if not _SHA256_RE.fullmatch(metadata.source.sha256):
        issues.append(_error("invalid_source_sha256", "empreinte SHA-256 invalide", "source.sha256"))

    contributor_ids = [item.contributor_id for item in metadata.contributors]
    affiliation_ids = [item.affiliation_id for item in metadata.affiliations]
    _duplicates(contributor_ids, "duplicate_contributor_id", "contributors", issues)
    _duplicates(affiliation_ids, "duplicate_affiliation_id", "affiliations", issues)
    known_affiliations = set(affiliation_ids)
    for index, contributor in enumerate(metadata.contributors):
        _validate_contributor(contributor, index, known_affiliations, issues)
    for index, affiliation in enumerate(metadata.affiliations):
        _validate_affiliation(affiliation, index, issues)
    for index, keyword in enumerate(metadata.keywords):
        if not keyword.strip():
            issues.append(_error("invalid_keyword", "mot-cle vide", f"document.keywords[{index}]"))
    return MetadataValidationResult(not any(issue.severity == "error" for issue in issues), tuple(issues))


def normalize_orcid(value: str) -> str | None:
    """Normaliser un ORCID vers ses 16 caracteres et verifier sa cle ISO 7064."""
    match = _ORCID_RE.fullmatch(value.strip())
    if not match:
        return None
    compact = match.group(1)
    total = 0
    for character in compact.replace("-", "")[:-1]:
        total = (total + int(character)) * 2
    remainder = (12 - total % 11) % 11
    expected = "X" if remainder == 10 else str(remainder)
    return compact if compact[-1] == expected else None


def _validate_contributor(item: Contributor, index: int, known_affiliations: set[str], issues: list[MetadataIssue]) -> None:
    path = f"contributors[{index}]"
    if not item.contributor_id.strip():
        issues.append(_error("invalid_contributor_id", "identifiant de contributeur obligatoire", f"{path}.id"))
    if item.role not in _ROLES:
        issues.append(_error("invalid_contributor_role", "role de contributeur invalide", f"{path}.role"))
    literal = item.literal_name.strip() if item.literal_name else ""
    structured = bool((item.given_name or "").strip() or (item.family_name or "").strip())
    if bool(literal) == structured:
        issues.append(_error("invalid_contributor_name", "utiliser un nom litteral ou un nom structure", path))
    if item.orcid and normalize_orcid(item.orcid) is None:
        issues.append(_error("invalid_orcid", "ORCID invalide", f"{path}.orcid"))
    for affiliation_id in item.affiliation_ids:
        if affiliation_id not in known_affiliations:
            issues.append(_error("unknown_affiliation_reference", f"affiliation inconnue : {affiliation_id}", f"{path}.affiliations"))


def _validate_affiliation(item: Affiliation, index: int, issues: list[MetadataIssue]) -> None:
    path = f"affiliations[{index}]"
    if not item.affiliation_id.strip():
        issues.append(_error("invalid_affiliation_id", "identifiant d'affiliation obligatoire", f"{path}.id"))
    if not item.name.strip():
        issues.append(_error("invalid_affiliation_name", "institution obligatoire", f"{path}.name"))
    if item.ror:
        parsed = urlparse(item.ror)
        if parsed.scheme != "https" or not parsed.netloc:
            issues.append(_error("invalid_ror", "URL ROR invalide", f"{path}.ror"))


def _duplicates(values: list[str], code: str, path: str, issues: list[MetadataIssue]) -> None:
    for value in sorted({candidate for candidate in values if values.count(candidate) > 1}):
        issues.append(_error(code, f"identifiant duplique : {value}", path))


def _error(code: str, message: str, path: str) -> MetadataIssue:
    return MetadataIssue(code, "error", message, path)
