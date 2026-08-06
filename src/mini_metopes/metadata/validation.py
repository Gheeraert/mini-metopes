"""Validation et normalisations deterministes des metadonnees Mini-Metopes.

Toutes les verifications sont locales : aucun appel reseau n'est effectue
pour DOI, ORCID, ROR ou URL de licence.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

from .model import (
    METADATA_SCHEMA_VERSION,
    Abstract,
    Affiliation,
    Collection,
    Contributor,
    DocumentMetadata,
    EditorialResponsibility,
    Funding,
    Identifier,
    KeywordGroup,
    License,
    MetadataIssue,
    MetadataValidationResult,
    Pagination,
    Publication,
    Rights,
)

_DOCUMENT_TYPES = frozenset({"article", "chapter", "introduction", "conclusion", "bibliography", "other"})
_ROLES = frozenset({"author", "editor", "translator", "scientific_editor", "other"})
_IDENTIFIER_TYPES = frozenset({"doi", "isbn-13", "isbn-10", "issn", "eissn", "local"})
_IDENTIFIER_FORMATS = frozenset({"print", "pdf", "epub", "html"})
_ABSTRACT_TYPES = frozenset({"summary", "abstract", "back-cover"})
_LANGUAGE_RE = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_ORCID_RE = re.compile(r"^(?:https://orcid\.org/)?(\d{4}-\d{4}-\d{4}-\d{3}[\dX])$")
_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
_DATE_RE = re.compile(r"^\d{4}(?:-(?:0[1-9]|1[0-2])(?:-(?:0[1-9]|[12]\d|3[01]))?)?$")
_ISSN_RE = re.compile(r"^\d{4}-?\d{3}[\dXx]$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SPDX_LICENSES: dict[str, tuple[str, str]] = {
    "CC-BY-4.0": ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
    "CC-BY-SA-4.0": ("CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/"),
    "CC-BY-ND-4.0": ("CC BY-ND 4.0", "https://creativecommons.org/licenses/by-nd/4.0/"),
    "CC-BY-NC-4.0": ("CC BY-NC 4.0", "https://creativecommons.org/licenses/by-nc/4.0/"),
    "CC-BY-NC-SA-4.0": ("CC BY-NC-SA 4.0", "https://creativecommons.org/licenses/by-nc-sa/4.0/"),
    "CC-BY-NC-ND-4.0": ("CC BY-NC-ND 4.0", "https://creativecommons.org/licenses/by-nc-nd/4.0/"),
    "CC0-1.0": ("CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"),
}
"""Sous-ensemble SPDX des licences Creative Commons 4.0 (et CC0 1.0).

