"""Acceptance test for the XMI renderer (phase 3): the round-trip

    fixture -> [parse] -> schema A -> [xmi render] -> out.xml
    out.xml -> [eaxmi parse] -> schema B

must yield a schema B that is semantically equal to schema A: same
packages/classes/attributes/enums/associations/generalizations, same diagram
membership and identical geometry.

Documented normalizations (see also renderers/EA_QUIRKS.md):

* ``''`` and ``'None'`` are treated as NULL: the eaxmi parser stores the
  string ``'None'`` for absent cardinalities and ``''`` for unresolvable
  attribute type references.
* Attributes with an ``EAID_src``/``EAID_dst`` id are artifacts of navigable
  association ends in EA exports; the renderer represents those ends as
  ownedEnd elements instead, so they are excluded from the comparison.
* For orphan placeholder classes only id/name are compared: the parser
  stores a generated explanation in ``definitie`` for one of the two ways
  orphans arise.
* ``Attribute.primitive`` is display-only when a classifier FK
  (``type_class_id``/``enumeration_id``) is set: the two parsers fill it
  differently (class name vs None), so it is ignored in that case.
"""

import crunch_uml.schema as sch
from crunch_uml import cli, const, db

NODE_FIELDS = ("x", "y", "width", "height", "z_order", "ea_style")
EDGE_FIELDS = ("waypoints", "hidden", "ea_geometry", "ea_style")
JUNCTION_MODELS = (
    (db.DiagramClass, "class_id", NODE_FIELDS),
    (db.DiagramEnumeration, "enumeration_id", NODE_FIELDS),
    (db.DiagramAssociation, "association_id", EDGE_FIELDS),
    (db.DiagramGeneralization, "generalization_id", EDGE_FIELDS),
)
ENTITY_MODELS = (
    db.Package,
    db.Class,
    db.Attribute,
    db.Enumeratie,
    db.EnumerationLiteral,
    db.Association,
    db.Generalization,
    db.Diagram,
)


def normalize(value):
    return None if value in ("", "None") else value


def is_association_end(entity_id):
    return entity_id.startswith("EAID_src") or entity_id.startswith("EAID_dst")


def roundtrip(fixture, inputtype, schema_a, schema_b, outputfile, db_create=False):
    import_args = ["-sch", schema_a, "import", "-f", fixture, "-t", inputtype]
    if db_create:
        import_args.append("-db_create")
    cli.main(import_args)
    cli.main(["-sch", schema_a, "export", "-f", outputfile, "-t", "xmi"])
    cli.main(["-sch", schema_b, "import", "-f", outputfile, "-t", "eaxmi"])


def assert_semantically_equal(schema_a, schema_b):
    database = db.Database(const.DATABASE_URL, db_create=False)
    session = database.session

    for model in ENTITY_MODELS:
        rows_a = {r.id: r for r in session.query(model).filter_by(schema_id=schema_a)}
        rows_b = {r.id: r for r in session.query(model).filter_by(schema_id=schema_b)}
        orphan_ids = {
            key
            for key, row in list(rows_a.items()) + list(rows_b.items())
            if getattr(row, "name", None) == const.ORPHAN_CLASS
        }
        ids_a = {key for key in rows_a if not is_association_end(key)}
        ids_b = {key for key in rows_b if not is_association_end(key)}
        assert ids_a == ids_b, (
            f"{model.__tablename__}: ids differ; only in A: {sorted(ids_a - ids_b)[:5]},"
            f" only in B: {sorted(ids_b - ids_a)[:5]}"
        )

        for key in ids_a:
            dict_a, dict_b = rows_a[key].to_dict(), rows_b[key].to_dict()
            for field, value_a in dict_a.items():
                if field in ("schema_id", "kopie"):
                    continue
                if key in orphan_ids and field == "definitie":
                    continue
                if (
                    field == "primitive"
                    and model is db.Attribute
                    and (dict_a.get("type_class_id") or dict_a.get("enumeration_id"))
                ):
                    continue
                assert normalize(value_a) == normalize(dict_b.get(field)), (
                    f"{model.__tablename__} {key} differs on {field}:" f" {value_a!r} vs {dict_b.get(field)!r}"
                )

    for model, key_field, fields in JUNCTION_MODELS:
        rows_a = {(r.diagram_id, getattr(r, key_field)): r for r in session.query(model).filter_by(schema_id=schema_a)}
        rows_b = {(r.diagram_id, getattr(r, key_field)): r for r in session.query(model).filter_by(schema_id=schema_b)}
        assert set(rows_a) == set(rows_b), (
            f"{model.__tablename__}: membership differs; only in A: {sorted(set(rows_a) - set(rows_b))[:5]},"
            f" only in B: {sorted(set(rows_b) - set(rows_a))[:5]}"
        )
        for key in rows_a:
            for field in fields:
                value_a, value_b = getattr(rows_a[key], field), getattr(rows_b[key], field)
                assert normalize(value_a) == normalize(
                    value_b
                ), f"{model.__tablename__} {key} differs on {field}: {value_a!r} vs {value_b!r}"


