"""
Tests voor fix_and_format_text in mode="table".

Dekt alle opsommingsvarianten die kunnen voorkomen in definities
van classes en attributen:
  - HTML <ul><li> ongeordende lijsten
  - HTML <ol><li> geordende lijsten
  - HTML geneste lijsten
  - HTML <p>-alinea's
  - HTML <br> regeleinden
  - HTML gemengd (paragraaf + lijst)
  - Markdown met * bullets
  - Markdown met + bullets
  - Markdown met - bullets (al correct, mogen niet dubbel escapen)
  - Markdown genummerde lijst (1. 2. 3.)
  - Enkelvoudige tekst (geen opmaak)
  - Tekst met pipe-tekens (|) die geëscaped moeten worden
  - Mojibake-tekst (Windows-1252 als latin1 gelezen, eigenlijk UTF-8)
"""

from crunch_uml.renderers.jinja2renderer import fix_and_format_text

# ---------------------------------------------------------------------------
# Hulpfuncties
# ---------------------------------------------------------------------------


def table(text: str) -> str:
    """Verkorte aanroep voor mode='table'."""
    return fix_and_format_text(text, mode="table")


# ---------------------------------------------------------------------------
# Lege / None invoer
# ---------------------------------------------------------------------------


def test_table_empty_string():
    assert table("") == ""


def test_table_none():
    assert fix_and_format_text(None, mode="table") == ""  # type: ignore[arg-type]


def test_table_whitespace_only():
    assert table("   \n  \n  ") == ""


# ---------------------------------------------------------------------------
# Enkelvoudige tekst (geen lijsten, geen HTML)
# ---------------------------------------------------------------------------


def test_table_plain_single_line():
    result = table("Gewone definitietekst")
    assert result == "Gewone definitietekst"
    # Geen <br> in een enkelvoudige regel
    assert "<br>" not in result


def test_table_plain_multiline_text():
    result = table("Regel één\nRegel twee\nRegel drie")
    # Newlines worden <br>
    assert "<br>" in result
    assert "Regel één" in result
    assert "Regel twee" in result


# ---------------------------------------------------------------------------
# HTML: paragrafen
# ---------------------------------------------------------------------------


def test_table_html_paragraphs():
    html = "<p>Eerste alinea.</p><p>Tweede alinea.</p>"
    result = table(html)
    assert "Eerste alinea." in result
    assert "Tweede alinea." in result
    assert "<br>" in result
    # Geen dubbele <br><br>
    assert "<br><br>" not in result


def test_table_html_paragraph_with_entity():
    html = "<p>Bedrag &gt; 0 &amp; &lt; 100</p>"
    result = table(html)
    assert "Bedrag" in result
    assert ">" in result or "&gt;" not in result  # entities gedecodeerd


# ---------------------------------------------------------------------------
# HTML: <br> regeleinden
# ---------------------------------------------------------------------------


def test_table_html_br_tags():
    html = "Tekst.<br/>Meer tekst.<br/>Nog meer."
    result = table(html)
    assert "Tekst." in result
    assert "Meer tekst." in result
    assert "<br>" in result
    assert "<br><br>" not in result


# ---------------------------------------------------------------------------
# HTML: ongeordende lijst <ul><li>
# ---------------------------------------------------------------------------


def test_table_html_ul_basic():
    html = "<ul><li>Item één</li><li>Item twee</li><li>Item drie</li></ul>"
    result = table(html)
    # Alle items aanwezig
    assert "Item één" in result
    assert "Item twee" in result
    assert "Item drie" in result
    # Items gescheiden door <br>
    assert "<br>" in result
    # Bullet markers mogen NIET het letterlijke '\1' bevatten (de oude buggy output)
    assert r"\1" not in result
    # Lijst-markers aanwezig (- of * of cijfers)
    assert "- " in result or "* " in result


def test_table_html_ul_with_intro():
    html = "<p>De opties zijn:</p><ul><li>Optie A</li><li>Optie B</li></ul>"
    result = table(html)
    assert "De opties zijn:" in result
    assert "Optie A" in result
    assert "Optie B" in result
    assert "<br>" in result
    assert r"\1" not in result


def test_table_html_ul_bullets_normalized_to_dash():
    """markdownify gebruikt * voor <ul>; na normalisatie moet dat - worden."""
    html = "<ul><li>Alpha</li><li>Beta</li></ul>"
    result = table(html)
    # Na fix: * wordt genormaliseerd naar -
    assert "- Alpha" in result
    assert "- Beta" in result
    # Geen rauwe * bullets meer (behalve eventueel escaped)
    # NB: we controleren dat \1 niet aanwezig is – dat was de buggy output
    assert r"\1" not in result


# ---------------------------------------------------------------------------
# HTML: geordende lijst <ol><li>
# ---------------------------------------------------------------------------


def test_table_html_ol_basic():
    html = "<ol><li>Eerste stap</li><li>Tweede stap</li><li>Derde stap</li></ol>"
    result = table(html)
    assert "Eerste stap" in result
    assert "Tweede stap" in result
    assert "Derde stap" in result
    assert "<br>" in result
    assert r"\1" not in result


def test_table_html_ol_with_intro():
    html = "<p>Voer de volgende stappen uit:</p><ol><li>Stap 1</li><li>Stap 2</li></ol>"
    result = table(html)
    assert "Voer de volgende stappen uit:" in result
    assert "Stap 1" in result
    assert "Stap 2" in result
    assert r"\1" not in result


