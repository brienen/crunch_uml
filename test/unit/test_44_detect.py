"""`crunch_uml detect`: classify a model file by content, reading at most 64 KiB.

The golden vector is test/data/detect_fixtures.tsv from the import study
(r2-formaten): the verdict per crunch_uml fixture of the reference detector.
The reference verdict names were Dutch free text; REFERENCE_VERDICTS maps them
onto the stable names of crunch_uml.detect.
"""

import gzip
import json
import os
import sqlite3
import struct
import subprocess
import sys

import pytest

from crunch_uml import detect

DATA = "./test/data"
GOLDEN = os.path.join(DATA, "detect_fixtures.tsv")
MINI_QEA = os.path.join(DATA, "MiniM4.qea")
MINI_XMI = os.path.join(DATA, "MiniM4.xml")

REFERENCE_VERDICTS = {
    "ea-xmi-2.1": "ea-xmi-2.1",
    "qea": "qea",
    "csv?": "csv",
    "xlsx": "xlsx",
    "rdf-xml": "rdf-xml",
    "ea-native-xml": "ea-native-xml",
    "json-anders": "json-other",
    "crunch-json": "crunch-json",
    "crunch-i18n-json": "crunch-i18n-json",
    "onbekend": "unknown",
    "xml-anders": "xml-other",
    "turtle+skos": "turtle",
}


def golden_rows():
    with open(GOLDEN, encoding="utf-8") as f:
        return [line.rstrip("\n").split("\t") for line in f if line.strip()]


@pytest.mark.parametrize("reference, details, name", golden_rows(), ids=lambda value: str(value)[:40])
def test_gouden_fixturelijst(reference, details, name):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        pytest.skip(f"fixture {name} not present")
    result = detect.detect(path)
    assert result["verdict"] == REFERENCE_VERDICTS[reference]
    assert result["accepted"] == (result["verdict"] in ("ea-xmi-2.1", "qea"))


def test_elk_verdict_heeft_een_formaat_en_code():
    for verdict, (fmt, code) in detect.VERDICTS.items():
        assert fmt in (detect.FORMAT_EAXMI, detect.FORMAT_QEA, detect.FORMAT_ARTIFACT, detect.FORMAT_UNKNOWN)
        assert (code is None) == (fmt != detect.FORMAT_UNKNOWN), verdict


# --------------------------------------------------------------------------
# Synthetic samples (as in r2-formaten/out/detect_samples.tsv, plus 0.7.0 rules)
# --------------------------------------------------------------------------

EA_XMI_HEAD = (
    "<?xml version='1.0' encoding='windows-1252' ?>\n"
    '<xmi:XMI xmlns:xmi="http://schema.omg.org/spec/XMI/2.1" xmi:version="2.1"'
    ' xmlns:uml="http://schema.omg.org/spec/UML/2.1">\n'
    '\t<xmi:Documentation exporter="Enterprise Architect" exporterVersion="6.5" exporterID="1628"/>\n'
    '\t<uml:Model xmi:type="uml:Model" name="EA_Model" visibility="public"/>\n'
)


