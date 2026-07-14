"""Unit tests for the diagram geometry columns on the junction tables.

Covers phase 1 of the diagram support upgrade: creating membership rows with
geometry, copying a package structure including diagram geometry and
association/generalization membership, cascade delete of a diagram, and the
additive migration of pre-existing database files.
"""

import json
import os
import sqlite3

import crunch_uml.schema as sch
from crunch_uml import const, db

SCHEMA = "diagram_geometry_test"
WAYPOINTS = json.dumps([{"x": 226.0, "y": 205.0}, {"x": 256.0, "y": 205.0}])


def build_model(schema: sch.Schema):
    """Build a minimal model: one package with two classes, an association,
    a generalization, an enumeration and one diagram containing them all."""
    package = db.Package(id="EAPK_TEST_ROOT", name="Model Test")
    schema.save(package)

    monument = db.Class(id="EAID_CLASS_MONUMENT", name="Monument", package_id=package.id)
    pand = db.Class(id="EAID_CLASS_PAND", name="Pand", package_id=package.id)
    schema.save(monument)
    schema.save(pand)

    assoc = db.Association(
        id="EAID_ASSOC_1",
        name="betreft",
        src_class_id=monument.id,
        dst_class_id=pand.id,
    )
    schema.save(assoc)

    gener = db.Generalization(id="EAID_GEN_1", superclass_id=monument.id, subclass_id=pand.id)
    schema.save(gener)

    enum = db.Enumeratie(id="EAID_ENUM_TYPE", name="TypeMonument", package_id=package.id)
    schema.save(enum)

    diagram = db.Diagram(id="EAID_DIAGRAM_1", name="Diagram Test", package_id=package.id)

    diagram.diagram_classes.append(
        db.DiagramClass(
            diagram_id=diagram.id,
            schema_id=schema.schema_id,
            class_id=monument.id,
            x=90.0,
            y=30.0,
            width=120.0,
            height=60.0,
            z_order=1,
            ea_style="DUID=740C889F;",
        )
    )
    diagram.diagram_classes.append(
        db.DiagramClass(
            diagram_id=diagram.id,
            schema_id=schema.schema_id,
            class_id=pand.id,
            x=280.0,
            y=30.0,
            width=109.0,
            height=80.0,
            z_order=2,
            ea_style="DUID=5EE10493;",
        )
    )
    diagram.diagram_enumerations.append(
        db.DiagramEnumeration(
            diagram_id=diagram.id,
            schema_id=schema.schema_id,
            enumeration_id=enum.id,
            x=30.0,
            y=240.0,
            width=100.0,
            height=70.0,
            z_order=3,
            ea_style="DUID=351317DC;",
        )
    )
    diagram.diagram_associations.append(
        db.DiagramAssociation(
            diagram_id=diagram.id,
            schema_id=schema.schema_id,
            association_id=assoc.id,
            waypoints=WAYPOINTS,
            hidden=False,
            ea_geometry="SX=0;SY=0;EX=0;EY=0;EDGE=2;$LLB=;Path=226:-205$256:-205$;",
            ea_style="Mode=3;EOID=0E0961A5;SOID=7F76508F;Color=-1;LWidth=0;Hidden=0;",
        )
    )
    diagram.diagram_generalizations.append(
        db.DiagramGeneralization(
            diagram_id=diagram.id,
            schema_id=schema.schema_id,
            generalization_id=gener.id,
            waypoints=None,
            hidden=True,
            ea_geometry="SX=0;SY=0;EX=0;EY=0;EDGE=1;$LLB=;Path=;",
            ea_style="Mode=3;EOID=973BE7D4;SOID=FC1F7D8E;Color=-1;LWidth=0;Hidden=1;",
        )
    )
    schema.add(diagram)
    return diagram


def get_junction_rows(session, model, schema_id):
    return session.query(model).filter_by(schema_id=schema_id).all()


