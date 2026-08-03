"""Encoding-afhandeling van de XMI-loader.

``chardet.detect()`` leest het volledige bestand en is daarmee veruit de
duurste stap bij het inlezen van grote XMI-modellen. Zodra de XML-declaratie
een encoding noemt is die detectie overbodig. Deze tests borgen dat de
detectie in dat geval achterwege blijft, en dat het gedrag verder ongewijzigd
is: de fallback bij een ontbrekende declaratie en de foutmelding met beide
encodings blijven werken.
"""

import pytest

from crunch_uml.parsers import xmiparser
from crunch_uml.parsers.xmiparser import extract_declared_encoding, load_xmi

XML_UTF8 = '<?xml version="1.0" encoding="UTF-8"?>\n<model><naam>Woonwagenstandplaats</naam></model>'
XML_LATIN1 = '<?xml version="1.0" encoding="ISO-8859-1"?>\n<model><naam>Café Zürich</naam></model>'
XML_NO_DECL = '<?xml version="1.0"?>\n<model><naam>Woonwagenstandplaats</naam></model>'


@pytest.fixture
def count_detect(monkeypatch):
    """Vervang chardet.detect door een teller die de echte detectie doet."""
    calls = []
    original = xmiparser.chardet.detect

    def counting_detect(raw):
        calls.append(len(raw))
        return original(raw)

    monkeypatch.setattr(xmiparser.chardet, "detect", counting_detect)
    return calls


def _write(tmp_path, name, text, encoding):
    path = tmp_path / name
    path.write_bytes(text.encode(encoding))
    return str(path)


def test_gedeclareerde_encoding_slaat_detectie_over(tmp_path, count_detect):
    """Het hete pad: encoding staat in de header, dus geen detectie."""
    path = _write(tmp_path, "utf8.xml", XML_UTF8, "utf-8")

    root = load_xmi(path)

    assert root.find("naam").text == "Woonwagenstandplaats"
    assert count_detect == [], "chardet.detect() mag niet draaien bij een gedeclareerde encoding"


def test_gedeclareerde_latin1_wordt_correct_gedecodeerd(tmp_path, count_detect):
    """Niet-UTF8 met declaratie: nog steeds geen detectie, wel juiste tekens."""
    path = _write(tmp_path, "latin1.xml", XML_LATIN1, "iso-8859-1")

    root = load_xmi(path)

    assert root.find("naam").text == "Café Zürich"
    assert count_detect == []


def test_zonder_declaratie_wordt_wel_gedetecteerd(tmp_path, count_detect):
    """Zonder encoding in de header is detectie de enige aanwijzing."""
    path = _write(tmp_path, "geen_decl.xml", XML_NO_DECL, "utf-8")

    root = load_xmi(path)

    assert root.find("naam").text == "Woonwagenstandplaats"
    assert len(count_detect) == 1


def test_onbruikbare_declaratie_meldt_beide_encodings(tmp_path, count_detect):
    """Faalpad: de melding noemt zowel de gedeclareerde als de gedetecteerde
    encoding, ook al is er in het hete pad niet gedetecteerd."""
    path = _write(tmp_path, "bogus.xml", XML_UTF8.replace("UTF-8", "bestaat-niet"), "utf-8")

    with pytest.raises(RuntimeError) as excinfo:
        load_xmi(path)

    melding = str(excinfo.value)
    assert "declared: bestaat-niet" in melding
    assert "detected: " in melding
    assert len(count_detect) == 1, "detectie hoort alleen in het faalpad te draaien"


def test_extract_declared_encoding_leest_de_header():
    assert extract_declared_encoding(XML_UTF8.encode("utf-8")) == "UTF-8"
    assert extract_declared_encoding(XML_LATIN1.encode("iso-8859-1")) == "ISO-8859-1"
    assert extract_declared_encoding(XML_NO_DECL.encode("utf-8")) is None
