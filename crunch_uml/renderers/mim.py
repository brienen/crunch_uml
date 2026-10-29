"""MIM 1.2-hulpfuncties voor de LOD-renderer.

Dit zijn de pure vertaalregels uit MIM 1.2 (Geonovum, hoofdstuk 4 en bijlage
6.4 "Transformatie MIM - RDFS/OWL/SHACL") plus de opschoning van EA-tagwaarden
zoals die in GGM-databases voorkomen. De module kent geen database en geen
rdflib-graaf; de renderer plakt de uitkomsten op de juiste resources.

Vocabulaire: https://docs.geostandaarden.nl/mim/mim/media/mim.ttl
Shapes:      https://docs.geostandaarden.nl/mim/mim/media/mim-shapes.ttl
"""

import datetime
import re
from typing import Optional, Tuple

from rdflib import Literal, Namespace, URIRef
from rdflib.namespace import XSD

MIM = Namespace("http://modellen.mim-standaard.nl/def/mim#")
MIM_VERSIE = "1.2"

# MIM-metaklassen zoals de renderer ze aan modelklassen toekent.
OBJECTTYPE = "Objecttype"
GEGEVENSGROEPTYPE = "Gegevensgroeptype"
GESTRUCTUREERD_DATATYPE = "GestructureerdDatatype"
RELATIEKLASSE = "Relatieklasse"
REFERENTIELIJST = "Referentielijst"
CODELIJST = "Codelijst"

# ---------------------------------------------------------------------------
# Opschonen van EA-tagwaarden
# ---------------------------------------------------------------------------

# EA zet achter de waarde van een tagged value met '#NOTES#' de notities van
# de tagdefinitie ("Description: ...", "Values: Ja,Nee", "Default: ..."). Bij
# een memo-tag staat vóór '#NOTES#' de placeholder '<memo>' en erachter soms
# de echte tekst.
_NOTES_SEP = "#NOTES#"
_TAG_META_RE = re.compile(r"^(description|values|default|type)\s*:", re.IGNORECASE)
_PLACEHOLDERS = {"", "<memo>", "nan", "none", "null", "<niet gespecificeerd>", "<geen>"}


def clean_value(value) -> Optional[str]:
    """Maak van een EA-tagwaarde de kale waarde, of None als er geen is.

    * ``'BRP#NOTES#Description: ...'`` -> ``'BRP'``;
    * ``'<memo>#NOTES#Elf cijfers'`` -> ``'Elf cijfers'`` (memo-tekst), maar
      ``'<memo>#NOTES#Description: ...'`` -> None (alleen tagdefinitie);
    * placeholders (``'<memo>'``, ``'nan'``, lege string) -> None.
    """
    if value is None:
        return None
    text = str(value)
    if _NOTES_SEP in text:
        head, tail = text.split(_NOTES_SEP, 1)
        head, tail = head.strip(), tail.strip()
        if head.casefold() == "<memo>" and tail and not _TAG_META_RE.match(tail):
            text = tail
        else:
            text = head
    text = text.strip()
    if text.casefold() in _PLACEHOLDERS:
        return None
    return text


_TRUE_WORDS = {"ja", "j", "true", "waar", "yes", "y", "1"}
_FALSE_WORDS = {"nee", "n", "false", "onwaar", "no", "0"}


def parse_bool(value) -> Optional[bool]:
    """'Ja'/'Nee' (en varianten) naar bool; onbekende tekst ('n.v.t.',
    'zie groep') geeft None, zodat de aanroeper de MIM-default kan kiezen."""
    text = clean_value(value)
    if text is None:
        return None
    word = text.casefold()
    if word in _TRUE_WORDS:
        return True
    if word in _FALSE_WORDS:
        return False
    return None


_MONTHS = {
    "januari": 1, "jan": 1, "january": 1,
    "februari": 2, "feb": 2, "february": 2,
    "maart": 3, "mrt": 3, "mar": 3, "march": 3,
    "april": 4, "apr": 4,
    "mei": 5, "may": 5,
    "juni": 6, "jun": 6, "june": 6,
    "juli": 7, "jul": 7, "july": 7,
    "augustus": 8, "aug": 8, "august": 8,
    "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "okt": 10, "oct": 10, "october": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}  # fmt: skip

_ISO_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T].*)?$")
_DMY_RE = re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})(?:[ T].*)?$")
_YMD_COMPACT_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
_DAY_MONTHNAME_RE = re.compile(r"^(\d{1,2})[ -]([A-Za-z]+)\.?[ -](\d{2}|\d{4})$")


