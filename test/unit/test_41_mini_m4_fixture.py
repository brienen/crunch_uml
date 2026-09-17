"""The MiniM4 fixture pair: every EA quirk fixed in 0.7.0, in a model of a few kilobytes.

test/data/MiniM4.qea and test/data/MiniM4.xml describe the same model (generated
by tools/make_mini_m4_fixture.py). The tests pin what both parsers must yield,
plus the one documented asymmetry: the eaxmi parser still reads an EA Boundary
as a class (the QEA marks it t_object 'Boundary' and it is skipped there).
"""

import os
import sqlite3

import pytest

import crunch_uml.db as db
from crunch_uml import cli, ea_geometry, ea_ids

MINI_QEA = "./test/data/MiniM4.qea"
MINI_XMI = "./test/data/MiniM4.xml"

KERN = "EAPK_4D4E0002_0000_4000_8000_000000000002"
PERSOON = "EAID_4D4E000A_0000_4000_8000_00000000000A"
GRENS = "EAID_4D4E000E_0000_4000_8000_00000000000E"
POSTCODE = "EAID_4D4E000F_0000_4000_8000_00000000000F"
GESLACHT = "EAID_4D4E0010_0000_4000_8000_000000000010"
AGGREGATIE = "EAID_4D4E001F_0000_4000_8000_00000000001F"
DIAGRAM_KERN = "EAID_4D4E0028_0000_4000_8000_000000000028"
DIAGRAM_DETAILS = "EAID_4D4E0029_0000_4000_8000_000000000029"
DIAGRAM_PACKAGES = "EAID_4D4E002A_0000_4000_8000_00000000002A"


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


def parse_into(path, source, parser, schema="default", create=True):
    _dispose_singleton()
    args = ["-db_url", f"sqlite:///{path}", "-sch", schema, "import", "-f", source, "-t", parser]
    if create:
        args.append("-db_create")
    try:
        rc = cli.main(args)
    finally:
        _dispose_singleton()
    assert rc == 0, f"import of {source} failed"


