from dataclasses import replace
from pathlib import Path

import pytest

from mini_metopes.metadata import load_metadata_file, metadata_from_json, metadata_to_json, write_metadata_file


FIXTURE = Path(__file__).parent / "fixtures" / "metadata" / "native-tei-conversion.metadata.json"


def test_json_round_trip_is_deterministic_and_unicode() -> None:
    loaded = load_metadata_file(FIXTURE)
    assert loaded.valid and loaded.metadata is not None
    rendered = metadata_to_json(loaded.metadata)
    assert rendered.endswith("\n")
    assert metadata_from_json(rendered).metadata == loaded.metadata
    assert metadata_to_json(loaded.metadata) == rendered


def test_invalid_json_and_atomic_write_preserve_target(tmp_path: Path) -> None:
    assert not metadata_from_json("{").valid
    loaded = load_metadata_file(FIXTURE)
    assert loaded.metadata is not None
    destination = tmp_path / "metadata.json"
    destination.write_text("ancienne", encoding="utf-8")
    with pytest.raises(ValueError):
        write_metadata_file(replace(loaded.metadata, title=""), destination)
    assert destination.read_text(encoding="utf-8") == "ancienne"
    write_metadata_file(loaded.metadata, destination)
    assert load_metadata_file(destination).valid
