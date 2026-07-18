"""Profil institutionnel et lien portable vers le DOCX source."""

from __future__ import annotations

import json
from pathlib import Path

from mini_metopes.metadata import (
    METADATA_SCHEMA_VERSION,
    DocumentMetadata,
    Publisher,
    Rights,
    Publication,
    SourceDocument,
    apply_institutional_profile,
    load_institutional_profile,
    resolve_source_document_path,
    source_document_reference,
)


PROFILE = Path(__file__).parents[1] / "profiles" / "purh.json"


def _metadata(**changes) -> DocumentMetadata:
    base = DocumentMetadata(
        schema_version=METADATA_SCHEMA_VERSION,
        source=SourceDocument("document.docx", "ab" * 32),
        document_type="chapter", language="fr", title="Titre",
    )
    from dataclasses import replace

    return replace(base, **changes)


def test_purh_profile_loads_and_fills_missing_values_only() -> None:
    profile, issues = load_institutional_profile(PROFILE)
    assert profile is not None and not issues
    assert profile.profile_id == "purh"

    merged = apply_institutional_profile(_metadata(), profile)
    assert merged.publication.publisher.name == "Presses universitaires de Rouen et du Havre"
    assert merged.publication.publisher.place == "Mont-Saint-Aignan"
    assert merged.rights.holder == "Presses universitaires de Rouen et du Havre"

    overridden = apply_institutional_profile(
        _metadata(
            publication=Publication(publisher=Publisher(name="Autre éditeur")),
            rights=Rights(holder="Autre détenteur"),
        ),
        profile,
    )
    assert overridden.publication.publisher.name == "Autre éditeur"
    assert overridden.rights.holder == "Autre détenteur"
    # les valeurs absentes restent completees
    assert overridden.publication.publisher.place == "Mont-Saint-Aignan"


def test_invalid_profile_reports_stable_codes(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    profile, issues = load_institutional_profile(broken)
    assert profile is None
    assert "invalid_profile_json" in {issue.code for issue in issues}

    missing_id = tmp_path / "missing.json"
    missing_id.write_text(json.dumps({"publisher": {"name": "X"}}), encoding="utf-8")
    profile, issues = load_institutional_profile(missing_id)
    assert profile is None
    assert "invalid_profile_id" in {issue.code for issue in issues}


def test_source_reference_prefers_relative_path(tmp_path: Path) -> None:
    docx = tmp_path / "chapitres" / "conclusion_racine.docx"
    docx.parent.mkdir()
    docx.write_bytes(b"contenu")
    metadata_path = tmp_path / "conclusion.metadata.json"

    reference = source_document_reference(docx, metadata_path)
    assert reference == "chapitres/conclusion_racine.docx"
    assert resolve_source_document_path(reference, metadata_path) == docx.resolve()

    sibling_reference = source_document_reference(docx, docx.parent / "meta.json")
    assert sibling_reference == "conclusion_racine.docx"

    parent_reference = source_document_reference(tmp_path / "autre.docx", docx.parent / "meta.json")
    assert parent_reference == "../autre.docx"


def test_absolute_path_is_resolved_as_is(tmp_path: Path) -> None:
    docx = tmp_path / "document.docx"
    docx.write_bytes(b"x")
    absolute = str(docx.resolve())
    assert resolve_source_document_path(absolute, tmp_path / "meta.json") == Path(absolute)


def test_cli_convert_applies_institutional_profile(tmp_path: Path) -> None:
    from mini_metopes.cli import main

    fixtures = Path(__file__).parent / "fixtures"
    output = tmp_path / "output.xml"
    code = main([
        "convert-docx", str(fixtures / "docx" / "native-tei-conversion.docx"), str(output),
        "--metadata", str(fixtures / "metadata" / "native-tei-conversion.metadata.json"),
        "--profile", str(PROFILE),
    ])
    assert code == 0
    content = output.read_text(encoding="utf-8")
    assert "<publisher>Presses universitaires de Rouen et du Havre</publisher>" in content
