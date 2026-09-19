"""Writer of the crunch_uml row artifact (``.cua.gz``), standard library only.

The artifact carries the parsed model as rows, so a consumer can read it
without crunch_uml, SQLAlchemy or a database (the Semantic Toolkit reads it
with the standard library). It is gzip-compressed JSON of this exact shape::

    {
      "format": "semtk-crunch-artifact",
      "format_version": 1,
      "datamodel_version": 1,
      "producer": {"crunch_version": "0.7.0", "producer_build": "<git sha or 'pypi'>"},
      "source": {"detected_format": "qea", "exporter": ..., "exporter_version": ...,
                 "xmi_version": ..., "sha256": ..., "size": 123},
      "capabilities": {"geometry": true, "tags": true, "stereotypes": true},
      "run": {"run_id": ..., "started_at": ..., "completed_at": ...},
      "tables": {"<table>": {"columns": [...], "rows": [[...], ...]}}
    }

Rules: "format" is the first key (content sniffers rely on it); every model
table is present, with its columns in schema order and its rows sorted by
primary key (SQLite BINARY collation, i.e. byte order); BOOLEAN columns are
JSON booleans; NULL is null; NaN and Infinity never appear (they become null);
the source file name is never recorded (privacy); the gzip header carries no
file name and a zero timestamp.

The writer streams row by row, so memory stays flat for large models.
"""

import gzip
import json
import logging
import math
import os
import sqlite3
from urllib.parse import quote

logger = logging.getLogger()

ARTIFACT_FORMAT = "semtk-crunch-artifact"
FORMAT_VERSION = 1
EXCLUDED_TABLES = frozenset({"crunch_uml_meta", "crunch_uml_runs"})

_SEPARATORS = (",", ":")


class ArtifactError(Exception):
    """The SQLite database cannot be written as an artifact."""


def _dumps(value):
    return json.dumps(value, separators=_SEPARATORS, ensure_ascii=False, allow_nan=False)


def _table_layout(con, table):
    info = con.execute(f'PRAGMA table_info("{table}")').fetchall()
    if not info:
        raise ArtifactError(f"table '{table}' does not exist in the parsed database")
    columns = [row[1] for row in info]
    booleans = [(row[2] or "").upper() == "BOOLEAN" for row in info]
    primary_key = [row[1] for row in sorted((r for r in info if r[5]), key=lambda r: r[5])]
    return columns, booleans, primary_key or columns


class _Cleaner:
    """Converts SQLite values to JSON values and counts what had to be changed."""

    def __init__(self):
        self.non_finite = 0
        self.nul_chars = 0

    def value(self, value, is_boolean):
        if value is None:
            return None
        if is_boolean:
            return bool(value)
        if isinstance(value, float) and not math.isfinite(value):
            self.non_finite += 1
            return None
        if isinstance(value, str) and "\x00" in value:
            self.nul_chars += value.count("\x00")
            return value.replace("\x00", "")
        if isinstance(value, bytes):
            raise ArtifactError("binary column values are not supported in an artifact")
        return value


def _read_run(con):
    try:
        row = con.execute(
            "SELECT run_id, started_at, completed_at FROM crunch_uml_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
    except sqlite3.Error:
        row = None
    if row is None:
        raise ArtifactError("the parsed database has no import-run marker")
    return {"run_id": row[0], "started_at": row[1], "completed_at": row[2]}


def _read_datamodel_version(con):
    try:
        row = con.execute("SELECT value FROM crunch_uml_meta WHERE key = 'datamodel_version'").fetchone()
    except sqlite3.Error:
        row = None
    if row is None:
        raise ArtifactError("the parsed database has no datamodel version")
    return int(row[0])


def write_artifact(sqlite_path, output_path, tables, producer, source, capabilities):
    """Write the artifact for ``tables`` of the SQLite file ``sqlite_path`` to ``output_path``.

    ``tables`` are the model table names (crunch_uml_meta/crunch_uml_runs are
    never written). Returns ``{table: row_count}``.
    """
    uri = "file:" + quote(os.path.abspath(sqlite_path)) + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        header = {
            "format": ARTIFACT_FORMAT,
            "format_version": FORMAT_VERSION,
            "datamodel_version": _read_datamodel_version(con),
            "producer": producer,
            "source": source,
            "capabilities": capabilities,
            "run": _read_run(con),
        }
        counts = {}
        cleaner = _Cleaner()
        with open(output_path, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            gz.write((_dumps(header)[:-1] + ',"tables":{').encode("utf-8"))
            for index, table in enumerate(sorted(t for t in tables if t not in EXCLUDED_TABLES)):
                columns, booleans, primary_key = _table_layout(con, table)
                prefix = "," if index else ""
                gz.write(f'{prefix}{_dumps(table)}:{{"columns":{_dumps(columns)},"rows":['.encode("utf-8"))
                order = ", ".join(f'"{column}" COLLATE BINARY' for column in primary_key)
                count = 0
                for row in con.execute(f'SELECT * FROM "{table}" ORDER BY {order}'):
                    values = [cleaner.value(value, is_boolean) for value, is_boolean in zip(row, booleans)]
                    gz.write((("," if count else "") + _dumps(values)).encode("utf-8"))
                    count += 1
                gz.write(b"]}")
                counts[table] = count
            gz.write(b"}}")
    finally:
        con.close()
    if cleaner.non_finite:
        logger.warning(f"Artifact: {cleaner.non_finite} non-finite numbers written as null.")
    if cleaner.nul_chars:
        logger.warning(f"Artifact: removed {cleaner.nul_chars} NUL characters from text values.")
    return counts
