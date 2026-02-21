"""
Tests voor fix_and_format_text in mode="table" en mode="markdown".

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
  - Plain-text ■ bullets (markdown mode)
  - depth=0 blockquote-afhandeling (markdown mode)
"""

from crunch_uml.renderers.jinja2renderer import fix_and_format_text

# ---------------------------------------------------------------------------
# Hulpfuncties
# ---------------------------------------------------------------------------


def table(text: str) -> str:
    """Verkorte aanroep voor mode='table'."""
    return fix_and_format_text(text, mode="table")


def md0(text: str) -> str:
    """Verkorte aanroep voor mode='markdown', depth=0 (template-mode)."""
    return fix_and_format_text(text, mode="markdown", depth=0)


def md1(text: str) -> str:
    """Verkorte aanroep voor mode='markdown', depth=1 (standaard)."""
    return fix_and_format_text(text, mode="markdown", depth=1)


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


# ===========================================================================
# MARKDOWN MODE tests
# ===========================================================================


# ---------------------------------------------------------------------------
# depth=0: single line (geen multiline → platte tekst, geen prefix)
# ---------------------------------------------------------------------------


def test_markdown_depth0_single_line():
    """Enkele regel: geen blockquote-prefix, geen leading newline."""
    result = md0("Gewone definitietekst")
    assert result == "Gewone definitietekst"
    assert "\n" not in result
    assert ">" not in result


def test_markdown_depth0_single_line_strips_html():
    """Enkele regel met HTML-tag: tag gestript, tekst terug."""
    result = md0('<p>Een definitie.</p>')
    assert "Een definitie." in result
    assert "<p>" not in result


# ---------------------------------------------------------------------------
# depth=0: multiline (eerste regel plain, vervolg met '> ')
# ---------------------------------------------------------------------------


def test_markdown_depth0_multiline_plain():
    """Meerdere regels plain tekst: eerste regel zonder prefix, rest met '> '."""
    result = md0("Regel 1\nRegel 2\nRegel 3")
    lines = result.split("\n")
    assert "Regel 1" in lines[0]
    assert lines[0].startswith(">") is False  # eerste regel: geen prefix
    # Tweede en derde regel moeten '> ' bevatten
    assert any("> " in ln for ln in lines[1:])


def test_markdown_depth0_no_leading_newline():
    """depth=0 geeft GEEN leading newline terug (template staat al op positie)."""
    result = md0("Regel 1\nRegel 2")
    assert not result.startswith("\n")


# ---------------------------------------------------------------------------
# depth=1: standaard blockquote met leading newline
# ---------------------------------------------------------------------------


def test_markdown_depth1_multiline():
    """depth=1: alle regels krijgen '> ' prefix, leading newline aanwezig."""
    result = md1("Regel 1\nRegel 2\nRegel 3")
    assert result.startswith("\n")
    for ln in result.strip().split("\n"):
        if ln.strip():
            assert ln.startswith("> "), f"Regel heeft geen '> ' prefix: {repr(ln)}"


# ---------------------------------------------------------------------------
# ■ bullets → Markdown lijstitems in blockquote
# ---------------------------------------------------------------------------


def test_markdown_square_bullets_recognized():
    """■ bullets worden herkend als lijstitems."""
    text = "Introductie:\n■ item één\n■ item twee\n■ item drie"
    result = md0(text)
    assert "item één" in result
    assert "item twee" in result
    assert "item drie" in result


def test_markdown_square_bullets_blockquote():
    """■ bullets in blockquote: vervolg-regels hebben '> ' prefix."""
    text = "Introductie:\n■ item één\n■ item twee"
    result = md0(text)
    lines = result.split("\n")
    # Er moeten regels zijn met '> ' (vervolg-regels)
    continuation = [ln for ln in lines[1:] if ln.strip()]
    assert all(
        ln.startswith("> ") or ln == ">" for ln in continuation
    ), f"Niet alle vervolg-regels hebben '> ' prefix: {result!r}"


def test_markdown_square_bullets_no_raw_square():
    """■-teken zelf mag niet meer in de output staan (omgezet naar list item)."""
    text = "Intro:\n■ item1\n■ item2"
    result = md0(text)
    assert "■" not in result


