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

EDITORIAL_RELATIONSHIPS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdHyper" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://example.test/body" TargetMode="External"/>
  <Relationship Id="rIdImage" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/>
</Relationships>
"""

FOOTNOTE_RELATIONSHIPS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdHyper" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://example.test/footnote" TargetMode="External"/>
</Relationships>
"""

ENDNOTE_RELATIONSHIPS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdHyper" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://example.test/endnote" TargetMode="External"/>
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
  <w:footnote w:id="7">
    <w:p>
      <w:r><w:t>Note de bas de page </w:t></w:r>
      <w:r><w:rPr><w:i/></w:rPr><w:t>italique</w:t><w:br/><w:t>avec saut.</w:t></w:r>
    </w:p>
    <w:p><w:r><w:t>Second paragraphe de note.</w:t></w:r></w:p>
  </w:footnote>
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
      <w:r><w:t>Texte litteral [footnote:7]</w:t></w:r>
      <w:r>
        <w:t>avant tabulation</w:t><w:tab/><w:t>apres tabulation</w:t><w:br/><w:t>apres saut</w:t>
        <w:footnoteReference w:id="7"/>
        <w:drawing><w:docPr id="1" name="Image synthétique"/><a:blip r:embed="rIdImage"/></w:drawing>
      </w:r>
      <w:r><w:t>avant page</w:t><w:br w:type="page"/><w:t>apres page</w:t><w:br w:type="column"/><w:t>apres colonne</w:t></w:r>
      <w:bookmarkStart w:id="12" w:name="repere_synthetique"/>
      <w:hyperlink r:id="rIdHyper"><w:r><w:rPr><w:rStyle w:val="EmphasisChar"/></w:rPr><w:t>lien</w:t></w:r></w:hyperlink>
      <w:hyperlink w:anchor="repere_synthetique"><w:r><w:t>lien interne</w:t></w:r></w:hyperlink>
      <w:r><w:endnoteReference w:id="9"/></w:r>
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

EDITORIAL_STYLES = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="Titre 1 localise"/><w:pPr><w:outlineLvl w:val="4"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="Titre 2 localise"/><w:pPr><w:outlineLvl w:val="1"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading4"><w:name w:val="Titre 4 localise"/><w:pPr><w:outlineLvl w:val="3"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Titre bibliographique"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Sous-titre bibliographique"/></w:style>
  <w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Citation"/><w:pPr><w:outlineLvl w:val="1"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="IntenseQuote"><w:name w:val="Citation intense"/></w:style>
  <w:style w:type="paragraph" w:styleId="UnknownParagraph"><w:name w:val="Style local inconnu"/><w:pPr><w:outlineLvl w:val="2"/></w:pPr></w:style>
  <w:style w:type="character" w:styleId="Emphasis"><w:name w:val="Mise en evidence"/></w:style>
  <w:style w:type="character" w:styleId="Strong"><w:name w:val="Fort"/></w:style>
  <w:style w:type="character" w:styleId="UnknownCharacter"><w:name w:val="Caractere local"/></w:style>
</w:styles>
"""

EDITORIAL_FOOTNOTES = """<?xml version="1.0" encoding="UTF-8"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:footnote w:id="-1" w:type="separator"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>
  <w:footnote w:id="10"><w:p><w:r><w:rPr><w:rStyle w:val="Emphasis"/></w:rPr><w:t>Note italique</w:t></w:r><w:r><w:br/><w:t> suite </w:t></w:r><w:hyperlink r:id="rIdHyper"><w:r><w:t>lien note</w:t></w:r></w:hyperlink></w:p></w:footnote>
  <w:footnote w:id="99"><w:p><w:r><w:t>Note non appelee</w:t></w:r></w:p></w:footnote>
</w:footnotes>
"""

EDITORIAL_ENDNOTES = """<?xml version="1.0" encoding="UTF-8"?>
<w:endnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:endnote w:id="-1" w:type="separator"><w:p><w:r><w:separator/></w:r></w:p></w:endnote>
  <w:endnote w:id="20"><w:p><w:r><w:t>Note de fin </w:t></w:r><w:hyperlink r:id="rIdHyper"><w:r><w:t>lien fin</w:t></w:r></w:hyperlink></w:p></w:endnote>
