"""
End-to-end completeness check on a GGM-sized .qea import.

We import test/data/Gemeentelijk Gegevensmodel 2.4.0.qea (a real Enterprise
Architect repository with hundreds of packages and thousands of attributes /
literals / tagged values) and compare the imported crunch_uml database
against the source SQLite directly:

* All in-scope entities (Class, DataType, Enumeration, their attributes /
  literals, all valid connectors) are present;
* Tagged values from t_objectproperties / t_attributetag / t_connectortag
  end up on the right ORM column;
* A sample class' definitie / gemma_type / stereotype matches the source.

Marked ``slow`` because importing the 30 MB repository takes a few seconds.
"""

import sqlite3

import pytest

import crunch_uml.db as db
import crunch_uml.schema as sch
from crunch_uml import cli, const
from crunch_uml.parsers.qeaparser import guid_to_eaid

GGM_QEA = "./test/data/Gemeentelijk Gegevensmodel 2.4.0.qea"
SCHEMA = "ggm24_completeness"


@pytest.fixture(scope="module")
def imported_schema():
    """Import the GGM .qea once for the whole module."""
    cli.main(
        [
            "-sch",
            SCHEMA,
            "import",
            "-f",
            GGM_QEA,
            "-t",
            "qea",
            "-db_create",
        ]
    )
    database = db.Database(const.DATABASE_URL, db_create=False)
    return sch.Schema(database, schema_name=SCHEMA)


@pytest.fixture(scope="module")
def src_cursor():
    """A cursor on the raw .qea SQLite file."""
    conn = sqlite3.connect(GGM_QEA)
    cur = conn.cursor()
    yield cur
    conn.close()


# ---------------------------------------------------------------------------
# Count parity — every in-scope row in the source must end up in crunch_uml.
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_packages_count_matches_source(imported_schema, src_cursor):
    src_n = src_cursor.execute("SELECT COUNT(*) FROM t_package").fetchone()[0]
    assert imported_schema.count_package() == src_n


@pytest.mark.slow
def test_classes_count_matches_source(imported_schema, src_cursor):
    src_n = src_cursor.execute("SELECT COUNT(*) FROM t_object WHERE Object_Type = 'Class'").fetchone()[0]
    assert imported_schema.count_class() == src_n


@pytest.mark.slow
def test_datatypes_count_matches_source(imported_schema, src_cursor):
    src_n = src_cursor.execute("SELECT COUNT(*) FROM t_object WHERE Object_Type = 'DataType'").fetchone()[0]
    assert imported_schema.count_datatype() == src_n


@pytest.mark.slow
def test_enumerations_count_matches_source(imported_schema, src_cursor):
    src_n = src_cursor.execute("SELECT COUNT(*) FROM t_object WHERE Object_Type = 'Enumeration'").fetchone()[0]
    assert imported_schema.count_enumeratie() == src_n


@pytest.mark.slow
def test_attributes_count_matches_source(imported_schema, src_cursor):
    src_n = src_cursor.execute(
        """
        SELECT COUNT(*) FROM t_attribute a
        JOIN t_object o ON a.Object_ID = o.Object_ID
        WHERE o.Object_Type IN ('Class', 'DataType')
        """
    ).fetchone()[0]
    assert imported_schema.count_attribute() == src_n


@pytest.mark.slow
def test_enum_literals_count_matches_source(imported_schema, src_cursor):
    src_n = src_cursor.execute(
        """
        SELECT COUNT(*) FROM t_attribute a
        JOIN t_object o ON a.Object_ID = o.Object_ID
        WHERE o.Object_Type = 'Enumeration'
        """
    ).fetchone()[0]
    assert imported_schema.count_enumeratieliteral() == src_n


@pytest.mark.slow
def test_generalizations_count_matches_source(imported_schema, src_cursor):
    src_n = src_cursor.execute("SELECT COUNT(*) FROM t_connector WHERE Connector_Type = 'Generalization'").fetchone()[0]
    assert imported_schema.count_generalizations() == src_n


