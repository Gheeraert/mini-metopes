"""Profil institutionnel facultatif : valeurs stables hors du JSON document.

Le moteur generique ne depend d'aucune institution : un profil est un petit
fichier JSON explicite (par exemple ``profiles/purh.json``) fournissant des
valeurs par defaut que le JSON du document surcharge toujours.
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from .model import (
    DocumentMetadata,
    InstitutionalProfile,
    MetadataIssue,
    Publisher,
    Rights,
)


def load_institutional_profile(path: Path) -> tuple[InstitutionalProfile | None, tuple[MetadataIssue, ...]]:
    """Lire un profil institutionnel JSON sans propager les erreurs attendues."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        return None, (MetadataIssue("profile_file_unreadable", "error", str(error), None),)
    except json.JSONDecodeError as error:
        return None, (MetadataIssue("invalid_profile_json", "error", error.msg, None),)
    if not isinstance(payload, dict):
        return None, (MetadataIssue("invalid_profile_structure", "error", "objet JSON attendu", None),)
    issues: list[MetadataIssue] = []
    profile_id = payload.get("profile_id")
    if not isinstance(profile_id, str) or not profile_id.strip():
        issues.append(MetadataIssue("invalid_profile_id", "error", "identifiant de profil obligatoire", "profile_id"))
    publisher_data = payload.get("publisher", {})
    if not isinstance(publisher_data, dict):
        issues.append(MetadataIssue("invalid_profile_structure", "error", "objet JSON attendu", "publisher"))
        publisher_data = {}
    address = publisher_data.get("address", [])
    if not isinstance(address, list) or any(not isinstance(line, str) for line in address):
        issues.append(MetadataIssue("invalid_profile_structure", "error", "tableau de chaines attendu", "publisher.address"))
        address = []
    rights_holder = payload.get("rights_holder")
    if rights_holder is not None and not isinstance(rights_holder, str):
        issues.append(MetadataIssue("invalid_profile_structure", "error", "chaine attendue", "rights_holder"))
        rights_holder = None
    for key in ("name", "place", "url"):
        value = publisher_data.get(key)
        if value is not None and not isinstance(value, str):
            issues.append(MetadataIssue("invalid_profile_structure", "error", "chaine attendue", f"publisher.{key}"))
    if any(issue.severity == "error" for issue in issues):
        return None, tuple(issues)
    assert isinstance(profile_id, str)
    return (
        InstitutionalProfile(
            profile_id=profile_id.strip(),
            publisher=Publisher(
                name=publisher_data.get("name"),
                place=publisher_data.get("place"),
                address=tuple(address),
                url=publisher_data.get("url"),
            ),
            rights_holder=rights_holder,
        ),
        tuple(issues),
    )


def apply_institutional_profile(metadata: DocumentMetadata, profile: InstitutionalProfile) -> DocumentMetadata:
    """Completer les valeurs absentes du document, sans jamais les ecraser."""
    publisher = metadata.publication.publisher
    defaults = profile.publisher
    merged_publisher = Publisher(
        name=publisher.name if publisher.name is not None else defaults.name,
        place=publisher.place if publisher.place is not None else defaults.place,
        address=publisher.address if publisher.address else defaults.address,
        url=publisher.url if publisher.url is not None else defaults.url,
    )
    merged_rights: Rights = metadata.rights
    if merged_rights.holder is None and profile.rights_holder is not None:
        merged_rights = replace(merged_rights, holder=profile.rights_holder)
    return replace(
        metadata,
        publication=replace(metadata.publication, publisher=merged_publisher),
        rights=merged_rights,
    )