def test_create_membership_with_geometry():
    database = db.Database(const.DATABASE_URL, db_create=True)
    schema = sch.Schema(database, SCHEMA)
    build_model(schema)
    database.commit()

    session = schema.get_session()
    diagram_classes = {dc.class_id: dc for dc in get_junction_rows(session, db.DiagramClass, SCHEMA)}
    assert len(diagram_classes) == 2
    monument = diagram_classes["EAID_CLASS_MONUMENT"]
    assert (monument.x, monument.y, monument.width, monument.height) == (90.0, 30.0, 120.0, 60.0)
    assert monument.z_order == 1
    assert monument.ea_style == "DUID=740C889F;"

    diagram_enums = get_junction_rows(session, db.DiagramEnumeration, SCHEMA)
    assert len(diagram_enums) == 1
    assert (diagram_enums[0].x, diagram_enums[0].y) == (30.0, 240.0)

    diagram_assocs = get_junction_rows(session, db.DiagramAssociation, SCHEMA)
    assert len(diagram_assocs) == 1
    assert json.loads(diagram_assocs[0].waypoints) == [
        {"x": 226.0, "y": 205.0},
        {"x": 256.0, "y": 205.0},
    ]
    assert diagram_assocs[0].hidden is False
    assert diagram_assocs[0].ea_geometry.startswith("SX=0;SY=0;")

    diagram_geners = get_junction_rows(session, db.DiagramGeneralization, SCHEMA)
    assert len(diagram_geners) == 1
    assert diagram_geners[0].hidden is True
    assert diagram_geners[0].waypoints is None

    database.close()


def test_membership_without_geometry_stays_valid():
    """Membership rows without any geometry (pre-existing data) remain valid."""
    database = db.Database(const.DATABASE_URL, db_create=True)
    schema = sch.Schema(database, SCHEMA)

    package = db.Package(id="EAPK_TEST_ROOT", name="Model Test")
    schema.save(package)
    clazz = db.Class(id="EAID_CLASS_1", name="Kaal", package_id=package.id)
    schema.save(clazz)
    diagram = db.Diagram(id="EAID_DIAGRAM_1", name="Diagram Kaal", package_id=package.id)
    diagram.diagram_classes.append(
        db.DiagramClass(diagram_id=diagram.id, schema_id=schema.schema_id, class_id=clazz.id)
    )
    schema.add(diagram)
    database.commit()

    session = schema.get_session()
    rows = get_junction_rows(session, db.DiagramClass, SCHEMA)
    assert len(rows) == 1
    assert rows[0].x is None
    assert rows[0].ea_style is None

    database.close()


def test_copy_preserves_geometry_and_relation_membership():
    database = db.Database(const.DATABASE_URL, db_create=True)
    schema = sch.Schema(database, SCHEMA)
    build_model(schema)
    database.commit()

    root = schema.get_package("EAPK_TEST_ROOT")
    kopie_schema = sch.Schema(database, "diagram_geometry_kopie")
    kopie = root.get_copy(None)
    kopie_schema.add(kopie, recursive=True)
    database.commit()

    session = kopie_schema.get_session()

    diagram_classes = {dc.class_id: dc for dc in get_junction_rows(session, db.DiagramClass, "diagram_geometry_kopie")}
    assert len(diagram_classes) == 2
    monument = diagram_classes["EAID_CLASS_MONUMENT"]
    assert (monument.x, monument.y, monument.width, monument.height) == (90.0, 30.0, 120.0, 60.0)
    assert monument.z_order == 1
    assert monument.ea_style == "DUID=740C889F;"

    diagram_enums = get_junction_rows(session, db.DiagramEnumeration, "diagram_geometry_kopie")
    assert len(diagram_enums) == 1
    assert (diagram_enums[0].x, diagram_enums[0].y, diagram_enums[0].z_order) == (30.0, 240.0, 3)

    # The previously missing association/generalization membership is copied,
    # including edge geometry.
    diagram_assocs = get_junction_rows(session, db.DiagramAssociation, "diagram_geometry_kopie")
    assert len(diagram_assocs) == 1
    assert diagram_assocs[0].association_id == "EAID_ASSOC_1"
    assert json.loads(diagram_assocs[0].waypoints) == json.loads(WAYPOINTS)
    assert diagram_assocs[0].hidden is False

    diagram_geners = get_junction_rows(session, db.DiagramGeneralization, "diagram_geometry_kopie")
    assert len(diagram_geners) == 1
    assert diagram_geners[0].generalization_id == "EAID_GEN_1"
    assert diagram_geners[0].hidden is True

    database.close()