</w:endnotes>
"""

EDITORIAL_DOCUMENT = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Bon</w:t></w:r><w:r><w:t>jour</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>Sous-section</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>
      <w:r><w:t>Texte </w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>gras</w:t></w:r>
      <w:r><w:rPr><w:i/></w:rPr><w:t> italique</w:t></w:r><w:r><w:rPr><w:smallCaps/></w:rPr><w:t> petites</w:t></w:r>
      <w:r><w:rPr><w:caps/></w:rPr><w:t> capitales</w:t></w:r><w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:t>2</w:t></w:r>
      <w:r><w:rPr><w:vertAlign w:val="subscript"/></w:rPr><w:t>i</w:t></w:r>
      <w:r><w:rPr><w:rStyle w:val="Emphasis"/></w:rPr><w:t> emphase</w:t></w:r>
      <w:r><w:rPr><w:rStyle w:val="Strong"/><w:b w:val="0"/></w:rPr><w:t> pas-fort</w:t></w:r>
      <w:r><w:rPr><w:rStyle w:val="UnknownCharacter"/></w:rPr><w:t> local</w:t></w:r>
      <w:r><w:t>A</w:t><w:tab/><w:t>B</w:t><w:br/><w:t>C</w:t><w:br w:type="page"/><w:t>D</w:t><w:br w:type="column"/><w:t>E</w:t></w:r>
      <w:hyperlink r:id="rIdHyper"><w:r><w:t>externe</w:t></w:r></w:hyperlink>
      <w:bookmarkStart w:id="1" w:name="repere"/><w:hyperlink w:anchor="repere"><w:r><w:t>interne</w:t></w:r></w:hyperlink>
      <w:r><w:t>avant-note</w:t><w:footnoteReference w:id="10"/><w:t>apres-note</w:t></w:r>
      <w:r><w:endnoteReference w:id="20"/></w:r>
      <w:r><w:drawing><w:docPr id="2" name="Dessin editorial"/><a:blip r:embed="rIdImage"/></w:drawing></w:r>
    </w:p>
    <w:p><w:r><w:t>Sans style</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="UnknownParagraph"/></w:pPr><w:r><w:t>Style inconnu</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr><w:r><w:t>Titre differe</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Subtitle"/></w:pPr><w:r><w:t>Sous-titre differe</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Quote"/></w:pPr><w:r><w:t>Citation differee</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="IntenseQuote"/></w:pPr><w:r><w:t>Citation poetique differee</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading4"/></w:pPr></w:p>
    <w:sectPr/>
  </w:body>
</w:document>
"""

QUOTATION_STYLES = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Citation localisee"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="IntenseQuote"><w:name w:val="Citation intense localisee"/><w:pPr><w:outlineLvl w:val="1"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Titre differe"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Sous-titre differe"/></w:style>
</w:styles>
"""

QUOTATION_DOCUMENT = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="Quote"/></w:pPr><w:r><w:rPr><w:b/></w:rPr><w:t>Premier</w:t></w:r><w:r><w:t> paragraphe</w:t><w:br/><w:t>avec retour</w:t></w:r><w:hyperlink r:id="rIdHyper"><w:r><w:rPr><w:i/></w:rPr><w:t> lien</w:t></w:r></w:hyperlink><w:r><w:footnoteReference w:id="30"/></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Quote"/></w:pPr><w:r><w:t>Second paragraphe.</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr><w:r><w:t>Interruption normale.</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Quote"/></w:pPr><w:r><w:t>Seconde citation.</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Quote"/></w:pPr></w:p>
    <w:p><w:pPr><w:pStyle w:val="IntenseQuote"/></w:pPr><w:r><w:t>Vers </w:t></w:r><w:r><w:t>un</w:t><w:br/><w:t>Vers </w:t></w:r><w:r><w:rPr><w:i/></w:rPr><w:t>deux</w:t></w:r><w:r><w:footnoteReference w:id="30"/><w:t> suite</w:t><w:br/><w:br/><w:t>Vers quatre</w:t><w:br w:type="page"/><w:t> apres page</w:t></w:r><w:hyperlink r:id="rIdHyper"><w:r><w:t> lien-vers</w:t></w:r></w:hyperlink></w:p>
    <w:p><w:pPr><w:pStyle w:val="IntenseQuote"/></w:pPr><w:r><w:t>Vers cinq</w:t><w:br/><w:t>Vers six</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="IntenseQuote"/></w:pPr><w:r><w:t>Strophe un seul vers</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="IntenseQuote"/></w:pPr></w:p>
    <w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr><w:r><w:t>Separation.</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="IntenseQuote"/></w:pPr><w:r><w:br/><w:t>Debut apres vide</w:t><w:br/></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr><w:r><w:t>Titre differe</w:t></w:r></w:p>
    <w:sectPr/>
  </w:body>
</w:document>
"""

