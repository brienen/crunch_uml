"""`crunch_uml pack`: EA model file -> row artifact (.cua.gz).

The artifact is read back here with the standard library only, the way the
Semantic Toolkit reads it, and compared row for row with a normal crunch_uml
import of the same file.
"""

import gzip
import json
import os
import sqlite3
import subprocess
import sys

import pytest

import crunch_uml.db as db
from crunch_uml import cli, pack

DATA = "./test/data"
MINI_QEA = os.path.join(DATA, "MiniM4.qea")
MINI_XMI = os.path.join(DATA, "MiniM4.xml")
GGM251_DIR = "/Users/arjen/kDrive/Development/GemeentelijkGegevensmodel-v2.5.1/v2.5.1"
GGM251_XMI = os.path.join(GGM251_DIR, "Gemeentelijk Gegevensmodel XMI2.1.xml")
GGM251_QEA = os.path.join(GGM251_DIR, "Gemeentelijk Gegevensmodel.qea")

HEADER_KEYS = ["format", "format_version", "datamodel_version", "producer", "source", "capabilities", "run", "tables"]


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
    _dispose_singleton()
    yield
    _dispose_singleton()


def _reject_constant(name):
    raise ValueError(f"non-finite number {name} in artifact")


def read_artifact(path):
    with gzip.open(path, "rb") as f:
        raw = f.read()
    return json.loads(raw, parse_constant=_reject_constant), raw


def parse_to_sqlite(path, source, parser):
    _dispose_singleton()
    try:
        assert cli.main(["-db_url", f"sqlite:///{path}", "import", "-f", source, "-t", parser, "-db_create"]) == 0
    finally:
        _dispose_singleton()


@pytest.fixture(scope="module", params=[("qea", MINI_QEA), ("eaxmi", MINI_XMI)], ids=["qea", "eaxmi"])
def packed(request, tmp_path_factory):
    fmt, source = request.param
    base = tmp_path_factory.mktemp(f"pack_{fmt}")
    output = base / "mini.cua.gz"
    exit_code, result = pack.pack(source, str(output))
    assert exit_code == 0, result
    artifact, raw = read_artifact(output)
    return fmt, source, output, result, artifact, raw


def test_kop_heeft_de_afgesproken_vorm(packed):
    fmt, source, output, result, artifact, raw = packed
    assert list(artifact.keys()) == HEADER_KEYS
    assert raw.startswith(b'{"format":"semtk-crunch-artifact"')
    assert artifact["format"] == "semtk-crunch-artifact"
    assert artifact["format_version"] == 1
    assert artifact["datamodel_version"] == db.DATAMODEL_VERSION == 1
    assert artifact["producer"]["crunch_version"] == "0.7.0"
    assert artifact["producer"]["producer_build"]
    assert set(artifact["source"]) == {
        "detected_format",
        "exporter",
        "exporter_version",
        "xmi_version",
        "sha256",
        "size",
    }
    assert artifact["source"]["detected_format"] == fmt
    assert artifact["source"]["size"] == os.path.getsize(source)
    assert artifact["capabilities"] == {"geometry": True, "tags": True, "stereotypes": True}
    assert artifact["run"]["run_id"] and artifact["run"]["started_at"] and artifact["run"]["completed_at"]
    assert result["counts"] == {name: len(table["rows"]) for name, table in artifact["tables"].items()}


def test_geen_bestandsnaam_in_het_artefact(packed):
    _, source, output, _, artifact, raw = packed
    assert "filename" not in artifact["source"]
    assert os.path.basename(source).encode() not in raw
    assert b"MiniM4.qea" not in raw and b"MiniM4.xml" not in raw
    with open(output, "rb") as f:
        gzip_header = f.read(10)
    assert gzip_header[3] & 0x08 == 0, "gzip header must not carry a file name"


def test_alle_modeltabellen_en_geen_metatabellen(packed):
    *_, artifact, _ = packed
    assert set(artifact["tables"]) == set(db.getTables())
    assert not {"crunch_uml_meta", "crunch_uml_runs"} & set(artifact["tables"])


