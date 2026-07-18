"""Fabriquer le corpus de référence Mini-Métopes (documents A à D).

Script de maintenance, non appelé par les tests. Il écrit dans
``tests/fixtures/corpus`` des paquets DOCX reproductibles (horodatages ZIP
fixés), leurs métadonnées, la TEI attendue et les diagnostics attendus.

Les ``expected.xml`` produits doivent être relus comme des objets éditoriaux
avant d'être acceptés comme références. Le script refuse de régénérer un cas
dont le contrat (succès ou blocage) ne correspond plus à l'intention déclarée.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "corpus"
sys.path.insert(0, str(ROOT / "src"))


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
  <Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>
  <Override PartName="/word/endnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml"/>
</Types>
"""


# Document A — Word français : identifiants localisés, w:name canoniques anglais.
FRENCH_WORD_STYLES = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Titre"><w:name w:val="Title"/><w:basedOn w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Titre1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Titre2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="1"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Notedebasdepage"><w:name w:val="footnote text"/><w:basedOn w:val="Normal"/></w:style>
  <w:style w:type="character" w:styleId="Appelnotedebasdep"><w:name w:val="footnote reference"/></w:style>
</w:styles>
"""

DOCUMENT_A = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="Titre"/></w:pPr><w:r><w:t>Petit traité minimal</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Titre1"/></w:pPr><w:r><w:t>Première section</w:t></w:r></w:p>
    <w:p>
      <w:r><w:t xml:space="preserve">Un paragraphe normal avec de l'</w:t></w:r>
      <w:r><w:rPr><w:i/></w:rPr><w:t>italique</w:t></w:r>
      <w:r><w:t xml:space="preserve"> et du </w:t></w:r>
      <w:r><w:rPr><w:b/></w:rPr><w:t>gras</w:t></w:r>
      <w:r><w:t>.</w:t></w:r>
      <w:r><w:rPr><w:rStyle w:val="Appelnotedebasdep"/></w:rPr><w:footnoteReference w:id="2"/></w:r>
    </w:p>
    <w:p><w:pPr><w:pStyle w:val="Titre2"/></w:pPr><w:r><w:t>Première sous-section</w:t></w:r></w:p>
    <w:p><w:r><w:t>Un second paragraphe normal.</w:t></w:r></w:p>
    <w:sectPr/>
  </w:body>
</w:document>
"""

FOOTNOTES_A = """<?xml version="1.0" encoding="UTF-8"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:footnote w:id="-1" w:type="separator"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>
  <w:footnote w:id="2"><w:p><w:pPr><w:pStyle w:val="Notedebasdepage"/></w:pPr><w:r><w:t>Note de bas de page minimale.</w:t></w:r></w:p></w:footnote>
</w:footnotes>
"""


# Document B — Word anglais : identifiants et noms canoniques.
ENGLISH_WORD_STYLES = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="1"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="2"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="BodyText"><w:name w:val="Body Text"/><w:basedOn w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="FootnoteText"><w:name w:val="footnote text"/><w:basedOn w:val="Normal"/></w:style>
  <w:style w:type="character" w:styleId="FootnoteReference"><w:name w:val="footnote reference"/></w:style>
  <w:style w:type="character" w:styleId="Hyperlink"><w:name w:val="Hyperlink"/></w:style>
</w:styles>
"""

NUMBERING_B = """<?xml version="1.0" encoding="UTF-8"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="10">
    <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:suff w:val="tab"/></w:lvl>
    <w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="lowerLetter"/><w:lvlText w:val="%2)"/><w:suff w:val="tab"/></w:lvl>
  </w:abstractNum>
  <w:abstractNum w:abstractNumId="11">
    <w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:suff w:val="tab"/></w:lvl>
  </w:abstractNum>
  <w:num w:numId="50"><w:abstractNumId w:val="10"/></w:num>
  <w:num w:numId="51"><w:abstractNumId w:val="11"/></w:num>
</w:numbering>
"""

RELATIONSHIPS_B = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdHyper" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://example.org/reference" TargetMode="External"/>
</Relationships>
"""


def _numbered(text: str, num_id: str, ilvl: str, style: str = "ListParagraph") -> str:
    return (
        f'<w:p><w:pPr><w:pStyle w:val="{style}"/><w:numPr><w:ilvl w:val="{ilvl}"/>'
        f'<w:numId w:val="{num_id}"/></w:numPr></w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>'
    )