QUOTATION_FOOTNOTES = """<?xml version="1.0" encoding="UTF-8"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:footnote w:id="-1" w:type="separator"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>
  <w:footnote w:id="30"><w:p><w:pPr><w:pStyle w:val="Quote"/></w:pPr><w:r><w:t>Citation dans note.</w:t></w:r></w:p><w:p><w:pPr><w:pStyle w:val="IntenseQuote"/></w:pPr><w:r><w:t>Vers note un</w:t><w:br/><w:t>Vers note deux</w:t></w:r><w:hyperlink r:id="rIdHyper"><w:r><w:t> lien-note</w:t></w:r></w:hyperlink></w:p></w:footnote>
</w:footnotes>
"""

QUOTATION_ENDNOTES = """<?xml version="1.0" encoding="UTF-8"?>
<w:endnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:endnote w:id="-1" w:type="separator"><w:p><w:r><w:separator/></w:r></w:p></w:endnote>
  <w:endnote w:id="40"><w:p><w:pPr><w:pStyle w:val="IntenseQuote"/></w:pPr><w:r><w:t>Vers fin</w:t></w:r></w:p></w:endnote>
</w:endnotes>
"""

QUOTATION_BODY_RELATIONSHIPS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdHyper" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://example.test/quote-body" TargetMode="External"/>
</Relationships>
"""

QUOTATION_FOOTNOTE_RELATIONSHIPS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdHyper" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://example.test/quote-footnote" TargetMode="External"/>
</Relationships>
"""

TEI_CONVERSION_DOCUMENT = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr><w:r><w:t>Avant le premier titre.</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Premiere section</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr><w:r><w:t>Texte </w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>gras</w:t></w:r><w:r><w:rPr><w:i/></w:rPr><w:t> italique</w:t></w:r><w:r><w:rPr><w:smallCaps/></w:rPr><w:t> petites</w:t></w:r><w:r><w:rPr><w:caps/></w:rPr><w:t> capitales</w:t></w:r><w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:t>2</w:t></w:r><w:r><w:rPr><w:vertAlign w:val="subscript"/></w:rPr><w:t>i</w:t></w:r><w:hyperlink r:id="rIdHyper"><w:r><w:t> lien</w:t></w:r></w:hyperlink><w:r><w:br/><w:t>apres retour</w:t><w:footnoteReference w:id="1"/><w:endnoteReference w:id="2"/></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Quote"/></w:pPr><w:r><w:t>Premier paragraphe cite.</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Quote"/></w:pPr><w:r><w:rPr><w:i/></w:rPr><w:t>Second paragraphe cite.</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="IntenseQuote"/></w:pPr><w:r><w:t>Vers un</w:t><w:br/><w:rPr><w:i/></w:rPr><w:t>Vers deux</w:t><w:footnoteReference w:id="1"/></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="IntenseQuote"/></w:pPr><w:r><w:t>Vers trois</w:t><w:br/><w:t>Vers quatre</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>Sous-section</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr><w:r><w:t>Texte de sous-section.</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading3"/></w:pPr><w:r><w:t>Niveau trois</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr><w:r><w:t>Texte final.</w:t></w:r></w:p>
    <w:sectPr/>
  </w:body>