def test_copy_skips_relations_that_are_not_copied():
    """Relations whose owning class cannot copy them (orphan endpoint, or a
    class without a package) must not get dangling membership rows in the
    copy."""
    database = db.Database(const.DATABASE_URL, db_create=True)
    schema = sch.Schema(database, SCHEMA)

    package = db.Package(id="EAPK_TEST_ROOT", name="Model Test")
    schema.save(package)
    monument = db.Class(id="EAID_CLASS_MONUMENT", name="Monument", package_id=package.id)
    orphan = db.Class(id="EAID_CLASS_ORPHAN", name=const.ORPHAN_CLASS)
    zwerver = db.Class(id="EAID_CLASS_ZWERVER", name="Zwerver")  # no package
    schema.save(monument)
    schema.save(orphan)
    schema.save(zwerver)

    # Association to an orphan placeholder: never copied by Class.get_copy.
    assoc_orphan = db.Association(
        id="EAID_ASSOC_ORPHAN", name="naar orphan", src_class_id=monument.id, dst_class_id=orphan.id
    )
    schema.save(assoc_orphan)
    # Association owned by a class without a package: never copied either.
    assoc_zwerver = db.Association(
        id="EAID_ASSOC_ZWERVER", name="van zwerver", src_class_id=zwerver.id, dst_class_id=monument.id
    )
    schema.save(assoc_zwerver)

    diagram = db.Diagram(id="EAID_DIAGRAM_1", name="Diagram Test", package_id=package.id)
    for class_id in (monument.id, orphan.id, zwerver.id):
        diagram.diagram_classes.append(
            db.DiagramClass(diagram_id=diagram.id, schema_id=schema.schema_id, class_id=class_id)
        )
    for assoc_id in (assoc_orphan.id, assoc_zwerver.id):
        diagram.diagram_associations.append(
            db.DiagramAssociation(diagram_id=diagram.id, schema_id=schema.schema_id, association_id=assoc_id)
        )
    schema.add(diagram)
    database.commit()

    root = schema.get_package("EAPK_TEST_ROOT")
    kopie_schema = sch.Schema(database, "diagram_geometry_kopie2")
    kopie = root.get_copy(None)
    kopie_schema.add(kopie, recursive=True)
    database.commit()

    session = kopie_schema.get_session()
    # Neither association is copied, so neither may have a membership row.
    assert get_junction_rows(session, db.DiagramAssociation, "diagram_geometry_kopie2") == []
    # No dangling membership: every membership row points to an existing association.
    assoc_ids = {a.id for a in session.query(db.Association).filter_by(schema_id="diagram_geometry_kopie2")}
    for row in get_junction_rows(session, db.DiagramAssociation, "diagram_geometry_kopie2"):
        assert row.association_id in assoc_ids

    database.close()