def parse_date(value) -> Optional[datetime.date]:
    """Datum uit de vormen die in EA-modellen voorkomen: ``2007-04-09``,
    ``2007-04-09 00:00:00``, ``9-4-2007``, ``20070409``, ``9 april 2007``,
    ``1 mei 2016``, ``24-Apr-09``. Onherkenbaar of ongeldig -> None."""
    text = clean_value(value)
    if text is None:
        return None
    try:
        if m := _ISO_RE.match(text):
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if m := _DMY_RE.match(text):
            return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if m := _YMD_COMPACT_RE.match(text):
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if m := _DAY_MONTHNAME_RE.match(text):
            month = _MONTHS.get(m.group(2).casefold())
            if month is None:
                return None
            year = int(m.group(3))
            if year < 100:
                year += 2000 if year < 70 else 1900
            return datetime.date(year, month, int(m.group(1)))
    except ValueError:
        return None
    return None


def date_literal(value) -> Optional[Literal]:
    """xsd:date-literal voor een datumtekst, of None als die niet te lezen is."""
    parsed = parse_date(value)
    return Literal(parsed.isoformat(), datatype=XSD.date) if parsed is not None else None


def normalize_number(value) -> Optional[str]:
    """'50.0' -> '50' (Excel-import schrijft gehele getallen als float);
    andere teksten ongewijzigd."""
    text = clean_value(value)
    if text is None:
        return None
    if re.fullmatch(r"-?\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


_VERSION_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


def version_segment(versie) -> Optional[str]:
    """Een versie als IRI-padsegment: ``v3.0.0`` blijft ``v3.0.0`` (punten zijn
    toegestaan in een IRI-pad), spaties en andere tekens worden ``-``. Wordt
    gebruikt voor ``owl:versionIRI`` en voor de graph-IRI's van views, zodat
    beide onder ``{basis}{versie}/`` vallen."""
    text = clean_value(versie)
    if text is None:
        return None
    return _VERSION_SEGMENT_RE.sub("-", text).strip("-.") or None


def lang_literal(text, lang: Optional[str]) -> Literal:
    """Literal met taaltag als er een taal is ingesteld, anders zonder.
    Witruimte aan begin en eind valt weg: EA bewaart een naam als
    'woonplaats ingetrokken ' met spatie, en die hoort niet in een label."""
    if isinstance(text, str):
        text = text.strip()
    return Literal(text, lang=lang) if lang else Literal(text)


# ---------------------------------------------------------------------------
# Kardinaliteit (MIM 6.4.9.15 en 6.4.9.18)
# ---------------------------------------------------------------------------

_UNBOUNDED = {"-1", "*", "n", "unbounded"}


def kardinaliteit(start, end) -> Optional[str]:
    """MIM-notatie ``a..z`` uit een (lower, upper)-paar zoals EA dat levert:
    ('0', '-1') -> '0..*', ('1', '1') -> '1..1', ('0', 'n') -> '0..*'.
    Onbekend of onbruikbaar (None, 'None', letters) -> None."""
    lower = clean_value(start)
    upper = clean_value(end)
    if lower is None or upper is None:
        return None
    lower = normalize_number(lower)
    upper = normalize_number(upper)
    if upper is not None and upper.casefold() in _UNBOUNDED:
        upper = "*"
    if lower is None or upper is None or not lower.isdigit() or not (upper == "*" or upper.isdigit()):
        return None
    return f"{lower}..{upper}"


def min_max_count(
    kard: Optional[str], mogelijk_geen_waarde: Optional[bool] = None
) -> Tuple[Optional[int], Optional[int]]:
    """(sh:minCount, sh:maxCount) voor een MIM-kardinaliteit.

    Tabel 6.4.9.15: '1' -> (1, 1); '*' -> (None, None); '0..1' -> (None, 1);
    '1..*' -> (1, None); 'a..z' -> (a, z). Een minimum van 0 wordt niet
    opgenomen. Bij mim:mogelijkGeenWaarde = true vervalt sh:minCount
    (6.4.9.18). Een onbruikbare kardinaliteit ('0..0', 'z' < 'a') geeft
    (None, None)."""
    if kard is None:
        return None, None
    if ".." in kard:
        lower, upper = kard.split("..", 1)
    else:
        lower = upper = kard
    if lower == "*":
        lower = "0"
    if not lower.isdigit() or not (upper == "*" or upper.isdigit()):
        return None, None
    min_count: Optional[int] = int(lower)
    max_count: Optional[int] = None if upper == "*" else int(upper)
    if max_count is not None and (max_count == 0 or max_count < min_count):  # type: ignore[operator]
        return None, None
    if min_count == 0 or mogelijk_geen_waarde:
        min_count = None
    return min_count, max_count


def lengte_bounds(lengte) -> Tuple[Optional[int], Optional[int]]:
    """(sh:minLength, sh:maxLength) voor mim:lengte.

    MIM 6.4.9.21: '..99' -> (None, 99); '1..' -> (1, None); '1..99' -> (1, 99).
    Een kaal getal ('50', '50.0') is in GGM-modellen de maximumlengte (zoals
    bij AN50) en geeft daarom (None, 50); dat wijkt af van de MIM-lezing
    'exact 50 tekens'. Niet-numeriek (bijv. '6,2' voor getallen) -> (None, None).
    """
    text = normalize_number(lengte)
    if text is None:
        return None, None
    if ".." in text:
        lower, upper = (part.strip() for part in text.split("..", 1))
        lower_n = int(lower) if lower.isdigit() else None
        upper_n = int(upper) if upper.isdigit() else None
        return lower_n, upper_n
    if text.isdigit():
        return None, int(text)
    return None, None


# ---------------------------------------------------------------------------
# Waardelijsten uit het MIM-vocabulaire
# ---------------------------------------------------------------------------

_AUTHENTICITEIT = {
    "authentiek": MIM.Authentiek,
    "basisgegeven": MIM.Basisgegeven,
    "wettelijkgegeven": MIM.WettelijkGegeven,
    "landelijkkerngegeven": MIM.LandelijkKerngegeven,
    # MIM: 'Overig' is alles wat geen van de voorgaande categorieën is; de
    # GGM-eigen aanduidingen vallen daaronder.
    "overig": MIM.OverigeAuthenticiteit,
    "overigeauthenticiteit": MIM.OverigeAuthenticiteit,
    "gemeentelijkkerngegeven": MIM.OverigeAuthenticiteit,
    "gemeentelijkbasisgegeven": MIM.OverigeAuthenticiteit,
    "nietauthentiek": MIM.OverigeAuthenticiteit,
}


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def authenticiteit(value) -> Optional[URIRef]:
    """Concept uit het scheme mim:Authenticiteit voor een tagwaarde, of None
    als de tekst geen (bekende) categorie is."""
    text = clean_value(value)
    if text is None:
        return None
    return _AUTHENTICITEIT.get(_key(text))


_INFORMATIEMODELTYPEN = {
    "conceptueel": MIM.ConceptueelInformatiemodel,
    "logisch": MIM.LogischInformatiemodel,
    "technisch": MIM.TechnischInformatiemodel,
}


def informatiemodeltype(value) -> Optional[URIRef]:
    text = clean_value(value)
    return _INFORMATIEMODELTYPEN.get(text.casefold()) if text else None


# Standaarddatatypen (MIM 6.4.6.2) van XSD terug naar het MIM-datatype.
_XSD_NAAR_MIM = {
    XSD.string: MIM.CharacterString,
    XSD.integer: MIM.Integer,
    XSD.int: MIM.Integer,
    XSD.long: MIM.Integer,
    XSD.nonNegativeInteger: MIM.Integer,
    XSD.positiveInteger: MIM.Integer,
    XSD.decimal: MIM.Decimal,
    XSD.float: MIM.Real,
    XSD.double: MIM.Real,
    XSD.boolean: MIM.Boolean,
    XSD.date: MIM.Date,
    XSD.dateTime: MIM.DateTime,
    XSD.gYear: MIM.Year,
    XSD.gDay: MIM.Day,
    XSD.gMonth: MIM.Month,
    XSD.anyURI: MIM.URI,
}


def mim_datatype(xsd_type) -> Optional[URIRef]:
    """Het MIM-primitieve datatype dat bij een XSD-datatype hoort, of None
    (bijv. geo:wktLiteral, xsd:time, xsd:base64Binary)."""
    return _XSD_NAAR_MIM.get(xsd_type)


# ---------------------------------------------------------------------------
# Soort modelklasse
# ---------------------------------------------------------------------------

_STEREOTYPE_SOORT = {
    "gegevensgroeptype": GEGEVENSGROEPTYPE,
    "groepattribuutsoort": GEGEVENSGROEPTYPE,
    "gestructureerddatatype": GESTRUCTUREERD_DATATYPE,
    "complexdatatype": GESTRUCTUREERD_DATATYPE,
    "datatype": GESTRUCTUREERD_DATATYPE,
    "relatieklasse": RELATIEKLASSE,
    "referentielijst": REFERENTIELIJST,
    "codelijst": CODELIJST,
}


def mim_soort(cls) -> str:
    """Welke MIM-metaklasse een modelklasse vertegenwoordigt.

    Een specifiek stereotype wint; anders beslist het pakket waarin de klasse
    staat (GGM: 'Groepattribuutsoort', 'Complex datatype', 'Datatypes',
    'Union', 'Referentielijsten') of de datatype-vlag; de rest is Objecttype.
    """
    soort = _STEREOTYPE_SOORT.get(_key(cls.stereotype or ""))
    if soort is not None:
        return soort
    package = getattr(cls, "package", None)
    pkg = _key(getattr(package, "name", None) or "")
    if "groepattribuutsoort" in pkg or "gegevensgroeptype" in pkg:
        return GEGEVENSGROEPTYPE
    if getattr(cls, "is_datatype", False) or "datatype" in pkg or pkg in {"union", "unions"}:
        return GESTRUCTUREERD_DATATYPE
    if "referentielijst" in pkg:
        return REFERENTIELIJST
    if "codelijst" in pkg:
        return CODELIJST
    return OBJECTTYPE