</w:document>
"""

TEI_CONVERSION_FOOTNOTES = """<?xml version="1.0" encoding="UTF-8"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:footnote w:id="-1" w:type="separator"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>
  <w:footnote w:id="1"><w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr><w:r><w:t>Note de bas de page.</w:t></w:r></w:p><w:p><w:pPr><w:pStyle w:val="Quote"/></w:pPr><w:r><w:t>Citation dans la note.</w:t></w:r></w:p><w:p><w:pPr><w:pStyle w:val="IntenseQuote"/></w:pPr><w:r><w:t>Vers de note</w:t><w:br/><w:t>Suite de note</w:t></w:r></w:p></w:footnote>
</w:footnotes>
"""

TEI_CONVERSION_ENDNOTES = """<?xml version="1.0" encoding="UTF-8"?>
<w:endnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:endnote w:id="-1" w:type="separator"><w:p><w:r><w:separator/></w:r></w:p></w:endnote>
  <w:endnote w:id="2"><w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr><w:r><w:t>Note de fin.</w:t></w:r></w:p></w:endnote>
</w:endnotes>
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


def editorial_parts() -> dict[str, bytes | str]:
    return {
        "[Content_Types].xml": CONTENT_TYPES,
        "word/document.xml": EDITORIAL_DOCUMENT,
        "word/styles.xml": EDITORIAL_STYLES,
        "word/numbering.xml": NUMBERING,
        "word/footnotes.xml": EDITORIAL_FOOTNOTES,
        "word/endnotes.xml": EDITORIAL_ENDNOTES,
        "word/_rels/document.xml.rels": EDITORIAL_RELATIONSHIPS,
        "word/_rels/footnotes.xml.rels": FOOTNOTE_RELATIONSHIPS,
        "word/_rels/endnotes.xml.rels": ENDNOTE_RELATIONSHIPS,
        "word/media/image1.png": b"synthetic-editorial-image",
    }


def quotation_parts() -> dict[str, bytes | str]:
    return {
        "[Content_Types].xml": CONTENT_TYPES,
        "word/document.xml": QUOTATION_DOCUMENT,
        "word/styles.xml": QUOTATION_STYLES,
        "word/footnotes.xml": QUOTATION_FOOTNOTES,
        "word/endnotes.xml": QUOTATION_ENDNOTES,
        "word/_rels/document.xml.rels": QUOTATION_BODY_RELATIONSHIPS,
        "word/_rels/footnotes.xml.rels": QUOTATION_FOOTNOTE_RELATIONSHIPS,
    }


def tei_conversion_parts() -> dict[str, bytes | str]:
    return {
        "[Content_Types].xml": CONTENT_TYPES,
        "word/document.xml": TEI_CONVERSION_DOCUMENT,
        "word/styles.xml": EDITORIAL_STYLES,
        "word/footnotes.xml": TEI_CONVERSION_FOOTNOTES,
        "word/endnotes.xml": TEI_CONVERSION_ENDNOTES,
        "word/_rels/document.xml.rels": EDITORIAL_RELATIONSHIPS,
    }


def main() -> None:
    basic = standard_parts(BASIC_DOCUMENT)
    basic["word/media/image1.png"] = b"synthetic-png-not-for-display"
    write_package(FIXTURES / "basic-inspection.docx", basic)
    write_package(FIXTURES / "poetry-inspection.docx", standard_parts(POETRY_DOCUMENT))
    write_package(FIXTURES / "textbox-inspection.docx", standard_parts(TEXTBOX_DOCUMENT))
    write_package(FIXTURES / "native-editorial.docx", editorial_parts())
    write_package(FIXTURES / "native-quotations.docx", quotation_parts())
    write_package(FIXTURES / "native-tei-conversion.docx", tei_conversion_parts())
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
