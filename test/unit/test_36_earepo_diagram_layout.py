"""Tests for writing diagram membership and geometry back to an EA
repository (phase 4), following the pattern of test_15_updateEAModel.

The source model is GGM_Monumenten_EA2.1.xml — a later snapshot of the same
model as Monumenten.qea, in which BeschermdeStatus was moved on "Diagram
Monumenten". Expected values are read from the fixtures:

* XML "Diagram Monumenten": BeschermdeStatus geometry
  "Left=126;Top=40;Right=247;Bottom=120;" seqno 6 — the .qea still has
  RectLeft=280, RectTop=-30, RectRight=389, RectBottom=-110, Sequence 3.
* XML "Diagram Monumenten Detail": Ambacht (Object_ID 6)
  "Left=450;Top=240;Right=550;Bottom=320;" seqno 4.
"""

import os
import shutil
import sqlite3

import crunch_uml.schema as sch
from crunch_uml import cli, const, db
from crunch_uml import ea_geometry as geo

EA_DB = "./test/output/Monumenten_layout.qea"
SCHEMA = "earepo_layout"

DIAGRAM_MONUMENTEN = 1  # {7429E175-1CBE-4336-BF92-6C5029395E69}
DIAGRAM_DETAIL = 2  # {58EA4966-DBC2-4359-94C4-ABC774DBE5E2}
OBJ_NOTE_1 = 3
OBJ_NOTE_2 = 4
OBJ_AMBACHT = 6
OBJ_BESCHERMDE_STATUS = 7
OBJ_BOUWTYPE = 10

BESCHERMDE_STATUS_ID = "EAID_32C02923_EE3A_4553_B94B_31E0C273A829"
BOUWTYPE_ID = "EAID_5E9DAFBB_C9B5_4706_A43D_07AD4979DED4"
DETAIL_DIAGRAM_ID = "EAID_58EA4966_DBC2_4359_94C4_ABC774DBE5E2"
MONUMENT_FUNCTIE_ASSOC = "EAID_FD27EB67_1CFA_4f40_AE79_329DE9DE6754"


def query(sql, params=()):
    connection = sqlite3.connect(EA_DB)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(sql, params).fetchall()
    connection.close()
    return rows


def diagram_object(diagram_id, object_id):
    rows = query(
        "SELECT * FROM t_diagramobjects WHERE Diagram_ID = ? AND Object_ID = ?",
        (diagram_id, object_id),
    )
    return rows[0] if rows else None


