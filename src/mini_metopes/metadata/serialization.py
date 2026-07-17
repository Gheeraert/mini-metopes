"""Lecture, ecriture atomique et JSON deterministe des metadonnees."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .model import Affiliation, Contributor, DocumentMetadata, MetadataIssue, MetadataLoadResult, MetadataSource
from .validation import normalize_orcid, validate_metadata


def metadata_to_data(metadata: DocumentMetadata) -> dict[str, Any]:
    """Transformer le modele en dictionnaire JSON public stable."""
    return {
        "schema_version": metadata.schema_version,
        "source": {"filename": metadata.source.filename, "sha256": metadata.source.sha256},
        "document": {
            "type": metadata.document_type,
            "language": metadata.language,
            "title": metadata.title,
            "subtitle": metadata.subtitle,
            "abstract": metadata.abstract,
            "keywords": list(metadata.keywords),
        },
        "contributors": [
            {"id": item.contributor_id, "role": item.role, "given_name": item.given_name, "family_name": item.family_name,
             "literal_name": item.literal_name, "orcid": normalize_orcid(item.orcid) if item.orcid else None,
             "affiliations": list(item.affiliation_ids)}
            for item in metadata.contributors
        ],
        "affiliations": [
            {"id": item.affiliation_id, "name": item.name, "unit": item.unit, "city": item.city,
             "country": item.country, "ror": item.ror}
            for item in metadata.affiliations
        ],
    }


def metadata_to_json(metadata: DocumentMetadata) -> str:
    """Serialiser un modele valide dans un JSON UTF-8 lisible et stable."""
    validation = validate_metadata(metadata)
    if not validation.valid:
        raise ValueError("metadonnees invalides : " + ", ".join(issue.code for issue in validation.issues))
    return json.dumps(metadata_to_data(metadata), ensure_ascii=False, indent=2) + "\n"


def metadata_from_json(data: str) -> MetadataLoadResult:
    """Charger et valider du JSON sans propager les erreurs utilisateur attendues."""
    try:
        payload = json.loads(data)
    except json.JSONDecodeError as error:
        return MetadataLoadResult(None, (MetadataIssue("invalid_json", "error", error.msg, None),))
    decoded = _decode_metadata_payload(payload)
    if decoded.issues:
        return MetadataLoadResult(None, decoded.issues)
    metadata = decoded.metadata
    assert metadata is not None
    validation = validate_metadata(metadata)
    return MetadataLoadResult(metadata if validation.valid else None, validation.issues)


@dataclass(frozen=True)
class _DecodedMetadata:
    metadata: DocumentMetadata | None
    issues: tuple[MetadataIssue, ...]


def _decode_metadata_payload(payload: object) -> _DecodedMetadata:
    issues: list[MetadataIssue] = []
    root = _require_object(payload, "$", issues)
    if root is None:
        return _DecodedMetadata(None, tuple(issues))
    source = _require_object(_field(root, "source", issues, "$"), "source", issues)
    document = _require_object(_field(root, "document", issues, "$"), "document", issues)
    contributors_data = _array(_field(root, "contributors", issues, "$"), "contributors", issues)
    affiliations_data = _array(_field(root, "affiliations", issues, "$"), "affiliations", issues)
    if source is None or document is None or contributors_data is None or affiliations_data is None:
        return _DecodedMetadata(None, tuple(issues))

    contributors = tuple(_decode_contributor(item, index, issues) for index, item in enumerate(contributors_data))
    affiliations = tuple(_decode_affiliation(item, index, issues) for index, item in enumerate(affiliations_data))
    if issues:
        return _DecodedMetadata(None, tuple(issues))
    return _DecodedMetadata(
        DocumentMetadata(
            schema_version=_string(_field(root, "schema_version", issues, "$"), "schema_version", issues) or "",
            source=MetadataSource(
                filename=_string(_field(source, "filename", issues, "source"), "source.filename", issues) or "",
                sha256=_string(_field(source, "sha256", issues, "source"), "source.sha256", issues) or "",
            ),
            document_type=_string(_field(document, "type", issues, "document"), "document.type", issues) or "",
            language=_string(_field(document, "language", issues, "document"), "document.language", issues) or "",
            title=_string(_field(document, "title", issues, "document"), "document.title", issues) or "",
            subtitle=_optional_string(document.get("subtitle"), "document.subtitle", issues),
            abstract=_optional_string(document.get("abstract"), "document.abstract", issues),
            keywords=_string_array(document.get("keywords", ()), "document.keywords", issues) or (),
            contributors=contributors,
            affiliations=affiliations,
        ),
        tuple(issues),
    )


def _decode_contributor(value: object, index: int, issues: list[MetadataIssue]) -> Contributor:
    path = f"contributors[{index}]"
    item = _require_object(value, path, issues)
    if item is None:
        return Contributor("", "", None, None, None, None, ())
    return Contributor(
        contributor_id=_string(_field(item, "id", issues, path), f"{path}.id", issues) or "",
        role=_string(_field(item, "role", issues, path), f"{path}.role", issues) or "",
        given_name=_optional_string(item.get("given_name"), f"{path}.given_name", issues),
        family_name=_optional_string(item.get("family_name"), f"{path}.family_name", issues),
        literal_name=_optional_string(item.get("literal_name"), f"{path}.literal_name", issues),
        orcid=_optional_string(item.get("orcid"), f"{path}.orcid", issues),
        affiliation_ids=_string_array(item.get("affiliations", ()), f"{path}.affiliations", issues) or (),
    )


def _decode_affiliation(value: object, index: int, issues: list[MetadataIssue]) -> Affiliation:
    path = f"affiliations[{index}]"
    item = _require_object(value, path, issues)
    if item is None:
        return Affiliation("", "")
    return Affiliation(
        affiliation_id=_string(_field(item, "id", issues, path), f"{path}.id", issues) or "",
        name=_string(_field(item, "name", issues, path), f"{path}.name", issues) or "",
        unit=_optional_string(item.get("unit"), f"{path}.unit", issues),
        city=_optional_string(item.get("city"), f"{path}.city", issues),
        country=_optional_string(item.get("country"), f"{path}.country", issues),
        ror=_optional_string(item.get("ror"), f"{path}.ror", issues),
    )


def _field(data: dict[str, object], name: str, issues: list[MetadataIssue], parent_path: str) -> object | None:
    if name not in data:
        path = name if parent_path == "$" else f"{parent_path}.{name}"
        issues.append(MetadataIssue("missing_metadata_field", "error", "champ obligatoire absent", path))
        return None
    return data[name]


def _require_object(value: object, path: str, issues: list[MetadataIssue]) -> dict[str, object] | None:
    if isinstance(value, dict):
        return value
    issues.append(MetadataIssue("invalid_metadata_structure", "error", "objet JSON attendu", None if path == "$" else path))
    return None


def _string(value: object, path: str, issues: list[MetadataIssue]) -> str | None:
    if isinstance(value, str):
        return value
    issues.append(MetadataIssue("invalid_field_type", "error", "chaine attendue", path))
    return None


def _optional_string(value: object, path: str, issues: list[MetadataIssue]) -> str | None:
    if value is None:
        return None
    return _string(value, path, issues)


def _array(value: object, path: str, issues: list[MetadataIssue]) -> list[object] | None:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    issues.append(MetadataIssue("invalid_field_type", "error", "tableau attendu", path))
    return None


def _string_array(value: object, path: str, issues: list[MetadataIssue]) -> tuple[str, ...] | None:
    items = _array(value, path, issues)
    if items is None:
        return None
    result: list[str] = []
    for index, item in enumerate(items):
        text = _string(item, f"{path}[{index}]", issues)
        if text is not None:
            result.append(text)
    return tuple(result)


def load_metadata_file(path: Path) -> MetadataLoadResult:
    """Lire un JSON de metadonnees UTF-8."""
    try:
        return metadata_from_json(path.read_text(encoding="utf-8"))
    except OSError as error:
        return MetadataLoadResult(None, (MetadataIssue("metadata_file_unreadable", "error", str(error), None),))


def write_metadata_file(metadata: DocumentMetadata, path: Path) -> None:
    """Ecrire atomiquement un JSON valide et preserver la cible en cas d'echec."""
    content = metadata_to_json(metadata).encode("utf-8")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=path.parent, prefix=f".{path.name}.", delete=False) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, path)
    except OSError:
        if temporary_path:
            temporary_path.unlink(missing_ok=True)
        raise