def connect(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


@pytest.fixture(scope="module", params=["qea", "eaxmi"])
def mini(request, tmp_path_factory):
    source = MINI_QEA if request.param == "qea" else MINI_XMI
    path = tmp_path_factory.mktemp(f"mini_{request.param}") / "mini.db"
    parse_into(path, source, request.param)
    con = connect(path)
    yield request.param, con
    con.close()


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    base = tmp_path_factory.mktemp("mini_pair")
    parse_into(base / "qea.db", MINI_QEA, "qea")
    parse_into(base / "xmi.db", MINI_XMI, "eaxmi")
    qea, xmi = connect(base / "qea.db"), connect(base / "xmi.db")
    yield qea, xmi
    qea.close()
    xmi.close()


def test_fixture_is_klein():
    assert os.path.getsize(MINI_QEA) < 100_000
    assert os.path.getsize(MINI_XMI) < 100_000


def test_domein_package_met_stereotype_en_tag(mini):
    _, con = mini
    row = con.execute("SELECT stereotype, afkorting, alias, author FROM packages WHERE id = ?", (KERN,)).fetchone()
    assert row["stereotype"] == "Domein"
    assert row["afkorting"] == "KRN"
    assert row["alias"] == "kern"
    assert row["author"] == "crunch_uml tests"


def test_aggregatie_is_een_associatie_met_tags(mini):
    _, con = mini
    row = con.execute("SELECT name, herkomst FROM associations WHERE id = ?", (AGGREGATIE,)).fetchone()
    assert row is not None, "the Aggregation connector must be imported"
    assert (row["name"], row["herkomst"]) == ("bestaat uit", "MiniM4")
    edge = con.execute(
        "SELECT hidden FROM diagram_association WHERE diagram_id = ? AND association_id = ?", (DIAGRAM_KERN, AGGREGATIE)
    ).fetchone()
    assert edge is not None


def test_attributen_zonder_guid_krijgen_synthetische_ids(mini):
    _, con = mini
    rows = con.execute("SELECT id, name FROM attributes WHERE clazz_id = ? ORDER BY name, id", (PERSOON,)).fetchall()
    names = sorted(r["name"] for r in rows)
    assert names == ["geboortedatum", "geslacht", "naam", "opmerking", "opmerking"]
    by_name = {}
    for r in rows:
        by_name.setdefault(r["name"], []).append(r["id"])
    expected_opmerking = {ea_ids.synthetic_id(PERSOON, "opmerking", 0), ea_ids.synthetic_id(PERSOON, "opmerking", 1)}
    assert set(by_name["opmerking"]) == expected_opmerking
    assert by_name["geboortedatum"] == [ea_ids.synthetic_id(PERSOON, "geboortedatum", 0)]
    assert con.execute("SELECT COUNT(*) FROM attributes WHERE id = ''").fetchone()[0] == 0


def test_enumeratiewaarden_zonder_isliteral_zijn_waarden(mini):
    _, con = mini
    names = sorted(
        r[0] for r in con.execute("SELECT name FROM enumerationliterals WHERE enumeratie_id = ?", (GESLACHT,))
    )
    assert names == ["man", "onbekend", "vrouw"]
    vrouw = con.execute("SELECT id FROM enumerationliterals WHERE name = 'vrouw'").fetchone()[0]
    assert vrouw == ea_ids.synthetic_id(GESLACHT, "vrouw", 0)


def test_dubbele_accolades_in_guid_geven_een_genormaliseerd_id(mini):
    _, con = mini
    assert [r[0] for r in con.execute("SELECT id FROM enumerations")] == [GESLACHT]
    geslacht = con.execute("SELECT enumeration_id FROM attributes WHERE name = 'geslacht'").fetchone()[0]
    assert geslacht == GESLACHT


def test_datatype_als_attribuuttype(mini):
    _, con = mini
    assert con.execute("SELECT type_class_id FROM attributes WHERE name = 'postcode'").fetchone()[0] == POSTCODE


def test_diagraminstellingen(mini):
    _, con = mini
    rows = {
        r["id"]: r
        for r in con.execute(
            "SELECT id, diagram_type, hide_attributes, hide_operations, ea_style, ea_style_ex FROM diagrams"
        )
    }
    assert (rows[DIAGRAM_KERN]["hide_attributes"], rows[DIAGRAM_KERN]["hide_operations"]) == (1, 1)
    assert (rows[DIAGRAM_DETAILS]["hide_attributes"], rows[DIAGRAM_DETAILS]["hide_operations"]) == (0, 0)
    assert rows[DIAGRAM_PACKAGES]["diagram_type"] == "Package"
    assert rows[DIAGRAM_KERN]["diagram_type"] == "Logical"
    assert "HideAtts=1;" in rows[DIAGRAM_KERN]["ea_style"]
    assert "SuppressedCompartments=" in rows[DIAGRAM_KERN]["ea_style_ex"]
    # The per-node override stays on the junction row, not on the diagram.
    node_style = con.execute(
        "SELECT ea_style FROM diagram_class WHERE diagram_id = ? AND class_id = ?", (DIAGRAM_DETAILS, PERSOON)
    ).fetchone()[0]
    assert "AttPub=0" in node_style


def test_boundary_asymmetrie_is_gedocumenteerd(mini):
    """QEA skips the Boundary; eaxmi still reads it as a class (filtering it is later work)."""
    parser, con = mini
    grens = con.execute("SELECT COUNT(*) FROM classes WHERE id = ?", (GRENS,)).fetchone()[0]
    assert grens == (1 if parser == "eaxmi" else 0)


def test_beide_formaten_leveren_dezelfde_ids(pair):
    qea, xmi = pair
    for table in (
        "packages",
        "attributes",
        "enumerations",
        "enumerationliterals",
        "associations",
        "generalizations",
        "diagrams",
    ):
        q = {r[0] for r in qea.execute(f"SELECT id FROM {table}")}
        x = {r[0] for r in xmi.execute(f"SELECT id FROM {table}")}
        assert q == x, table
    q_classes = {r[0] for r in qea.execute("SELECT id FROM classes")}
    x_classes = {r[0] for r in xmi.execute("SELECT id FROM classes")}
    assert x_classes - q_classes == {GRENS}


def test_parse_is_deterministisch(tmp_path):
    """Two parses of the same file give identical rows, including placeholder classes."""
    xmi = tmp_path / "dangling.xml"
    with open(MINI_XMI, encoding="windows-1252") as f:
        content = f.read()
    # Make one association end dangle: its memberEnd points at a missing ownedEnd.
    dangling = content.replace('<memberEnd xmi:idref="EAID_dst4E001E', '<memberEnd xmi:idref="EAID_dstGONE', 1)
    assert dangling != content
    xmi.write_text(dangling, encoding="windows-1252")

    parse_into(tmp_path / "a.db", str(xmi), "eaxmi")
    parse_into(tmp_path / "b.db", str(xmi), "eaxmi")
    a, b = connect(tmp_path / "a.db"), connect(tmp_path / "b.db")
    try:
        for table in ("classes", "associations"):
            rows_a = sorted((tuple(r) for r in a.execute(f"SELECT * FROM {table}")), key=repr)
            rows_b = sorted((tuple(r) for r in b.execute(f"SELECT * FROM {table}")), key=repr)
            assert rows_a == rows_b, table
        orphans = [r[0] for r in a.execute("SELECT id FROM classes WHERE name = '<Orphan Class>'")]
        assert orphans and all(o.startswith(ea_ids.PLACEHOLDER_ID_PREFIX) for o in orphans)
    finally:
        a.close()
        b.close()


def test_herimport_maakt_geen_extra_plaatshouders(tmp_path):
    """Re-importing into the same schema no longer adds a placeholder class per run."""
    xmi = tmp_path / "dangling.xml"
    with open(MINI_XMI, encoding="windows-1252") as f:
        xmi.write_text(
            f.read().replace('<memberEnd xmi:idref="EAID_dst4E001E', '<memberEnd xmi:idref="EAID_dstGONE', 1),
            encoding="windows-1252",
        )
    path = tmp_path / "herimport.db"
    parse_into(path, str(xmi), "eaxmi")
    parse_into(path, str(xmi), "eaxmi", create=False)
    con = connect(path)
    try:
        assert con.execute("SELECT COUNT(*) FROM classes WHERE name = '<Orphan Class>'").fetchone()[0] == 1
    finally:
        con.close()


def test_diagramkolommen_komen_er_additief_bij(tmp_path):
    """A database written before 0.7.0 gains the five diagram columns on connect;
    the datamodel version stays 1 and existing rows survive."""
    path = tmp_path / "oud.db"
    parse_into(path, MINI_QEA, "qea")
    con = sqlite3.connect(path)
    for column in ("diagram_type", "hide_attributes", "hide_operations", "ea_style", "ea_style_ex"):
        con.execute(f"ALTER TABLE diagrams DROP COLUMN {column}")
    con.commit()
    con.close()

    _dispose_singleton()
    try:
        db.Database(f"sqlite:///{path}", db_create=False, on_version_mismatch="fail")
    finally:
        _dispose_singleton()

    con = sqlite3.connect(path)
    try:
        columns = {r[1] for r in con.execute("PRAGMA table_info(diagrams)")}
        assert {"diagram_type", "hide_attributes", "hide_operations", "ea_style", "ea_style_ex"} <= columns
        assert con.execute("SELECT value FROM crunch_uml_meta WHERE key = 'datamodel_version'").fetchone()[0] == "1"
        assert con.execute("SELECT COUNT(*) FROM diagrams").fetchone()[0] == 3
    finally:
        con.close()


# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "guid, expected",
    [
        ("{4D4E0010-0000-4000-8000-000000000010}", "EAID_4D4E0010_0000_4000_8000_000000000010"),
        ("{{4D4E0010-0000-4000-8000-000000000010}}", "EAID_4D4E0010_0000_4000_8000_000000000010"),
        (None, None),
        ("", None),
    ],
)
def test_guid_to_ea_id(guid, expected):
    assert ea_ids.guid_to_ea_id(guid) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("EAID_{4D4E0010_0000}", "EAID_4D4E0010_0000"),
        ("EAID_{{4D4E0010_0000}}", "EAID_4D4E0010_0000"),
        ("EAPK_{4D4E0010_0000}", "EAPK_4D4E0010_0000"),
        ("EAID_4D4E0010_0000", "EAID_4D4E0010_0000"),
        ("EAJava_int", "EAJava_int"),
        ("", ""),
        (None, None),
    ],
)
def test_normalize_ea_id(value, expected):
    assert ea_ids.normalize_ea_id(value) == expected