# ---------------------------------------------------------------------------
# HTML: geneste lijsten
# ---------------------------------------------------------------------------


def test_table_html_nested_ul():
    html = "<ul>" "<li>Hoofd A<ul><li>Sub 1</li><li>Sub 2</li></ul></li>" "<li>Hoofd B</li>" "</ul>"
    result = table(html)
    assert "Hoofd A" in result
    assert "Sub 1" in result
    assert "Sub 2" in result
    assert "Hoofd B" in result
    assert r"\1" not in result


# ---------------------------------------------------------------------------
# Markdown-invoer: diverse bullet-varianten
# ---------------------------------------------------------------------------


def test_table_markdown_dash_bullets():
    """- bullets zijn al correct en mogen niet worden gewijzigd."""
    text = "Intro:\n- Item A\n- Item B\n- Item C"
    result = table(text)
    assert "Item A" in result
    assert "Item B" in result
    assert "Item C" in result
    assert r"\1" not in result
    # - markers blijven behouden
    assert "- Item A" in result


def test_table_markdown_star_bullets():
    """* bullets moeten worden genormaliseerd naar -."""
    text = "Intro:\n* Item A\n* Item B"
    result = table(text)
    assert "Item A" in result
    assert "Item B" in result
    assert r"\1" not in result
    # Na normalisatie: - markers
    assert "- Item A" in result
    assert "- Item B" in result


def test_table_markdown_plus_bullets():
    """+ bullets moeten worden genormaliseerd naar -."""
    text = "Intro:\n+ Item X\n+ Item Y"
    result = table(text)
    assert "Item X" in result
    assert "Item Y" in result
    assert r"\1" not in result
    assert "- Item X" in result
    assert "- Item Y" in result


def test_table_markdown_numbered_list():
    """Genummerde lijsten (1. 2. 3.) moeten intact blijven."""
    text = "Stappen:\n1. Eerste\n2. Tweede\n3. Derde"
    result = table(text)
    assert "Eerste" in result
    assert "Tweede" in result
    assert "Derde" in result
    assert r"\1" not in result


def test_table_markdown_indented_star_bullets():
    """Ingesprongen * bullets (bijv. geneste lijsten) correct afhandelen."""
    text = "Hoofd:\n* Item A\n    * Sub A1\n    * Sub A2\n* Item B"
    result = table(text)
    assert "Item A" in result
    assert "Sub A1" in result
    assert "Item B" in result
    assert r"\1" not in result
    # Ingesprongen bullets ook genormaliseerd
    assert "- Item A" in result


# ---------------------------------------------------------------------------
# Pipe-tekens escapen
# ---------------------------------------------------------------------------


def test_table_pipe_escaped():
    """Pipe-tekens in tekst moeten worden geëscaped zodat tabelcellen intact blijven."""
    text = "Waarde A | Waarde B | Waarde C"
    result = table(text)
    assert "\\|" in result
    # Geen ongescapte pipes
    # (tenzij ze deel uitmaken van \\| zelf)
    parts = result.split("\\|")
    for part in parts:
        assert "|" not in part


def test_table_pipe_in_list():
    html = "<ul><li>Optie A | variant 1</li><li>Optie B | variant 2</li></ul>"
    result = table(html)
    assert "\\|" in result
    assert r"\1" not in result


# ---------------------------------------------------------------------------
# Geen dubbele <br>
# ---------------------------------------------------------------------------


def test_table_no_double_br():
    """Opeenvolgende <br><br> zijn niet toegestaan."""
    html = "<p>A</p><p></p><p>B</p>"
    result = table(html)
    assert "<br><br>" not in result


def test_table_single_line_no_br():
    """Een enkelvoudige tekst zonder structure mag geen <br> bevatten."""
    result = table("Eén regel tekst")
    assert "<br>" not in result


# ---------------------------------------------------------------------------
# HTML-tags in tekst (font, span, etc.)
# ---------------------------------------------------------------------------


def test_table_html_font_tag():
    """font-tags uit EA-exports moeten worden verwijderd."""
    html = 'Representatie van <font color="#993300">AbstractGML</font>.'
    result = table(html)
    assert "AbstractGML" in result
    # font-tag zelf weg
    assert "<font" not in result


# ---------------------------------------------------------------------------
# Integratietest: complexe definitie
# ---------------------------------------------------------------------------


def test_table_complex_definition():
    """Realistische definitie met paragraaf + ongeordende lijst."""
    html = (
        "<p>Een klasse die meerdere aspecten beschrijft:</p>"
        "<ul>"
        "<li>Aspect één: de eerste eigenschap.</li>"
        "<li>Aspect twee: de tweede eigenschap met een | pipe.</li>"
        "<li>Aspect drie: de derde eigenschap.</li>"
        "</ul>"
        "<p>Zie ook de bijbehorende enumeratie.</p>"
    )
    result = table(html)

    # Inhoud aanwezig
    assert "Een klasse die meerdere aspecten beschrijft:" in result
    assert "Aspect één" in result
    assert "Aspect twee" in result
    assert "Aspect drie" in result
    assert "Zie ook de bijbehorende enumeratie." in result

    # Structuur correct
    assert "<br>" in result
    assert "<br><br>" not in result
    assert "\\|" in result  # pipe geëscaped
    assert r"\1" not in result  # oude bug afwezig