DOCUMENT_B = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr><w:r><w:t>An Ordinary Academic Article</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Introduction</w:t></w:r></w:p>
    <w:p>
      <w:r><w:t xml:space="preserve">Opening paragraph with a reference</w:t></w:r>
      <w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteReference w:id="2"/></w:r>
      <w:r><w:t xml:space="preserve"> and a link to </w:t></w:r>
      <w:hyperlink r:id="rIdHyper"><w:r><w:rPr><w:rStyle w:val="Hyperlink"/></w:rPr><w:t>an external resource</w:t></w:r></w:hyperlink>
      <w:r><w:t>.</w:t></w:r>
    </w:p>
    <w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr><w:r><w:t>A consecutive paragraph continuing the previous one.</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>State of the Art</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Quote"/></w:pPr><w:r><w:t>A prose quotation attributed to an earlier author.</w:t></w:r></w:p>
    <w:p><w:r><w:t>The ordered enumeration follows.</w:t></w:r></w:p>
    {_numbered("First ordered item", "50", "0")}
    {_numbered("Nested ordered item", "50", "1")}
    {_numbered("Second ordered item", "50", "0")}
    <w:p><w:r><w:t>The unordered enumeration follows.</w:t></w:r></w:p>
    {_numbered("First bulleted item", "51", "0")}
    {_numbered("Second bulleted item", "51", "0")}
    <w:p><w:pPr><w:pStyle w:val="Heading3"/></w:pPr><w:r><w:t>Method</w:t></w:r></w:p>
    <w:p>
      <w:r><w:t xml:space="preserve">Closing paragraph with a second note</w:t></w:r>
      <w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteReference w:id="3"/></w:r>
      <w:r><w:t>.</w:t></w:r>
    </w:p>
    <w:sectPr/>
  </w:body>
</w:document>
"""

FOOTNOTES_B = """<?xml version="1.0" encoding="UTF-8"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:footnote w:id="-1" w:type="separator"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>
  <w:footnote w:id="2"><w:p><w:pPr><w:pStyle w:val="FootnoteText"/></w:pPr><w:r><w:t>First footnote of the article.</w:t></w:r></w:p></w:footnote>
  <w:footnote w:id="3"><w:p><w:pPr><w:pStyle w:val="FootnoteText"/></w:pPr><w:r><w:t>Second footnote of the article.</w:t></w:r></w:p></w:footnote>
</w:footnotes>
"""


# Document C — noms affichés localisés en français (autres producteurs).
FRENCH_NAME_STYLES = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="TitrePrincipal"><w:name w:val="Titre"/><w:basedOn w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Titre1"><w:name w:val="Titre 1"/><w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Citationintense"><w:name w:val="Citation intense"/><w:basedOn w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Notedebasdepage"><w:name w:val="Note de bas de page"/><w:basedOn w:val="Normal"/></w:style>
  <w:style w:type="character" w:styleId="Accentuation"><w:name w:val="Accentuation"/></w:style>
</w:styles>
"""

DOCUMENT_C = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="TitrePrincipal"/></w:pPr><w:r><w:t>Stances pour une conversion</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Titre1"/></w:pPr><w:r><w:t>Le poème</w:t></w:r></w:p>
    <w:p>
      <w:r><w:t xml:space="preserve">Le narrateur introduit le poème en </w:t></w:r>
      <w:r><w:rPr><w:rStyle w:val="Accentuation"/></w:rPr><w:t>prose</w:t></w:r>
      <w:r><w:t>.</w:t></w:r>
      <w:r><w:footnoteReference w:id="2"/></w:r>
    </w:p>
    <w:p><w:pPr><w:pStyle w:val="Citationintense"/></w:pPr>
      <w:r><w:t>Premier vers de la première strophe</w:t><w:br/><w:t>Deuxième vers de la première strophe</w:t></w:r>
    </w:p>
    <w:p><w:pPr><w:pStyle w:val="Citationintense"/></w:pPr>
      <w:r><w:t xml:space="preserve">Premier vers de la seconde strophe, en </w:t></w:r>
      <w:r><w:rPr><w:i/></w:rPr><w:t>italique</w:t></w:r>
      <w:r><w:br/><w:t>Deuxième vers de la seconde strophe</w:t></w:r>
      <w:r><w:footnoteReference w:id="3"/></w:r>
    </w:p>
    <w:p><w:r><w:t>Le narrateur conclut en prose.</w:t></w:r></w:p>
    <w:sectPr/>
  </w:body>