def test_copy_skips_relation_owned_by_class_from_other_root():
    """A diagram may show a class from another root package. A relation owned
    by such a class is only copied when its far endpoint is in scope of the
    *owning class's* root — mirroring Class.get_copy. Here the far endpoint
    lives in the diagram's root, not the owner's, so no membership row may be
    created (the relation itself never reaches the copy)."""
    database = db.Database(const.DATABASE_URL, db_create=True)
    schema = sch.Schema(database, SCHEMA)

    root1 = db.Package(id="EAPK_ROOT_1", name="Model Een")
    root2 = db.Package(id="EAPK_ROOT_2", name="Model Twee")
    schema.save(root1)
    schema.save(root2)
    klasse_a = db.Class(id="EAID_CLASS_A", name="KlasseA", package_id=root1.id)
    klasse_b = db.Class(id="EAID_CLASS_B", name="KlasseB", package_id=root2.id)
    schema.save(klasse_a)
    schema.save(klasse_b)
    assoc = db.Association(id="EAID_ASSOC_BA", name="b naar a", src_class_id=klasse_b.id, dst_class_id=klasse_a.id)
    schema.save(assoc)

    diagram = db.Diagram(id="EAID_DIAGRAM_X", name="Cross root", package_id=root1.id)
    for class_id in (klasse_a.id, klasse_b.id):
        diagram.diagram_classes.append(
            db.DiagramClass(diagram_id=diagram.id, schema_id=schema.schema_id, class_id=class_id)
        )
    diagram.diagram_associations.append(
        db.DiagramAssociation(diagram_id=diagram.id, schema_id=schema.schema_id, association_id=assoc.id)
    )
    schema.add(diagram)
    database.commit()

    root = schema.get_package("EAPK_ROOT_1")
    kopie_schema = sch.Schema(database, "diagram_geometry_kopie3")
    kopie = root.get_copy(None)
    kopie_schema.add(kopie, recursive=True)
    database.commit()

    session = kopie_schema.get_session()
    # No dangling membership: every membership row points to an existing association.
    assoc_ids = {a.id for a in session.query(db.Association).filter_by(schema_id="diagram_geometry_kopie3")}
    for row in get_junction_rows(session, db.DiagramAssociation, "diagram_geometry_kopie3"):
        assert row.association_id in assoc_ids

    database.close()


def test_diagram_get_instances_supports_all_types():
    """Diagram.get_instances references get_associations_inscope and
    get_generalizations_inscope on Package; those helpers did not exist
    before phase 1."""
    database = db.Database(const.DATABASE_URL, db_create=True)
    schema = sch.Schema(database, SCHEMA)
    diagram = build_model(schema)
    database.commit()

    associations = diagram.get_instances(db.Association, "EAPK_TEST_ROOT")
    assert {assoc.id for assoc in associations} == {"EAID_ASSOC_1"}
    generalizations = diagram.get_instances(db.Generalization, "EAPK_TEST_ROOT")
    assert {gener.id for gener in generalizations} == {"EAID_GEN_1"}

    database.close()


def test_old_database_file_gets_missing_columns_added():
    """A database file written before the geometry columns existed must stay
    usable: missing nullable columns are added on connect."""
    path = "./test/output/old_style.db"
    if os.path.exists(path):
        os.remove(path)
    raw = sqlite3.connect(path)
    # Old-style minimal schema: presence of 'packages' suppresses create_all.
    raw.execute("CREATE TABLE packages (id VARCHAR NOT NULL, schema_id VARCHAR NOT NULL, PRIMARY KEY (id, schema_id))")
    raw.execute(
        "CREATE TABLE diagram_class (diagram_id VARCHAR NOT NULL, schema_id VARCHAR NOT NULL,"
        " class_id VARCHAR NOT NULL, PRIMARY KEY (diagram_id, schema_id, class_id))"
    )
    raw.execute("INSERT INTO diagram_class VALUES ('d1', 'oud', 'c1')")
    raw.commit()
    raw.close()

    # The Database class is a singleton per process: detach the shared
    # instance, connect to the old file, and restore afterwards.
    saved_instance = db.Database._instance
    db.Database._instance = None
    try:
        database = db.Database(f"sqlite:///{path}")
        rows = database.session.query(db.DiagramClass).filter_by(schema_id="oud").all()
        assert len(rows) == 1
        assert rows[0].class_id == "c1"
        assert rows[0].x is None
        assert rows[0].ea_style is None
        # Missing tables were created as well.
        assert database.session.query(db.Diagram).count() == 0
        # The database predates the version marker: it gets stamped with the
        # current datamodel version on connect.
        assert database._read_datamodel_version() == db.DATAMODEL_VERSION
        database.close()
    finally:
        db.Database._instance = saved_instance
        os.remove(path)