def test_rijen_gelijk_aan_een_gewone_import(packed, tmp_path):
    fmt, source, _, _, artifact, _ = packed
    sqlite_path = tmp_path / "direct.db"
    parse_to_sqlite(sqlite_path, source, fmt)
    con = sqlite3.connect(sqlite_path)
    try:
        for name, table in artifact["tables"].items():
            info = con.execute(f'PRAGMA table_info("{name}")').fetchall()
            assert table["columns"] == [row[1] for row in info], name
            booleans = [(row[2] or "").upper() == "BOOLEAN" for row in info]
            expected = [
                [bool(v) if (is_bool and v is not None) else v for v, is_bool in zip(row, booleans)]
                for row in con.execute(f'SELECT * FROM "{name}"')
            ]
            assert len(table["rows"]) == len(expected), name
            assert sorted(map(json.dumps, table["rows"])) == sorted(map(json.dumps, expected)), name
    finally:
        con.close()


def test_rijen_gesorteerd_op_primaire_sleutel(packed):
    *_, artifact, _ = packed
    for name, table in artifact["tables"].items():
        mapped = db.Base.metadata.tables[name]
        key_columns = [column.name for column in mapped.primary_key.columns]
        positions = [table["columns"].index(column) for column in key_columns]
        keys = [tuple((row[p] or "").encode("utf-8") for p in positions) for row in table["rows"]]
        assert keys == sorted(keys), name


def test_booleans_zijn_json_booleans(packed):
    *_, artifact, _ = packed
    classes = artifact["tables"]["classes"]
    column = classes["columns"].index("is_datatype")
    assert {row[column] for row in classes["rows"]} == {True, False}
    diagrams = artifact["tables"]["diagrams"]
    hide = diagrams["columns"].index("hide_attributes")
    assert {row[hide] for row in diagrams["rows"]} == {True, False}


def test_pack_raakt_de_database_van_het_proces_niet(tmp_path):
    own = tmp_path / "eigen.db"
    instance = db.Database(f"sqlite:///{own}", db_create=True)
    exit_code, _ = pack.pack(MINI_QEA, str(tmp_path / "x.cua.gz"))
    assert exit_code == 0
    assert db.Database._instance is instance
    con = sqlite3.connect(own)
    try:
        assert con.execute("SELECT COUNT(*) FROM classes").fetchone()[0] == 0
    finally:
        con.close()


# --------------------------------------------------------------------------
# Refusals: exit code 2 with a code from the toolkit's message catalogue
# --------------------------------------------------------------------------

EMPTY_EA_XMI = """<?xml version='1.0' encoding='windows-1252' ?>
<xmi:XMI xmlns:xmi="http://schema.omg.org/spec/XMI/2.1" xmi:version="2.1" xmlns:uml="http://schema.omg.org/spec/UML/2.1">
\t<xmi:Documentation exporter="Enterprise Architect" exporterVersion="6.5" exporterID="1628"/>
\t<uml:Model xmi:type="uml:Model" name="EA_Model" visibility="public">
\t\t<packagedElement xmi:type="uml:Package" xmi:id="EAPK_LEEG" name="Leeg" visibility="public"/>
\t</uml:Model>
\t<xmi:Extension extender="Enterprise Architect" extenderID="6.5">
\t\t<elements/>
\t</xmi:Extension>
</xmi:XMI>
"""


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    return str(path)


def test_nul_klassen_geeft_model_empty(tmp_path):
    output = tmp_path / "leeg.cua.gz"
    exit_code, result = pack.pack(_write(tmp_path, "leeg.xml", EMPTY_EA_XMI), str(output))
    assert exit_code != 0
    assert result["code"] == "model_empty"
    assert not output.exists()


