"""Integration tests for diagram geometry parsing (phase 2).

Expected values are read directly from the fixtures:

* GGM_Monumenten_EA2.1.xml, diagram "Diagram Monumenten Detail"
  (EAID_58EA4966_DBC2_4359_94C4_ABC774DBE5E2), e.g. Bouwactiviteit:
  geometry="Left=30;Top=40;Right=130;Bottom=120;" seqno="3" style="DUID=DC2C05F0;"
* Monumenten.qea, same diagram: Bouwactiviteit RectLeft=30, RectTop=-40,
  RectRight=130, RectBottom=-120, Sequence=3, ObjectStyle="DUID=DC2C05F0;"
* InkomenMIM.{xml,qea}: generalization {14B94C41-1654-4425-9F6F-293123C0CF5C}
  on diagram "Diagram Terug- en invordering" has Path=580:-820$ (XMI) and
  Path "580:-820;" (QEA).
"""

import json

import crunch_uml.schema as sch
from crunch_uml import cli, const, db

DETAIL_DIAGRAM = "EAID_58EA4966_DBC2_4359_94C4_ABC774DBE5E2"
BOUWACTIVITEIT = "EAID_4AD539EC_A308_43da_B025_17A1647303F3"
TYPE_MONUMENT = "EAID_5C808AC9_CB09_4f4d_813E_821829856BA8"
INKOMEN_GEN_WITH_PATH = "EAID_14B94C41_1654_4425_9F6F_293123C0CF5C"

SCHEMA_XMI = "geoparse_monumenten_xmi"
SCHEMA_QEA = "geoparse_monumenten_qea"
SCHEMA_INK_XMI = "geoparse_inkomen_xmi"
SCHEMA_INK_QEA = "geoparse_inkomen_qea"


def setup_module():
    cli.main(["-sch", SCHEMA_XMI, "import", "-f", "./test/data/GGM_Monumenten_EA2.1.xml", "-t", "eaxmi", "-db_create"])
    cli.main(["-sch", SCHEMA_QEA, "import", "-f", "./test/data/Monumenten.qea", "-t", "qea"])
    cli.main(["-sch", SCHEMA_INK_XMI, "import", "-f", "./test/data/InkomenMIM.xml", "-t", "eaxmi"])
    cli.main(["-sch", SCHEMA_INK_QEA, "import", "-f", "./test/data/InkomenMIM.qea", "-t", "qea"])


def get_session():
    database = db.Database(const.DATABASE_URL, db_create=False)
    return database.session


def junction_rows(session, model, schema_id, **filters):
    return session.query(model).filter_by(schema_id=schema_id, **filters).all()


def test_eaxmi_node_geometry():
    session = get_session()
    nodes = {dc.class_id: dc for dc in junction_rows(session, db.DiagramClass, SCHEMA_XMI, diagram_id=DETAIL_DIAGRAM)}
    assert len(nodes) == 7

    bouwactiviteit = nodes[BOUWACTIVITEIT]
    assert (bouwactiviteit.x, bouwactiviteit.y) == (30.0, 40.0)
    assert (bouwactiviteit.width, bouwactiviteit.height) == (100.0, 80.0)
    assert bouwactiviteit.z_order == 3
    assert bouwactiviteit.ea_style == "DUID=DC2C05F0;"

    beschermde_status = nodes["EAID_32C02923_EE3A_4553_B94B_31E0C273A829"]
    assert (beschermde_status.x, beschermde_status.y) == (230.0, 240.0)
    assert (beschermde_status.width, beschermde_status.height) == (100.0, 80.0)
    assert beschermde_status.z_order == 9

    enums = {
        de.enumeration_id: de
        for de in junction_rows(session, db.DiagramEnumeration, SCHEMA_XMI, diagram_id=DETAIL_DIAGRAM)
    }
    type_monument = enums[TYPE_MONUMENT]
    # geometry="Left=30;Top=240;Right=130;Bottom=310;" seqno="8"
    assert (type_monument.x, type_monument.y) == (30.0, 240.0)
    assert (type_monument.width, type_monument.height) == (100.0, 70.0)
    assert type_monument.z_order == 8


def test_eaxmi_edge_geometry_without_waypoints():
    session = get_session()
    edges = junction_rows(session, db.DiagramAssociation, SCHEMA_XMI, diagram_id=DETAIL_DIAGRAM)
    assert len(edges) == 6
    for edge in edges:
        # All detail-diagram edges have Path=; (no intermediate points). The
        # canonical form keeps ea_geometry without the Path part and
        # ea_style without the Hidden part.
        assert edge.waypoints is None
        assert edge.hidden is False
        assert "Path=" not in edge.ea_geometry
        assert "Hidden=" not in edge.ea_style
        assert edge.ea_geometry.endswith("ILHS=;")