</w:document>
"""

FOOTNOTES_C = """<?xml version="1.0" encoding="UTF-8"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:footnote w:id="-1" w:type="separator"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>
  <w:footnote w:id="2"><w:p><w:pPr><w:pStyle w:val="Notedebasdepage"/></w:pPr><w:r><w:t>Note sur la prose introductive.</w:t></w:r></w:p></w:footnote>
  <w:footnote w:id="3"><w:p><w:pPr><w:pStyle w:val="Notedebasdepage"/></w:pPr><w:r><w:t>Note sur la seconde strophe.</w:t></w:r></w:p></w:footnote>
</w:footnotes>
"""


# Document D — cas invalides ou limites, un sous-dossier par cas.
STYLES_D_TEI_QUOTE = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:customStyle="1" w:styleId="TEIquote"><w:name w:val="TEI_quote"/><w:basedOn w:val="Normal"/></w:style>
</w:styles>
"""

DOCUMENT_D_TEI_QUOTE = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Section</w:t></w:r></w:p>
    <w:p><w:r><w:t>Paragraphe normal.</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="TEIquote"/></w:pPr><w:r><w:t>Citation préparée avec le modèle Métopes.</w:t></w:r></w:p>
    <w:sectPr/>
  </w:body>
</w:document>
"""

STYLES_D_MINIMAL = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading4"><w:name w:val="heading 4"/><w:pPr><w:outlineLvl w:val="3"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/></w:style>
</w:styles>
"""

DOCUMENT_D_HEADING_JUMP = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Section</w:t></w:r></w:p>
    <w:p><w:r><w:t>Paragraphe.</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading4"/></w:pPr><w:r><w:t>Saut direct au niveau 4</w:t></w:r></w:p>
    <w:p><w:r><w:t>Paragraphe final.</w:t></w:r></w:p>
    <w:sectPr/>
  </w:body>
</w:document>
"""

DOCUMENT_D_DISCONTINUOUS_LIST = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {_numbered("Premier item", "50", "0")}
    <w:p><w:r><w:t>Interruption de la liste.</w:t></w:r></w:p>
    {_numbered("Reprise de la même instance", "50", "0")}
    <w:sectPr/>
  </w:body>
</w:document>
"""

DOCUMENT_D_TEXTBOX = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Texte principal.</w:t></w:r></w:p>
    <w:p><w:r>
      <w:drawing><w:txbxContent><w:p><w:r><w:t>Texte dans une zone de texte.</w:t></w:r></w:p></w:txbxContent></w:drawing>
    </w:r></w:p>
    <w:sectPr/>
  </w:body>
