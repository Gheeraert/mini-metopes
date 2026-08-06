"""Hierarchie de titres livre uniquement (decision 0037).

Titre1 = partie (optionnelle), Titre2 = pivot chapitre (monographie) ou
contribution (ouvrage collectif, detection automatique des 2+ occurrences),
Titre3-6 = section1-4.
"""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from mini_metopes.metadata import load_metadata_file
from mini_metopes.tei import convert_docx_to_tei
from test_docx_numbering import paragraph, runtime_docx, write_docx

FIXTURES = Path(__file__).parent / "fixtures"
METADATA = FIXTURES / "metadata" / "native-tei-conversion.metadata.json"
NS = {"tei": "http://www.tei-c.org/ns/1.0"}

STYLES = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading4"><w:name w:val="heading 4"/></w:style>
  <w:style w:type="paragraph" w:styleId="Signature"><w:name w:val="Signature"/></w:style>
</w:styles>
"""


def _metadata():
    loaded = load_metadata_file(METADATA)
    assert loaded.metadata is not None
    return loaded.metadata


def _convert(name: str, body: str):
    path = runtime_docx(name)
    write_docx(path, body, styles=STYLES)
    return convert_docx_to_tei(path, metadata=_metadata())


def test_monograph_with_part_chapter_and_sections_gets_typed_divs() -> None:
    body = (
        paragraph("Partie I", style="Heading1")
        + paragraph("Chapitre 1", style="Heading2")
        + paragraph("Corps du chapitre.")
        + paragraph("Section", style="Heading3")
        + paragraph("Corps de section.")
        + paragraph("Sous-section", style="Heading4")
        + paragraph("Corps de sous-section.")
    )
    result = _convert("monograph-part-chapter-sections.docx", body)

    assert result.is_successful, result.diagnostics
    tree = etree.fromstring(result.xml_bytes)
    part = tree.xpath("//tei:body/tei:div[@type='part']", namespaces=NS)
    assert len(part) == 1
    chapter = part[0].xpath("./tei:div[@type='chapter']", namespaces=NS)
    assert len(chapter) == 1
    section1 = chapter[0].xpath("./tei:div[@type='section1']", namespaces=NS)
    assert len(section1) == 1
    section2 = section1[0].xpath("./tei:div[@type='section2']", namespaces=NS)
    assert len(section2) == 1


def test_flat_monograph_with_a_single_chapter_is_not_treated_as_collective() -> None:
    body = paragraph("Chapitre unique", style="Heading2") + paragraph("Corps.")
    result = _convert("monograph-single-chapter.docx", body)

    assert result.is_successful, result.diagnostics
    tree = etree.fromstring(result.xml_bytes)
    assert tree.xpath("//tei:body//tei:div[@type='chapter']", namespaces=NS)
    assert not tree.xpath("//tei:group", namespaces=NS)


def test_two_or_more_titre2_headings_trigger_the_collective_group_shape() -> None:
    body = (
        paragraph("Contribution un", style="Heading2")
        + paragraph("Corps un.")
        + paragraph("Contribution deux", style="Heading2")
        + paragraph("Corps deux.")
        + paragraph("Contribution trois", style="Heading2")
        + paragraph("Corps trois.")
    )
    result = _convert("collective-three-contributions.docx", body)

    assert result.is_successful, result.diagnostics
    tree = etree.fromstring(result.xml_bytes)
    group = tree.xpath("//tei:text/tei:group[@type='article']", namespaces=NS)
    assert len(group) == 1
    contributions = group[0].xpath("./tei:text", namespaces=NS)
    assert len(contributions) == 3
    titles = [
        c.xpath("./tei:front/tei:div[@type='titlePage']/tei:p[@rend='title-main']/text()", namespaces=NS)[0]
        for c in contributions
    ]
    assert titles == ["Contribution un", "Contribution deux", "Contribution trois"]
    for contribution in contributions:
        assert contribution.xpath("./tei:body", namespaces=NS)


def test_collective_contribution_sections_restart_at_section1() -> None:
    body = (
        paragraph("Contribution un", style="Heading2")
        + paragraph("Section interne", style="Heading3")
        + paragraph("Corps de section.")
        + paragraph("Contribution deux", style="Heading2")
        + paragraph("Corps deux.")
    )
    result = _convert("collective-section-restart.docx", body)

    assert result.is_successful, result.diagnostics
    tree = etree.fromstring(result.xml_bytes)
    first_body = tree.xpath("(//tei:group/tei:text)[1]/tei:body", namespaces=NS)[0]
    section = first_body.xpath("./tei:div[@type='section1']", namespaces=NS)
    assert len(section) == 1
    assert not first_body.xpath(".//tei:div[not(@type)]", namespaces=NS)


def test_collective_contributions_each_end_with_their_own_signature() -> None:
    """Integration Signature + ouvrage collectif : chaque contribution se
    termine par sa propre signature, terminale par rapport au pivot Titre2
    suivant (decision 0037, seuil <= 2)."""
    body = (
        paragraph("Contribution un", style="Heading2")
        + paragraph("Corps un.")
        + paragraph("Claire Dubuisson", style="Signature")
        + paragraph("Universite de Rouen", style="Signature")
        + paragraph("Contribution deux", style="Heading2")
        + paragraph("Corps deux.")
        + paragraph("Autre Auteur", style="Signature")
    )
    result = _convert("collective-with-signatures.docx", body)

    assert result.is_successful, result.diagnostics
    assert "misplaced_signature_not_serializable" not in [d.code for d in result.diagnostics]
    tree = etree.fromstring(result.xml_bytes)
    contributions = tree.xpath("//tei:group/tei:text", namespaces=NS)
    assert len(contributions) == 2
    first_paragraphs = contributions[0].xpath("./tei:body/tei:p/text()", namespaces=NS)
    assert first_paragraphs[-2:] == ["Claire Dubuisson", "Universite de Rouen"]
    second_paragraphs = contributions[1].xpath("./tei:body/tei:p/text()", namespaces=NS)
    assert second_paragraphs[-1] == "Autre Auteur"


def test_part_with_two_or_more_contributions_is_refused() -> None:
    """TEI n'admet pas <text>/<group> comme enfant de <div> : une partie ne
    peut pas contenir un ouvrage collectif (decision 0037)."""
    body = (
        paragraph("Partie I", style="Heading1")
        + paragraph("Contribution un", style="Heading2")
        + paragraph("Corps un.")
        + paragraph("Contribution deux", style="Heading2")
        + paragraph("Corps deux.")
    )
    result = _convert("part-with-collective.docx", body)

    assert not result.is_successful
    assert result.xml_bytes is None
    assert "part_with_collective_work_not_serializable" in [d.code for d in result.diagnostics]
