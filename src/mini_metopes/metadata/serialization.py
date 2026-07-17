"""Lecture, ecriture atomique et JSON deterministe des metadonnees."""

from __future__ import annotations

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
    try:
        source = payload["source"]
        document = payload["document"]
        metadata = DocumentMetadata(
            schema_version=payload["schema_version"],
            source=MetadataSource(filename=source["filename"], sha256=source["sha256"]),
            document_type=document["type"], language=document["language"], title=document["title"],
            subtitle=document.get("subtitle"), abstract=document.get("abstract"),
            keywords=tuple(document.get("keywords", ())),
            contributors=tuple(Contributor(
                contributor_id=item["id"], role=item["role"], given_name=item.get("given_name"),
                family_name=item.get("family_name"), literal_name=item.get("literal_name"),
                orcid=item.get("orcid"), affiliation_ids=tuple(item.get("affiliations", ()))
            ) for item in payload.get("contributors", ())),
            affiliations=tuple(Affiliation(
                affiliation_id=item["id"], name=item["name"], unit=item.get("unit"), city=item.get("city"),
                country=item.get("country"), ror=item.get("ror")
            ) for item in payload.get("affiliations", ())),
        )
    except (KeyError, TypeError) as error:
        return MetadataLoadResult(None, (MetadataIssue("invalid_metadata_structure", "error", str(error), None),))
    validation = validate_metadata(metadata)
    return MetadataLoadResult(metadata if validation.valid else None, validation.issues)


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