@pytest.mark.parametrize(
    "name, content, code",
    [
        ("tekst.txt", "gewoon tekst", "file_type_unknown"),
        (
            "doctype.xml",
            '<?xml version="1.0"?>\n<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]>\n<xmi:XMI/>',
            "xml_forbidden",
        ),
        (
            "magicdraw.xml",
            '<?xml version="1.0"?>\n<xmi:XMI xmlns:xmi="http://www.omg.org/spec/XMI/20131001">'
            "<xmi:exporter>MagicDraw UML</xmi:exporter></xmi:XMI>",
            "xmi_not_ea",
        ),
        ("afgekapt.xml", EMPTY_EA_XMI[: len(EMPTY_EA_XMI) // 2], "xml_malformed"),
    ],
)
def test_geweigerde_invoer(tmp_path, name, content, code):
    output = tmp_path / "x.cua.gz"
    exit_code, result = pack.pack(_write(tmp_path, name, content), str(output))
    assert exit_code == 2
    assert result == {"status": "error", "code": code, "message": result["message"]}
    assert not output.exists()


def test_verkeerd_verwacht_formaat(tmp_path):
    exit_code, result = pack.pack(MINI_XMI, str(tmp_path / "x.cua.gz"), inputtype="qea")
    assert (exit_code, result["code"]) == (2, "file_type_unknown")


def test_kapotte_xml_die_detectie_passeert_is_xml_malformed(tmp_path):
    """Well-formed head and tail, broken middle: the parser refuses it (no recover)."""
    with open(MINI_XMI, "rb") as f:
        data = f.read()
    broken = data.replace(b"<packagedElement", b"<packagedElement <<", 1)
    exit_code, result = pack.pack(_write(tmp_path, "kapot.xml", broken), str(tmp_path / "x.cua.gz"))
    assert (exit_code, result["code"]) == (2, "xml_malformed")


def test_cli_schrijft_een_json_regel_en_exitcode(tmp_path):
    env = dict(os.environ, PYTHONPATH=os.getcwd())
    output = tmp_path / "cli.cua.gz"
    ok = subprocess.run(
        [sys.executable, "-m", "crunch_uml.cli", "pack", "-f", MINI_QEA, "-t", "qea", "-o", str(output)],
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )
    assert ok.returncode == 0, ok.stderr
    lines = [line for line in ok.stdout.splitlines() if line.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["status"] == "ok"
    assert output.exists()

    refused = subprocess.run(
        [sys.executable, "-m", "crunch_uml.cli", "pack", "-f", _write(tmp_path, "t.txt", "x"), "-o", str(output)],
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )
    assert refused.returncode == 2
    assert json.loads(refused.stdout.strip())["code"] == "file_type_unknown"


# --------------------------------------------------------------------------
# The real thing (slow): GGM 2.5.1, outside the repository
# --------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.parametrize("source, fmt", [(GGM251_XMI, "eaxmi"), (GGM251_QEA, "qea")], ids=["xmi", "qea"])
def test_ggm251(tmp_path, source, fmt):
    if not os.path.exists(source):
        pytest.skip("GGM 2.5.1 source files not available")
    output = tmp_path / "ggm.cua.gz"
    exit_code, result = pack.pack(source, str(output), inputtype=fmt)
    assert exit_code == 0, result
    assert os.path.getsize(output) < 8 * 1024 * 1024
    artifact, raw = read_artifact(output)
    assert len(raw) < 32 * 1024 * 1024
    packages = artifact["tables"]["packages"]
    stereotype = packages["columns"].index("stereotype")
    assert sum(1 for row in packages["rows"] if row[stereotype] == "Domein") == 60
    for table in ("attributes", "enumerationliterals"):
        id_column = artifact["tables"][table]["columns"].index("id")
        assert all(row[id_column] for row in artifact["tables"][table]["rows"]), table


@pytest.mark.parametrize("module", ["crunch_uml/artifact.py", "crunch_uml/detect.py"])
def test_schrijver_en_detectie_gebruiken_alleen_de_standaardbibliotheek(module):
    """The artifact writer and the detector import nothing outside the standard library,
    so their rules can be mirrored by consumers that do not install crunch_uml."""
    import ast

    with open(module, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported, module
    assert imported <= set(sys.stdlib_module_names), imported - set(sys.stdlib_module_names)
