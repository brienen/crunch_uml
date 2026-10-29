"""
Tests voor de pure MIM 1.2-hulpfuncties in crunch_uml/renderers/mim.py:
opschoning van EA-tagwaarden, datums, booleans, kardinaliteit (MIM 6.4.9.15
en 6.4.9.18), lengte (6.4.9.21), authenticiteit en de soortbepaling van
modelklassen. Geen database nodig.
"""

import datetime
from types import SimpleNamespace

import pytest
from rdflib import Literal
from rdflib.namespace import XSD

from crunch_uml.renderers import mim

# ---------------------------------------------------------------------------
# Opschonen van EA-tagwaarden
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ruw,verwacht",
    [
        ("BRP", "BRP"),
        ("  BRP  ", "BRP"),
        # Waarde met de notities van de tagdefinitie erachter.
        ("BRP#NOTES#Description: De registratie ...", "BRP"),
        ("Ja#NOTES#Values: Ja,Nee\nDefault: Nee\n", "Ja"),
        # Alleen een tagdefinitie, geen waarde.
        ("#NOTES#Description: De datum waarop ...", None),
        # Memo-tag: de echte tekst staat achter #NOTES# ...
        ("<memo>#NOTES#Elf cijfers", "Elf cijfers"),
        # ... maar niet als daar alleen de tagdefinitie staat.
        ("<memo>#NOTES#Description: Een toelichting", None),
        # Herhaalde memotekst (EA plakt die bij elke profielsynchronisatie opnieuw aan).
        ("<memo>#NOTES#Zin.#NOTES#Zin.#NOTES#Zin.", "Zin."),
        ("<memo>#NOTES#Zin.\n\n#NOTES#Zin.\n\n#NOTES#Zin.", "Zin."),
        ("<memo>#NOTES#Eerste.#NOTES#Tweede.#NOTES#Eerste.", "Eerste.\n\nTweede."),
        ("<memo>#NOTES#Tekst#NOTES#Description: Aanvullende beschrijving", "Tekst"),
        ("\u2022\tTekst#NOTES#Description: A#NOTES#Description: A", "\u2022\tTekst"),
        ("<memo>", None),
        ("nan", None),
        ("None", None),
        ("", None),
        (None, None),
        ("<niet gespecificeerd>", None),
    ],
)
def test_clean_value(ruw, verwacht):
    assert mim.clean_value(ruw) == verwacht


@pytest.mark.parametrize(
    "ruw,verwacht",
    [
        ("BRP", ("BRP", None)),
        ("BRP#NOTES#Description: De registratie ...", ("BRP", None)),
        ("#NOTES#Description: De datum ...", ("", None)),
        ("<memo>#NOTES#Elf cijfers", ("<memo>", "Elf cijfers")),
        ("<memo>#NOTES#Zin.#NOTES#Zin.#NOTES#Zin.", ("<memo>", "Zin.")),
        ("<memo>#NOTES#Eerste.#NOTES#Tweede.", ("<memo>", "Eerste.\r\n\r\nTweede.")),
        ("<memo>#NOTES#Description: Een toelichting", ("<memo>", "")),
        ("<memo>", ("<memo>", None)),
        (None, (None, None)),
    ],
)
def test_split_tag_value(ruw, verwacht):
    assert mim.split_tag_value(ruw) == verwacht


@pytest.mark.parametrize(
    "ruw,verwacht",
    [
        ('Representatie van <font color="#993300">Feature</font>.', "Representatie van Feature."),
        ("cre&#235;ren en &amp;", "creëren en &"),
        ("<b>Let op</b>: <i>x</i> en <u>y</u>", "Let op: x en y"),
        (
            "Woonplaats:\n<ul>\n\t<li>naam</li>\n\t<li>status </li>\n</ul>\nEinde",
            "Woonplaats:\n\n- naam\n- status\n\nEinde",
        ),
        ("<ol><li>een</li><li>twee</li></ol>", "1. een\n2. twee"),
        ("regel 1<br>regel 2<br/>regel 3", "regel 1\nregel 2\nregel 3"),
        ("<p>Eerste</p><p>Tweede</p>", "Eerste\n\nTweede"),
        # Geen HTML: ongemoeid, ook met '<' of '&' in een naam.
        ("bijstandsnorm 1 pnr < 21 jr (adresloze)", "bijstandsnorm 1 pnr < 21 jr (adresloze)"),
        ("Q & A", "Q & A"),
        ("Gewone tekst\n\nmet alinea", "Gewone tekst\n\nmet alinea"),
        ("", ""),
        (None, None),
    ],
)
def test_plain_text(ruw, verwacht):
    assert mim.plain_text(ruw) == verwacht


