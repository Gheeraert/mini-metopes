from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from mini_metopes.metadata import (
    Affiliation, Contributor, DocumentMetadata, METADATA_SCHEMA_VERSION, MetadataSource,
    compute_file_sha256, default_metadata_path,
)


def test_metadata_model_is_immutable_and_default_path_is_portable() -> None:
    metadata = DocumentMetadata(METADATA_SCHEMA_VERSION, MetadataSource("mon.document.docx", "a" * 64), "chapter", "fr", "Titre")
    with pytest.raises(FrozenInstanceError):
        metadata.title = "Autre"  # type: ignore[misc]
    assert default_metadata_path(Path("mon.document.DOCX")) == Path("mon.document.metadata.json")


def test_sha256_reads_file_by_content(tmp_path: Path) -> None:
    source = tmp_path / "document.docx"
    source.write_bytes(b"fixture")
    assert compute_file_sha256(source) == "f16d05ec6b29248d2c61adb1e9263f78e4f7bace1b955014a2d17872cfe4064d"
