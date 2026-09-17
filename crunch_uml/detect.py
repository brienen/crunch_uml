"""Content-based file type detection for model uploads (``crunch_uml detect``).

Decides what a file *is* - never trusting its name or extension - before any
parser touches it. Rules:

* Read at most 64 KiB from the start of the file, plus at most 64 KiB from its
  end for XML (EA writes its ``xmi:Extension`` block last).
* No DOM parser: XML is recognised with bounded regular expressions on text.
* SQLite files are opened read-only and immutable, and only ``sqlite_master``
  is read.
* Standard library only, so the same rules can be mirrored elsewhere (the
  toolkit's browser-side check uses the same verdicts).

Accepted formats: EA-XMI 2.1 from Enterprise Architect with an extension block
(``eaxmi``), an EA repository in rollback-journal mode with the ten ``t_*``
tables and no views or triggers (``qea``), and a crunch_uml row artifact
(``artifact``). Everything else gets a verdict and a refusal code from the
toolkit's message catalogue (``file_type_unknown``, ``xmi_not_ea``,
``xml_forbidden``, ``xml_malformed``, ``qea_unreadable``).
"""

import json
import os
import re
import sqlite3
import struct
import zlib
from urllib.parse import quote

SNIFF_BYTES = 64 * 1024

QEA_TABLES = frozenset(
    {
        "t_package",
        "t_object",
        "t_attribute",
        "t_connector",
        "t_objectproperties",
        "t_attributetag",
        "t_connectortag",
        "t_diagram",
        "t_diagramobjects",
        "t_diagramlinks",
    }
)
CRUNCH_TABLES = frozenset(
    {
        "packages",
        "classes",
        "attributes",
        "enumerations",
        "enumerationliterals",
        "associations",
        "generalizations",
        "diagrams",
        "diagram_class",
        "diagram_enumeration",
        "diagram_association",
        "diagram_generalization",
    }
)

ARTIFACT_FORMAT = "semtk-crunch-artifact"

FORMAT_EAXMI = "eaxmi"
FORMAT_QEA = "qea"
FORMAT_ARTIFACT = "artifact"
FORMAT_UNKNOWN = "unknown"

CODE_FILE_TYPE_UNKNOWN = "file_type_unknown"
CODE_XMI_NOT_EA = "xmi_not_ea"
CODE_XML_MALFORMED = "xml_malformed"
CODE_XML_FORBIDDEN = "xml_forbidden"
CODE_QEA_UNREADABLE = "qea_unreadable"

# verdict -> (format, refusal code or None when accepted)
VERDICTS = {
    "ea-xmi-2.1": (FORMAT_EAXMI, None),
    "qea": (FORMAT_QEA, None),
    "artifact": (FORMAT_ARTIFACT, None),
    # EA-XMI that cannot be used as is
    "ea-xmi-no-extension": (FORMAT_UNKNOWN, CODE_XMI_NOT_EA),
    "ea-xmi-other-version": (FORMAT_UNKNOWN, CODE_XMI_NOT_EA),
    "xmi-1.x": (FORMAT_UNKNOWN, CODE_XMI_NOT_EA),
    "xmi-other-tool": (FORMAT_UNKNOWN, CODE_XMI_NOT_EA),
    "xmi-unknown-exporter": (FORMAT_UNKNOWN, CODE_XMI_NOT_EA),
    "eclipse-uml2": (FORMAT_UNKNOWN, CODE_XMI_NOT_EA),
    "xml-truncated": (FORMAT_UNKNOWN, CODE_XML_MALFORMED),
    "xml-doctype": (FORMAT_UNKNOWN, CODE_XML_FORBIDDEN),
    # SQLite that is not a usable EA repository
    "qea-wal": (FORMAT_UNKNOWN, CODE_QEA_UNREADABLE),
    "qea-views-triggers": (FORMAT_UNKNOWN, CODE_QEA_UNREADABLE),
    "sqlite-unreadable": (FORMAT_UNKNOWN, CODE_QEA_UNREADABLE),
    "crunch-sqlite": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    "sqlite-other": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    # Everything else
    "jet-ace": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    "firebird": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    "xlsx": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    "zip-other": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    "gzip-other": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    "utf16-32-bom": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    "nul-bytes": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    "ea-native-xml": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    "rdf-xml": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    "archimate-exchange": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    "xml-other": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    "xml-unknown": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    "crunch-json": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    "crunch-i18n-json": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    "json-ld": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    "json-other": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    "turtle": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    "linkml-yaml": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    "csv": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    "empty": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
    "unknown": (FORMAT_UNKNOWN, CODE_FILE_TYPE_UNKNOWN),
}

