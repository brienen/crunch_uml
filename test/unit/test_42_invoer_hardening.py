"""Hardening for untrusted input (0.7.0).

* ``translators`` is imported lazily: it contacts the network on import, which
  made even ``crunch_uml -h`` fail offline without ``translators_default_region``.
* EA-XMI goes through one hardened lxml parser: no entity expansion, no network,
  no DOCTYPE, no silent recovery from broken XML.
* chardet never reads more than 64 KiB.
* A .qea is opened read-only and immutable.
* The "table started empty" fast path is decided per schema, so a second schema
  in a shared database is not slower than the first.
"""

import hashlib
import os
import shutil
import sqlite3
import stat
import subprocess
import sys

import pytest
from lxml import etree
from sqlalchemy import event

import crunch_uml.db as db
from crunch_uml import cli, xmlsafe
from crunch_uml.parsers import xmiparser
from crunch_uml.parsers.xmiparser import load_xmi

MINI_QEA = "./test/data/MiniM4.qea"
MINI_XMI = "./test/data/MiniM4.xml"


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


def _clean_env():
    env = {key: value for key, value in os.environ.items() if key != "translators_default_region"}
    env["PYTHONPATH"] = os.getcwd()
    return env


# --------------------------------------------------------------------------
# translators
# --------------------------------------------------------------------------


def test_help_importeert_translators_niet():
    """`crunch_uml -h` works without translators_default_region and never imports
    translators (whose import needs the network)."""
    script = (
        "import sys\n"
        "from crunch_uml import cli\n"
        "try:\n"
        "    cli.main(['-h'])\n"
        "except SystemExit as exit_:\n"
        "    code = exit_.code\n"
        "else:\n"
        "    code = 0\n"
        "print('TRANSLATORS_LOADED=' + str('translators' in sys.modules))\n"
        "sys.exit(code)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], env=_clean_env(), capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
    assert "TRANSLATORS_LOADED=False" in result.stdout


# --------------------------------------------------------------------------
# XML
# --------------------------------------------------------------------------

BILLION_LAUGHS = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
]>
<xmi:XMI xmlns:xmi="http://schema.omg.org/spec/XMI/2.1" xmi:version="2.1"><a>&lol3;</a></xmi:XMI>
"""

EXTERNAL_ENTITY = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<xmi:XMI xmlns:xmi="http://schema.omg.org/spec/XMI/2.1" xmi:version="2.1"><a>&xxe;</a></xmi:XMI>
"""


@pytest.mark.parametrize("content", [BILLION_LAUGHS, EXTERNAL_ENTITY], ids=["billion-laughs", "external-entity"])
def test_doctype_wordt_geweigerd(tmp_path, content):
    path = tmp_path / "evil.xml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(xmlsafe.XMLForbiddenError):
        load_xmi(str(path))


def test_doctype_achter_lang_commentaar_wordt_ook_geweigerd(tmp_path):
    """The prolog scan reads 64 KiB; a DOCTYPE behind a longer comment is caught
    on the parsed tree - and its entities are never expanded."""
    comment = "<!--" + "x" * (xmlsafe.SNIFF_BYTES + 1000) + "-->\n"
    content = BILLION_LAUGHS.replace("<!DOCTYPE", comment + "<!DOCTYPE", 1)
    path = tmp_path / "evil_late.xml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(xmlsafe.XMLForbiddenError):
        load_xmi(str(path))


def test_import_met_doctype_faalt_zonder_iets_op_te_slaan(tmp_path):
    source = tmp_path / "evil.xml"
    source.write_text(EXTERNAL_ENTITY, encoding="utf-8")
    database = tmp_path / "evil.db"
    rc = cli.main(["-db_url", f"sqlite:///{database}", "import", "-f", str(source), "-t", "eaxmi", "-db_create"])
    assert rc == 1