@pytest.mark.slow
def test_associations_count_matches_source_after_filter(imported_schema, src_cursor):
    """Phase 4 of the QEA parser only keeps connectors whose endpoints are
    Class/DataType/Enumeration objects. The handful of connectors that point
    at ProxyConnector/Component/Actor must NOT inflate the imported count."""
    src_n = src_cursor.execute(
        """
        SELECT COUNT(*) FROM t_connector c
        JOIN t_object so ON c.Start_Object_ID = so.Object_ID
        JOIN t_object eo ON c.End_Object_ID   = eo.Object_ID
        WHERE c.Connector_Type IN ('Association', 'Realisation')
          AND so.Object_Type IN ('Class', 'DataType', 'Enumeration')
          AND eo.Object_Type IN ('Class', 'DataType', 'Enumeration')
        """
    ).fetchone()[0]
    assert imported_schema.count_association() == src_n


# ---------------------------------------------------------------------------
# Tagged-value transfer — the actual point of phase 5.
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_class_definitie_from_t_object_note(imported_schema, src_cursor):
    """Class.definitie is filled from t_object.Note in phase 2 (not from
    tagged values). Verify it lands on the right column for a broad sample.

    Regression guard for the historical bug where the diff renderer compared
    a non-existent 'definition' column and so silently ignored these.
    """
    rows = src_cursor.execute(
        """
        SELECT ea_guid, Note FROM t_object
        WHERE Object_Type IN ('Class', 'DataType')
          AND Note IS NOT NULL AND TRIM(Note) != ''
        """
    ).fetchall()
    assert len(rows) > 100, "Expected many classes with a Note in the GGM fixture"

    sample = rows[: min(100, len(rows))]
    mismatches = []
    for ea_guid, expected in sample:
        eaid = guid_to_eaid(ea_guid)
        clazz = imported_schema.get_class(eaid) or imported_schema.get_datatype(eaid)
        if clazz is None or (clazz.definitie or "") != (expected or ""):
            mismatches.append((eaid, expected[:40] if expected else None, clazz.definitie if clazz else None))
    assert not mismatches, (
        f"Class.definitie not applied for {len(mismatches)} classes; " f"first mismatches: {mismatches[:3]}"
    )


@pytest.mark.slow
def test_attribute_definitie_from_t_attribute_notes(imported_schema, src_cursor):
    """Attribute.definitie is filled from t_attribute.Notes (phase 3)."""
    rows = src_cursor.execute(
        """
        SELECT a.ea_guid, a.Notes
        FROM t_attribute a
        JOIN t_object o ON a.Object_ID = o.Object_ID
        WHERE o.Object_Type IN ('Class', 'DataType')
          AND a.ea_guid IS NOT NULL
          AND a.Notes IS NOT NULL AND TRIM(a.Notes) != ''
        """
    ).fetchall()
    assert len(rows) > 100, "Expected many attributes with Notes in the GGM fixture"

    sample = rows[: min(100, len(rows))]
    mismatches = []
    for ea_guid, expected in sample:
        eaid = guid_to_eaid(ea_guid)
        attr = imported_schema.get_attribute(eaid)
        if attr is None or (attr.definitie or "") != (expected or ""):
            mismatches.append((eaid, expected[:40] if expected else None, attr.definitie if attr else None))
    assert not mismatches, (
        f"Attribute.definitie not applied for {len(mismatches)} attributes; " f"first mismatches: {mismatches[:3]}"
    )


@pytest.mark.slow
def test_object_tagged_values_are_applied(imported_schema, src_cursor):
    """Tagged values that *do* live in t_objectproperties (herkomst,
    gemma-type, gemma-url, populatie, …) must reach the matching ORM
    column. This exercises phase 5 — the same loop where dropping the
    per-row save() saved ~50 seconds on this fixture."""
    rows = src_cursor.execute(
        """
        SELECT o.ea_guid, LOWER(op.Property) AS prop, op.Value
        FROM t_objectproperties op
        JOIN t_object o ON op.Object_ID = o.Object_ID
        WHERE o.Object_Type IN ('Class', 'DataType', 'Enumeration')
          AND LOWER(op.Property) IN ('herkomst', 'gemma-type', 'gemma-url', 'populatie', 'kwaliteit')
          AND op.Value IS NOT NULL AND op.Value != ''
        """
    ).fetchall()
    assert len(rows) > 100, "Expected many tagged values in the GGM fixture"

    field_map = {
        "herkomst": "herkomst",
        "gemma-type": "gemma_type",
        "gemma-url": "gemma_url",
        "populatie": "populatie",
        "kwaliteit": "kwaliteit",
    }
    mismatches = []
    sample = rows[: min(200, len(rows))]
    for ea_guid, prop, expected in sample:
        eaid = guid_to_eaid(ea_guid)
        obj = (
            imported_schema.get_class(eaid)
            or imported_schema.get_datatype(eaid)
            or imported_schema.get_enumeration(eaid)
        )
        if obj is None:
            mismatches.append((eaid, prop, expected, "<object not found>"))
            continue
        actual = getattr(obj, field_map[prop], None)
        if (actual or "") != (expected or ""):
            mismatches.append((eaid, prop, expected, actual))
    assert not mismatches, (
        f"Tagged-value mismatch on {len(mismatches)}/{len(sample)} rows; " f"first mismatches: {mismatches[:3]}"
    )