def test_roundtrip_monumenten_eaxmi():
    roundtrip(
        "./test/data/GGM_Monumenten_EA2.1.xml",
        "eaxmi",
        "xmirt_mon_a",
        "xmirt_mon_b",
        "./test/output/xmirt_monumenten.xml",
        db_create=True,
    )
    assert_semantically_equal("xmirt_mon_a", "xmirt_mon_b")

    # Spot checks against the fixture so the comparison cannot pass vacuously.
    database = db.Database(const.DATABASE_URL, db_create=False)
    schema_b = sch.Schema(database, "xmirt_mon_b")
    assert schema_b.count_class() == 11
    assert schema_b.count_diagrams() == 2
    detail = schema_b.get_diagram("EAID_58EA4966_DBC2_4359_94C4_ABC774DBE5E2")
    bouwactiviteit = next(
        dc for dc in detail.diagram_classes if dc.class_id == "EAID_4AD539EC_A308_43da_B025_17A1647303F3"
    )
    assert (bouwactiviteit.x, bouwactiviteit.y, bouwactiviteit.width, bouwactiviteit.height) == (
        30.0,
        40.0,
        100.0,
        80.0,
    )
    assert bouwactiviteit.z_order == 3
    assert bouwactiviteit.ea_style == "DUID=DC2C05F0;"


def test_roundtrip_monumenten_qea():
    """Same acceptance test starting from the QEA repository file."""
    roundtrip(
        "./test/data/Monumenten.qea",
        "qea",
        "xmirt_qea_a",
        "xmirt_qea_b",
        "./test/output/xmirt_monumenten_qea.xml",
    )
    assert_semantically_equal("xmirt_qea_a", "xmirt_qea_b")

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema_b = sch.Schema(database, "xmirt_qea_b")
    assert schema_b.count_diagrams() == 2
    detail = schema_b.get_diagram("EAID_58EA4966_DBC2_4359_94C4_ABC774DBE5E2")
    assert len(detail.diagram_classes) == 6
    assert len(detail.diagram_associations) == 5


def test_roundtrip_schuldhulpverlening_eaxmi():
    """Larger model with generalizations on diagrams, waypoint paths and
    orphan placeholders for elements outside the export."""
    roundtrip(
        "./test/data/Model Schuldhulpverlening.xml",
        "eaxmi",
        "xmirt_shv_a",
        "xmirt_shv_b",
        "./test/output/xmirt_schuldhulp.xml",
    )
    assert_semantically_equal("xmirt_shv_a", "xmirt_shv_b")

    database = db.Database(const.DATABASE_URL, db_create=False)
    session = database.session
    schema_b = sch.Schema(database, "xmirt_shv_b")
    assert schema_b.count_diagrams() == 5
    gens = session.query(db.DiagramGeneralization).filter_by(schema_id="xmirt_shv_b").all()
    assert len(gens) == 5
    # At least one association edge in this model carries real waypoints.
    assocs = session.query(db.DiagramAssociation).filter_by(schema_id="xmirt_shv_b").all()
    assert any(a.waypoints for a in assocs)


def test_roundtrip_inkomen_qea():
    """MIM model with named/stereotyped generalizations, datatypes with
    definitions and synthetic attribute ids — fields that only exist when
    the source is a QEA repository."""
    roundtrip(
        "./test/data/InkomenMIM.qea",
        "qea",
        "xmirt_ink_a",
        "xmirt_ink_b",
        "./test/output/xmirt_inkomen.xml",
    )
    assert_semantically_equal("xmirt_ink_a", "xmirt_ink_b")

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema_b = sch.Schema(database, "xmirt_ink_b")
    assert schema_b.count_generalizations() == 30
    assert schema_b.count_datatype() == 30
    gen = schema_b.get_generalization("EAID_14B94C41_1654_4425_9F6F_293123C0CF5C")
    assert gen.name == "Vordering generaliseert Rentevordering"
    assert gen.stereotype == "Generalisatie"


def test_render_survives_control_characters_and_unplaced_class():
    """Control characters (ingestible via json/xlsx imports) may not crash
    the renderer, and a class without a (known) package is placed in the
    first root package instead of being dropped."""
    database = db.Database(const.DATABASE_URL, db_create=True)
    schema = sch.Schema(database, "xmirt_edge_a")
    package = db.Package(id="EAPK_EDGE_ROOT", name="Model Edge")
    schema.save(package)
    clazz = db.Class(
        id="EAID_EDGE_CLASS",
        name="MetControlChar",
        package_id=package.id,
        definitie="foute\x0btekst",
    )
    schema.save(clazz)
    zwevend = db.Class(id="EAID_EDGE_ZWEVEND", name="Zwevend", package_id="EAPK_BESTAAT_NIET")
    schema.save(zwevend)
    database.commit()

    cli.main(["-sch", "xmirt_edge_a", "export", "-f", "./test/output/xmirt_edge.xml", "-t", "xmi"])
    cli.main(["-sch", "xmirt_edge_b", "import", "-f", "./test/output/xmirt_edge.xml", "-t", "eaxmi"])

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema_b = sch.Schema(database, "xmirt_edge_b")
    met_control_char = schema_b.get_class("EAID_EDGE_CLASS")
    assert met_control_char is not None
    assert met_control_char.definitie == "foutetekst"  # control character removed
    zwevend_b = schema_b.get_class("EAID_EDGE_ZWEVEND")
    assert zwevend_b is not None
    assert zwevend_b.package_id == "EAPK_EDGE_ROOT"  # relocated, not dropped


def test_rendered_file_contains_ea_extension():
    """The rendered file has the structural markers EA needs on import."""
    with open("./test/output/xmirt_monumenten.xml", encoding="utf-8") as f:
        content = f.read()
    assert 'exporter="Enterprise Architect"' in content
    assert '<xmi:Extension extender="Enterprise Architect"' in content
    assert "<uml:Model" in content
    assert "Path=" in content  # edge geometry present
    assert 'geometry="Left=' in content  # node geometry present