def test_afgekapte_xml_wordt_niet_stil_hersteld(tmp_path):
    """recover=False: a truncated export fails loudly instead of importing half a model."""
    with open(MINI_XMI, "rb") as f:
        data = f.read()
    path = tmp_path / "truncated.xml"
    path.write_bytes(data[: len(data) // 2])
    with pytest.raises(etree.XMLSyntaxError):
        load_xmi(str(path))


def test_parser_opties_zijn_gehard():
    parser = xmlsafe.make_parser()
    root = etree.fromstring(
        b'<!DOCTYPE a [<!ENTITY e "expanded">]><a>&e;</a>',
        parser,
    )
    # The entity reference is kept as a reference, never expanded.
    assert "expanded" not in etree.tostring(root).decode()
    assert xmlsafe.SAFE_PARSER_OPTIONS["resolve_entities"] is False
    assert xmlsafe.SAFE_PARSER_OPTIONS["no_network"] is True
    assert xmlsafe.SAFE_PARSER_OPTIONS["huge_tree"] is False


def test_chardet_leest_hooguit_64_kib(tmp_path, monkeypatch):
    """Without an encoding in the XML declaration, detection looks at the head only
    (0.6.0 ran chardet over the whole file: +28 s on a GGM)."""
    calls = []
    original = xmiparser.chardet.detect

    def counting_detect(raw):
        calls.append(len(raw))
        return original(raw)

    monkeypatch.setattr(xmiparser.chardet, "detect", counting_detect)
    body = "".join(f'<e n="{i}">waarde {i}</e>' for i in range(20000))
    path = tmp_path / "geen_encoding.xml"
    path.write_text(f'<?xml version="1.0"?>\n<model>{body}</model>', encoding="utf-8")
    assert os.path.getsize(path) > 4 * xmlsafe.SNIFF_BYTES

    root = load_xmi(str(path))

    assert len(root) == 20000
    assert calls and max(calls) <= xmlsafe.SNIFF_BYTES


# --------------------------------------------------------------------------
# QEA
# --------------------------------------------------------------------------


def _sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_qea_wordt_alleen_lezend_geopend(tmp_path):
    """The parser reads a .qea in a read-only directory without touching it:
    same bytes, no journal/WAL/SHM side files."""
    folder = tmp_path / "bron"
    folder.mkdir()
    source = folder / "model met spaties #1.qea"
    shutil.copyfile(MINI_QEA, source)
    before = _sha256(source)
    source.chmod(stat.S_IRUSR)
    folder.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        database = tmp_path / "doel.db"
        rc = cli.main(["-db_url", f"sqlite:///{database}", "import", "-f", str(source), "-t", "qea", "-db_create"])
        assert rc == 0
        assert sorted(os.listdir(folder)) == [source.name]
    finally:
        folder.chmod(stat.S_IRWXU)
        source.chmod(stat.S_IRUSR | stat.S_IWUSR)
    assert _sha256(source) == before
    con = sqlite3.connect(database)
    try:
        # Four classes, one datatype and the placeholder for the enumeration at an association end.
        assert con.execute("SELECT COUNT(*) FROM classes").fetchone()[0] == 6
    finally:
        con.close()


# --------------------------------------------------------------------------
# Shared database: fast path per schema
# --------------------------------------------------------------------------


def _import_counting_statements(database, schema):
    """Import MiniM4.qea into ``schema`` in a fresh process-like Database instance
    and return the number of SQL statements sent to the target database."""
    _dispose_singleton()
    url = f"sqlite:///{database}"
    instance = db.Database(url, db_create=False)
    statements = []

    @event.listens_for(instance.engine, "before_cursor_execute")
    def count(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    try:
        rc = cli.main(["-db_url", url, "-sch", schema, "import", "-f", MINI_QEA, "-t", "qea"])
    finally:
        event.remove(instance.engine, "before_cursor_execute", count)
        _dispose_singleton()
    assert rc == 0
    return len(statements)


def test_tweede_schema_in_dezelfde_database_blijft_op_het_snelle_pad(tmp_path):
    database = tmp_path / "gedeeld.db"
    first = _import_counting_statements(database, "eerste")
    second = _import_counting_statements(database, "tweede")
    # 0.6.0: the second schema fell back to merge() (a SELECT per row) and sent
    # several times as many statements. Allow a little slack for the extra
    # per-schema emptiness probes.
    assert second <= first + 20, (first, second)

    con = sqlite3.connect(database)
    try:
        counts = dict(con.execute("SELECT schema_id, COUNT(*) FROM attributes GROUP BY schema_id").fetchall())
    finally:
        con.close()
    assert counts == {"eerste": 6, "tweede": 6}