def test_lang_literal_maakt_platte_tekst_van_html():
    assert mim.lang_literal('<font color="#1">A &amp; B</font> ', "nl") == Literal("A & B", lang="nl")
    assert mim.lang_literal("x < 21", None) == Literal("x < 21")


@pytest.mark.parametrize(
    "ruw,verwacht",
    [
        ("Ja", True),
        ("ja", True),
        ("True", True),
        ("1", True),
        ("Nee", False),
        ("false", False),
        ("0", False),
        ("Nee#NOTES#Values: Ja,Nee", False),
        ("n.v.t.", None),
        ("zie groep", None),
        ("Zie groep", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_bool(ruw, verwacht):
    assert mim.parse_bool(ruw) is verwacht


@pytest.mark.parametrize(
    "ruw,verwacht",
    [
        ("2007-04-09", datetime.date(2007, 4, 9)),
        ("2007-04-09 00:00:00", datetime.date(2007, 4, 9)),
        ("2016-05-01T12:00:00", datetime.date(2016, 5, 1)),
        ("9-4-2007", datetime.date(2007, 4, 9)),
        ("09/04/2007", datetime.date(2007, 4, 9)),
        ("20070409", datetime.date(2007, 4, 9)),
        ("1 mei 2016", datetime.date(2016, 5, 1)),
        ("9 april 2007", datetime.date(2007, 4, 9)),
        ("30 november 2007", datetime.date(2007, 11, 30)),
        ("1 maart 2009", datetime.date(2009, 3, 1)),
        ("24-Apr-09", datetime.date(2009, 4, 24)),
        ("27-Apr-09", datetime.date(2009, 4, 27)),
        ("12 March 2021", datetime.date(2021, 3, 12)),
        # Met tagdefinitie erachter.
        ("2007-04-09 00:00:00#NOTES#Description: De datum ...", datetime.date(2007, 4, 9)),
        # Onbruikbaar.
        ("#NOTES#Description: De datum ...", None),
        ("31 februari 2009", None),
        ("binnenkort", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_date(ruw, verwacht):
    assert mim.parse_date(ruw) == verwacht


def test_date_literal_is_xsd_date():
    assert mim.date_literal("1 mei 2016") == Literal("2016-05-01", datatype=XSD.date)
    assert mim.date_literal("onbekend") is None


@pytest.mark.parametrize("ruw,verwacht", [("50.0", "50"), ("50", "50"), ("6,2", "6,2"), ("1..99", "1..99"), ("", None)])
def test_normalize_number(ruw, verwacht):
    assert mim.normalize_number(ruw) == verwacht


def test_lang_literal():
    assert mim.lang_literal("Zaak", "nl") == Literal("Zaak", lang="nl")
    assert mim.lang_literal("Zaak", "") == Literal("Zaak")
    assert mim.lang_literal("Zaak", None) == Literal("Zaak")


# ---------------------------------------------------------------------------
# Kardinaliteit
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "start,eind,verwacht",
    [
        ("0", "-1", "0..*"),
        ("0", "*", "0..*"),
        ("0", "n", "0..*"),
        ("0", "N", "0..*"),
        ("1", "1", "1..1"),
        ("0", "1", "0..1"),
        ("1", "-1", "1..*"),
        ("1", "2", "1..2"),
        ("2", "-1", "2..*"),
        # Onbekend of onbruikbaar.
        (None, None, None),
        ("None", "None", None),
        ("1", None, None),
        ("-1", "-1", None),
        ("", "1", None),
        ("a", "b", None),
    ],
)
def test_kardinaliteit(start, eind, verwacht):
    assert mim.kardinaliteit(start, eind) == verwacht


@pytest.mark.parametrize(
    "kard,mgw,verwacht",
    [
        # Tabel MIM 6.4.9.15.
        ("1", None, (1, 1)),
        ("*", None, (None, None)),
        ("0..1", None, (None, 1)),
        ("0..*", None, (None, None)),
        ("1..1", None, (1, 1)),
        ("1..*", None, (1, None)),
        ("2..5", None, (2, 5)),
        # MIM 6.4.9.18: bij mogelijk geen waarde vervalt sh:minCount.
        ("1..1", True, (None, 1)),
        ("1..*", True, (None, None)),
        ("2..5", True, (None, 5)),
        ("0..1", True, (None, 1)),
        ("1..1", False, (1, 1)),
        # Onbruikbaar.
        (None, None, (None, None)),
        ("0..0", None, (None, None)),
        ("3..1", None, (None, None)),
    ],
)
def test_min_max_count(kard, mgw, verwacht):
    assert mim.min_max_count(kard, mgw) == verwacht


@pytest.mark.parametrize(
    "lengte,verwacht",
    [
        ("..99", (None, 99)),
        ("1..", (1, None)),
        ("1..99", (1, 99)),
        # Kaal getal: maximumlengte (GGM-conventie, zoals AN50).
        ("50", (None, 50)),
        ("50.0", (None, 50)),
        # Getalnotatie voor numerieke types is geen tekenlengte.
        ("6,2", (None, None)),
        ("", (None, None)),
        (None, (None, None)),
    ],
)
def test_lengte_bounds(lengte, verwacht):
    assert mim.lengte_bounds(lengte) == verwacht


# ---------------------------------------------------------------------------
# Waardelijsten
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ruw,verwacht",
    [
        ("Authentiek", mim.MIM.Authentiek),
        ("authentiek", mim.MIM.Authentiek),
        ("Basisgegeven", mim.MIM.Basisgegeven),
        ("Wettelijk gegeven", mim.MIM.WettelijkGegeven),
        ("Landelijk kerngegeven", mim.MIM.LandelijkKerngegeven),
        ("Overig", mim.MIM.OverigeAuthenticiteit),
        ("Gemeentelijk kerngegeven", mim.MIM.OverigeAuthenticiteit),
        ("Authentiek#NOTES#Values: Authentiek,Basisgegeven", mim.MIM.Authentiek),
        ("Authentiek indien de status 'bestaand' is", None),
        ("", None),
        (None, None),
    ],
)
def test_authenticiteit(ruw, verwacht):
    assert mim.authenticiteit(ruw) == verwacht


def test_informatiemodeltype():
    assert mim.informatiemodeltype("logisch") == mim.MIM.LogischInformatiemodel
    assert mim.informatiemodeltype("Conceptueel") == mim.MIM.ConceptueelInformatiemodel
    assert mim.informatiemodeltype("technisch") == mim.MIM.TechnischInformatiemodel
    assert mim.informatiemodeltype("fysiek") is None


@pytest.mark.parametrize(
    "xsd_type,verwacht",
    [
        (XSD.string, mim.MIM.CharacterString),
        (XSD.integer, mim.MIM.Integer),
        (XSD.decimal, mim.MIM.Decimal),
        (XSD.double, mim.MIM.Real),
        (XSD.boolean, mim.MIM.Boolean),
        (XSD.date, mim.MIM.Date),
        (XSD.dateTime, mim.MIM.DateTime),
        (XSD.gYear, mim.MIM.Year),
        (XSD.anyURI, mim.MIM.URI),
        (XSD.time, None),
        (XSD.base64Binary, None),
    ],
)
def test_mim_datatype(xsd_type, verwacht):
    assert mim.mim_datatype(xsd_type) == verwacht


# ---------------------------------------------------------------------------
# Soort modelklasse
# ---------------------------------------------------------------------------


def klasse(stereotype=None, package=None, is_datatype=False):
    return SimpleNamespace(stereotype=stereotype, package=SimpleNamespace(name=package), is_datatype=is_datatype)


@pytest.mark.parametrize(
    "cls,verwacht",
    [
        (klasse("Objecttype", "Model Kern"), mim.OBJECTTYPE),
        (klasse(None, "Model Kern"), mim.OBJECTTYPE),
        # Het stereotype wint als het specifiek is.
        (klasse("Gegevensgroeptype", "Model Kern"), mim.GEGEVENSGROEPTYPE),
        (klasse("Gestructureerd datatype", "Model Kern"), mim.GESTRUCTUREERD_DATATYPE),
        (klasse("Relatieklasse", "Model Kern"), mim.RELATIEKLASSE),
        (klasse("Referentielijst", "Model Kern"), mim.REFERENTIELIJST),
        (klasse("Codelijst", "Model Kern"), mim.CODELIJST),
        # GGM: het pakket bepaalt het, ook al staat er 'Objecttype' op.
        (klasse("Objecttype", "Groepattribuutsoort"), mim.GEGEVENSGROEPTYPE),
        (klasse(None, "Complex datatype", is_datatype=True), mim.GESTRUCTUREERD_DATATYPE),
        (klasse(None, "Datatypes", is_datatype=True), mim.GESTRUCTUREERD_DATATYPE),
        (klasse(None, "Union", is_datatype=True), mim.GESTRUCTUREERD_DATATYPE),
        (klasse(None, "Model Kern", is_datatype=True), mim.GESTRUCTUREERD_DATATYPE),
        (klasse("Objecttype", "Referentielijsten"), mim.REFERENTIELIJST),
    ],
)
def test_mim_soort(cls, verwacht):
    assert mim.mim_soort(cls) == verwacht


def test_mim_soort_zonder_pakket():
    assert mim.mim_soort(SimpleNamespace(stereotype="Objecttype", package=None, is_datatype=False)) == mim.OBJECTTYPE
