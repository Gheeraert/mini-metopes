"""Modele immuable des metadonnees associees a un DOCX (schema JSON 1.0)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


METADATA_SCHEMA_VERSION = "1.0"

ContributorRole = Literal["author", "editor", "translator", "scientific_editor", "other"]
DocumentType = Literal["article", "chapter", "introduction", "conclusion", "bibliography", "other"]
IdentifierType = Literal["doi", "isbn-13", "isbn-10", "issn", "eissn", "local"]
IdentifierFormat = Literal["print", "pdf", "epub", "html"]
AbstractType = Literal["summary", "abstract", "back-cover"]
MetadataSeverity = Literal["warning", "error"]


@dataclass(frozen=True)
class SourceDocument:
    """Lien portable vers le DOCX source, sans jamais l'incorporer.

    ``path`` est de preference relatif au fichier JSON ; il peut etre absolu
    quand aucun chemin relatif raisonnable n'existe. ``sha256`` fige l'etat
    du document au moment de la validation des metadonnees.
    """

    path: str
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
    """Auteur ou contributeur intellectuel, ordre significatif."""

    contributor_id: str
    role: ContributorRole
    given_name: str | None = None
    family_name: str | None = None
    literal_name: str | None = None
    orcid: str | None = None
    email: str | None = None
    role_label: str | None = None
    affiliation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class EditorialResponsibility:
    """Suivi editorial de la publication (distinct des auteurs)."""

    responsibility: str
    name: str


@dataclass(frozen=True)
class Publisher:
    """Editeur commercial ; les valeurs stables peuvent venir d'un profil."""

    name: str | None = None
    place: str | None = None
    address: tuple[str, ...] = ()
    url: str | None = None


@dataclass(frozen=True)
class Publication:
    """Informations de publication de l'unite editoriale."""

    publisher: Publisher = Publisher()
    publication_date: str | None = None


@dataclass(frozen=True)
class Identifier:
    """Identifiant public type ; le format n'est jamais devine."""

    identifier_type: IdentifierType
    value: str
    identifier_format: IdentifierFormat | None = None


@dataclass(frozen=True)
class License:
    """Licence affichee et son URI reelle ; jamais de valeur de substitution.

    ``spdx_id`` est facultatif et complete ``name``/``url`` en texte libre :
    quand il designe une licence Creative Commons connue
    (``validation.SPDX_LICENSES``), ``name``/``url`` peuvent rester absents
    et sont alors resolus automatiquement (voir
    ``validation.resolved_license``).
    """

    name: str | None = None
    url: str | None = None
    spdx_id: str | None = None


@dataclass(frozen=True)
class Rights:
    """Droits : detenteur, mention affichee, licence eventuelle."""

    holder: str | None = None
    statement: str | None = None
    license: License = License()


@dataclass(frozen=True)
class Abstract:
    """Texte editorial type : resume, abstract traduit ou quatrieme."""

    abstract_type: AbstractType
    language: str
    text: str


@dataclass(frozen=True)
class KeywordGroup:
    """Groupe de mots-cles d'une langue ; l'ordre est conserve."""

    language: str
    items: tuple[str, ...]
    scheme: str = "keywords"


@dataclass(frozen=True)
class Collection:
    """Collection editoriale simple, sans sous-collections."""

    title: str
    issn: str | None = None
    volume: str | None = None
    editor: str | None = None


@dataclass(frozen=True)
class Funding:
    """Financement de l'unite editoriale (ex. ANR, ERC) ; nom libre, non normalise."""

    funder: str
    grant_number: str | None = None


@dataclass(frozen=True)
class Pagination:
    """Pagination de l'unite (bornes) ou du volume complet (etendue)."""

    page_from: int | None = None
    page_to: int | None = None
    extent: int | None = None


@dataclass(frozen=True)
class DocumentMetadata:
    """Metadonnees versionnees, independantes de la GUI et de la TEI."""

    schema_version: str
    source: SourceDocument
    document_type: DocumentType
    language: str
    title: str
    subtitle: str | None = None
    contributors: tuple[Contributor, ...] = ()
    affiliations: tuple[Affiliation, ...] = ()
    editorial_responsibility: tuple[EditorialResponsibility, ...] = ()
    publication: Publication = Publication()
    identifiers: tuple[Identifier, ...] = ()
    rights: Rights = Rights()
    abstracts: tuple[Abstract, ...] = ()
    keywords: tuple[KeywordGroup, ...] = ()
    collection: Collection | None = None
    pagination: Pagination | None = None
    funding: tuple[Funding, ...] = ()


@dataclass(frozen=True)
class InstitutionalProfile:
    """Valeurs institutionnelles stables et facultatives (ex. PURH)."""

    profile_id: str
    publisher: Publisher = Publisher()
    rights_holder: str | None = None


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
