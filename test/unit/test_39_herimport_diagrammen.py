"""Herimport van een model in een database die het al kent.

Diagrammen werden met een harde insert weggeschreven in plaats van met een
insert-or-update. Een tweede import van hetzelfde model liep daardoor stuk op
de primaire sleutel van de diagrams-tabel, waarna de hele import werd
teruggedraaid. Dat blokkeerde het bijwerken van een model in een gedeelde
database.
"""

import sqlite3

import pytest

import crunch_uml.db as db
from crunch_uml import cli

MONUMENTEN_XMI = "./test/data/GGM_Monumenten_EA2.1.xml"
MONUMENTEN_QEA = "./test/data/Monumenten.qea"

# Tabellen met modelinhoud; de meta-tabellen (crunch_uml_meta, crunch_uml_runs)
# horen er niet bij, die veranderen per run.
MODEL_TABLES = [
    "packages",
    "classes",
    "attributes",
    "enumerations",
    "enumerationliterals",
    "associations",
    "generalizations",
    "diagrams",
    "diagram_class",
    "diagram_enumeration",
    "diagram_association",
    "diagram_generalization",
]


def _dispose_singleton():
    inst = db.Database._instance
    if inst is not None:
        try:
            inst.session.close()
        except Exception:  # noqa: S110 - best-effort teardown
            pass
        try:
            inst.engine.dispose()
        except Exception:  # noqa: S110 - best-effort teardown
            pass
        db.Database._instance = None


@pytest.fixture(autouse=True)
def _reset_database_singleton():
    """De Database-singleton overleeft tests; dispose ervoor en erna zodat een
    achtergebleven instantie onze -db_url niet kaapt."""
    _dispose_singleton()
    yield
    _dispose_singleton()


def _db_url(path):
    return f"sqlite:///{path}"


def _counts(path):
    con = sqlite3.connect(path)
    try:
        return {table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in MODEL_TABLES}
    finally:
        con.close()


def _import(path, bestand, parser, eerste=False):
    args = ["-db_url", _db_url(path), "import", "-f", bestand, "-t", parser]
    if eerste:
        args.append("-db_create")
    return cli.main(args)


def test_herimport_xmi_met_diagrammen_slaagt(tmp_path):
    """Tweede import van hetzelfde XMI-model mag niet stuklopen."""
    path = tmp_path / "herimport_xmi.db"
    assert _import(path, MONUMENTEN_XMI, "eaxmi", eerste=True) == 0
    na_eerste = _counts(path)
    assert na_eerste["diagrams"] > 0, "testmodel moet diagrammen bevatten, anders dekt de test niets"

    assert _import(path, MONUMENTEN_XMI, "eaxmi") == 0, "herimport in een gevulde database moet slagen"


def test_herimport_xmi_laat_de_inhoud_ongewijzigd(tmp_path):
    """Hetzelfde model twee keer importeren levert dezelfde database op:
    bestaande rijen worden bijgewerkt, niet gedupliceerd."""
    path = tmp_path / "idempotent_xmi.db"
    assert _import(path, MONUMENTEN_XMI, "eaxmi", eerste=True) == 0
    na_eerste = _counts(path)

    # Zonder deze controle slaagt de test ook als de tweede import afbreekt:
    # een teruggedraaide import laat de tellingen immers ook ongemoeid.
    assert _import(path, MONUMENTEN_XMI, "eaxmi") == 0
    na_tweede = _counts(path)

    assert na_tweede == na_eerste


def test_herimport_qea_met_diagrammen_slaagt(tmp_path):
    """Dezelfde garantie voor de QEA-parser, die zijn diagrammen langs een
    ander pad opbouwt."""
    path = tmp_path / "herimport_qea.db"
    assert _import(path, MONUMENTEN_QEA, "qea", eerste=True) == 0
    na_eerste = _counts(path)
    assert na_eerste["diagrams"] > 0, "testmodel moet diagrammen bevatten, anders dekt de test niets"

    assert _import(path, MONUMENTEN_QEA, "qea") == 0
    assert _counts(path) == na_eerste
