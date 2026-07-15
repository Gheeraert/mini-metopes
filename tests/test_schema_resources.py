"""Tests d'accès aux ressources normatives installées."""

from __future__ import annotations

import hashlib
import json
from importlib import resources


def test_official_schema_resources_are_packaged() -> None:
    root = resources.files("mini_metopes").joinpath(
        "resources", "schemas", "commons-publishing"
    )
    schema = root.joinpath("commons-publishing.rng")
    provenance = root.joinpath("PROVENANCE.json")
    licence = root.joinpath("LICENSE.txt")

    assert schema.is_file()
    assert provenance.is_file()
    assert licence.is_file()
    assert json.loads(provenance.read_text(encoding="utf-8"))["local_modifications"] is False
    assert "CeCILL-B" in licence.read_text(encoding="utf-8")


def test_embedded_rng_matches_provenance_sha256() -> None:
    root = resources.files("mini_metopes").joinpath(
        "resources", "schemas", "commons-publishing"
    )
    provenance = json.loads(
        root.joinpath("PROVENANCE.json").read_text(encoding="utf-8")
    )
    actual = hashlib.sha256(root.joinpath("commons-publishing.rng").read_bytes()).hexdigest()

    assert actual == provenance["source_sha256"], (
        "Le RNG embarque ne correspond pas a source_sha256 dans PROVENANCE.json: "
        f"{actual} != {provenance['source_sha256']}"
    )