def test_datamodel_version_is_stamped_and_kept_out_of_exports():
    """Every database carries the datamodel version in crunch_uml_meta; the
    meta table must not leak into the generic renderers (it is not part of
    Base.metadata)."""
    database = db.Database(const.DATABASE_URL, db_create=True)
    assert database._read_datamodel_version() == db.DATAMODEL_VERSION
    assert "crunch_uml_meta" not in db.getTables()
    database.close()


def test_incompatible_datamodel_version_recreates_database():
    """A database with a different datamodel version is incompatible: it is
    recreated from scratch on connect (data discarded) and restamped."""
    path = "./test/output/incompatible_version.db"
    if os.path.exists(path):
        os.remove(path)
    raw = sqlite3.connect(path)
    raw.execute("CREATE TABLE packages (id VARCHAR NOT NULL, schema_id VARCHAR NOT NULL, PRIMARY KEY (id, schema_id))")
    raw.execute("INSERT INTO packages VALUES ('EAPK_OUD', 'default')")
    raw.execute("CREATE TABLE crunch_uml_meta (key VARCHAR NOT NULL PRIMARY KEY, value VARCHAR)")
    raw.execute("INSERT INTO crunch_uml_meta VALUES ('datamodel_version', '9999')")
    raw.commit()
    raw.close()

    saved_instance = db.Database._instance
    db.Database._instance = None
    try:
        database = db.Database(f"sqlite:///{path}")
        # Recreated: the old package row is gone, the version is restamped
        # and the full current table set exists.
        assert database.session.query(db.Package).count() == 0
        assert database._read_datamodel_version() == db.DATAMODEL_VERSION
        rows = database.session.query(db.DiagramClass).all()
        assert rows == []
        database.close()
    finally:
        db.Database._instance = saved_instance
        os.remove(path)


def test_compatible_database_keeps_data_between_connects():
    """Same datamodel version: reconnecting must not touch existing data."""
    path = "./test/output/compatible_version.db"
    if os.path.exists(path):
        os.remove(path)

    saved_instance = db.Database._instance
    db.Database._instance = None
    try:
        database = db.Database(f"sqlite:///{path}")
        schema = sch.Schema(database, "blijft")
        schema.save(db.Package(id="EAPK_BLIJFT", name="Blijft"))
        database.commit()
        database.close()

        db.Database._instance = None
        database = db.Database(f"sqlite:///{path}")
        assert database.session.query(db.Package).filter_by(schema_id="blijft").count() == 1
        assert database._read_datamodel_version() == db.DATAMODEL_VERSION
        database.close()
    finally:
        db.Database._instance = saved_instance
        os.remove(path)


def test_cascade_delete_diagram_removes_geometry_rows():
    database = db.Database(const.DATABASE_URL, db_create=True)
    schema = sch.Schema(database, SCHEMA)
    build_model(schema)
    database.commit()

    session = schema.get_session()
    diagram = schema.get_diagram("EAID_DIAGRAM_1")
    session.delete(diagram)
    database.commit()

    assert get_junction_rows(session, db.DiagramClass, SCHEMA) == []
    assert get_junction_rows(session, db.DiagramEnumeration, SCHEMA) == []
    assert get_junction_rows(session, db.DiagramAssociation, SCHEMA) == []
    assert get_junction_rows(session, db.DiagramGeneralization, SCHEMA) == []

    # The model elements themselves are untouched.
    assert schema.count_class() == 2
    assert schema.count_enumeratie() == 1
    assert schema.count_association() == 1
    assert schema.count_generalizations() == 1

    database.close()
