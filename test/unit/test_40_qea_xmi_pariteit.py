"""Cross-format parity: the same Enterprise Architect model read as .qea and as EA-XMI.

Regression tests for the defects fixed in 0.7.0 (import study 2026-09-17,
r2-qea-defecten). Each of these tests fails on 0.6.0:

* QEA read no package stereotypes (t_object companion row), so a GGM landed in
  one domain instead of ~61.
* QEA skipped every Aggregation connector.
* EA-XMI stored members exported with ``xmi:id=""`` under the empty primary
  key, collapsing hundreds of attributes into one row without a warning, and
  ignored enumeration values exported as ``uml:Property``.
* Enumerations with a doubled-brace GUID got a different id per format.

Every pair is parsed into its own fresh SQLite database and compared with
plain SQL, so the tests do not depend on ORM session state.
"""

import os
import sqlite3

import pytest

import crunch_uml.db as db
from crunch_uml import cli

INKOMEN_QEA = "./test/data/InkomenMIM.qea"
INKOMEN_XMI = "./test/data/InkomenMIM.xml"
GGM240_QEA = "./test/data/Gemeentelijk Gegevensmodel 2.4.0.qea"
GGM240_XMI = "./test/data/Gemeentelijk Gegevensmodel 2.4.0.xml"

ID_TABLES = (
    "packages",
    "classes",
    "attributes",
    "enumerations",
    "enumerationliterals",
    "associations",
    "generalizations",
    "diagrams",
)


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


def parse_into(path, source, parser):
    """Parse ``source`` into a fresh SQLite file and return a read-only connection."""
    _dispose_singleton()
    try:
        rc = cli.main(["-db_url", f"sqlite:///{path}", "import", "-f", source, "-t", parser, "-db_create"])
    finally:
        _dispose_singleton()
    assert rc == 0, f"import of {source} failed"
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def scalar(con, sql, *params):
    return con.execute(sql, params).fetchone()[0]


def ids(con, table, where="1=1"):
    return {row[0] for row in con.execute(f"SELECT id FROM {table} WHERE {where}")}


def assert_no_empty_ids(con):
    for table in ID_TABLES:
        assert scalar(con, f"SELECT COUNT(*) FROM {table} WHERE id = '' OR id IS NULL") == 0, table


NON_PSEUDO = "id NOT LIKE 'EAID_src%' AND id NOT LIKE 'EAID_dst%'"


@pytest.fixture(scope="module")
def inkomen(tmp_path_factory):
    base = tmp_path_factory.mktemp("inkomen")
    qea = parse_into(base / "qea.db", INKOMEN_QEA, "qea")
    xmi = parse_into(base / "xmi.db", INKOMEN_XMI, "eaxmi")
    yield qea, xmi
    qea.close()
    xmi.close()


def test_inkomen_mim_leden_zonder_guid_gaan_niet_verloren(inkomen):
    """InkomenMIM: 827 members have no GUID. Both formats yield all of them:
    444 attributes and 458 enumeration values (0.6.0 eaxmi: 85 and 0)."""
    qea, xmi = inkomen
    assert scalar(qea, "SELECT COUNT(*) FROM attributes") == 444
    assert scalar(xmi, f"SELECT COUNT(*) FROM attributes WHERE {NON_PSEUDO}") == 444
    assert scalar(qea, "SELECT COUNT(*) FROM enumerationliterals") == 458
    assert scalar(xmi, "SELECT COUNT(*) FROM enumerationliterals") == 458
    assert_no_empty_ids(qea)
    assert_no_empty_ids(xmi)


def test_inkomen_mim_synthetische_ids_zijn_gelijk_in_beide_formaten(inkomen):
    """The ids minted for GUID-less members are the same whichever format was read."""
    qea, xmi = inkomen
    syn_attr_qea = ids(qea, "attributes", "id LIKE 'EAID_syn_%'")
    syn_lit_qea = ids(qea, "enumerationliterals", "id LIKE 'EAID_syn_%'")
    assert len(syn_attr_qea) == 369
    assert len(syn_lit_qea) == 458
    assert syn_attr_qea == ids(xmi, "attributes", "id LIKE 'EAID_syn_%'")
    assert syn_lit_qea == ids(xmi, "enumerationliterals", "id LIKE 'EAID_syn_%'")
    assert ids(qea, "attributes") == ids(xmi, "attributes", NON_PSEUDO)
    assert ids(qea, "enumerationliterals") == ids(xmi, "enumerationliterals")


def test_inkomen_mim_qea_leest_aggregaties(inkomen):
    """60 of the 70 connectors in InkomenMIM.qea are aggregations (0.6.0: 10 associations)."""
    qea, _ = inkomen
    assert scalar(qea, "SELECT COUNT(*) FROM associations") == 70


@pytest.fixture(scope="module")
def ggm240(tmp_path_factory):
    if not (os.path.exists(GGM240_QEA) and os.path.exists(GGM240_XMI)):
        pytest.skip("GGM 2.4.0 fixture pair not available")
    base = tmp_path_factory.mktemp("ggm240")
    qea = parse_into(base / "qea.db", GGM240_QEA, "qea")
    xmi = parse_into(base / "xmi.db", GGM240_XMI, "eaxmi")
    yield qea, xmi
    qea.close()
    xmi.close()


@pytest.mark.slow
def test_ggm240_domeinen_associaties_en_waarden_gelijk(ggm240):
    """GGM 2.4.0: 60 «Domein» packages via both formats, 1,106 associations via QEA
    (0.6.0: 0 stereotypes and 1,019), 3,971 enumeration values via both (0.6.0 eaxmi: 3,507)."""
    qea, xmi = ggm240
    domein = "SELECT COUNT(*) FROM packages WHERE stereotype = 'Domein'"
    assert scalar(qea, domein) == 60
    assert scalar(xmi, domein) == 60
    assert scalar(qea, "SELECT COUNT(*) FROM associations") == 1106
    assert scalar(qea, "SELECT COUNT(*) FROM enumerationliterals") == 3971
    assert scalar(xmi, "SELECT COUNT(*) FROM enumerationliterals") == 3971
    assert_no_empty_ids(qea)
    assert_no_empty_ids(xmi)


@pytest.mark.slow
def test_ggm240_ids_van_enumeraties_en_waarden_gelijk(ggm240):
    """115 enumerations carry a {{GUID}}; after normalization every enumeration and
    every enumeration value has the same id in both formats."""
    qea, xmi = ggm240
    assert ids(qea, "enumerations") == ids(xmi, "enumerations")
    assert ids(qea, "enumerationliterals") == ids(xmi, "enumerationliterals")
    assert not any("{" in i for i in ids(xmi, "enumerations"))


@pytest.mark.slow
def test_ggm240_diagraminstellingen_gelijk(ggm240):
    """HideAtts/HideOps and the diagram type agree for every diagram present in both formats."""
    qea, xmi = ggm240

    def settings(con):
        return {
            row[0]: row[1:]
            for row in con.execute("SELECT id, hide_attributes, hide_operations, diagram_type FROM diagrams")
        }

    in_qea, in_xmi = settings(qea), settings(xmi)
    common = set(in_qea) & set(in_xmi)
    assert len(common) == 256
    assert {i: in_qea[i] for i in common} == {i: in_xmi[i] for i in common}
    hidden = sum(1 for i in common if in_qea[i][0] == 1 and in_qea[i][2] == "Logical")
    assert hidden == 117