def write(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    return str(path)


def make_sqlite(path, statements, wal=False):
    con = sqlite3.connect(path)
    if wal:
        con.execute("PRAGMA journal_mode=WAL")
    for statement in statements:
        con.execute(statement)
    con.commit()
    con.close()
    return str(path)


QEA_TABLE_DDL = [f"CREATE TABLE {table} (id INTEGER)" for table in sorted(detect.QEA_TABLES)]


SAMPLES = {
    "utf16.xml": (b"\xff\xfe" + "<?xml version='1.0'?><a/>".encode("utf-16-le"), "utf16-32-bom", None),
    "nul.bin": (b"abc\x00def", "nul-bytes", None),
    "doctype.xml": (
        '<?xml version="1.0"?>\n<!DOCTYPE x [<!ENTITY e "e">]>\n<xmi:XMI xmi:version="2.1"/>',
        "xml-doctype",
        "xml_forbidden",
    ),
    "fake.eapx": (b"\x00\x01\x00\x00Standard Jet DB\x00" + b"\x00" * 100, "jet-ace", "file_type_unknown"),
    "fake.feap": (
        b"\x01" + b"\x00" * 15 + struct.pack("<H", 4096) + struct.pack("<H", 0x800B) + b"\x00" * 100,
        "firebird",
        None,
    ),
    "xmi11.xml": (
        '<?xml version="1.0"?>\n<XMI xmi.version="1.1"><XMI.header><XMI.documentation>'
        "<XMI.exporter>Enterprise Architect</XMI.exporter></XMI.documentation></XMI.header></XMI>",
        "xmi-1.x",
        "xmi_not_ea",
    ),
    "magicdraw.xml": (
        '<?xml version="1.0" encoding="UTF-8"?>\n<xmi:XMI xmlns:xmi="http://www.omg.org/spec/XMI/20131001"'
        ' xmlns:uml="http://www.omg.org/spec/UML/20131001"><xmi:Documentation>'
        "<xmi:exporter>MagicDraw UML</xmi:exporter></xmi:Documentation></xmi:XMI>",
        "xmi-other-tool",
        "xmi_not_ea",
    ),
    "papyrus.uml": (
        '<?xml version="1.0" encoding="UTF-8"?>\n<uml:Model xmi:version="20131001"'
        ' xmlns:xmi="http://www.omg.org/spec/XMI/20131001" xmlns:uml="http://www.eclipse.org/uml2/5.0.0/UML"/>',
        "eclipse-uml2",
        "xmi_not_ea",
    ),
    "linkml.yaml": ("id: https://example.org/x\nname: x\nclasses:\n  A: {}\n", "linkml-yaml", None),
    "ea_truncated.xml": (EA_XMI_HEAD + "\t<xmi:Extension extender=", "xml-truncated", "xml_malformed"),
    "ea_no_extension.xml": (EA_XMI_HEAD + "</xmi:XMI>\n", "ea-xmi-no-extension", "xmi_not_ea"),
    "ea_xmi_241.xml": (EA_XMI_HEAD.replace('xmi:version="2.1"', 'xmi:version="2.4.1"'), "ea-xmi-other-version", None),
    "gzip_other.gz": (gzip.compress(b'{"hello": "world"}'), "gzip-other", None),
    "empty.xml": (b"", "empty", "file_type_unknown"),
}


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_synthetische_voorbeelden(tmp_path, name):
    data, verdict, code = SAMPLES[name]
    result = detect.detect(write(tmp_path, name, data))
    assert result["verdict"] == verdict
    assert result["accepted"] is False
    if code:
        assert result["code"] == code


def test_ea_xmi_met_extensie_achteraan_groot_bestand(tmp_path):
    """The extension block sits at the end of a real export: detection reads the tail."""
    filler = "\t<!-- " + "x" * 200_000 + " -->\n"
    content = EA_XMI_HEAD + filler + '\t<xmi:Extension extender="Enterprise Architect" extenderID="6.5"/>\n</xmi:XMI>\n'
    result = detect.detect(write(tmp_path, "big.xml", content))
    assert result["verdict"] == "ea-xmi-2.1"
    assert result["format"] == "eaxmi"
    assert (result["exporter"], result["exporter_version"], result["xmi_version"]) == (
        "Enterprise Architect",
        "6.5",
        "2.1",
    )
    assert result["encoding"] == "windows-1252"


def test_qea_in_wal_modus_wordt_geweigerd(tmp_path):
    path = make_sqlite(tmp_path / "wal.qea", QEA_TABLE_DDL, wal=True)
    result = detect.detect(path)
    assert (result["verdict"], result["code"]) == ("qea-wal", "qea_unreadable")


@pytest.mark.parametrize(
    "extra",
    ["CREATE VIEW v AS SELECT 1", "CREATE TRIGGER t AFTER INSERT ON t_object BEGIN SELECT 1; END"],
    ids=["view", "trigger"],
)
def test_qea_met_view_of_trigger_wordt_geweigerd(tmp_path, extra):
    path = make_sqlite(tmp_path / "sneaky.qea", QEA_TABLE_DDL + [extra])
    result = detect.detect(path)
    assert (result["verdict"], result["code"]) == ("qea-views-triggers", "qea_unreadable")


def test_sqlite_zonder_ea_tabellen(tmp_path):
    path = make_sqlite(tmp_path / "other.qea", ["CREATE TABLE t_package (id INTEGER)"])
    assert detect.detect(path)["verdict"] == "sqlite-other"


def test_onleesbare_sqlite(tmp_path):
    path = write(tmp_path, "broken.qea", b"SQLite format 3\x00" + b"\x10\x00\x01\x01" + b"\xff" * 4000)
    result = detect.detect(path)
    assert result["verdict"] in ("sqlite-unreadable", "sqlite-other")
    assert result["accepted"] is False


def test_artefact_wordt_herkend(tmp_path):
    header = '{"format":"semtk-crunch-artifact","format_version":1,"datamodel_version":1,'
    header += '"producer":{"crunch_version":"0.7.0","producer_build":"pypi"},"tables":{}}'
    result = detect.detect(write(tmp_path, "x.cua.gz", gzip.compress(header.encode())))
    assert (result["verdict"], result["format"], result["accepted"]) == ("artifact", "artifact", True)
    assert (result["format_version"], result["datamodel_version"], result["crunch_version"]) == (1, 1, "0.7.0")


class CountingFile:
    """Wraps a file object so a test can see how much detection actually reads."""

    def __init__(self, f, reads):
        self._f = f
        self._reads = reads

    def read(self, n=-1):
        assert n != -1, "detect must never read a whole file"
        data = self._f.read(n)
        self._reads.append(len(data))
        return data

    def seek(self, *args):
        return self._f.seek(*args)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._f.close()


def count_reads(monkeypatch):
    """Patch ``detect.open`` to count every read; returns the list of read sizes."""
    reads = []
    real_open = open

    def counting_open(path, mode="r", *args, **kwargs):
        return CountingFile(real_open(path, mode, *args, **kwargs), reads)

    monkeypatch.setattr(detect, "open", counting_open, raising=False)
    return reads


def test_leest_hooguit_64_kib_kop_en_staart(tmp_path, monkeypatch):
    content = EA_XMI_HEAD + "<!--" + "y" * 5_000_000 + "-->\n<xmi:Extension/>\n</xmi:XMI>\n"
    path = write(tmp_path, "huge.xml", content)
    reads = count_reads(monkeypatch)
    result = detect.detect(path)
    assert result["verdict"] == "ea-xmi-2.1"
    # The prolog ends in the head (the comment sits inside the root element), so
    # the follow of a long prolog never starts.
    assert sum(reads) <= 2 * detect.SNIFF_BYTES


def _doctype_behind_comment(comment_size):
    comment = "<!--" + "y" * comment_size + "-->\n"
    doctype = "<!DOCTYPE x [<!ENTITY e SYSTEM 'file:///etc/passwd'>]>\n"
    return '<?xml version="1.0"?>\n' + comment + doctype + EA_XMI_HEAD + "<xmi:Extension/>\n</xmi:XMI>\n"


def test_doctype_achter_een_lang_commentaar_wordt_gezien(tmp_path, monkeypatch):
    """A prolog longer than the head is followed: a DOCTYPE hidden behind a comment
    that outruns the sniff window is still a DOCTYPE."""
    path = write(tmp_path, "laat.xml", _doctype_behind_comment(4 * detect.SNIFF_BYTES))
    reads = count_reads(monkeypatch)

    result = detect.detect(path)

    assert (result["verdict"], result["code"]) == ("xml-doctype", "xml_forbidden")
    assert sum(reads) <= 3 * detect.SNIFF_BYTES + detect.PROLOG_BYTES


def test_de_prologwandeling_leest_niet_eindeloos_door(tmp_path, monkeypatch):
    """Past PROLOG_BYTES detection stops following and says it cannot place the file;
    a refusal either way, and never a read of the whole document."""
    path = write(tmp_path, "eindeloos.xml", _doctype_behind_comment(2 * detect.PROLOG_BYTES))
    reads = count_reads(monkeypatch)

    result = detect.detect(path)

    assert (result["verdict"], result["code"]) == ("xml-unknown", "file_type_unknown")
    assert sum(reads) <= 3 * detect.SNIFF_BYTES + detect.PROLOG_BYTES


def test_cli_geeft_een_json_regel(tmp_path):
    env = dict(os.environ, PYTHONPATH=os.getcwd())
    for path, expected_rc, verdict in ((MINI_QEA, 0, "qea"), (MINI_XMI, 0, "ea-xmi-2.1")):
        result = subprocess.run(
            [sys.executable, "-m", "crunch_uml.cli", "detect", "-f", path],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        assert result.returncode == expected_rc, result.stderr
        assert len(lines) == 1
        payload = json.loads(lines[0])
        assert payload["verdict"] == verdict
        assert {"verdict", "format", "accepted", "code"} <= payload.keys()

    refused = write(tmp_path, "nope.txt", "just text")
    result = subprocess.run(
        [sys.executable, "-m", "crunch_uml.cli", "detect", "-f", refused],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout.strip())["code"] == "file_type_unknown"
