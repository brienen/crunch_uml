"""The MiniM4 fixture pair: every EA quirk fixed in 0.7.0, in a model of a few kilobytes.

test/data/MiniM4.qea and test/data/MiniM4.xml describe the same model (generated
by tools/make_mini_m4_fixture.py). The tests pin what both parsers must yield,
plus the one documented asymmetry: the eaxmi parser still reads an EA Boundary
and ProxyConnector as a class (the QEA marks them t_object 'Boundary' /
'ProxyConnector' and skips them). Since 0.7.0 every class row says what kind of
element it came from (``classes.object_type``), so a consumer can tell.

Every import is also checked for referential integrity: Postgres enforces the
foreign keys during an import, SQLite does not unless asked.
"""

import os
import sqlite3

import pytest

import crunch_uml.db as db
from crunch_uml import cli, const, ea_geometry, ea_ids

MINI_QEA = "./test/data/MiniM4.qea"
MINI_XMI = "./test/data/MiniM4.xml"

KERN = "EAPK_4D4E0002_0000_4000_8000_000000000002"
PERSOON = "EAID_4D4E000A_0000_4000_8000_00000000000A"
HUISHOUDEN = "EAID_4D4E000C_0000_4000_8000_00000000000C"
GRENS = "EAID_4D4E000E_0000_4000_8000_00000000000E"
POSTCODE = "EAID_4D4E000F_0000_4000_8000_00000000000F"
GESLACHT = "EAID_4D4E0010_0000_4000_8000_000000000010"
PROXY = "EAID_4D4E0011_0000_4000_8000_000000000011"
AGGREGATIE = "EAID_4D4E001F_0000_4000_8000_00000000001F"
NAAR_ENUMERATIE = "EAID_4D4E0021_0000_4000_8000_000000000021"
VAN_ENUMERATIE = "EAID_4D4E0022_0000_4000_8000_000000000022"
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


def test_associatie_met_enumeratie_als_eind_krijgt_een_plaatshouderklasse(mini):
    """EA lets an association end on an enumeration (GGM 2.5.1 has three, 2.4.0 nineteen).
    Association ends live in ``classes``, so both parsers add one ``<Orphan Class>`` with the
    enumeration's id, also when two associations share that end. Before the fix the QEA parser
    left the end dangling and a Postgres import stopped on ``fk_dst_class``."""
    _, con = mini
    ends = {
        r["id"]: (r["src_class_id"], r["dst_class_id"])
        for r in con.execute(
            "SELECT id, src_class_id, dst_class_id FROM associations WHERE id IN (?, ?)",
            (NAAR_ENUMERATIE, VAN_ENUMERATIE),
        )
    }
    assert ends == {NAAR_ENUMERATIE: (HUISHOUDEN, GESLACHT), VAN_ENUMERATIE: (GESLACHT, PERSOON)}
    placeholders = con.execute("SELECT id, name, package_id, is_datatype FROM classes WHERE id = ?", (GESLACHT,))
    assert [tuple(r) for r in placeholders] == [(GESLACHT, const.ORPHAN_CLASS, None, 0)]
    # The enumeration keeps its own tagged value; the placeholder with the same id gets none.
    assert con.execute("SELECT herkomst FROM enumerations WHERE id = ?", (GESLACHT,)).fetchone()[0] == "EA"
    assert con.execute("SELECT herkomst FROM classes WHERE id = ?", (GESLACHT,)).fetchone()[0] is None


def test_herimport_qea_houdt_het_enumeratietype_van_een_attribuut(tmp_path):
    """A re-import into the same schema finds the placeholder class with the enumeration's id;
    the attribute typed by that enumeration must still point at the enumeration."""
    path = tmp_path / "herimport_qea.db"
    parse_into(path, MINI_QEA, "qea")
    parse_into(path, MINI_QEA, "qea", create=False)
    con = connect(path)
    try:
        row = con.execute("SELECT enumeration_id, type_class_id FROM attributes WHERE name = 'geslacht'").fetchone()
        assert tuple(row) == (GESLACHT, None)
        assert con.execute("SELECT herkomst FROM enumerations WHERE id = ?", (GESLACHT,)).fetchone()[0] == "EA"
        assert con.execute("SELECT COUNT(*) FROM classes WHERE name = ?", (const.ORPHAN_CLASS,)).fetchone()[0] == 1
        assert [tuple(r) for r in con.execute("PRAGMA foreign_key_check")] == []
    finally:
        con.close()


def test_referentiele_integriteit(mini):
    """Every foreign key holds, so the same parse also succeeds on Postgres."""
    _, con = mini
    assert [tuple(r) for r in con.execute("PRAGMA foreign_key_check")] == []