_DECLARED_ENCODING_RE = re.compile(r"<\?xml[^>]*encoding=[\"']([^\"']+)[\"']")
_PI_OR_COMMENT_RE = re.compile(r"<\?.*?\?>|<!--.*?-->", re.S)
_ROOT_RE = re.compile(r"<([A-Za-z_][\w.\-]*:)?([A-Za-z_][\w.\-]*)([^>]*)>", re.S)
_XMI_VERSION_RE = re.compile(r"xmi[:.]version=[\"']([^\"']+)[\"']")
_UML_NS_RE = re.compile(r"xmlns:uml=[\"']([^\"']+)[\"']")
_EA_DOCUMENTATION_RE = re.compile(r"<xmi:Documentation\b([^>]*)>")
_ATTR_RE = r"\b{}=[\"']([^\"']*)[\"']"
_OTHER_EXPORTER_RES = (
    re.compile(r"<xmi:exporter>([^<]+)</xmi:exporter>"),  # MagicDraw/Cameo
    re.compile(r"<XMI\.exporter>([^<]+)</XMI\.exporter>"),  # XMI 1.x
)
_JSON_TABLE_KEY_RE = re.compile(r'^\s{0,4}"([a-z_0-9]+)"\s*:\s*\[', re.M)


def _attr(attrs, name):
    match = re.search(_ATTR_RE.format(re.escape(name)), attrs)
    return match.group(1) if match else None


def _result(verdict, size, **fields):
    fmt, code = VERDICTS[verdict]
    result = {
        "verdict": verdict,
        "format": fmt,
        "accepted": code is None,
        "code": code,
        "size": size,
        "encoding": None,
        "exporter": None,
        "exporter_version": None,
        "xmi_version": None,
    }
    result.update(fields)
    return result


def _read_head_and_tail(path, size):
    with open(path, "rb") as f:
        head = f.read(SNIFF_BYTES)
        if size <= SNIFF_BYTES:
            return head, head
        f.seek(max(size - SNIFF_BYTES, SNIFF_BYTES))
        return head, f.read(SNIFF_BYTES)


def _detect_sqlite(path, head, size):
    # Header bytes 18/19: file format write/read version, 1 = rollback journal, 2 = WAL.
    journal = "wal" if 2 in (head[18], head[19]) else "rollback"
    try:
        uri = "file:" + quote(os.path.abspath(path)) + "?mode=ro&immutable=1"
        con = sqlite3.connect(uri, uri=True)
        try:
            rows = con.execute("SELECT type, name FROM sqlite_master").fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return _result("sqlite-unreadable", size, journal=journal)
    tables = {name for kind, name in rows if kind == "table"}
    has_views_or_triggers = any(kind in ("view", "trigger") for kind, _ in rows)
    if QEA_TABLES <= tables:
        if has_views_or_triggers:
            return _result("qea-views-triggers", size, journal=journal)
        if journal == "wal":
            return _result("qea-wal", size, journal=journal)
        return _result("qea", size, journal=journal, exporter="Enterprise Architect")
    if CRUNCH_TABLES <= tables:
        return _result("crunch-sqlite", size, journal=journal)
    return _result("sqlite-other", size, journal=journal)


def _detect_gzip(head, size):
    """A crunch_uml artifact is gzip-JSON whose first key is ``"format"``."""
    try:
        text = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(head, SNIFF_BYTES).decode("utf-8", "replace")
    except zlib.error:
        return _result("gzip-other", size)
    if re.match(r'\s*\{\s*"format"\s*:\s*"' + ARTIFACT_FORMAT + '"', text):
        fields = {}
        for key in ("format_version", "datamodel_version"):
            match = re.search(r'"' + key + r'"\s*:\s*(\d+)', text)
            fields[key] = int(match.group(1)) if match else None
        match = re.search(r'"crunch_version"\s*:\s*"([^"]*)"', text)
        fields["crunch_version"] = match.group(1) if match else None
        return _result("artifact", size, **fields)
    return _result("gzip-other", size)