def test_synthetic_id_is_stabiel_en_onderscheidend():
    a = ea_ids.synthetic_id("EAID_X", "naam", 0)
    assert a == ea_ids.synthetic_id("EAID_X", "naam", 0)
    assert a.startswith(ea_ids.SYNTHETIC_ID_PREFIX) and len(a) == len(ea_ids.SYNTHETIC_ID_PREFIX) + 40
    assert len({a, ea_ids.synthetic_id("EAID_X", "naam", 1), ea_ids.synthetic_id("EAID_Y", "naam", 0)}) == 3


def test_minter_telt_duplicaten_per_eigenaar_en_naam():
    minter = ea_ids.SyntheticIdMinter("test")
    first = minter.mint("EAID_X", "a")
    second = minter.mint("EAID_X", "a")
    other = minter.mint("EAID_Y", "a")
    assert first == ea_ids.synthetic_id("EAID_X", "a", 0)
    assert second == ea_ids.synthetic_id("EAID_X", "a", 1)
    assert other == ea_ids.synthetic_id("EAID_Y", "a", 0)
    assert minter.count == 3


@pytest.mark.parametrize(
    "style, expected",
    [
        ("HideRel=0;HideAtts=1;HideOps=0;", (True, False)),
        ("HideAtts=0;", (False, None)),
        ("ShowTags=0;", (None, None)),
        (None, (None, None)),
        ("", (None, None)),
    ],
)
def test_parse_diagram_hide_flags(style, expected):
    assert ea_geometry.parse_diagram_hide_flags(style) == expected
