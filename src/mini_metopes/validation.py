"""Validation Relax NG du noyau TEI Commons Publishing."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path

from lxml import etree


_RESOURCE_PARTS = (
    "resources",
    "schemas",
    "commons-publishing",
    "commons-publishing.rng",
)


@dataclass(frozen=True)
class ValidationIssue:
    """Une erreur produite par le parseur XML ou le validateur Relax NG."""

    message: str
    line: int | None = None
    column: int | None = None
    domain: str | None = None
    type_name: str | None = None
    level: str = "error"


@dataclass(frozen=True)
class ValidationResult:
    """Le résultat déterministe d'une validation XML."""

    valid: bool
    issues: tuple[ValidationIssue, ...]


def _xml_parser() -> etree.XMLParser:
    """Créer un parseur XML sans réseau, DTD externe ni résolution d'entités."""
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        recover=False,
        remove_blank_text=False,
    )


def _issue_from_error(error: etree._LogEntry, *, domain: str | None = None) -> ValidationIssue:
    return ValidationIssue(
        message=error.message,
        line=error.line or None,
        column=error.column or None,
        domain=domain or error.domain_name,
        type_name=error.type_name,
        level=error.level_name.lower(),
    )


@lru_cache(maxsize=1)
def _commons_publishing_schema() -> etree.RelaxNG:
    """Charger et compiler le RNG embarqué indépendamment du répertoire courant."""
    schema_resource = resources.files("mini_metopes").joinpath(*_RESOURCE_PARTS)
    schema_root = etree.fromstring(schema_resource.read_bytes(), parser=_xml_parser())
    return etree.RelaxNG(schema_root)


def validate_xml_bytes(data: bytes) -> ValidationResult:
    """Valider des octets XML contre le RNG Commons Publishing embarqué.

    Les erreurs de syntaxe XML sont signalées avec ``domain="xml"`` et les
    violations Relax NG avec le domaine fourni par libxml2.
    """
    try:
        document = etree.fromstring(data, parser=_xml_parser())
    except etree.XMLSyntaxError as error:
        issues = tuple(_issue_from_error(item, domain="xml") for item in error.error_log)
        return ValidationResult(valid=False, issues=issues)

    return validate_xml_tree(document)


def validate_xml_tree(document: etree._Element | etree._ElementTree) -> ValidationResult:
    """Valider un arbre lxml deja analyse contre le RNG Commons Publishing."""
    schema = _commons_publishing_schema()
    if schema.validate(document):
        return ValidationResult(valid=True, issues=())
    return ValidationResult(
        valid=False,
        issues=tuple(_issue_from_error(item, domain="relaxng") for item in schema.error_log),
    )


def validate_xml_file(path: Path) -> ValidationResult:
    """Lire puis valider un fichier XML.

    Les erreurs d'accès au fichier sont volontairement propagées afin que les
    interfaces appelantes puissent choisir leur diagnostic.
    """
    return validate_xml_bytes(path.read_bytes())
