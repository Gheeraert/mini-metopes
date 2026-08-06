"""API publique des metadonnees JSON Mini-Metopes."""

from .discovery import (
    compute_file_sha256,
    default_metadata_path,
    resolve_source_document_path,
    source_document_reference,
)
from .extraction import extract_metadata_suggestions
from .merge import metadata_consistency_issues
from .model import *
from .profile import apply_institutional_profile, load_institutional_profile
from .serialization import load_metadata_file, metadata_from_json, metadata_to_data, metadata_to_json, write_metadata_file
from .validation import (
    SPDX_LICENSES,
    keyword_duplicate_pairs,
    normalize_doi,
    normalize_isbn,
    normalize_issn,
    normalize_orcid,
    resolved_license,
    validate_metadata,
)

__all__ = [name for name in globals() if not name.startswith("_")]
