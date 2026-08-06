"""Extensions du RNG Commons Publishing embarque pour le contrat Impressions.

Verifie, avant toute logique de serialisation, que le schema etendu (decision
0037) accepte les nouvelles valeurs/elements necessaires a la hierarchie de
titres livre (div/@type part|chapter|titlePage, p/@rend title-main|title-sub,
element group), et que le reste de l'enum ferme n'a pas ete ouvert par erreur.
"""

from __future__ import annotations

from mini_metopes.validation import validate_xml_bytes

_TEI_OPEN = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<TEI xmlns="http://www.tei-c.org/ns/1.0">\n'
    "  <teiHeader>\n"
    "    <fileDesc>\n"
    "      <titleStmt><title>Document minimal</title></titleStmt>\n"
    "      <publicationStmt><p>Publication de test.</p></publicationStmt>\n"
    "      <sourceDesc><p>Source de test.</p></sourceDesc>\n"
    "    </fileDesc>\n"
    "  </teiHeader>\n"
)
_TEI_CLOSE = "</TEI>\n"


def _wrap(text_xml: str) -> bytes:
    return (_TEI_OPEN + text_xml + _TEI_CLOSE).encode("utf-8")


def test_div_type_part_is_accepted() -> None:
    result = validate_xml_bytes(_wrap('<text><body><div type="part"><head>Partie I</head><p>Texte.</p></div></body></text>'))
    assert result.valid, result.issues


def test_div_type_chapter_is_accepted() -> None:
    result = validate_xml_bytes(_wrap('<text><body><div type="chapter"><head>Chapitre</head><p>Texte.</p></div></body></text>'))
    assert result.valid, result.issues


def test_div_type_titlepage_inside_front_is_accepted() -> None:
    result = validate_xml_bytes(
        _wrap(
            '<text><front><div type="titlePage"><p rend="title-main">Titre</p></div></front>'
            "<body><p>Texte.</p></body></text>"
        )
    )
    assert result.valid, result.issues


def test_p_rend_title_main_and_title_sub_are_accepted() -> None:
    result = validate_xml_bytes(
        _wrap(
            '<text><front><div type="titlePage">'
            '<p rend="title-main">Titre</p><p rend="title-sub">Sous-titre</p>'
            "</div></front><body><p>Texte.</p></body></text>"
        )
    )
    assert result.valid, result.issues


def test_group_of_texts_with_titlepage_is_accepted() -> None:
    result = validate_xml_bytes(
        _wrap(
            '<text><group type="article">'
            '<text><front><div type="titlePage"><p rend="title-main">Contribution un</p></div></front>'
            "<body><p>Corps un.</p></body></text>"
            '<text><front><div type="titlePage"><p rend="title-main">Contribution deux</p></div></front>'
            "<body><p>Corps deux.</p></body></text>"
            "</group></text>"
        )
    )
    assert result.valid, result.issues


def test_div_type_still_rejects_an_unknown_value() -> None:
    result = validate_xml_bytes(_wrap('<text><body><div type="bogus"><head>Titre</head><p>Texte.</p></div></body></text>'))
    assert not result.valid
    assert all(issue.domain == "relaxng" for issue in result.issues)


def test_p_rend_still_rejects_an_unknown_value() -> None:
    result = validate_xml_bytes(_wrap('<text><body><p rend="bogus">Texte.</p></body></text>'))
    assert not result.valid
    assert all(issue.domain == "relaxng" for issue in result.issues)
