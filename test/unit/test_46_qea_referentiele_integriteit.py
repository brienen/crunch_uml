"""Referential integrity of a QEA import, the property Postgres enforces and SQLite does not.

Before 0.7.0 was tagged, ``crunch_uml import -t qea`` of the GGM 2.5.1 repository into
Postgres stopped in phase 4 on ``fk_dst_class``: three associations end on an Enumeration,
which lives in ``enumerations``, not in ``classes``. SQLite (and so ``pack``) stored the
dangling rows without complaint. The QEA parser now gives such an end a placeholder class,
as the eaxmi parser does.

* Every QEA fixture in the repository is parsed into SQLite and checked with
  ``PRAGMA foreign_key_check`` (the two GGM repositories are ``slow``).
* The real Postgres import of GGM 2.5.1 (``slow``) runs against
  ``CRUNCH_UML_TEST_POSTGRES_URL`` (default: the local semantic-toolkit staging database)
  and is skipped when that database cannot be reached. It writes into a fresh schema
  named ``<CRUNCH_UML_TEST_POSTGRES_SCHEMA_PREFIX>qea_fk_<random>`` and removes its rows
  afterwards. The database is never created or dropped (no ``-db_create``).
"""

import os
import sqlite3
import uuid

import pytest
import sqlalchemy as sa

import crunch_uml.db as db
from crunch_uml import cli, const

DATA = os.path.join("test", "data")
GGM240_QEA = os.path.join(DATA, "Gemeentelijk Gegevensmodel 2.4.0.qea")
GGM251_QEA = os.path.join(DATA, "Gemeentelijk Gegevensmodel v2.5.1.qea")
POSTGRES_URL = os.environ.get(
    "CRUNCH_UML_TEST_POSTGRES_URL", "postgresql://crunch_writer:crunch_writer_dev@localhost:5432/crunch_staging"
)
SCHEMA_PREFIX = os.environ.get("CRUNCH_UML_TEST_POSTGRES_SCHEMA_PREFIX", "pytest_")

# Association ends on an Enumeration in GGM 2.5.1: (association, enumeration).
GGM251_ENUM_ENDS = {
    ("EAID_133EB5E3_4BBC_4bf7_8462_98F9532803A0", "EAID_6C1FC62B_EE66_4c73_BDBF_A59114A3806A"),  # heeft → gebruiksdoel
    ("EAID_266F9975_CC9F_4d21_BDDF_20EC737CF568", "EAID_356C8F59_3721_46d0_BCD0_C17B0130035C"),  # soort → Heffingsoort
    ("EAID_3F138B95_B799_496c_8B92_7BAD804EBAAC", "EAID_D2F0A41E_E49A_4d27_B0A2_DEF81C612A5B"),  # is van soort
}