def test_eaxmi_waypoints():
    session = get_session()
    rows = junction_rows(session, db.DiagramGeneralization, SCHEMA_INK_XMI, generalization_id=INKOMEN_GEN_WITH_PATH)
    assert len(rows) == 1
    gen = rows[0]
    assert json.loads(gen.waypoints) == [{"x": 580.0, "y": 820.0}]
    assert gen.hidden is False
    assert gen.ea_style == "Mode=3;EOID=2696C3FD;SOID=82D9D375;Color=-1;LWidth=0;"


def test_qea_diagram_membership_and_metadata():
    """QEA import now also yields the previously missing diagram membership."""
    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database, SCHEMA_QEA)
    assert schema.count_diagrams() == 2

    detail = schema.get_diagram(DETAIL_DIAGRAM)
    assert detail is not None
    assert detail.name == "Diagram Monumenten Detail"
    assert detail.author == "Arjen Brienen"
    assert detail.version == "1.0"
    assert detail.package_id == "EAPK_5B6708DC_CE09_4284_8DCE_DD1B744BB652"
    assert len(detail.diagram_classes) == 6
    assert len(detail.diagram_enumerations) == 1
    assert len(detail.diagram_associations) == 5
    assert len(detail.diagram_generalizations) == 0

    # Diagram 1 contains two Notes and a NoteLink next to one class; only the
    # class becomes membership.
    monumenten = schema.get_diagram("EAID_7429E175_1CBE_4336_BF92_6C5029395E69")
    assert len(monumenten.diagram_classes) == 1
    assert len(monumenten.diagram_associations) == 0


def test_qea_node_geometry():
    session = get_session()
    nodes = {dc.class_id: dc for dc in junction_rows(session, db.DiagramClass, SCHEMA_QEA, diagram_id=DETAIL_DIAGRAM)}
    bouwactiviteit = nodes[BOUWACTIVITEIT]
    # RectLeft=30, RectTop=-40, RectRight=130, RectBottom=-120 (negative
    # top/bottom in the QEA database) -> canonical (30, 40, 100, 80).
    assert (bouwactiviteit.x, bouwactiviteit.y) == (30.0, 40.0)
    assert (bouwactiviteit.width, bouwactiviteit.height) == (100.0, 80.0)
    assert bouwactiviteit.z_order == 3
    assert bouwactiviteit.ea_style == "DUID=DC2C05F0;"


def test_qea_waypoints():
    session = get_session()
    rows = junction_rows(session, db.DiagramGeneralization, SCHEMA_INK_QEA, generalization_id=INKOMEN_GEN_WITH_PATH)
    assert len(rows) == 1
    gen = rows[0]
    # QEA Path column "580:-820;" -> canonical y flipped.
    assert json.loads(gen.waypoints) == [{"x": 580.0, "y": 820.0}]
    assert gen.hidden is False


def test_cross_check_eaxmi_vs_qea_geometry_identical():
    """The same model read through eaxmi and qea yields identical geometry
    for every element the two sources share. Membership itself may differ
    slightly: the XMI export represents aggregations as uml:Association
    (imported) while the qea parser skips them. The InkomenMIM pair is
    compared in full; for Monumenten only the detail diagram is compared
    because the .xml fixture is a later snapshot in which elements on
    "Diagram Monumenten" were moved."""
    session = get_session()

    checked = 0
    for schema_x, schema_q, only_diagram in (
        (SCHEMA_XMI, SCHEMA_QEA, DETAIL_DIAGRAM),
        (SCHEMA_INK_XMI, SCHEMA_INK_QEA, None),
    ):
        for model, key, fields in (
            (db.DiagramClass, "class_id", ("x", "y", "width", "height", "z_order", "ea_style")),
            (db.DiagramEnumeration, "enumeration_id", ("x", "y", "width", "height", "z_order", "ea_style")),
            (db.DiagramAssociation, "association_id", ("waypoints", "hidden", "ea_geometry", "ea_style")),
            (db.DiagramGeneralization, "generalization_id", ("waypoints", "hidden", "ea_geometry", "ea_style")),
        ):
            rows_x = {(r.diagram_id, getattr(r, key)): r for r in junction_rows(session, model, schema_x)}
            rows_q = {(r.diagram_id, getattr(r, key)): r for r in junction_rows(session, model, schema_q)}
            shared = set(rows_x) & set(rows_q)
            if only_diagram is not None:
                shared = {item for item in shared if item[0] == only_diagram}
            for item in shared:
                for field in fields:
                    assert getattr(rows_x[item], field) == getattr(rows_q[item], field), (
                        f"{model.__tablename__} {item} differs on {field}:"
                        f" {getattr(rows_x[item], field)!r} vs {getattr(rows_q[item], field)!r}"
                    )
                checked += 1

    # Make sure the comparison actually covered a substantial intersection.
    assert checked > 100