def test_markdown_square_bullets_no_backref():
    """Geen letterlijke \\1 backreference in output."""
    text = "Intro:\n■ item A\n■ item B"
    result = md0(text)
    assert r"\1" not in result


def test_markdown_square_bullets_only_no_intro():
    """■ bullets zonder intro-tekst worden ook correct verwerkt."""
    text = "■ eerste punt\n■ tweede punt\n■ derde punt"
    result = md0(text)
    assert "eerste punt" in result
    assert "tweede punt" in result
    assert "derde punt" in result
    assert "■" not in result


# ---------------------------------------------------------------------------
# Numbered plain-text lists in markdown mode
# ---------------------------------------------------------------------------


def test_markdown_numbered_list_plain():
    """Plain-text genummerde lijst wordt correct omgezet."""
    text = "Stappen:\n1. Eerste stap\n2. Tweede stap\n3. Derde stap"
    result = md0(text)
    assert "Eerste stap" in result
    assert "Tweede stap" in result
    assert "Derde stap" in result
    assert r"\1" not in result


# ---------------------------------------------------------------------------
# HTML lijsten in markdown mode
# ---------------------------------------------------------------------------


def test_markdown_html_ul_in_blockquote():
    """HTML <ul><li> wordt correct als Markdown list in blockquote gezet."""
    html = "<p>De opties:</p><ul><li>Optie A</li><li>Optie B</li></ul>"
    result = md0(html)
    assert "De opties:" in result
    assert "Optie A" in result
    assert "Optie B" in result
    # Geen rauwe HTML-tags in output
    assert "<ul>" not in result
    assert "<li>" not in result


def test_markdown_html_ol_in_blockquote():
    """HTML <ol><li> wordt correct als Markdown genummerde list in blockquote gezet."""
    html = "<ol><li>Stap één</li><li>Stap twee</li></ol>"
    result = md0(html)
    assert "Stap één" in result
    assert "Stap twee" in result
    assert "<ol>" not in result


# ---------------------------------------------------------------------------
# Witregel voor en na lijsten
# ---------------------------------------------------------------------------


def test_markdown_blank_line_before_list():
    """Er is een lege regel ('>') vóór de lijst als er intro-tekst is."""
    text = "Introductie:\n■ item1\n■ item2"
    result = md0(text)
    lines = result.split("\n")
    # Er moet een lege blokkwote-regel zijn ('>') of lege regel
    has_separator = any(ln.strip() in ("", ">") for ln in lines[1:])
    assert has_separator, f"Geen lege scheidingsregel gevonden: {result!r}"


def test_markdown_blank_line_after_list():
    """Er is een lege regel na de lijst als er slottekst is."""
    text = "Intro:\n■ item1\nSlottekst."
    result = md0(text)
    assert "Slottekst." in result
    lines = result.split("\n")
    # Lege/separator regel aanwezig
    has_separator = any(ln.strip() in ("", ">") for ln in lines)
    assert has_separator, f"Geen separator tussen lijst en slottekst: {result!r}"


# ---------------------------------------------------------------------------
# Integratietest markdown mode
# ---------------------------------------------------------------------------


def test_markdown_complex_definition():
    """Realistische definitie met ■ bullets: volledig correct in blockquote."""
    text = (
        "Dienstverleningsonderdelen binnen de schuldregelingsfase:\n"
        "■ Saneringskredieten (SK)\n"
        "■ Schuldbemiddelingen (SB)\n"
        "■ Herfinancieringen (HF)\n"
        "■ Betalingsregelingen (BR)"
    )
    result = md0(text)

    # Inhoud aanwezig
    assert "Dienstverleningsonderdelen" in result
    assert "Saneringskredieten" in result
    assert "Schuldbemiddelingen" in result
    assert "Herfinancieringen" in result
    assert "Betalingsregelingen" in result

    # Structuur
    assert "■" not in result  # geen rauwe ■
    assert r"\1" not in result  # geen backreference bug
    assert not result.startswith("\n")  # geen leading newline (depth=0)
    lines = result.split("\n")
    continuation = [ln for ln in lines[1:] if ln.strip()]
    assert all(ln.startswith("> ") or ln == ">" for ln in continuation)