def _sniff_text(head):
    """Decode the head for pattern matching; None plus a verdict when it must be refused."""
    if head.startswith(b"\xef\xbb\xbf"):
        return head[3:].decode("utf-8", "replace"), None
    if head[:4] in (b"\x00\x00\xfe\xff", b"\xff\xfe\x00\x00") or head[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return None, "utf16-32-bom"  # would dodge every ASCII scan
    if b"\x00" in head:
        return None, "nul-bytes"  # UTF-16 without BOM, or binary
    return head.decode("latin-1"), None


def _detect_xml(text, tail_text, size):
    if re.search(r"<!DOCTYPE|<!ENTITY", text):
        return _result("xml-doctype", size)
    declared = _DECLARED_ENCODING_RE.search(text)
    encoding = declared.group(1) if declared else None
    body = _PI_OR_COMMENT_RE.sub("", text)
    root = _ROOT_RE.search(body)
    if not root:
        return _result("xml-unknown", size, encoding=encoding)
    prefix, local, attrs = (root.group(1) or "").rstrip(":"), root.group(2), root.group(3)
    version = _XMI_VERSION_RE.search(attrs)
    xmi_version = version.group(1) if version else None
    uml_ns = _UML_NS_RE.search(text)
    exporter = exporter_version = None
    documentation = _EA_DOCUMENTATION_RE.search(text)
    if documentation:
        exporter = _attr(documentation.group(1), "exporter")
        exporter_version = _attr(documentation.group(1), "exporterVersion")
    if not exporter:
        for pattern in _OTHER_EXPORTER_RES:
            match = pattern.search(text)
            if match:
                exporter = match.group(1).strip()
                break
    fields = dict(encoding=encoding, exporter=exporter, exporter_version=exporter_version, xmi_version=xmi_version)

    if local == "Package" and not prefix and re.search(r"<Table name=\"t_package\"", text):
        return _result("ea-native-xml", size, **fields)
    if local == "XMI" and (xmi_version or "").startswith("1."):
        return _result("xmi-1.x", size, **fields)
    if local == "XMI" or (prefix == "uml" and local in ("Model", "Package", "Profile")):
        if exporter and "enterprise architect" in exporter.lower():
            if xmi_version != "2.1":
                return _result("ea-xmi-other-version", size, **fields)
            if not re.search(r"</(?:[A-Za-z_][\w.\-]*:)?XMI>\s*$", tail_text):
                return _result("xml-truncated", size, **fields)
            if "xmi:Extension" not in tail_text:
                return _result("ea-xmi-no-extension", size, **fields)
            return _result("ea-xmi-2.1", size, **fields)
        if uml_ns and "eclipse.org/uml2" in uml_ns.group(1):
            return _result("eclipse-uml2", size, **fields)
        if exporter:
            return _result("xmi-other-tool", size, **fields)
        return _result("xmi-unknown-exporter", size, **fields)
    if local == "RDF" and prefix == "rdf":
        return _result("rdf-xml", size, **fields)
    if local == "model" and "archimate" in text[:2000].lower():
        return _result("archimate-exchange", size, **fields)
    return _result("xml-other", size, **fields)


def detect(path):
    """Classify the file at ``path``; returns a JSON-serialisable dict (see :data:`VERDICTS`)."""
    size = os.path.getsize(path)
    if size == 0:
        return _result("empty", 0)
    head, tail = _read_head_and_tail(path, size)

    if head[:16] == b"SQLite format 3\x00":
        return _detect_sqlite(path, head, size)
    if head[:4] == b"\x00\x01\x00\x00" and head[4:19] in (b"Standard Jet DB", b"Standard ACE DB"):
        return _result("jet-ace", size)
    if head[:1] == b"\x01" and len(head) > 20:
        page = struct.unpack("<H", head[16:18])[0]
        ods = struct.unpack("<H", head[18:20])[0]
        if page in (1024, 2048, 4096, 8192, 16384, 32768) and (ods & 0x7FFF) in range(8, 14):
            return _result("firebird", size)
    if head[:4] == b"PK\x03\x04":
        return _result("xlsx" if b"xl/" in head else "zip-other", size)
    if head[:2] == b"\x1f\x8b":
        return _detect_gzip(head, size)

    text, refused = _sniff_text(head)
    if text is None:
        return _result(refused, size)
    stripped = text.lstrip()
    if stripped.startswith("<"):
        tail_text, tail_refused = _sniff_text(tail)
        return _detect_xml(text, tail_text if tail_refused is None else "", size)
    if stripped.startswith("{") or stripped.startswith("["):
        if set(_JSON_TABLE_KEY_RE.findall(text)) & CRUNCH_TABLES:
            return _result("crunch-json", size)
        if '"@context"' in text:
            return _result("json-ld", size)
        if re.match(r'\{\s*"(nl|en|de|fr)"\s*:', stripped):
            return _result("crunch-i18n-json", size)
        return _result("json-other", size)
    if re.search(r"^\s*(@prefix|PREFIX|@base)\s", text, re.M | re.I):
        return _result("turtle", size)
    if re.search(r"^id:\s*\S+", text, re.M) and re.search(r"^(classes|slots|enums|prefixes|imports):", text, re.M):
        return _result("linkml-yaml", size)
    if "," in stripped.split("\n", 1)[0]:
        return _result("csv", size)
    return _result("unknown", size)


def detect_json(path):
    """:func:`detect` as one JSON line (the output of ``crunch_uml detect``)."""
    return json.dumps(detect(path), ensure_ascii=False, sort_keys=False)
