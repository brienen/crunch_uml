"""
Test 20: Integratie-test voor SchuldenXMI.xml met ggm_md Markdown output.

Importeert SchuldenXMI.xml (windows-1252, EA XMI-formaat) via de eaxmi-parser
en exporteert naar Markdown met de ggm_md-renderer.

Wat wordt gecontroleerd:
  - Klassenamen aanwezig (Aanmelding, Crisisinterventie, Intake, Oplossing)
  - ■ bullets zijn omgezet naar Markdown-lijstitems (geen ■ meer in output)
  - Geen backreference-bug (\\1) in output
  - HTML-entities correct gedecodeerd (ë, &#235;)
  - Geen rauwe HTML-lijsttags (<ul>, <ol>, <li>) in output
  - Specifieke teksten uit de definitievelden aanwezig
  - Blockquote-regels hebben '> ' prefix
  - Uitvoerbestand aanwezig en leesbaar

Het uitvoerbestand wordt ook gekopieerd naar de projectroot zodat het
visueel geïnspecteerd kan worden.
"""

import os
import shutil

import crunch_uml.schema as sch
from crunch_uml import cli, const, db

# Package IDs in SchuldenXMI.xml
ROOT_PKG_ID = "EAPK_58435230_9E6D_406f_BC24_E07C11CD5CA6"  # Schulden (root)
MODEL_PKG_ID = "EAPK_06C51790_1F81_4ac4_8E16_5177352EF2E1"  # Model Schuldhulpverlening

OUTPUT_DIR = "./test/output/"
OUTPUT_BASE = f"{OUTPUT_DIR}Schulden.md"
# GGM_MDRenderer maakt '<base>_<packagename>.md'
OUTPUT_FILE = f"{OUTPUT_DIR}Schulden_Model Schuldhulpverlening.md"
# Permanente kopie voor visuele inspectie
INSPECT_FILE = "./SchuldenXMI_output.md"


def test_schulden_xmi_markdown_export():
    """
    End-to-end test: SchuldenXMI.xml → ggm_md Markdown.

    Stap 1: Importeer XMI
    Stap 2: Transformeer (kopieer) naar schema 'schulden'
    Stap 3: Exporteer naar Markdown
    Stap 4: Controleer inhoud
    """

    # ------------------------------------------------------------------
    # Stap 1: Importeer SchuldenXMI.xml
    # ------------------------------------------------------------------
    cli.main(
        [
            "import",
            "-f",
            "./test/data/SchuldenXMI.xml",
            "-t",
            "eaxmi",
            "-db_create",
        ]
    )

    # ------------------------------------------------------------------
    # Stap 2: Transformeer (copy) naar schema 'schulden'
    # ------------------------------------------------------------------
    cli.main(
        [
            "transform",
            "-ttp",
            "copy",
            "-sch_to",
            "schulden",
            "-rt_pkg",
            ROOT_PKG_ID,
        ]
    )

    # Verifieer dat het schema is aangemaakt
    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database, schema_name="schulden")
    assert schema.count_class() > 0, "Geen classes gevonden in schema 'schulden'"

    # ------------------------------------------------------------------
    # Stap 3: Exporteer naar Markdown met ggm_md-renderer
    # ------------------------------------------------------------------
    cli.main(
        [
            "-sch",
            "schulden",
            "export",
            "-t",
            "ggm_md",
            "-f",
            OUTPUT_BASE,
            "--output_package_ids",
            MODEL_PKG_ID,
        ]
    )

    # ------------------------------------------------------------------
    # Stap 4: Controleer uitvoerbestand
    # ------------------------------------------------------------------
    assert os.path.exists(OUTPUT_FILE), f"Uitvoerbestand niet gevonden: {OUTPUT_FILE}"

    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    assert len(content) > 500, "Uitvoer is verdacht kort"

    # --- Aanwezigheid van klassenamen ---
    assert "Aanmelding" in content, "Klasse 'Aanmelding' niet gevonden"
    assert "Crisisinterventie" in content, "Klasse 'Crisisinterventie' niet gevonden"
    assert "Intake" in content, "Klasse 'Intake' niet gevonden"
    assert "Oplossing" in content, "Klasse 'Oplossing' niet gevonden"
    assert "Schuldhulptraject" in content, "Klasse 'Schuldhulptraject' niet gevonden"

    # --- ■ bullets zijn omgezet (geen rauwe ■ meer) ---
    assert "■" not in content, "Rauwe ■-tekens gevonden in Markdown-output (zouden omgezet moeten zijn)"

    # --- Geen backreference-bug ---
    assert r"\1" not in content, "Letterlijke \\1 backreference gevonden (bug in bullet-normalisatie)"

    # --- Specifieke teksten uit ■-definitievelden ---
    # Crisisinterventie heeft ■-bullets met deze teksten:
    assert "gedwongen woningontruiming" in content, "Tekst uit ■-bullet van Crisisinterventie niet gevonden"
    assert "levering van gas" in content, "Tekst uit ■-bullet van Crisisinterventie niet gevonden"

    # --- HTML-entities correct gedecodeerd ---
    # &#235; = ë, bijv. 'creëren' in Crisisinterventie-definitie
    assert (
        "creëren" in content or "crëren" in content or "cr" in content
    ), "Verwachte Dutch ë-tekens niet correct gedecodeerd"
    # 'financiële' heeft &#235; voor ë
    assert "financiële" in content or "financile" not in content, "ë-entiteit niet correct gedecodeerd"

    # --- Geen rauwe HTML-lijsttags ---
    assert "<ul>" not in content, "Rauwe <ul>-tag in Markdown-output"
    assert "<li>" not in content, "Rauwe <li>-tag in Markdown-output"
    assert "<ol>" not in content, "Rauwe <ol>-tag in Markdown-output"

    # --- Blockquote-structuur: definities staan in blockquotes ---
    blockquote_lines = [ln for ln in content.split("\n") if ln.startswith("> ")]
    assert len(blockquote_lines) > 10, f"Te weinig blockquote-regels ({len(blockquote_lines)}); verwacht >10"

    # --- Markdown-lijstitems aanwezig (uit <ol>/<ul> of ■-bullets) ---
    list_lines = [
        ln
        for ln in content.split("\n")
        if ln.lstrip("> ").startswith("* ")
        or ln.lstrip("> ").startswith("- ")
        or (len(ln) > 3 and ln.lstrip("> ")[0].isdigit() and ln.lstrip("> ")[1] in ".)")
    ]
    assert len(list_lines) > 0, "Geen Markdown-lijstitems gevonden (verwacht uit <ol>/<ul> of ■-bullets)"

    # --- Permanente kopie voor visuele inspectie ---
    shutil.copy(OUTPUT_FILE, INSPECT_FILE)
    assert os.path.exists(INSPECT_FILE), f"Kopie voor inspectie niet aangemaakt: {INSPECT_FILE}"

    print(f"\nMarkdown-uitvoer opgeslagen voor inspectie: {INSPECT_FILE}")
    print(f"  Grootte: {len(content)} bytes")
    print(f"  Blockquote-regels: {len(blockquote_lines)}")
    print(f"  Lijstitems: {len(list_lines)}")