@pytest.mark.parametrize("element", [GRENS, PROXY], ids=["boundary", "proxyconnector"])
def test_boundary_asymmetrie_is_gedocumenteerd(mini, element):
    """QEA skips the Boundary and the ProxyConnector; eaxmi still reads them as classes
    (filtering them is the consumer's call, on ``object_type``)."""
    parser, con = mini
    count = con.execute("SELECT COUNT(*) FROM classes WHERE id = ?", (element,)).fetchone()[0]
    assert count == (1 if parser == "eaxmi" else 0)


def test_object_type_zegt_wat_voor_element_een_klasse_was(mini):
    """``classes.object_type`` is the EA element kind in lowercase: ``t_object.Object_Type``
    in a QEA, the ``xmi:type`` of the EA extension element in an EA-XMI (the uml:Model tree
    exports a Boundary or ProxyConnector as a plain uml:Class). The placeholder for an
    association end on an enumeration records 'enumeration'. Same value in both formats
    for every row both formats have; the rows themselves are unchanged (no filter)."""
    parser, con = mini
    kinds = {r["id"]: r["object_type"] for r in con.execute("SELECT id, object_type FROM classes")}
    expected = {
        PERSOON: "class",
        HUISHOUDEN: "class",
        "EAID_4D4E000B_0000_4000_8000_00000000000B": "class",  # Adres
        "EAID_4D4E000D_0000_4000_8000_00000000000D": "class",  # Ingezetene
        POSTCODE: "datatype",
        GESLACHT: "enumeration",
    }
    if parser == "eaxmi":
        expected[GRENS] = "boundary"
        expected[PROXY] = "proxyconnector"
    assert kinds == expected
    assert con.execute("SELECT is_datatype FROM classes WHERE id = ?", (POSTCODE,)).fetchone()[0] == 1


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
    assert x_classes - q_classes == {GRENS, PROXY}
    q_kinds = {r[0]: r[1] for r in qea.execute("SELECT id, object_type FROM classes")}
    x_kinds = {r[0]: r[1] for r in xmi.execute("SELECT id, object_type FROM classes")}
    assert {k: v for k, v in x_kinds.items() if k in q_kinds} == q_kinds


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
        orphans = {r[0] for r in a.execute("SELECT id FROM classes WHERE name = '<Orphan Class>'")}
        dangling_end = {o for o in orphans if o.startswith(ea_ids.PLACEHOLDER_ID_PREFIX)}
        # One hashed placeholder for the dangling end, one for the enumeration end.
        assert len(dangling_end) == 1
        assert orphans - dangling_end == {GESLACHT}
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
        orphans = [r[0] for r in con.execute("SELECT id FROM classes WHERE name = '<Orphan Class>' ORDER BY id")]
        assert len(orphans) == 2 and GESLACHT in orphans
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


def test_accolade_ids_worden_in_de_tekst_genormaliseerd():
    from crunch_uml.parsers.xmiparser import normalize_braced_ids

    data = (
        b'<a xmi:id="EAID_{AB_CD}" type="EAPK_{{EF}}" other="EAID_12"'
        b' note="EAJava_{x}"/>\n<b>tekst "EAID_{AB CD" zonder sluiting</b>'
    )
    assert normalize_braced_ids(data) == (
        b'<a xmi:id="EAID_AB_CD" type="EAPK_EF" other="EAID_12"'
        b' note="EAJava_{x}"/>\n<b>tekst "EAID_{AB CD" zonder sluiting</b>'
    )
    unchanged = b'<a xmi:id="EAID_1"/>'
    assert normalize_braced_ids(unchanged) is unchanged


@pytest.mark.parametrize("source,parser", [(MINI_QEA, "qea"), (MINI_XMI, "eaxmi")])
def test_synthetic_ids_are_reported_once_not_per_element(source, parser, tmp_path, caplog):
    """A model can have hundreds of members without a guid (InkomenMIM: 827). The
    import says so in one WARNING with the count; each minted id is DEBUG, so it
    does not bury every other warning in the log of an import or of the runner."""
    import logging

    with caplog.at_level(logging.DEBUG):
        parse_into(tmp_path / "log.db", source, parser)

    about_ids = [r for r in caplog.records if "synthetic id" in r.getMessage()]
    warnings = [r for r in about_ids if r.levelno >= logging.WARNING]
    per_element = [r for r in about_ids if "has no source id" in r.getMessage()]

    assert len(warnings) == 1, [r.getMessage() for r in warnings]
    assert "4 elements" in warnings[0].getMessage()
    assert len(per_element) == 4
    assert all(r.levelno == logging.DEBUG for r in per_element)