@pytest.mark.slow
def test_attribute_tagged_values_are_applied(imported_schema, src_cursor):
    """Tagged values on attributes live in t_attributetag and are resolved
    via the parser's _attr_id_map (numeric ID → eaid). Verify a real
    sample reaches the ORM column."""
    rows = src_cursor.execute(
        """
        SELECT a.ea_guid, LOWER(at.Property) AS prop, at.VALUE
        FROM t_attributetag at
        JOIN t_attribute a ON at.ElementID = a.ID
        JOIN t_object o    ON a.Object_ID = o.Object_ID
        WHERE o.Object_Type IN ('Class', 'DataType')
          AND a.ea_guid IS NOT NULL
          AND LOWER(at.Property) IN ('herkomst', 'populatie', 'lengte', 'patroon', 'mogelijk-geen-waarde')
          AND at.VALUE IS NOT NULL AND at.VALUE != ''
        """
    ).fetchall()
    assert len(rows) > 50, "Expected many attribute tagged values in the GGM fixture"

    field_map = {
        "herkomst": "herkomst",
        "populatie": "populatie",
        "lengte": "lengte",
        "patroon": "patroon",
        "mogelijk-geen-waarde": "mogelijk_geen_waarde",
    }
    mismatches = []
    sample = rows[: min(100, len(rows))]
    for ea_guid, prop, expected in sample:
        eaid = guid_to_eaid(ea_guid)
        attr = imported_schema.get_attribute(eaid)
        if attr is None:
            mismatches.append((eaid, prop, expected, "<attribute not found>"))
            continue
        actual = getattr(attr, field_map[prop], None)
        if (actual or "") != (expected or ""):
            mismatches.append((eaid, prop, expected, actual))
    assert not mismatches, (
        f"Attribute tagged-value mismatch on {len(mismatches)}/{len(sample)} rows; "
        f"first mismatches: {mismatches[:3]}"
    )


# ---------------------------------------------------------------------------
# Synthetic-id literals — guards against regressing the NULL ea_guid fix.
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_literals_with_null_ea_guid_are_imported_with_synthetic_ids(imported_schema, src_cursor):
    """The QEA file has enum literals (and some attributes) with ea_guid IS
    NULL. The parser mints synthetic IDs of the form ``EAID_attr_<n>`` so
    these rows are preserved instead of crashing the import."""
    src_n = src_cursor.execute(
        """
        SELECT COUNT(*) FROM t_attribute a
        JOIN t_object o ON a.Object_ID = o.Object_ID
        WHERE o.Object_Type IN ('Class', 'DataType', 'Enumeration')
          AND a.ea_guid IS NULL
        """
    ).fetchone()[0]
    assert src_n > 0, "Fixture is expected to contain some NULL-ea_guid rows"

    from sqlalchemy.orm import Session

    with Session(imported_schema.database.engine) as session:
        synth_attr = (
            session.query(db.Attribute)
            .filter(db.Attribute.schema_id == SCHEMA, db.Attribute.id.like("EAID_attr_%"))
            .count()
        )
        synth_lit = (
            session.query(db.EnumerationLiteral)
            .filter(
                db.EnumerationLiteral.schema_id == SCHEMA,
                db.EnumerationLiteral.id.like("EAID_attr_%"),
            )
            .count()
        )
    assert synth_attr + synth_lit == src_n, (
        f"Expected {src_n} synthetic-id rows in total, got " f"{synth_attr} attributes + {synth_lit} literals"
    )
