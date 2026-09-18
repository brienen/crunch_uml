"""Hardening for untrusted input (0.7.0).

* ``translators`` is imported lazily: it contacts the network on import, which
  made even ``crunch_uml -h`` fail offline without ``translators_default_region``.
* EA-XMI goes through one hardened lxml parser: no entity expansion, no network,
  no DOCTYPE, no silent recovery from broken XML. The DOCTYPE is refused on the
  bytes, before libxml2 sees them, so the error class does not depend on the
  libxml2 build.
* chardet never reads more than 64 KiB.
* A .qea is opened read-only and immutable.
* The "table started empty" fast path is decided per schema, so a second schema
  in a shared database is not slower than the first.
"""

import hashlib
import json
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
from crunch_uml import cli, detect, pack, xmlsafe
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


ENTITY_LOOP = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE lolz [
  <!ENTITY a "&b;">
  <!ENTITY b "&a;">
]>
<xmi:XMI xmlns:xmi="http://schema.omg.org/spec/XMI/2.1" xmi:version="2.1"><x>&a;</x></xmi:XMI>
"""

BARE_ENTITY = """<?xml version="1.0" encoding="UTF-8"?>
<!ENTITY xxe SYSTEM "file:///etc/passwd">
<xmi:XMI xmlns:xmi="http://schema.omg.org/spec/XMI/2.1" xmi:version="2.1"><a/></xmi:XMI>
"""


def _behind_long_comment(content):
    """The same document with a comment longer than the sniff window in front of it."""
    comment = "<!--" + "x" * (xmlsafe.SNIFF_BYTES + 1000) + "-->\n"
    declaration = "<!DOCTYPE" if "<!DOCTYPE" in content else "<!ENTITY"
    return content.replace(declaration, comment + declaration, 1)


@pytest.mark.parametrize(
    "content",
    [BILLION_LAUGHS, EXTERNAL_ENTITY, ENTITY_LOOP, BARE_ENTITY],
    ids=["billion-laughs", "external-entity", "entity-loop", "bare-entity"],
)
def test_doctype_achter_lang_commentaar_wordt_ook_geweigerd(tmp_path, content):
    """A DOCTYPE behind a comment longer than the sniff window is still a DOCTYPE.

    It used to be caught on the parsed tree, which made the error class depend on
    the libxml2 build: a recursive entity in the internal subset is refused by
    libxml2 itself ("Detected an entity reference loop") and the tree to inspect
    never exists. The walk over the prolog answers before the parser runs.
    """
    path = tmp_path / "evil_late.xml"
    path.write_text(_behind_long_comment(content), encoding="utf-8")
    with pytest.raises(xmlsafe.XMLForbiddenError):
        load_xmi(str(path))


def test_doctype_na_een_bom_wordt_geweigerd(tmp_path):
    path = tmp_path / "bom.xml"
    path.write_bytes(b"\xef\xbb\xbf" + EXTERNAL_ENTITY.encode("utf-8"))
    with pytest.raises(xmlsafe.XMLForbiddenError):
        load_xmi(str(path))


@pytest.mark.parametrize("encoding", ["utf-16", "utf-16-le", "utf-32"])
def test_doctype_in_utf16_of_utf32_wordt_geweigerd(tmp_path, encoding):
    """`detect` refuses these on the byte-order mark; should one reach the parser
    anyway, the walk sees the declaration in the decoded text."""
    path = tmp_path / f"{encoding}.xml"
    path.write_bytes(EXTERNAL_ENTITY.replace("UTF-8", encoding).encode(encoding))
    with pytest.raises(xmlsafe.XMLForbiddenError):
        load_xmi(str(path))


DOCTYPE_AS_CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
<!-- an export may describe what it refuses: <!DOCTYPE x [<!ENTITY e "e">]> -->
<xmi:XMI xmlns:xmi="http://schema.omg.org/spec/XMI/2.1" xmi:version="2.1">
  <!-- <!DOCTYPE inside a comment in the document -->
  <a><![CDATA[<!DOCTYPE x [<!ENTITY e "e">]>]]></a>
</xmi:XMI>
"""


def test_doctype_tekst_in_het_document_is_geen_doctype(tmp_path):
    """Only a declaration before the root element counts; the words in a comment or
    a CDATA section do not. The blanket search over the head refused this."""
    path = tmp_path / "praat_erover.xml"
    path.write_text(DOCTYPE_AS_CONTENT, encoding="utf-8")
    root = load_xmi(str(path))
    assert root.find("a").text == '<!DOCTYPE x [<!ENTITY e "e">]>'
    assert detect.detect(str(path))["verdict"] != "xml-doctype"


def test_onbekende_entiteit_zonder_doctype_blijft_malformed(tmp_path):
    """The net under the walk catches DTD constructs only: an undefined entity in a
    document without a DOCTYPE stays broken XML, not forbidden XML."""
    path = tmp_path / "losse_entiteit.xml"
    path.write_text('<?xml version="1.0"?>\n<a>&nbsp;</a>\n', encoding="utf-8")
    with pytest.raises(etree.XMLSyntaxError):
        load_xmi(str(path))


@pytest.mark.parametrize(
    "content",
    [BILLION_LAUGHS, EXTERNAL_ENTITY, ENTITY_LOOP, _behind_long_comment(ENTITY_LOOP)],
    ids=["billion-laughs", "external-entity", "entity-loop", "entity-loop-behind-comment"],
)
def test_pack_en_detect_weigeren_met_xml_forbidden(tmp_path, content):
    """One code for the whole family, on every libxml2: the toolkit runner turns
    `xml_forbidden` and `xml_malformed` into different messages for the user."""
    source = tmp_path / "evil.xml"
    source.write_text(content, encoding="utf-8")
    assert detect.detect(str(source))["code"] == detect.CODE_XML_FORBIDDEN
    exit_code, result = pack.pack(str(source), str(tmp_path / "x.cua.gz"))
    assert (exit_code, result["code"]) == (2, detect.CODE_XML_FORBIDDEN)


def test_pack_geeft_een_json_regel_met_xml_forbidden(tmp_path):
    source = tmp_path / "evil.xml"
    source.write_text(_behind_long_comment(ENTITY_LOOP), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "crunch_uml.cli", "pack", "-f", str(source), "-o", str(tmp_path / "x.cua.gz")],
        env=_clean_env(),
        capture_output=True,
        text=True,
        timeout=120,
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert result.returncode == 2, result.stderr
    assert len(lines) == 1
    assert json.loads(lines[0])["code"] == detect.CODE_XML_FORBIDDEN


@pytest.mark.parametrize(
    "data, verdict",
    [
        ('<?xml version="1.0"?><a/>', xmlsafe.PROLOG_CLEAN),
        ("\ufeff<!DOCTYPE a><a/>", xmlsafe.PROLOG_DOCTYPE),
        ("<!-- <a/> --> <!DOCTYPE a><a/>", xmlsafe.PROLOG_DOCTYPE),
        ("<a><!DOCTYPE b></a>", xmlsafe.PROLOG_CLEAN),
        ("  <!-- never closed", xmlsafe.PROLOG_TRUNCATED),
        ("<?pi never closed", xmlsafe.PROLOG_TRUNCATED),
        ("   ", xmlsafe.PROLOG_TRUNCATED),
    ],
    ids=["clean", "bom-doctype", "comment-then-doctype", "doctype-in-root", "open-comment", "open-pi", "blank"],
)
def test_prolog_wandeling_stopt_bij_het_wortelelement(data, verdict):
    assert xmlsafe.scan_prolog(data) == verdict
    assert xmlsafe.scan_prolog(data.encode("utf-8")) == verdict


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
