"""Lecture, ecriture atomique et JSON deterministe des metadonnees (v2)."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .model import (
    Abstract,
    Affiliation,
    Collection,
    Contributor,
    DocumentMetadata,
    EditorialResponsibility,
    Identifier,
    KeywordGroup,
    License,
    MetadataIssue,
    MetadataLoadResult,
    Pagination,
    Publication,
    Publisher,
    Rights,
    SourceDocument,
)
from .validation import normalize_orcid, validate_metadata


def metadata_to_data(metadata: DocumentMetadata) -> dict[str, Any]:
    """Transformer le modele en dictionnaire JSON public stable.

    Les groupes facultatifs entierement absents ne sont pas emis : le JSON
    reste lisible et ne contient pas de structures vides factices.
    """
    data: dict[str, Any] = {
        "schema_version": metadata.schema_version,
        "source_document": {"path": metadata.source.path, "sha256": metadata.source.sha256},
        "document": {
            "type": metadata.document_type,
            "language": metadata.language,
            "title": metadata.title,
            "subtitle": metadata.subtitle,
        },
        "contributors": [
            _drop_empty({
                "id": item.contributor_id,
                "role": item.role,
                "role_label": item.role_label,
                "given_name": item.given_name,
                "family_name": item.family_name,
                "literal_name": item.literal_name,
                "orcid": normalize_orcid(item.orcid) if item.orcid else None,
                "email": item.email,
                "affiliations": list(item.affiliation_ids),
            }, keep=("id", "role", "affiliations"))
            for item in metadata.contributors
        ],
        "affiliations": [
            _drop_empty({
                "id": item.affiliation_id,
                "name": item.name,
                "unit": item.unit,
                "city": item.city,
                "country": item.country,
                "ror": item.ror,
            }, keep=("id", "name"))
            for item in metadata.affiliations
        ],
    }
    if metadata.editorial_responsibility:
        data["editorial_responsibility"] = [
            {"responsibility": item.responsibility, "name": item.name}
            for item in metadata.editorial_responsibility
        ]
    publication = _publication_to_data(metadata.publication)
    if publication:
        data["publication"] = publication
    if metadata.identifiers:
        data["identifiers"] = [
            {"type": item.identifier_type, "value": item.value, "format": item.identifier_format}
            for item in metadata.identifiers
        ]
    rights = _rights_to_data(metadata.rights)
    if rights:
        data["rights"] = rights
    if metadata.abstracts:
        data["abstracts"] = [
            {"type": item.abstract_type, "language": item.language, "text": item.text}
            for item in metadata.abstracts
        ]
    if metadata.keywords:
        data["keywords"] = [
            {"language": group.language, "scheme": group.scheme, "items": list(group.items)}
            for group in metadata.keywords
        ]
    if metadata.collection is not None:
        data["collection"] = _drop_empty({
            "title": metadata.collection.title,
            "issn": metadata.collection.issn,
            "volume": metadata.collection.volume,
        }, keep=("title",))
    if metadata.pagination is not None:
        if metadata.pagination.extent is not None:
            data["pagination"] = {"extent": metadata.pagination.extent}
        else:
            data["pagination"] = {"from": metadata.pagination.page_from, "to": metadata.pagination.page_to}
    return data


def _publication_to_data(publication: Publication) -> dict[str, Any]:
    publisher = _drop_empty({
        "name": publication.publisher.name,
        "place": publication.publisher.place,
        "address": list(publication.publisher.address),
        "url": publication.publisher.url,
    }, keep=())
    result = _drop_empty({
        "publisher": publisher or None,
        "publication_date": publication.publication_date,
    }, keep=())
    return result


def _rights_to_data(rights: Rights) -> dict[str, Any]:
    license_data = _drop_empty({"name": rights.license.name, "url": rights.license.url}, keep=())
    return _drop_empty({
        "holder": rights.holder,
        "statement": rights.statement,
        "license": license_data or None,
    }, keep=())


def _drop_empty(data: dict[str, Any], *, keep: tuple[str, ...]) -> dict[str, Any]:
    return {
        key: value
        for key, value in data.items()
        if key in keep or (value is not None and value != [])
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
    if decoded.metadata is None:
        return MetadataLoadResult(None, decoded.issues)
    if decoded.issues:
        return MetadataLoadResult(None, decoded.issues)
    validation = validate_metadata(decoded.metadata)
    return MetadataLoadResult(decoded.metadata if validation.valid else None, validation.issues)


@dataclass(frozen=True)
class _DecodedMetadata:
    metadata: DocumentMetadata | None
    issues: tuple[MetadataIssue, ...]


def _decode_metadata_payload(payload: object) -> _DecodedMetadata:
    issues: list[MetadataIssue] = []
    root = _require_object(payload, "$", issues)
    if root is None:
        return _DecodedMetadata(None, tuple(issues))
    source = _require_object(_field(root, "source_document", issues, "$"), "source_document", issues)
    document = _require_object(_field(root, "document", issues, "$"), "document", issues)
    contributors_data = _array(_field(root, "contributors", issues, "$"), "contributors", issues)
    affiliations_data = _array(_field(root, "affiliations", issues, "$"), "affiliations", issues)
    if source is None or document is None or contributors_data is None or affiliations_data is None:
        return _DecodedMetadata(None, tuple(issues))

    contributors = tuple(_decode_contributor(item, index, issues) for index, item in enumerate(contributors_data))
    affiliations = tuple(_decode_affiliation(item, index, issues) for index, item in enumerate(affiliations_data))
    responsibilities = tuple(
        _decode_responsibility(item, index, issues)
        for index, item in enumerate(_optional_array(root, "editorial_responsibility", issues))
    )
    identifiers = tuple(
        _decode_identifier(item, index, issues)
        for index, item in enumerate(_optional_array(root, "identifiers", issues))
    )
    abstracts = tuple(
        _decode_abstract(item, index, issues)
        for index, item in enumerate(_optional_array(root, "abstracts", issues))
    )
    keywords = tuple(
        _decode_keyword_group(item, index, issues)
        for index, item in enumerate(_optional_array(root, "keywords", issues))
    )
    publication = _decode_publication(root.get("publication"), issues)
    rights = _decode_rights(root.get("rights"), issues)
    collection = _decode_collection(root.get("collection"), issues)
    pagination = _decode_pagination(root.get("pagination"), issues)
    if issues:
        return _DecodedMetadata(None, tuple(issues))
    return _DecodedMetadata(
        DocumentMetadata(
            schema_version=_string(_field(root, "schema_version", issues, "$"), "schema_version", issues) or "",
            source=SourceDocument(
                path=_string(_field(source, "path", issues, "source_document"), "source_document.path", issues) or "",
                sha256=_string(_field(source, "sha256", issues, "source_document"), "source_document.sha256", issues) or "",
            ),
            document_type=_string(_field(document, "type", issues, "document"), "document.type", issues) or "",
            language=_string(_field(document, "language", issues, "document"), "document.language", issues) or "",
            title=_string(_field(document, "title", issues, "document"), "document.title", issues) or "",
            subtitle=_optional_string(document.get("subtitle"), "document.subtitle", issues),
            contributors=contributors,
            affiliations=affiliations,
            editorial_responsibility=responsibilities,
            publication=publication,
            identifiers=identifiers,
            rights=rights,
            abstracts=abstracts,
            keywords=keywords,
            collection=collection,
            pagination=pagination,
        ),
        tuple(issues),
    )


def _decode_contributor(value: object, index: int, issues: list[MetadataIssue]) -> Contributor:
    path = f"contributors[{index}]"
    item = _require_object(value, path, issues)
    if item is None:
        return Contributor("", "")
    return Contributor(
        contributor_id=_string(_field(item, "id", issues, path), f"{path}.id", issues) or "",
        role=_string(_field(item, "role", issues, path), f"{path}.role", issues) or "",
        given_name=_optional_string(item.get("given_name"), f"{path}.given_name", issues),
        family_name=_optional_string(item.get("family_name"), f"{path}.family_name", issues),
        literal_name=_optional_string(item.get("literal_name"), f"{path}.literal_name", issues),
        orcid=_optional_string(item.get("orcid"), f"{path}.orcid", issues),
        email=_optional_string(item.get("email"), f"{path}.email", issues),
        role_label=_optional_string(item.get("role_label"), f"{path}.role_label", issues),
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


def _decode_responsibility(value: object, index: int, issues: list[MetadataIssue]) -> EditorialResponsibility:
    path = f"editorial_responsibility[{index}]"
    item = _require_object(value, path, issues)
    if item is None:
        return EditorialResponsibility("", "")
    return EditorialResponsibility(
        responsibility=_string(_field(item, "responsibility", issues, path), f"{path}.responsibility", issues) or "",
        name=_string(_field(item, "name", issues, path), f"{path}.name", issues) or "",
    )


def _decode_identifier(value: object, index: int, issues: list[MetadataIssue]) -> Identifier:
    path = f"identifiers[{index}]"
    item = _require_object(value, path, issues)
    if item is None:
        return Identifier("", "")
    return Identifier(
        identifier_type=_string(_field(item, "type", issues, path), f"{path}.type", issues) or "",
        value=_string(_field(item, "value", issues, path), f"{path}.value", issues) or "",
        identifier_format=_optional_string(item.get("format"), f"{path}.format", issues),
    )


def _decode_abstract(value: object, index: int, issues: list[MetadataIssue]) -> Abstract:
    path = f"abstracts[{index}]"
    item = _require_object(value, path, issues)
    if item is None:
        return Abstract("", "", "")
    return Abstract(
        abstract_type=_string(_field(item, "type", issues, path), f"{path}.type", issues) or "",
        language=_string(_field(item, "language", issues, path), f"{path}.language", issues) or "",
        text=_string(_field(item, "text", issues, path), f"{path}.text", issues) or "",
    )


def _decode_keyword_group(value: object, index: int, issues: list[MetadataIssue]) -> KeywordGroup:
    path = f"keywords[{index}]"
    item = _require_object(value, path, issues)
    if item is None:
        return KeywordGroup("", ())
    scheme = _optional_string(item.get("scheme"), f"{path}.scheme", issues)
    return KeywordGroup(
        language=_string(_field(item, "language", issues, path), f"{path}.language", issues) or "",
        items=_string_array(_field(item, "items", issues, path) or [], f"{path}.items", issues) or (),
        scheme=scheme if scheme is not None else "keywords",
    )


def _decode_publication(value: object, issues: list[MetadataIssue]) -> Publication:
    if value is None:
        return Publication()
    item = _require_object(value, "publication", issues)
    if item is None:
        return Publication()
    publisher_value = item.get("publisher")
    publisher = Publisher()
    if publisher_value is not None:
        publisher_item = _require_object(publisher_value, "publication.publisher", issues)
        if publisher_item is not None:
            publisher = Publisher(
                name=_optional_string(publisher_item.get("name"), "publication.publisher.name", issues),
                place=_optional_string(publisher_item.get("place"), "publication.publisher.place", issues),
                address=_string_array(publisher_item.get("address", ()), "publication.publisher.address", issues) or (),
                url=_optional_string(publisher_item.get("url"), "publication.publisher.url", issues),
            )
    return Publication(
        publisher=publisher,
        publication_date=_optional_string(item.get("publication_date"), "publication.publication_date", issues),
    )


def _decode_rights(value: object, issues: list[MetadataIssue]) -> Rights:
    if value is None:
        return Rights()
    item = _require_object(value, "rights", issues)
    if item is None:
        return Rights()
    license_value = item.get("license")
    license_model = License()
    if license_value is not None:
        license_item = _require_object(license_value, "rights.license", issues)
        if license_item is not None:
            license_model = License(
                name=_optional_string(license_item.get("name"), "rights.license.name", issues),
                url=_optional_string(license_item.get("url"), "rights.license.url", issues),
            )
    return Rights(
        holder=_optional_string(item.get("holder"), "rights.holder", issues),
        statement=_optional_string(item.get("statement"), "rights.statement", issues),
        license=license_model,
    )


def _decode_collection(value: object, issues: list[MetadataIssue]) -> Collection | None:
    if value is None:
        return None
    item = _require_object(value, "collection", issues)
    if item is None:
        return None
    return Collection(
        title=_string(_field(item, "title", issues, "collection"), "collection.title", issues) or "",
        issn=_optional_string(item.get("issn"), "collection.issn", issues),
        volume=_optional_string(item.get("volume"), "collection.volume", issues),
    )


def _decode_pagination(value: object, issues: list[MetadataIssue]) -> Pagination | None:
    if value is None:
        return None
    item = _require_object(value, "pagination", issues)
    if item is None:
        return None
    return Pagination(
        page_from=_optional_integer(item.get("from"), "pagination.from", issues),
        page_to=_optional_integer(item.get("to"), "pagination.to", issues),
        extent=_optional_integer(item.get("extent"), "pagination.extent", issues),
    )


def _field(data: dict[str, object], name: str, issues: list[MetadataIssue], parent_path: str) -> object | None:
    if name not in data:
        path = name if parent_path == "$" else f"{parent_path}.{name}"
        issues.append(MetadataIssue("missing_metadata_field", "error", "champ obligatoire absent", path))
        return None
    return data[name]


def _optional_array(data: dict[str, object], name: str, issues: list[MetadataIssue]) -> list[object]:
    if name not in data or data[name] is None:
        return []
    return _array(data[name], name, issues) or []


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


def _optional_integer(value: object, path: str, issues: list[MetadataIssue]) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    issues.append(MetadataIssue("invalid_field_type", "error", "entier attendu", path))
    return None


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