def test_earepo_writes_diagram_layout():
    shutil.copyfile("./test/data/Monumenten.qea", EA_DB)

    # Create an insert scenario: remove Ambacht from the detail diagram in
    # the repo; the model still contains that membership.
    connection = sqlite3.connect(EA_DB)
    connection.execute(
        "DELETE FROM t_diagramobjects WHERE Diagram_ID = ? AND Object_ID = ?",
        (DIAGRAM_DETAIL, OBJ_AMBACHT),
    )
    connection.commit()
    connection.close()
    assert diagram_object(DIAGRAM_DETAIL, OBJ_AMBACHT) is None

    cli.main(["-sch", SCHEMA, "import", "-f", "./test/data/GGM_Monumenten_EA2.1.xml", "-t", "eaxmi", "-db_create"])

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database, SCHEMA)
    session = schema.get_session()

    # Create a delete scenario: drop Bouwtype from the detail diagram in the
    # model; the repo still has that membership.
    session.query(db.DiagramClass).filter_by(
        schema_id=SCHEMA, diagram_id=DETAIL_DIAGRAM_ID, class_id=BOUWTYPE_ID
    ).delete()
    # And a waypoint scenario: give one association on the detail diagram a
    # path; the repo column must get the qea encoding (';' pairs, negative y).
    assoc_membership = (
        session.query(db.DiagramAssociation)
        .filter_by(schema_id=SCHEMA, diagram_id=DETAIL_DIAGRAM_ID, association_id=MONUMENT_FUNCTIE_ASSOC)
        .one()
    )
    assoc_membership.waypoints = geo.waypoints_to_json([{"x": 100.0, "y": 200.0}])
    database.commit()

    cli.main(["-sch", SCHEMA, "export", "-f", EA_DB, "-t", "earepo"])

    # Update: BeschermdeStatus moved on "Diagram Monumenten" in the newer XML.
    beschermde_status = diagram_object(DIAGRAM_MONUMENTEN, OBJ_BESCHERMDE_STATUS)
    assert (
        beschermde_status["RectLeft"],
        beschermde_status["RectTop"],
        beschermde_status["RectRight"],
        beschermde_status["RectBottom"],
    ) == (126, -40, 247, -120)
    assert beschermde_status["Sequence"] == 6

    # Untouched: Notes are not managed by crunch_uml and keep their layout.
    note = diagram_object(DIAGRAM_MONUMENTEN, OBJ_NOTE_1)
    assert (note["RectLeft"], note["RectTop"], note["RectRight"], note["RectBottom"]) == (90, -30, 210, -90)
    assert diagram_object(DIAGRAM_MONUMENTEN, OBJ_NOTE_2) is not None
    notelink = query("SELECT * FROM t_diagramlinks WHERE DiagramID = ?", (DIAGRAM_MONUMENTEN,))
    assert len(notelink) == 1  # the NoteLink row survives

    # Elements of the newer model that do not exist in the repo are skipped:
    # diagram 1 keeps its 3 object rows (2 notes + BeschermdeStatus).
    assert len(query("SELECT * FROM t_diagramobjects WHERE Diagram_ID = ?", (DIAGRAM_MONUMENTEN,))) == 3

    # Insert: Ambacht is back on the detail diagram, with the XML geometry.
    ambacht = diagram_object(DIAGRAM_DETAIL, OBJ_AMBACHT)
    assert ambacht is not None
    assert (ambacht["RectLeft"], ambacht["RectTop"], ambacht["RectRight"], ambacht["RectBottom"]) == (
        450,
        -240,
        550,
        -320,
    )
    assert ambacht["Sequence"] == 4
    assert ambacht["ObjectStyle"].startswith("DUID=C9231E63;")

    # Delete: Bouwtype membership disappeared from the model.
    assert diagram_object(DIAGRAM_DETAIL, OBJ_BOUWTYPE) is None

    # Waypoints: written in qea encoding (';' pairs, negative y).
    link = query(
        "SELECT l.* FROM t_diagramlinks l JOIN t_connector c ON c.Connector_ID = l.ConnectorID"
        " WHERE l.DiagramID = ? AND c.ea_guid = ?",
        (DIAGRAM_DETAIL, "{FD27EB67-1CFA-4f40-AE79-329DE9DE6754}"),
    )
    assert len(link) == 1
    assert link[0]["Path"] == "100:-200;"
    assert link[0]["Hidden"] == 0
    assert link[0]["Geometry"].startswith("SX=")

    # Round-trip: parsing the updated repo yields the same geometry as the
    # eaxmi schema for all shared membership.
    cli.main(["-sch", "earepo_layout_check", "import", "-f", EA_DB, "-t", "qea"])
    database = db.Database(const.DATABASE_URL, db_create=False)
    session = database.session

    for model, key, fields in (
        (db.DiagramClass, "class_id", ("x", "y", "width", "height", "z_order", "ea_style")),
        (db.DiagramEnumeration, "enumeration_id", ("x", "y", "width", "height", "z_order", "ea_style")),
        (db.DiagramAssociation, "association_id", ("waypoints", "hidden", "ea_geometry", "ea_style")),
        (db.DiagramGeneralization, "generalization_id", ("waypoints", "hidden", "ea_geometry", "ea_style")),
    ):
        rows_model = {(r.diagram_id, getattr(r, key)): r for r in session.query(model).filter_by(schema_id=SCHEMA)}
        rows_repo = {
            (r.diagram_id, getattr(r, key)): r for r in session.query(model).filter_by(schema_id="earepo_layout_check")
        }
        shared = set(rows_model) & set(rows_repo)
        for item in shared:
            for field in fields:
                assert getattr(rows_model[item], field) == getattr(
                    rows_repo[item], field
                ), f"{model.__tablename__} {item} differs on {field}"

    os.remove(EA_DB)
