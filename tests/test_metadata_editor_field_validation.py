"""Validation immediate d'une entree isolee pour les dialogues de l'editeur GUI.

Chaque fonction reutilise ``validate_metadata`` (source unique de verite,
voir ``metadata_controller._probe_metadata``) plutot que de dupliquer des
regles : ces tests verifient a la fois qu'une entree invalide est bien
signalee et qu'une entree valide ne remonte aucune erreur preexistante sans
rapport (isolation du document minimal jetable).
"""

from __future__ import annotations

from mini_metopes.gui.metadata_controller import (
    abstract_field_errors,
    affiliation_field_errors,
    collection_field_errors,
    contributor_field_errors,
    funding_field_errors,
    identifier_field_errors,
    keyword_group_field_errors,
    license_field_errors,
    responsibility_field_errors,
)
from mini_metopes.metadata import (
    Abstract,
    Affiliation,
    Collection,
    Contributor,
    EditorialResponsibility,
    Funding,
    Identifier,
    KeywordGroup,
    License,
)


def test_contributor_field_errors_catches_the_literal_vs_structured_name_rule() -> None:
    """Le cas concret signale par l'audit : remplir nom littéral ET prénom/nom."""
    both = Contributor("p1", "author", given_name="A", literal_name="Collectif")
    assert contributor_field_errors(both, ()) != ()

    neither = Contributor("p1", "author")
    assert contributor_field_errors(neither, ()) != ()

    valid = Contributor("p1", "author", given_name="A", family_name="B")
    assert contributor_field_errors(valid, ()) == ()


def test_contributor_field_errors_catches_invalid_orcid() -> None:
    invalid = Contributor("p1", "author", literal_name="X", orcid="0000-0000-0000-0000")
    assert any("ORCID" in message for message in contributor_field_errors(invalid, ()))


def test_contributor_field_errors_do_not_leak_unrelated_document_state() -> None:
    """L'isolement dans un document minimal ne doit jamais faire remonter
    d'erreur qui ne concerne pas le contributeur en cours d'edition."""
    valid = Contributor("p1", "author", literal_name="X", affiliation_ids=("aff-1",))
    errors = contributor_field_errors(valid, known_affiliation_ids=("aff-1",))
    assert errors == ()


def test_affiliation_field_errors_catches_invalid_ror() -> None:
    invalid = Affiliation("aff-1", "Universite", ror="ror.org/x")
    assert any("ROR" in message for message in affiliation_field_errors(invalid))
    assert affiliation_field_errors(Affiliation("aff-1", "Universite")) == ()


def test_identifier_field_errors_catches_invalid_doi() -> None:
    assert identifier_field_errors(Identifier("doi", "pas-un-doi")) != ()
    assert identifier_field_errors(Identifier("doi", "10.4000/x.1")) == ()


def test_funding_field_errors_catches_empty_funder() -> None:
    assert funding_field_errors(Funding(" ")) != ()
    assert funding_field_errors(Funding("ANR")) == ()


def test_abstract_field_errors_catches_invalid_language() -> None:
    assert abstract_field_errors(Abstract("summary", "français", "x")) != ()
    assert abstract_field_errors(Abstract("summary", "fr", "x")) == ()


def test_keyword_group_field_errors_catches_empty_group() -> None:
    assert keyword_group_field_errors(KeywordGroup("fr", ())) != ()
    assert keyword_group_field_errors(KeywordGroup("fr", ("mot",))) == ()


def test_responsibility_field_errors_catches_empty_fields() -> None:
    assert responsibility_field_errors(EditorialResponsibility(" ", "Nom")) != ()
    assert responsibility_field_errors(EditorialResponsibility("éditrice", "Nom")) == ()


def test_collection_field_errors_catches_empty_title() -> None:
    assert collection_field_errors(Collection(" ")) != ()
    assert collection_field_errors(Collection("Une collection")) == ()


def test_license_field_errors_catches_unknown_spdx_id() -> None:
    assert license_field_errors(License(spdx_id="MIT")) != ()
    assert license_field_errors(License(spdx_id="CC-BY-4.0")) == ()


def test_license_field_errors_do_not_block_on_mismatch_warning() -> None:
    """license_spdx_id_mismatch est un avertissement (decision 0023) : le
    dialogue ne doit jamais bloquer dessus, seules les erreurs comptent."""
    mismatched = License(name="Nom personnalise", spdx_id="CC-BY-4.0")
    assert license_field_errors(mismatched) == ()
