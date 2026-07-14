"""Round-trip tests for diagram membership + geometry through the generic
formats (phase 4): json, xlsx and csv. The i18n format deliberately skips the
junction tables (indexed records need an ``id`` column and nothing on them is
translatable) — see the coverage matrix in docs/technisch/datamodel.md.
"""

import json

import crunch_uml.schema as sch
from crunch_uml import cli, const, db

SOURCE = "fmt_geo_source"

JUNCTION_MODELS = (
    (db.DiagramClass, "class_id", ("x", "y", "width", "height", "z_order", "ea_style")),
    (db.DiagramEnumeration, "enumeration_id", ("x", "y", "width", "height", "z_order", "ea_style")),
    (db.DiagramAssociation, "association_id", ("waypoints", "hidden", "ea_geometry", "ea_style")),
    (db.DiagramGeneralization, "generalization_id", ("waypoints", "hidden", "ea_geometry", "ea_style")),
)


def setup_module():
    cli.main(["-sch", SOURCE, "import", "-f", "./test/data/GGM_Monumenten_EA2.1.xml", "-t", "eaxmi", "-db_create"])


def get_session():
    return db.Database(const.DATABASE_URL, db_create=False).session


def assert_junction_rows_equal(schema_a, schema_b, expect_rows=True):
    session = get_session()
    total = 0
    for model, key, fields in JUNCTION_MODELS:
        rows_a = {(r.diagram_id, getattr(r, key)): r for r in session.query(model).filter_by(schema_id=schema_a)}
        rows_b = {(r.diagram_id, getattr(r, key)): r for r in session.query(model).filter_by(schema_id=schema_b)}
        assert set(rows_a) == set(rows_b), (
            f"{model.__tablename__}: membership differs: only A: {sorted(set(rows_a) - set(rows_b))[:4]},"
            f" only B: {sorted(set(rows_b) - set(rows_a))[:4]}"
        )
        for item, row_a in rows_a.items():
            for field in fields:
                value_a, value_b = getattr(row_a, field), getattr(rows_b[item], field)
                assert (
                    value_a == value_b
                ), f"{model.__tablename__} {item} differs on {field}: {value_a!r} vs {value_b!r}"
            total += 1
    if expect_rows:
        assert total > 15  # geometry actually flowed through


def test_json_roundtrip_includes_diagram_geometry():
    outputfile = "./test/output/fmt_geo.json"
    cli.main(["-sch", SOURCE, "export", "-f", outputfile, "-t", "json"])

    with open(outputfile) as f:
        data = json.load(f)
    assert len(data["diagram_class"]) == 10
    node = next(r for r in data["diagram_class"] if r["class_id"] == "EAID_4AD539EC_A308_43da_B025_17A1647303F3")
    assert (node["x"], node["y"], node["width"], node["height"]) == (30.0, 40.0, 100.0, 80.0)

    cli.main(["-sch", "fmt_geo_json", "import", "-f", outputfile, "-t", "json"])
    assert_junction_rows_equal(SOURCE, "fmt_geo_json")


def test_xlsx_roundtrip_includes_diagram_geometry():
    outputfile = "./test/output/fmt_geo.xlsx"
    cli.main(["-sch", SOURCE, "export", "-f", outputfile, "-t", "xlsx"])
    cli.main(["-sch", "fmt_geo_xlsx", "import", "-f", outputfile, "-t", "xlsx"])
    assert_junction_rows_equal(SOURCE, "fmt_geo_xlsx")


def test_csv_roundtrip_includes_diagram_geometry():
    prefix = "./test/output/fmt_geo_csv"
    cli.main(["-sch", SOURCE, "export", "-f", prefix, "-t", "csv"])
    # The csv renderer writes one file per table; junction tables included.
    for table in ("diagram_class", "diagram_enumeration", "diagram_association", "diagram_generalization"):
        cli.main(
            [
                "-sch",
                "fmt_geo_csv",
                "import",
                "-f",
                f"{prefix}_{table}.csv",
                "-t",
                "csv",
                "--entity_name",
                table,
            ]
        )
    assert_junction_rows_equal(SOURCE, "fmt_geo_csv")


def test_old_json_without_geometry_still_imports():
    """Files written before diagram membership/geometry existed (like the
    Monumenten.json fixture) keep importing."""
    cli.main(["-sch", "fmt_geo_old", "import", "-f", "./test/data/Monumenten.json", "-t", "json"])
    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database, "fmt_geo_old")
    assert schema.count_class() == 10
    assert schema.count_package() == 3
    session = schema.get_session()
    assert session.query(db.DiagramClass).filter_by(schema_id="fmt_geo_old").count() == 0
