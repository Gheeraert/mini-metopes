"""API de serialisation TEI Commons Publishing."""

from .conversion import convert_docx_to_tei, prepare_tei_conversion
from .model import TeiConversionDiagnostic, TeiConversionResult, TeiDiagnosticOrigin, TeiDiagnosticSeverity
from .serializer import serialize_editorial_document_to_tei, write_tei_conversion_result

__all__ = [
    "TeiConversionDiagnostic",
    "TeiConversionResult",
    "TeiDiagnosticOrigin",
    "TeiDiagnosticSeverity",
    "convert_docx_to_tei",
    "prepare_tei_conversion",
    "serialize_editorial_document_to_tei",
    "write_tei_conversion_result",
]
