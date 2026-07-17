"""Resultats structures de la conversion vers TEI Commons Publishing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mini_metopes.validation import ValidationIssue


TeiDiagnosticSeverity = Literal["info", "warning", "error"]
TeiDiagnosticOrigin = Literal["inspection", "editorial", "serialization"]


@dataclass(frozen=True)
class TeiConversionDiagnostic:
    """Diagnostic de conversion, independant des erreurs Relax NG."""

    code: str
    severity: TeiDiagnosticSeverity
    message: str
    origin: TeiDiagnosticOrigin = "serialization"
    source_paragraph_index: int | None = None
    note_id: str | None = None
    source_part: str | None = None
    run_index: int | None = None
    style_id: str | None = None


@dataclass(frozen=True)
class TeiConversionResult:
    """TEI serialisee, diagnostics de conversion et resultat de validation."""

    xml_bytes: bytes | None
    diagnostics: tuple[TeiConversionDiagnostic, ...]
    validation_issues: tuple[ValidationIssue, ...]

    @property
    def is_successful(self) -> bool:
        """Indiquer si une TEI valide et sans erreur bloquante est disponible."""
        return (
            self.xml_bytes is not None
            and not self.validation_issues
            and not any(diagnostic.severity == "error" for diagnostic in self.diagnostics)
        )