Volontairement limite aux licences les plus frequentes en edition
universitaire francophone ; toute autre licence reste representable en
texte libre (``License.name``/``License.url``) sans ``spdx_id``.
"""


def validate_metadata(metadata: DocumentMetadata) -> MetadataValidationResult:
    """Valider les contraintes que le decodage JSON ne peut pas exprimer seul."""
    issues: list[MetadataIssue] = []
    if metadata.schema_version != METADATA_SCHEMA_VERSION:
        issues.append(_error("unsupported_schema_version", "version de schema non prise en charge", "schema_version"))
    if not metadata.title.strip():
        issues.append(_error("missing_title", "titre obligatoire", "document.title"))
    _validate_language(metadata.language, "document.language", issues, required=True)
    if metadata.document_type not in _DOCUMENT_TYPES:
        issues.append(_error("invalid_document_type", "type de document invalide", "document.type"))
    if not metadata.source.path.strip():
        issues.append(_error("invalid_source_path", "chemin du DOCX source obligatoire", "source_document.path"))
    if not _SHA256_RE.fullmatch(metadata.source.sha256):
        issues.append(_error("invalid_source_sha256", "empreinte SHA-256 invalide", "source_document.sha256"))

    contributor_ids = [item.contributor_id for item in metadata.contributors]
    affiliation_ids = [item.affiliation_id for item in metadata.affiliations]
    _duplicates(contributor_ids, "duplicate_contributor_id", "contributors", issues)
    _duplicates(affiliation_ids, "duplicate_affiliation_id", "affiliations", issues)
    known_affiliations = {value.strip() for value in affiliation_ids}
    for index, contributor in enumerate(metadata.contributors):
        _validate_contributor(contributor, index, known_affiliations, issues)
    for index, affiliation in enumerate(metadata.affiliations):
        _validate_affiliation(affiliation, index, issues)
    for index, responsibility in enumerate(metadata.editorial_responsibility):
        _validate_responsibility(responsibility, index, issues)
    _validate_publication(metadata.publication, issues)
    for index, identifier in enumerate(metadata.identifiers):
        _validate_identifier_entry(identifier, index, issues)
    _validate_identifier_duplicates(metadata.identifiers, issues)
    _validate_rights(metadata.rights, issues)
    for index, abstract in enumerate(metadata.abstracts):
        _validate_abstract(abstract, index, issues)
    for index, group in enumerate(metadata.keywords):
        _validate_keyword_group(group, index, issues)
    if metadata.collection is not None:
        _validate_collection(metadata.collection, issues)
    if metadata.pagination is not None:
        _validate_pagination(metadata.pagination, issues)
    for index, funding in enumerate(metadata.funding):
        _validate_funding(funding, index, issues)
    return MetadataValidationResult(not any(issue.severity == "error" for issue in issues), tuple(issues))


# ---------------------------------------------------------------------------
# Normalisations documentees


def normalize_orcid(value: str) -> str | None:
    """Normaliser un ORCID (URI admise) vers ``0000-0000-0000-000X``.

    La cle ISO 7064 mod 11-2 est verifiee ; retourne ``None`` si invalide.
    """
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


def normalize_doi(value: str) -> str | None:
    """Normaliser un DOI : URI ``doi.org`` ou prefixe ``doi:`` admis.

    Retourne la forme brute ``10.xxxx/suffixe`` sans resolution reseau,
    ou ``None`` si la forme est manifestement invalide.
    """
    candidate = value.strip()
    lowered = candidate.lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/", "doi:"):
        if lowered.startswith(prefix):
            candidate = candidate[len(prefix):]
            break
    return candidate if _DOI_RE.fullmatch(candidate) else None


def normalize_isbn(value: str) -> str | None:
    """Normaliser un ISBN : tirets et espaces retires, cle verifiee.

    Retourne les 10 ou 13 caracteres compacts, ou ``None`` si invalide.
    La forme avec tirets fournie par l'utilisateur est conservee dans le
    JSON ; la forme compacte ne sert qu'a la verification et a la TEI.
    """
    compact = re.sub(r"[\s-]", "", value).upper()
    if re.fullmatch(r"\d{13}", compact):
        checksum = sum(int(digit) * (1 if index % 2 == 0 else 3) for index, digit in enumerate(compact[:12]))
        return compact if (10 - checksum % 10) % 10 == int(compact[12]) else None
    if re.fullmatch(r"\d{9}[\dX]", compact):
        total = sum((10 - index) * (10 if digit == "X" else int(digit)) for index, digit in enumerate(compact))
        return compact if total % 11 == 0 else None
    return None


def normalize_issn(value: str) -> str | None:
    """Normaliser un ISSN vers ``NNNN-NNNC`` et verifier sa cle mod 11."""
    if not _ISSN_RE.fullmatch(value.strip()):
        return None
    compact = value.strip().replace("-", "").upper()
    total = sum((8 - index) * int(digit) for index, digit in enumerate(compact[:7]))
    remainder = (11 - total % 11) % 11
    expected = "X" if remainder == 10 else str(remainder)
    return f"{compact[:4]}-{compact[4:]}" if compact[7] == expected else None


def keyword_duplicate_pairs(items: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    """Reperer les mots-cles equivalents a la casse ou aux accents pres.

    Aucune deduplication automatique n'est faite : les paires signalees
    alimentent seulement un diagnostic d'avertissement.
    """
    seen: dict[str, str] = {}
    pairs: list[tuple[str, str]] = []
    for item in items:
        folded = "".join(
            char for char in unicodedata.normalize("NFKD", " ".join(item.casefold().split()))
            if not unicodedata.combining(char)
        )
        if folded in seen and seen[folded] != item:
            pairs.append((seen[folded], item))
        seen.setdefault(folded, item)
    return tuple(pairs)


# ---------------------------------------------------------------------------
# Validations par groupe


def _validate_contributor(item: Contributor, index: int, known_affiliations: set[str], issues: list[MetadataIssue]) -> None:
    path = f"contributors[{index}]"
    _validate_identifier(item.contributor_id, "invalid_contributor_id", f"{path}.id", issues)
    if not item.contributor_id.strip():
        issues.append(_error("invalid_contributor_id", "identifiant de contributeur obligatoire", f"{path}.id"))
    if item.role not in _ROLES:
        issues.append(_error("invalid_contributor_role", "role de contributeur invalide", f"{path}.role"))
    if item.role == "other" and not (item.role_label or "").strip():
        issues.append(_error("missing_contributor_role_label", "libelle obligatoire pour le role other", f"{path}.role_label"))
    literal = item.literal_name.strip() if item.literal_name else ""
    structured = bool((item.given_name or "").strip() or (item.family_name or "").strip())
    if bool(literal) == structured:
        issues.append(_error("invalid_contributor_name", "utiliser un nom litteral ou un nom structure", path))
    if item.orcid and normalize_orcid(item.orcid) is None:
        issues.append(_error("invalid_orcid", "ORCID invalide", f"{path}.orcid"))
    if item.email and not _EMAIL_RE.fullmatch(item.email.strip()):
        issues.append(_error("invalid_email", "adresse electronique invalide", f"{path}.email"))
    for affiliation_id in item.affiliation_ids:
        if affiliation_id.strip() != affiliation_id or not affiliation_id.strip():
            issues.append(_error("invalid_affiliation_reference", f"reference d'affiliation invalide : {affiliation_id}", f"{path}.affiliations"))
        elif affiliation_id.strip() not in known_affiliations:
            issues.append(_error("unknown_affiliation_reference", f"affiliation inconnue : {affiliation_id}", f"{path}.affiliations"))


def _validate_affiliation(item: Affiliation, index: int, issues: list[MetadataIssue]) -> None:
    path = f"affiliations[{index}]"
    _validate_identifier(item.affiliation_id, "invalid_affiliation_id", f"{path}.id", issues)
    if not item.affiliation_id.strip():
        issues.append(_error("invalid_affiliation_id", "identifiant d'affiliation obligatoire", f"{path}.id"))
    if not item.name.strip():
        issues.append(_error("invalid_affiliation_name", "institution obligatoire", f"{path}.name"))
    if item.ror:
        parsed = urlparse(item.ror)
        if (
            parsed.scheme != "https"
            or parsed.netloc not in {"ror.org", "www.ror.org"}
            or parsed.path.count("/") != 1
            or not parsed.path.strip("/")
            or parsed.params
            or parsed.query
            or parsed.fragment
        ):
            issues.append(_error("invalid_ror", "URL ROR invalide", f"{path}.ror"))


def _validate_responsibility(item: EditorialResponsibility, index: int, issues: list[MetadataIssue]) -> None:
    path = f"editorial_responsibility[{index}]"
    if not item.responsibility.strip():
        issues.append(_error("invalid_responsibility", "intitule de responsabilite obligatoire", f"{path}.responsibility"))
    if not item.name.strip():
        issues.append(_error("invalid_responsibility_name", "nom du ou de la responsable obligatoire", f"{path}.name"))


def _validate_publication(publication: Publication, issues: list[MetadataIssue]) -> None:
    publisher = publication.publisher
    if publisher.name is not None and not publisher.name.strip():
        issues.append(_error("invalid_publisher_name", "nom d'editeur vide", "publication.publisher.name"))
    if publisher.url:
        _validate_http_url(publisher.url, "invalid_publisher_url", "publication.publisher.url", issues)
    for index, line in enumerate(publisher.address):
        if not line.strip():
            issues.append(_error("invalid_publisher_address", "ligne d'adresse vide", f"publication.publisher.address[{index}]"))
    if publication.publication_date is not None and not _is_valid_partial_date(publication.publication_date):
        issues.append(_error("invalid_publication_date", "date attendue : AAAA, AAAA-MM ou AAAA-MM-JJ", "publication.publication_date"))


def _validate_identifier_entry(item: Identifier, index: int, issues: list[MetadataIssue]) -> None:
    path = f"identifiers[{index}]"
    if item.identifier_type not in _IDENTIFIER_TYPES:
        issues.append(_error("invalid_identifier_type", f"type d'identifiant inconnu : {item.identifier_type}", f"{path}.type"))
        return
    if item.identifier_format is not None and item.identifier_format not in _IDENTIFIER_FORMATS:
        issues.append(_error("invalid_identifier_format", f"format de publication inconnu : {item.identifier_format}", f"{path}.format"))
    if not item.value.strip():
        issues.append(_error("invalid_identifier_value", "valeur d'identifiant vide", f"{path}.value"))
        return
    if item.identifier_type == "doi" and normalize_doi(item.value) is None:
        issues.append(_error("invalid_doi", "DOI manifestement invalide", f"{path}.value"))
    if item.identifier_type in {"isbn-13", "isbn-10"}:
        normalized = normalize_isbn(item.value)
        expected_length = 13 if item.identifier_type == "isbn-13" else 10
        if normalized is None or len(normalized) != expected_length:
            issues.append(_error("invalid_isbn", "ISBN invalide (cle de controle ou longueur)", f"{path}.value"))
        elif item.identifier_format is None:
            issues.append(_error("missing_identifier_format", "format de publication obligatoire pour un ISBN", f"{path}.format"))
    if item.identifier_type in {"issn", "eissn"} and normalize_issn(item.value) is None:
        issues.append(_error("invalid_issn", "ISSN invalide", f"{path}.value"))


def _validate_rights(rights: Rights, issues: list[MetadataIssue]) -> None:
    if rights.holder is not None and not rights.holder.strip():
        issues.append(_error("invalid_rights_holder", "detenteur des droits vide", "rights.holder"))
    if rights.statement is not None and not rights.statement.strip():
        issues.append(_error("invalid_rights_statement", "mention de droits vide", "rights.statement"))
    if rights.license.name is not None and not rights.license.name.strip():
        issues.append(_error("invalid_license_name", "nom de licence vide", "rights.license.name"))
    if rights.license.url:
        _validate_http_url(rights.license.url, "invalid_license_url", "rights.license.url", issues)
    if rights.license.url and rights.license.name is None and rights.license.spdx_id is None:
        issues.append(_error("missing_license_name", "nom de licence obligatoire avec une URL", "rights.license.name"))
    _validate_license_spdx_id(rights.license, issues)


def _validate_license_spdx_id(license_: License, issues: list[MetadataIssue]) -> None:
    if license_.spdx_id is None:
        return
    canonical = SPDX_LICENSES.get(license_.spdx_id)
    if canonical is None:
        issues.append(_error("invalid_license_spdx_id", f"identifiant SPDX inconnu : {license_.spdx_id}", "rights.license.spdx_id"))
        return
    canonical_name, canonical_url = canonical
    if license_.name is not None and license_.name.strip() and license_.name.strip() != canonical_name:
        issues.append(MetadataIssue(
            "license_spdx_id_mismatch", "warning",
            f"nom de licence « {license_.name} » different du nom canonique « {canonical_name} » pour {license_.spdx_id}",
            "rights.license.name",
        ))
    if license_.url is not None and license_.url.strip() and license_.url.strip() != canonical_url:
        issues.append(MetadataIssue(
            "license_spdx_id_mismatch", "warning",
            f"URL de licence differente de l'URL canonique « {canonical_url} » pour {license_.spdx_id}",
            "rights.license.url",
        ))


def resolved_license(license_: License) -> License:
    """Completer name/url depuis spdx_id quand ils sont absents, sans ecraser une valeur explicite.

    Utilisee a la serialisation pour eviter de dupliquer le registre
    ``SPDX_LICENSES`` : la validation se contente de signaler les
    incoherences (avertissement), jamais de corriger silencieusement une
    valeur deja renseignee.
    """
    if license_.spdx_id is None:
        return license_
    canonical = SPDX_LICENSES.get(license_.spdx_id)
    if canonical is None:
        return license_
    canonical_name, canonical_url = canonical
    return License(
        name=license_.name if license_.name is not None else canonical_name,
        url=license_.url if license_.url is not None else canonical_url,
        spdx_id=license_.spdx_id,
    )


def _validate_abstract(item: Abstract, index: int, issues: list[MetadataIssue]) -> None:
    path = f"abstracts[{index}]"
    if item.abstract_type not in _ABSTRACT_TYPES:
        issues.append(_error("invalid_abstract_type", f"type de resume inconnu : {item.abstract_type}", f"{path}.type"))
    _validate_language(item.language, f"{path}.language", issues, required=True)
    if not item.text.strip():
        issues.append(_error("empty_abstract", "resume vide", f"{path}.text"))


def _validate_keyword_group(group: KeywordGroup, index: int, issues: list[MetadataIssue]) -> None:
    path = f"keywords[{index}]"
    _validate_language(group.language, f"{path}.language", issues, required=True)
    if not group.scheme.strip() or any(char.isspace() for char in group.scheme.strip()):
        issues.append(_error("invalid_keyword_scheme", "schema de mots-cles invalide", f"{path}.scheme"))
    if not group.items:
        issues.append(_error("empty_keyword_group", "groupe de mots-cles vide", f"{path}.items"))
    for item_index, item in enumerate(group.items):
        if not item.strip():
            issues.append(_error("invalid_keyword", "mot-cle vide", f"{path}.items[{item_index}]"))
    for first, second in keyword_duplicate_pairs(group.items):
        issues.append(
            MetadataIssue(
                "similar_keywords",
                "warning",
                f"mots-cles equivalents a la casse ou aux accents pres : {first} / {second}",
                f"{path}.items",
            )
        )


def _validate_collection(collection: Collection, issues: list[MetadataIssue]) -> None:
    if not collection.title.strip():
        issues.append(_error("invalid_collection_title", "titre de collection obligatoire", "collection.title"))
    if collection.issn is not None and normalize_issn(collection.issn) is None:
        issues.append(_error("invalid_issn", "ISSN de collection invalide", "collection.issn"))
    if collection.volume is not None and not collection.volume.strip():
        issues.append(_error("invalid_collection_volume", "numero de volume vide", "collection.volume"))
    if collection.editor is not None and not collection.editor.strip():
        issues.append(_error("invalid_collection_editor", "nom d'editeur de collection vide", "collection.editor"))


def _validate_funding(funding: Funding, index: int, issues: list[MetadataIssue]) -> None:
    path = f"funding[{index}]"
    if not funding.funder.strip():
        issues.append(_error("invalid_funder", "organisme de financement obligatoire", f"{path}.funder"))
    if funding.grant_number is not None and not funding.grant_number.strip():
        issues.append(_error("invalid_grant_number", "numero de subvention vide", f"{path}.grant_number"))


def _validate_pagination(pagination: Pagination, issues: list[MetadataIssue]) -> None:
    bounded = pagination.page_from is not None or pagination.page_to is not None
    if bounded and pagination.extent is not None:
        issues.append(_error("conflicting_pagination", "bornes et etendue exclusives", "pagination"))
        return
    if bounded:
        if pagination.page_from is None or pagination.page_to is None:
            issues.append(_error("incomplete_pagination", "bornes from et to obligatoires ensemble", "pagination"))
            return
        if pagination.page_from < 1 or pagination.page_to < pagination.page_from:
            issues.append(_error("invalid_pagination", "bornes de pagination incoherentes", "pagination"))
    elif pagination.extent is not None:
        if pagination.extent < 1:
            issues.append(_error("invalid_pagination", "etendue de pagination invalide", "pagination.extent"))
    else:
        issues.append(_error("incomplete_pagination", "pagination sans bornes ni etendue", "pagination"))


# ---------------------------------------------------------------------------
# Aides


def _validate_language(value: str, path: str, issues: list[MetadataIssue], *, required: bool) -> None:
    if not value.strip():
        if required:
            issues.append(_error("missing_language", "langue obligatoire", path))
        return
    if not _LANGUAGE_RE.fullmatch(value):
        issues.append(_error("invalid_language", "langue BCP 47 invalide", path))


def _is_valid_partial_date(value: str) -> bool:
    """Accepter AAAA, AAAA-MM ou AAAA-MM-JJ calendairement possibles."""
    if not _DATE_RE.fullmatch(value):
        return False
    parts = value.split("-")
    if len(parts) == 3:
        import datetime

        try:
            datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            return False
    return True


def _validate_http_url(value: str, code: str, path: str, issues: list[MetadataIssue]) -> None:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        issues.append(_error(code, "URL http(s) invalide", path))


def _validate_identifier_duplicates(identifiers: tuple[Identifier, ...], issues: list[MetadataIssue]) -> None:
    """Signaler les identifiants qui deviendraient indistinguables dans la TEI.

    Une meme valeur repetee (copier-coller) et deux identifiants de meme
    type et de meme support (ex. deux ISBN "print") se serialisent tous les
    deux en `idno` sans qu'aucun attribut ne les distingue.
    """
    seen_values: dict[tuple[str, str], int] = {}
    seen_type_format: dict[tuple[str, str], int] = {}
    for index, identifier in enumerate(identifiers):
        path = f"identifiers[{index}]"
        normalized_value = identifier.value.strip().lower()
        if normalized_value:
            value_key = (identifier.identifier_type, normalized_value)
            if value_key in seen_values:
                issues.append(_error(
                    "duplicate_identifier_value",
                    f"identifiant duplique : {identifier.value.strip()}",
                    f"{path}.value",
                ))
            else:
                seen_values[value_key] = index
        if identifier.identifier_format is not None:
            format_key = (identifier.identifier_type, identifier.identifier_format)
            if format_key in seen_type_format:
                issues.append(_error(
                    "duplicate_identifier_type_format",
                    f"deux identifiants {identifier.identifier_type}/{identifier.identifier_format} indistinguables dans la TEI",
                    path,
                ))
            else:
                seen_type_format[format_key] = index


def _duplicates(values: list[str], code: str, path: str, issues: list[MetadataIssue]) -> None:
    normalized = [value.strip() for value in values]
    for value in sorted({candidate for candidate in normalized if normalized.count(candidate) > 1 and candidate}):
        issues.append(_error(code, f"identifiant duplique : {value}", path))


def _validate_identifier(value: str, code: str, path: str, issues: list[MetadataIssue]) -> None:
    if value != value.strip() and value.strip():
        issues.append(_error(code, "identifiant avec espaces initiaux ou finaux", path))


def _error(code: str, message: str, path: str) -> MetadataIssue:
    return MetadataIssue(code, "error", message, path)