</w:document>
"""


def write_package(path: Path, files: dict[str, bytes | str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in files.items():
            info = ZipInfo(name, date_time=(2024, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, content.encode("utf-8") if isinstance(content, str) else content)


def write_metadata(directory: Path, *, title: str, subtitle: str | None, language: str, family_name: str, given_name: str) -> None:
    from mini_metopes.metadata import (
        METADATA_SCHEMA_VERSION,
        Contributor,
        DocumentMetadata,
        SourceDocument,
        compute_file_sha256,
        metadata_to_json,
    )

    docx_path = directory / "source.docx"
    metadata = DocumentMetadata(
        schema_version=METADATA_SCHEMA_VERSION,
        source=SourceDocument(path=docx_path.name, sha256=compute_file_sha256(docx_path)),
        document_type="chapter",
        language=language,
        title=title,
        subtitle=subtitle,
        contributors=(
            Contributor(
                contributor_id="person-1",
                role="author",
                given_name=given_name,
                family_name=family_name,
            ),
        ),
    )
    (directory / "metadata.json").write_text(metadata_to_json(metadata), encoding="utf-8")


def diagnostics_to_json(diagnostics) -> str:
    payload = [asdict(diagnostic) for diagnostic in diagnostics]
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def convert(directory: Path):
    from mini_metopes.metadata import load_metadata_file
    from mini_metopes.tei import convert_docx_to_tei

    loaded = load_metadata_file(directory / "metadata.json")
    assert loaded.metadata is not None, [issue for issue in loaded.issues]
    return convert_docx_to_tei(directory / "source.docx", metadata=loaded.metadata)


def write_expectations(directory: Path, *, expect_tei: bool) -> None:
    result = convert(directory)
    (directory / "expected-diagnostics.json").write_text(diagnostics_to_json(result.diagnostics), encoding="utf-8")
    expected_xml = directory / "expected.xml"
    if expect_tei:
        assert result.is_successful, (directory.name, result.diagnostics)
        expected_xml.write_bytes(result.xml_bytes)
    else:
        assert not result.is_successful, (directory.name, "une conversion attendue bloquante a produit une TEI")
        assert result.xml_bytes is None
        if expected_xml.exists():
            expected_xml.unlink()


def build_document_a() -> None:
    directory = CORPUS / "document-a"
    write_package(
        directory / "source.docx",
        {
            "[Content_Types].xml": CONTENT_TYPES,
            "word/document.xml": DOCUMENT_A,
            "word/styles.xml": FRENCH_WORD_STYLES,
            "word/footnotes.xml": FOOTNOTES_A,
        },
    )
    write_metadata(
        directory,
        title="Petit traité minimal",
        subtitle=None,
        language="fr",
        family_name="Deportroyal",
        given_name="Blaise",
    )
    write_expectations(directory, expect_tei=True)


def build_document_b() -> None:
    directory = CORPUS / "document-b"
    write_package(
        directory / "source.docx",
        {
            "[Content_Types].xml": CONTENT_TYPES,
            "word/document.xml": DOCUMENT_B,
            "word/styles.xml": ENGLISH_WORD_STYLES,
            "word/numbering.xml": NUMBERING_B,
            "word/footnotes.xml": FOOTNOTES_B,
            "word/_rels/document.xml.rels": RELATIONSHIPS_B,
        },
    )
    write_rich_purh_metadata(directory)
    write_expectations(directory, expect_tei=True)


def write_rich_purh_metadata(directory: Path) -> None:
    """Metadonnees completes PURH pour le document B, relues comme reference."""
    from mini_metopes.metadata import (
        METADATA_SCHEMA_VERSION,
        Abstract,
        Affiliation,
        Collection,
        Contributor,
        DocumentMetadata,
        EditorialResponsibility,
        Identifier,
        KeywordGroup,
        License,
        Pagination,
        Publication,
        Publisher,
        Rights,
        SourceDocument,
        compute_file_sha256,
        metadata_to_json,
    )

    docx_path = directory / "source.docx"
    metadata = DocumentMetadata(
        schema_version=METADATA_SCHEMA_VERSION,
        source=SourceDocument(path=docx_path.name, sha256=compute_file_sha256(docx_path)),
        document_type="chapter",
        language="en-GB",
        title="An Ordinary Academic Article",
        subtitle="Sections, quotations and lists",
        contributors=(
            Contributor(
                contributor_id="person-1", role="author", given_name="Jane", family_name="Author",
                orcid="0000-0002-1825-0097", affiliation_ids=("affiliation-1",),
            ),
            Contributor(
                contributor_id="person-2", role="scientific_editor", given_name="Paul", family_name="Directeur",
                affiliation_ids=("affiliation-1",),
            ),
        ),
        affiliations=(
            Affiliation("affiliation-1", "Université de Rouen Normandie", city="Rouen", country="FR"),
        ),
        editorial_responsibility=(EditorialResponsibility("éditrice", "Anaïs Monchy"),),
        publication=Publication(
            publisher=Publisher(
                name="Presses universitaires de Rouen et du Havre",
                place="Mont-Saint-Aignan",
                address=("Place Émile-Blondel", "76821 Mont-Saint-Aignan Cedex"),
                url="https://purh.univ-rouen.fr",
            ),
            publication_date="2026",
        ),
        identifiers=(
            Identifier("doi", "10.4000/example.12345"),
            Identifier("isbn-13", "979-10-240-1755-6", "print"),
            Identifier("isbn-13", "978-2-87775-994-6", "pdf"),
            Identifier("issn", "1291-0961"),
        ),
        rights=Rights(
            holder="Presses universitaires de Rouen et du Havre",
            statement="Tous droits réservés.",
            license=License("CC BY-NC-ND 4.0", "https://creativecommons.org/licenses/by-nc-nd/4.0/"),
        ),
        abstracts=(
            Abstract("summary", "fr", "Résumé français de l'article ordinaire."),
            Abstract("abstract", "en", "English abstract of the ordinary article."),
            Abstract("back-cover", "fr", "Texte de quatrième de couverture.\nSecond paragraphe de la quatrième."),
        ),
        keywords=(
            KeywordGroup("fr", ("Racine", "tragédie", "genre")),
            KeywordGroup("en", ("Racine", "tragedy", "gender")),
        ),
        collection=Collection(title="Collection synthétique", issn="0000-0019", volume="12"),
        pagination=Pagination(page_from=125, page_to=148),
    )
    (directory / "metadata.json").write_text(metadata_to_json(metadata), encoding="utf-8")


def build_document_c() -> None:
    directory = CORPUS / "document-c"
    write_package(
        directory / "source.docx",
        {
            "[Content_Types].xml": CONTENT_TYPES,
            "word/document.xml": DOCUMENT_C,
            "word/styles.xml": FRENCH_NAME_STYLES,
            "word/footnotes.xml": FOOTNOTES_C,
        },
    )
    write_metadata(
        directory,
        title="Stances pour une conversion",
        subtitle=None,
        language="fr",
        family_name="Deportroyal",
        given_name="Blaise",
    )
    write_expectations(directory, expect_tei=True)


def build_document_d() -> None:
    root = CORPUS / "document-d"
    cases: dict[str, tuple[dict[str, bytes | str], bool]] = {
        "unknown-custom-style": (
            {
                "[Content_Types].xml": CONTENT_TYPES,
                "word/document.xml": DOCUMENT_D_TEI_QUOTE,
                "word/styles.xml": STYLES_D_TEI_QUOTE,
            },
            False,
        ),
        "heading-level-jump": (
            {
                "[Content_Types].xml": CONTENT_TYPES,
                "word/document.xml": DOCUMENT_D_HEADING_JUMP,
                "word/styles.xml": STYLES_D_MINIMAL,
            },
            True,
        ),
        "discontinuous-list": (
            {
                "[Content_Types].xml": CONTENT_TYPES,
                "word/document.xml": DOCUMENT_D_DISCONTINUOUS_LIST,
                "word/styles.xml": STYLES_D_MINIMAL,
                "word/numbering.xml": NUMBERING_B,
            },
            False,
        ),
        "textbox": (
            {
                "[Content_Types].xml": CONTENT_TYPES,
                "word/document.xml": DOCUMENT_D_TEXTBOX,
                "word/styles.xml": STYLES_D_MINIMAL,
            },
            False,
        ),
    }
    for name, (files, expect_tei) in cases.items():
        directory = root / name
        write_package(directory / "source.docx", files)
        write_metadata(
            directory,
            title=f"Cas invalide {name}",
            subtitle=None,
            language="fr",
            family_name="Test",
            given_name="Corpus",
        )
        write_expectations(directory, expect_tei=expect_tei)

    malformed = root / "malformed-package"
    malformed.mkdir(parents=True, exist_ok=True)
    (malformed / "source.docx").write_bytes(b"not a ZIP package at all")
    write_metadata(
        malformed,
        title="Cas invalide malformed-package",
        subtitle=None,
        language="fr",
        family_name="Test",
        given_name="Corpus",
    )
    from mini_metopes.docx import DocxInspectionError
    from mini_metopes.metadata import load_metadata_file
    from mini_metopes.tei import convert_docx_to_tei

    loaded = load_metadata_file(malformed / "metadata.json")
    assert loaded.metadata is not None
    try:
        convert_docx_to_tei(malformed / "source.docx", metadata=loaded.metadata)
    except DocxInspectionError as error:
        (malformed / "expected-diagnostics.json").write_text(
            json.dumps({"inspection_error": error.code}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        raise AssertionError("le paquet malformé aurait dû lever DocxInspectionError")


def main() -> None:
    build_document_a()
    build_document_b()
    build_document_c()
    build_document_d()


if __name__ == "__main__":
    main()
