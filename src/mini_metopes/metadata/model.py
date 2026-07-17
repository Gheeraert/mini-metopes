"""Modele immuable des metadonnees associees a un DOCX."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


METADATA_SCHEMA_VERSION = "1.0"
ContributorRole = Literal["author", "editor", "translator", "compiler", "contributor"]
DocumentType = Literal["book", "chapter", "article", "front_matter", "back_matter", "other"]
MetadataSeverity = Literal["warning", "error"]


@dataclass(frozen=True)
class MetadataSource:
    """Identite portable du DOCX auquel les metadonnees sont associees."""

    filename: str
    sha256: str


@dataclass(frozen=True)
class Affiliation:
    """Affiliation institutionnelle reutilisable par plusieurs personnes."""

    affiliation_id: str
    name: str
    unit: str | None = None
    city: str | None = None
    country: str | None = None
    ror: str | None = None


@dataclass(frozen=True)
class Contributor:
    """Responsable editorial, structure ou sous forme de nom litteral."""

    contributor_id: str
    role: ContributorRole
    given_name: str | None = None
    family_name: str | None = None
    literal_name: str | None = None
    orcid: str | None = None
    affiliation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class DocumentMetadata:
    """Metadonnees versionnees, independantes de la GUI et de la TEI."""

    schema_version: str
    source: MetadataSource
    document_type: DocumentType
    language: str
    title: str
    subtitle: str | None = None
    abstract: str | None = None
    keywords: tuple[str, ...] = ()
    contributors: tuple[Contributor, ...] = ()
    affiliations: tuple[Affiliation, ...] = ()


@dataclass(frozen=True)
class MetadataIssue:
    """Diagnostic stable de validation, chargement ou coherence."""

    code: str
    severity: MetadataSeverity
    message: str
    path: str | None = None


@dataclass(frozen=True)
class MetadataValidationResult:
    """Resultat structure de la validation metier."""

    valid: bool
    issues: tuple[MetadataIssue, ...]


@dataclass(frozen=True)
class MetadataLoadResult:
    """Resultat de lecture JSON sans exception pour les erreurs attendues."""

    metadata: DocumentMetadata | None
    issues: tuple[MetadataIssue, ...]

    @property
    def valid(self) -> bool:
        return self.metadata is not None and not any(issue.severity == "error" for issue in self.issues)


@dataclass(frozen=True)
class MetadataSuggestions:
    """Valeurs uniquement proposees depuis le preambule Word."""

    title: str | None
    subtitle: str | None
    diagnostics: tuple[MetadataIssue, ...]
    consumed_paragraph_indexes: tuple[int, ...]
