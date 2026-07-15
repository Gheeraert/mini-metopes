"""Fabriquer les petites fixtures DOCX synthétiques de l'inspecteur.

Ce script de maintenance n'est pas appelé par les tests. Il écrit uniquement
dans ``tests/fixtures/docx`` et fixe les horodatages ZIP pour des binaires
reproductibles.
"""

from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "docx"

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
  <Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>
  <Override PartName="/word/endnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml"/>
</Types>
"""

RELATIONSHIPS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdHyper" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://example.test/notice" TargetMode="External"/>
  <Relationship Id="rIdImage" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/>
</Relationships>
"""

STYLES = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
  </w:style>
  <w:style w:type="paragraph" w:customStyle="1" w:styleId="Heading1">
    <w:name w:val="Titre 1"/>
    <w:basedOn w:val="Normal"/>
    <w:link w:val="Heading1Char"/>
    <w:qFormat/>
    <w:uiPriority w:val="9"/>
    <w:pPr><w:outlineLvl w:val="0"/></w:pPr>
  </w:style>
  <w:style w:type="character" w:styleId="Heading1Char">
    <w:name w:val="Titre 1 Caractère"/>
    <w:link w:val="Heading1"/>
  </w:style>
  <w:style w:type="character" w:styleId="EmphasisChar">
    <w:name w:val="Accent synthétique"/>
  </w:style>
  <w:style w:type="paragraph" w:customStyle="1" w:styleId="TEIverse">
    <w:name w:val="Vers d'observation"/>
    <w:basedOn w:val="Normal"/>
  </w:style>
</w:styles>
"""

NUMBERING = """<?xml version="1.0" encoding="UTF-8"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="1"/></w:abstractNum>
  <w:num w:numId="42"><w:abstractNumId w:val="1"/></w:num>
</w:numbering>
"""

FOOTNOTES = """<?xml version="1.0" encoding="UTF-8"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:footnote w:id="-1" w:type="separator"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>
  <w:footnote w:id="7"><w:p><w:r><w:t>Note de bas de page synthétique.</w:t></w:r></w:p></w:footnote>
  <w:footnote w:id="3"><w:p><w:r><w:t>Note dans le vers synthétique.</w:t></w:r></w:p></w:footnote>
</w:footnotes>
"""

ENDNOTES = """<?xml version="1.0" encoding="UTF-8"?>
<w:endnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:endnote w:id="-1" w:type="separator"><w:p><w:r><w:separator/></w:r></w:p></w:endnote>
  <w:endnote w:id="9"><w:p><w:r><w:t>Note de fin synthétique.</w:t></w:r></w:p></w:endnote>
</w:endnotes>
"""

BASIC_DOCUMENT = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Titre synthétique</w:t></w:r></w:p>
    <w:p>
      <w:pPr><w:pStyle w:val="Normal"/></w:pPr>
      <w:r><w:t xml:space="preserve">Texte </w:t></w:r>
      <w:r><w:rPr><w:b/></w:rPr><w:t>gras</w:t></w:r>
      <w:r><w:rPr><w:b w:val="0"/></w:rPr><w:t> non gras</w:t></w:r>
      <w:r><w:rPr><w:i/></w:rPr><w:t> italique</w:t></w:r>
      <w:r><w:rPr><w:smallCaps/></w:rPr><w:t> petites capitales</w:t></w:r>
      <w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:t>2</w:t></w:r>
      <w:r><w:rPr><w:vertAlign w:val="subscript"/></w:rPr><w:t>i</w:t></w:r>
      <w:r><w:tab/><w:t>après tabulation</w:t><w:br/><w:t>après saut</w:t></w:r>
      <w:bookmarkStart w:id="12" w:name="repere_synthetique"/>
      <w:hyperlink r:id="rIdHyper"><w:r><w:rPr><w:rStyle w:val="EmphasisChar"/></w:rPr><w:t>lien</w:t></w:r></w:hyperlink>
      <w:r><w:footnoteReference w:id="7"/></w:r>
      <w:r><w:endnoteReference w:id="9"/></w:r>
      <w:r><w:drawing><w:docPr id="1" name="Image synthétique"/><a:blip r:embed="rIdImage"/></w:drawing></w:r>
    </w:p>
    <w:p><w:pPr><w:pStyle w:val="Normal"/><w:numPr><w:ilvl w:val="1"/><w:numId w:val="42"/></w:numPr></w:pPr><w:r><w:t>Élément numéroté</w:t></w:r></w:p>
    <w:sectPr/>
  </w:body>
</w:document>
"""

POETRY_DOCUMENT = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="TEIverse"/></w:pPr>
      <w:r><w:t>Premier vers </w:t></w:r>
      <w:r><w:rPr><w:i/></w:rPr><w:t>italique</w:t><w:br/><w:t>Deuxième vers</w:t><w:br/><w:t>Troisième vers</w:t></w:r>
      <w:r><w:footnoteReference w:id="3"/></w:r>
    </w:p>
    <w:p><w:pPr><w:pStyle w:val="TEIverse"/></w:pPr>
      <w:r><w:t>Premier vers seconde strophe</w:t><w:br/><w:t>Deuxième vers seconde strophe</w:t></w:r>
    </w:p>
    <w:sectPr/>
  </w:body>
</w:document>
"""

TEXTBOX_DOCUMENT = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:t>Texte exterieur</w:t></w:r>
      <w:r>
        <w:drawing>
          <w:txbxContent>
            <w:p><w:r><w:t>Texte de la zone</w:t></w:r></w:p>
          </w:txbxContent>
        </w:drawing>
      </w:r>
    </w:p>
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


def standard_parts(document: str) -> dict[str, bytes | str]:
    return {
        "[Content_Types].xml": CONTENT_TYPES,
        "word/document.xml": document,
        "word/styles.xml": STYLES,
        "word/numbering.xml": NUMBERING,
        "word/footnotes.xml": FOOTNOTES,
        "word/endnotes.xml": ENDNOTES,
        "word/_rels/document.xml.rels": RELATIONSHIPS,
    }


def main() -> None:
    basic = standard_parts(BASIC_DOCUMENT)
    basic["word/media/image1.png"] = b"synthetic-png-not-for-display"
    write_package(FIXTURES / "basic-inspection.docx", basic)
    write_package(FIXTURES / "poetry-inspection.docx", standard_parts(POETRY_DOCUMENT))
    write_package(FIXTURES / "textbox-inspection.docx", standard_parts(TEXTBOX_DOCUMENT))
    write_package(
        FIXTURES / "optional-parts-absent.docx",
        {
            "word/document.xml": """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Minimal</w:t></w:r></w:p></w:body></w:document>""",
        },
    )
    (FIXTURES / "not-a-zip.docx").write_bytes(b"not a ZIP package")
    write_package(FIXTURES / "without-document.docx", {"[Content_Types].xml": CONTENT_TYPES})
    write_package(
        FIXTURES / "malformed-document.docx",
        {"word/document.xml": "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"},
    )


if __name__ == "__main__":
    main()
