"""API de serialisation TEI Commons Publishing."""

from .conversion import convert_docx_to_tei
from .model import TeiConversionDiagnostic, TeiConversionResult, TeiDiagnosticSeverity
from .serializer import serialize_editorial_document_to_tei, write_tei_conversion_result

__all__ = [
    "TeiConversionDiagnostic",
    "TeiConversionResult",
    "TeiDiagnosticSeverity",
    "convert_docx_to_tei",
    "serialize_editorial_document_to_tei",
    "write_tei_conversion_result",
]
