import json
import sqlite3

import pytest
from sqlalchemy import select

import crunch_uml.db as db
from crunch_uml import cli, const
from crunch_uml.db import DATAMODEL_VERSION, DATAMODEL_VERSION_KEY, crunch_runs_table

MONUMENTEN = "./test/data/GGM_Monumenten_EA2.1.xml"


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


@pytest.fixture(autouse=True)
def _reset_database_singleton():
    """The Database singleton survives across tests (export-only CLI runs
    never close it, and a failed construction leaves engine+session behind).
    Dispose BEFORE each test — so a stale instance from another test file
    can't hijack our -db_url — and after, so we leave no stale one behind."""
    _dispose_singleton()
    yield
    _dispose_singleton()


def _sqlite_path(tmp_path, name):
    return tmp_path / name


def _db_url(path):
    return f"sqlite:///{path}"


def _fetch_runs(path):
    con = sqlite3.connect(path)
    try:
        rows = con.execute(
            "SELECT run_id, schema_id, started_at, completed_at, crunch_version, datamodel_version"
            " FROM crunch_uml_runs ORDER BY started_at"
        ).fetchall()
    finally:
        con.close()
    return rows


def _tamper_datamodel_version(path, value="999"):
    con = sqlite3.connect(path)
    try:
        con.execute(
            "UPDATE crunch_uml_meta SET value = ? WHERE key = ?",
            (value, DATAMODEL_VERSION_KEY),
        )
        con.commit()
    finally:
        con.close()


def _read_version(path):
    con = sqlite3.connect(path)
    try:
        row = con.execute("SELECT value FROM crunch_uml_meta WHERE key = ?", (DATAMODEL_VERSION_KEY,)).fetchone()
    finally:
        con.close()
    return row[0] if row else None


def _count_classes(path):
    con = sqlite3.connect(path)
    try:
        return con.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
    finally:
        con.close()


def test_marker_completed_after_successful_import(tmp_path):
    path = _sqlite_path(tmp_path, "marker.db")
    rc = cli.main(["-db_url", _db_url(path), "import", "-f", MONUMENTEN, "-t", "eaxmi", "-db_create"])
    assert rc == 0

    runs = _fetch_runs(path)
    assert len(runs) == 1
    run_id, schema_id, started_at, completed_at, crunch_version, datamodel_version = runs[0]
    assert schema_id == const.DEFAULT_SCHEMA
    assert started_at is not None
    assert completed_at is not None, "completion marker must be stamped after a successful import"
    assert completed_at >= started_at
    assert datamodel_version == str(DATAMODEL_VERSION)


def test_marker_stays_incomplete_on_aborted_import(tmp_path):
    path = _sqlite_path(tmp_path, "aborted.db")
    broken = tmp_path / "broken.json"
    broken.write_text("{ this is not valid json", encoding="utf-8")

    rc = cli.main(["-db_url", _db_url(path), "import", "-f", str(broken), "-t", "json", "-db_create"])
    assert rc == 1

    runs = _fetch_runs(path)
    assert len(runs) == 1
    assert runs[0][3] is None, "aborted import must leave completed_at NULL (torn run)"


def test_runs_table_never_leaks_into_exports(tmp_path):
    path = _sqlite_path(tmp_path, "leak.db")
    out = tmp_path / "export.json"
    rc = cli.main(["-db_url", _db_url(path), "import", "-f", MONUMENTEN, "-t", "eaxmi", "-db_create"])
    assert rc == 0
    rc = cli.main(["-db_url", _db_url(path), "export", "-t", "json", "-f", str(out)])
    assert rc == 0
    exported = json.loads(out.read_text(encoding="utf-8"))
    assert "crunch_uml_runs" not in exported
    assert "crunch_uml_meta" not in exported


def test_version_mismatch_on_explicit_db_url_fails_without_dropping(tmp_path):
    path = _sqlite_path(tmp_path, "staging.db")
    rc = cli.main(["-db_url", _db_url(path), "import", "-f", MONUMENTEN, "-t", "eaxmi", "-db_create"])
    assert rc == 0
    classes_before = _count_classes(path)
    assert classes_before > 0
    _tamper_datamodel_version(path)

    # No -db_create, no policy flag: 'auto' on an explicit db_url must FAIL
    # fast and leave the database untouched (council condition 2).
    rc = cli.main(["-db_url", _db_url(path), "import", "-f", MONUMENTEN, "-t", "eaxmi"])
    assert rc == 1
    assert _read_version(path) == "999", "version marker must not be rewritten on refusal"
    assert _count_classes(path) == classes_before, "no data may be dropped on refusal"


def test_version_mismatch_recreate_flag_rebuilds_and_clears_stale_runs(tmp_path):
    path = _sqlite_path(tmp_path, "rebuild.db")
    rc = cli.main(["-db_url", _db_url(path), "import", "-f", MONUMENTEN, "-t", "eaxmi", "-db_create"])
    assert rc == 0
    assert len(_fetch_runs(path)) == 1
    _tamper_datamodel_version(path)

    rc = cli.main(
        ["-db_url", _db_url(path), "-on_version_mismatch", "recreate", "import", "-f", MONUMENTEN, "-t", "eaxmi"]
    )
    assert rc == 0
    assert _read_version(path) == str(DATAMODEL_VERSION)
    runs = _fetch_runs(path)
    assert len(runs) == 1, "recreate must clear stale run markers (their data is gone)"
    assert runs[0][3] is not None


def test_version_mismatch_on_default_db_still_recreates(tmp_path):
    # Backwards compatibility: the local default database keeps the historical
    # recreate behaviour under 'auto'. conftest patches const.DATABASE_URL to
    # a sqlite file, so cli.main without -db_url hits the "default" branch.
    default_path = const.DATABASE_URL.replace("sqlite:///", "")
    rc = cli.main(["import", "-f", MONUMENTEN, "-t", "eaxmi", "-db_create"])
    assert rc == 0
    _tamper_datamodel_version(default_path)

    rc = cli.main(["import", "-f", MONUMENTEN, "-t", "eaxmi"])
    assert rc == 0, "default database must recreate on mismatch (historical behaviour)"
    assert _read_version(default_path) == str(DATAMODEL_VERSION)


def test_start_and_complete_run_via_database_api(tmp_path):
    path = _sqlite_path(tmp_path, "api.db")
    database = db.Database(_db_url(path), db_create=True)
    try:
        run_id = database.start_import_run("myschema")
        assert run_id is not None
        with database.engine.connect() as connection:
            row = connection.execute(
                select(crunch_runs_table.c.completed_at).where(crunch_runs_table.c.run_id == run_id)
            ).first()
        assert row is not None and row[0] is None

        database.complete_import_run(run_id)
        with database.engine.connect() as connection:
            row = connection.execute(
                select(crunch_runs_table.c.completed_at).where(crunch_runs_table.c.run_id == run_id)
            ).first()
        assert row is not None and row[0] is not None
    finally:
        database.close()