# Every table with rows per schema, children before parents.
SCHEMA_TABLES = (
    "diagram_association",
    "diagram_class",
    "diagram_enumeration",
    "diagram_generalization",
    "diagrams",
    "attributes",
    "enumerationliterals",
    "associations",
    "generalizations",
    "classes",
    "enumerations",
    "packages",
    "crunch_uml_runs",
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


def _import(db_url, source, schema, create):
    args = ["-db_url", db_url, "-sch", schema, "import", "-f", source, "-t", "qea"]
    if create:
        args.append("-db_create")
    _dispose_singleton()
    try:
        return cli.main(args)
    finally:
        _dispose_singleton()


@pytest.mark.parametrize(
    "source",
    [
        os.path.join(DATA, "MiniM4.qea"),
        os.path.join(DATA, "Monumenten.qea"),
        os.path.join(DATA, "MonumentenMIM.qea"),
        os.path.join(DATA, "InkomenMIM.qea"),
        os.path.join(DATA, "TestProject.qea"),
        # RSGBPlus has one association to an enumeration.
        os.path.join(DATA, "RSGBPlus.qea"),
        pytest.param(GGM240_QEA, marks=pytest.mark.slow),
        pytest.param(GGM251_QEA, marks=pytest.mark.slow),
    ],
    ids=lambda path: os.path.splitext(os.path.basename(path))[0],
)
def test_qea_import_heeft_geen_verweesde_verwijzingen(tmp_path, source):
    if not os.path.exists(source):
        pytest.skip(f"{source} not available")
    path = tmp_path / "integriteit.db"
    assert _import(f"sqlite:///{path}", source, "default", create=True) == 0
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        assert con.execute("PRAGMA foreign_key_check").fetchall() == []
        # A placeholder shares its id with an enumeration and is never a class of the model itself.
        placeholders = {r[0] for r in con.execute("SELECT id FROM classes WHERE name = ?", (const.ORPHAN_CLASS,))}
        enumerations = {r[0] for r in con.execute("SELECT id FROM enumerations")}
        assert placeholders <= enumerations
    finally:
        con.close()


@pytest.fixture
def postgres_schema():
    try:
        engine = sa.create_engine(POSTGRES_URL)
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
    except Exception as ex:  # driver missing, server down, wrong credentials
        pytest.skip(f"Postgres not reachable at {POSTGRES_URL.split('@')[-1]}: {type(ex).__name__}")
    schema = f"{SCHEMA_PREFIX}qea_fk_{uuid.uuid4().hex[:8]}"
    yield engine, schema
    _dispose_singleton()
    with engine.begin() as conn:
        existing = set(sa.inspect(conn).get_table_names())
        conn.execute(sa.text("SET CONSTRAINTS ALL DEFERRED"))
        for table in SCHEMA_TABLES:
            if table in existing:
                delete = f"DELETE FROM {table} WHERE schema_id = :schema"  # noqa: S608 - table from SCHEMA_TABLES
                conn.execute(sa.text(delete), {"schema": schema})
    engine.dispose()


@pytest.mark.slow
def test_ggm251_qea_importeert_in_postgres(postgres_schema):
    """Postgres checks every foreign key while the rows are written: the import only
    succeeds when no association or generalization ends outside ``classes``."""
    if not os.path.exists(GGM251_QEA):
        pytest.skip("GGM 2.5.1 repository not available")
    engine, schema = postgres_schema
    assert _import(POSTGRES_URL, GGM251_QEA, schema, create=False) == 0

    with engine.connect() as conn:

        def scalar(sql):
            return conn.execute(sa.text(sql), {"schema": schema}).scalar()

        assert scalar("SELECT COUNT(*) FROM crunch_uml_runs WHERE schema_id = :schema AND completed_at IS NULL") == 0
        assert scalar("SELECT COUNT(*) FROM crunch_uml_runs WHERE schema_id = :schema") == 1
        assert scalar("SELECT COUNT(*) FROM packages WHERE schema_id = :schema AND stereotype = 'Domein'") == 60
        assert scalar("SELECT COUNT(*) FROM associations WHERE schema_id = :schema") == 1109
        assert scalar("SELECT COUNT(*) FROM classes WHERE schema_id = :schema") == 1014
        ends = {
            (r[0], r[1])
            for r in conn.execute(
                sa.text(
                    "SELECT a.id, c.id FROM associations a JOIN classes c"
                    " ON c.schema_id = a.schema_id AND c.id IN (a.src_class_id, a.dst_class_id)"
                    " WHERE a.schema_id = :schema AND c.name = :orphan"
                ),
                {"schema": schema, "orphan": const.ORPHAN_CLASS},
            )
        }
        assert ends == GGM251_ENUM_ENDS
        # The enumerations keep their tagged values; the placeholders with the same ids carry none.
        enum_ids = {"ids": [enum_id for _, enum_id in GGM251_ENUM_ENDS], "schema": schema}
        exported = conn.execute(
            sa.text("SELECT datum_tijd_export FROM enumerations WHERE schema_id = :schema AND id = ANY(:ids)"), enum_ids
        )
        assert [r[0] for r in exported] == ["28062023-11:06:06"] * 3
        placeholder_tags = conn.execute(
            sa.text("SELECT datum_tijd_export FROM classes WHERE schema_id = :schema AND id = ANY(:ids)"), enum_ids
        )
        assert [r[0] for r in placeholder_tags] == [None] * 3
