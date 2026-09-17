"""Generate the MiniM4 fixture pair: test/data/MiniM4.qea and test/data/MiniM4.xml.

A deliberately tiny Enterprise Architect model (< 100 KB per file) that carries
every EA quirk crunch_uml 0.7.0 fixed, in both source formats:

* a «Domein» package with a package tagged value (QEA: stereotype on the
  companion t_object row);
* an Aggregation connector with a tagged value (QEA skipped these before 0.7.0);
* attributes without a GUID, two of them with the same name (QEA ea_guid NULL,
  XMI xmi:id="");
* an enumeration value without IsLiteral=1 (XMI: ownedAttribute uml:Property,
  one of them without a GUID);
* an enumeration whose GUID has a doubled brace pair ({{...}} in the QEA,
  EAID_{...} in the XMI), referenced as an attribute type;
* a Boundary on a diagram (QEA: t_object 'Boundary'; XMI: uml:Class with an
  extension element of type uml:Boundary);
* associations with an enumeration at one end, in both directions (the GGM has
  them); crunch_uml keeps association ends in ``classes``, so both parsers add
  one ``<Orphan Class>`` placeholder with the enumeration's id;
* diagram settings: HideAtts=1 on one diagram, a per-node attribute override
  (AttPub=0;...) on another, and a non-class diagram type.

Both files describe the same model the way EA writes it, so the two parsers
must agree on everything except the documented Boundary asymmetry (the eaxmi
parser still reads it as a class). The QEA table definitions are copied from
test/data/Monumenten.qea, an EA-written repository.

Run from the repository root:  python tools/make_mini_m4_fixture.py
"""

import os
import sqlite3
from xml.sax.saxutils import quoteattr

DATA = os.path.join("test", "data")
QEA_OUT = os.path.join(DATA, "MiniM4.qea")
XMI_OUT = os.path.join(DATA, "MiniM4.xml")
TEMPLATE_QEA = os.path.join(DATA, "Monumenten.qea")
EA_TABLES = (
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
)

AUTHOR = "crunch_uml tests"
CREATED = "2026-09-17 12:00:00"
MODIFIED = "2026-09-17 12:30:00"


def guid(n):
    """Deterministic EA-style GUID number n: {4D4E0000-0000-4000-8000-0000000000nn}."""
    return f"{{4D4E{n:04X}-0000-4000-8000-{n:012X}}}"


def eaid(g, prefix="EAID"):
    return f"{prefix}_" + g.strip("{}").replace("-", "_")


# --------------------------------------------------------------------------
# The model
# --------------------------------------------------------------------------
PKG_ROOT, PKG_KERN, PKG_OVERIG = guid(1), guid(2), guid(3)
PERSOON, ADRES, HUISHOUDEN, INGEZETENE, GRENS, POSTCODE = (guid(n) for n in range(10, 16))
GESLACHT_INNER = guid(16)
GESLACHT_QEA = "{" + GESLACHT_INNER + "}"  # doubled braces, as found in the GGM
ATTR_NAAM, ATTR_GESLACHT, ATTR_POSTCODE = guid(20), guid(21), guid(22)
LIT_MAN, LIT_ONBEKEND = guid(23), guid(24)
ASSOC, AGGR, GEN, ASSOC_TO_ENUM, ASSOC_FROM_ENUM = (guid(n) for n in range(30, 35))
DIA_KERN, DIA_DETAILS, DIA_PACKAGES = guid(40), guid(41), guid(42)
TAG_IDS = iter(guid(n) for n in range(50, 60))

PDATA_HIDE = (
    "HideRel=0;ShowTags=0;ShowReqs=0;ShowCons=0;OpParams=1;ShowSN=0;ScalePI=0;PPgs.cx=1;PPgs.cy=1;PSize=9;"
    "ShowIcons=1;SuppCN=0;HideProps=0;HideParents=0;UseAlias=0;HideAtts=1;HideOps=1;HideStereo=0;HideEStereo=0;"
    "ShowRec=1;ShowRes=0;ShowShape=1;FormName=;"
)
PDATA_SHOW = PDATA_HIDE.replace("HideAtts=1;HideOps=1;", "HideAtts=0;HideOps=0;")
STYLE_EX = "ExcludeRTF=0;DocAll=0;HideQuals=0;AttPkg=1;ShowTests=0;ShowMaint=0;SuppressFOC=1;SuppressedCompartments=;"
NODE_HIDE_ATTS = "AttPro=0;AttPri=0;AttPub=0;AttPkg=0;DUID=4D4E0001;"

# QEA object ids
O_KERN, O_OVERIG, O_PERSOON, O_ADRES, O_HUISHOUDEN, O_INGEZETENE, O_GRENS, O_POSTCODE, O_GESLACHT = range(1, 10)

OBJECTS = [
    # Object_ID, Object_Type, Name, Package_ID, ea_guid, Note, Stereotype, Alias, Phase, PDATA1
    (O_KERN, "Package", "Kern", 1, PKG_KERN, None, "Domein", "kern", "1.0", "2"),
    (O_OVERIG, "Package", "Overig", 1, PKG_OVERIG, None, None, None, "1.0", "3"),
    (O_PERSOON, "Class", "Persoon", 2, PERSOON, "Een mens.", None, None, "1.0", None),
    (O_ADRES, "Class", "Adres", 2, ADRES, None, None, None, "1.0", None),
    (O_HUISHOUDEN, "Class", "Huishouden", 2, HUISHOUDEN, None, None, None, "1.0", None),
    (O_INGEZETENE, "Class", "Ingezetene", 2, INGEZETENE, None, None, None, "1.0", None),
    (O_GRENS, "Boundary", "Grens", 2, GRENS, None, None, None, "1.0", None),
    (O_POSTCODE, "DataType", "Postcode", 3, POSTCODE, None, None, None, "1.0", None),
    (O_GESLACHT, "Enumeration", "Geslacht", 2, GESLACHT_QEA, None, None, None, "1.0", None),
]

ATTRIBUTES = [
    # ID, Object_ID, Name, Pos, ea_guid, Type, Classifier, StyleEx
    (100, O_PERSOON, "naam", 0, ATTR_NAAM, "CharacterString", "0", "volatile=0;"),
    (101, O_PERSOON, "geboortedatum", 1, None, "Date", "0", "volatile=0;"),
    (102, O_PERSOON, "opmerking", 2, None, "CharacterString", "0", "volatile=0;"),
    (103, O_PERSOON, "opmerking", 3, None, "CharacterString", "0", "volatile=0;"),
    (104, O_PERSOON, "geslacht", 4, ATTR_GESLACHT, "Geslacht", str(O_GESLACHT), "volatile=0;"),
    (105, O_ADRES, "postcode", 0, ATTR_POSTCODE, "Postcode", str(O_POSTCODE), "volatile=0;"),
    (106, O_GESLACHT, "man", 0, LIT_MAN, None, "0", "IsLiteral=1;volatile=0;"),
    (107, O_GESLACHT, "vrouw", 1, None, None, "0", "IsLiteral=0;volatile=0;"),
    (108, O_GESLACHT, "onbekend", 2, LIT_ONBEKEND, None, "0", "IsLiteral=0;volatile=0;"),
]

CONNECTORS = [
    # Connector_ID, Name, Connector_Type, Start_Object_ID, End_Object_ID, ea_guid
    (200, "woont op", "Association", O_PERSOON, O_ADRES, ASSOC),
    (201, "bestaat uit", "Aggregation", O_PERSOON, O_HUISHOUDEN, AGGR),
    (202, None, "Generalization", O_INGEZETENE, O_PERSOON, GEN),
    (203, "heeft", "Association", O_HUISHOUDEN, O_GESLACHT, ASSOC_TO_ENUM),
    (204, "hoort bij", "Association", O_GESLACHT, O_PERSOON, ASSOC_FROM_ENUM),
]

OBJECT_TAGS = [(O_KERN, "afkorting", "KRN"), (O_PERSOON, "herkomst", "MiniM4"), (O_GESLACHT, "herkomst", "EA")]
ATTRIBUTE_TAGS = [(100, "lengte", "200")]
CONNECTOR_TAGS = [(201, "herkomst", "MiniM4")]

DIAGRAMS = [
    # Diagram_ID, Package_ID, Diagram_Type, Name, ea_guid, PDATA, StyleEx
    (1, 2, "Logical", "Kern overzicht", DIA_KERN, PDATA_HIDE, STYLE_EX),
    (2, 2, "Logical", "Kern details", DIA_DETAILS, PDATA_SHOW, STYLE_EX),
    (3, 3, "Package", "Packages", DIA_PACKAGES, PDATA_SHOW, STYLE_EX),
]

# Diagram_ID, Object_ID, x, y, width, height, Sequence, ObjectStyle
DIAGRAM_OBJECTS = [
    (1, O_PERSOON, 50, 40, 120, 80, 1, "DUID=4D4E0010;"),
    (1, O_ADRES, 300, 40, 120, 60, 2, "DUID=4D4E0011;"),
    (1, O_HUISHOUDEN, 50, 220, 120, 60, 3, "DUID=4D4E0012;"),
    (1, O_GESLACHT, 300, 220, 110, 70, 4, "DUID=4D4E0013;"),
    (1, O_GRENS, 20, 10, 500, 400, 5, "DUID=4D4E0014;"),
    (2, O_PERSOON, 60, 60, 150, 100, 1, NODE_HIDE_ATTS),
    (2, O_INGEZETENE, 60, 260, 120, 60, 2, "DUID=4D4E0015;"),
    (3, O_POSTCODE, 40, 40, 100, 50, 1, "DUID=4D4E0016;"),
]

EDGE_GEOMETRY = "SX=0;SY=0;EX=0;EY=0;EDGE=2;$LLB=;LLT=;LMT=;LMB=;LRT=;LRB=;IRHS=;ILHS=;"
# DiagramID, ConnectorID, Style (without Hidden), Hidden, waypoints [(x, y_ea)] with EA's negative y
DIAGRAM_LINKS = [
    (1, 200, "Mode=3;EOID=4D4E0011;SOID=4D4E0010;Color=-1;LWidth=0;", 0, [(235, -80), (235, -70)]),
    (1, 201, "Mode=3;EOID=4D4E0012;SOID=4D4E0010;Color=-1;LWidth=0;", 0, []),
    (2, 202, "Mode=3;EOID=4D4E0010;SOID=4D4E0015;Color=-1;LWidth=0;", 1, []),
]


# --------------------------------------------------------------------------
# QEA
# --------------------------------------------------------------------------
def write_qea(path):
    template = sqlite3.connect(f"file:{TEMPLATE_QEA}?mode=ro&immutable=1", uri=True)
    ddl = {
        name: sql
        for name, sql in template.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name IN (%s)" % ",".join("?" * len(EA_TABLES)),
            EA_TABLES,
        )
    }
    template.close()
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.execute("PRAGMA page_size=1024")
    for table in EA_TABLES:
        con.execute(ddl[table])

    con.execute(
        "INSERT INTO t_package (Package_ID, Name, Parent_ID, ea_guid, Notes, Version, CreatedDate, ModifiedDate)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (1, "MiniM4", 0, PKG_ROOT, "Testmodel voor crunch_uml 0.7.0.", "1.0", CREATED, MODIFIED),
    )
    con.execute(
        "INSERT INTO t_package (Package_ID, Name, Parent_ID, ea_guid, Notes, Version, CreatedDate, ModifiedDate)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (2, "Kern", 1, PKG_KERN, None, "1.0", CREATED, MODIFIED),
    )
    con.execute(
        "INSERT INTO t_package (Package_ID, Name, Parent_ID, ea_guid, Notes, Version, CreatedDate, ModifiedDate)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (3, "Overig", 1, PKG_OVERIG, None, "1.0", CREATED, MODIFIED),
    )
    for obj_id, obj_type, name, pkg, g, note, stereo, alias, phase, pdata1 in OBJECTS:
        con.execute(
            "INSERT INTO t_object (Object_ID, Object_Type, Name, Package_ID, ea_guid, Note, Stereotype, Author,"
            " Version, CreatedDate, ModifiedDate, Status, Alias, Phase, PDATA1)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                obj_id,
                obj_type,
                name,
                pkg,
                g,
                note,
                stereo,
                AUTHOR,
                "1.0",
                CREATED,
                MODIFIED,
                "Proposed",
                alias,
                phase,
                pdata1,
            ),
        )
    for attr_id, obj_id, name, pos, g, typ, classifier, style_ex in ATTRIBUTES:
        con.execute(
            "INSERT INTO t_attribute (ID, Object_ID, Name, Pos, ea_guid, Type, Classifier, Scope, LowerBound,"
            " UpperBound, StyleEx) VALUES (?, ?, ?, ?, ?, ?, ?, 'Public', '1', '1', ?)",
            (attr_id, obj_id, name, pos, g, typ, classifier, style_ex),
        )
    for conn_id, name, typ, start, end, g in CONNECTORS:
        con.execute(
            "INSERT INTO t_connector (Connector_ID, Name, Connector_Type, Start_Object_ID, End_Object_ID, ea_guid,"
            " SourceCard, DestCard, DestIsAggregate, Direction) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                conn_id,
                name,
                typ,
                start,
                end,
                g,
                None if typ == "Generalization" else "1",
                None if typ == "Generalization" else "1",
                1 if typ == "Aggregation" else 0,
                "Source -> Destination",
            ),
        )
    for obj_id, prop, value in OBJECT_TAGS:
        con.execute(
            "INSERT INTO t_objectproperties (Object_ID, Property, Value, ea_guid) VALUES (?, ?, ?, ?)",
            (obj_id, prop, value, next(TAG_IDS)),
        )
    for elem_id, prop, value in ATTRIBUTE_TAGS:
        con.execute(
            "INSERT INTO t_attributetag (ElementID, Property, VALUE, ea_guid) VALUES (?, ?, ?, ?)",
            (elem_id, prop, value, next(TAG_IDS)),
        )
    for elem_id, prop, value in CONNECTOR_TAGS:
        con.execute(
            "INSERT INTO t_connectortag (ElementID, Property, VALUE, ea_guid) VALUES (?, ?, ?, ?)",
            (elem_id, prop, value, next(TAG_IDS)),
        )
    for dia_id, pkg, typ, name, g, pdata, style_ex in DIAGRAMS:
        con.execute(
            "INSERT INTO t_diagram (Diagram_ID, Package_ID, Diagram_Type, Name, ea_guid, PDATA, StyleEx, Author,"
            " Version, CreatedDate, ModifiedDate) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (dia_id, pkg, typ, name, g, pdata, style_ex, AUTHOR, "1.0", CREATED, MODIFIED),
        )
    for dia_id, obj_id, x, y, w, h, seq, style in DIAGRAM_OBJECTS:
        con.execute(
            "INSERT INTO t_diagramobjects (Diagram_ID, Object_ID, RectLeft, RectTop, RectRight, RectBottom, Sequence,"
            " ObjectStyle) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (dia_id, obj_id, x, -y, x + w, -(y + h), seq, style),
        )
    for dia_id, conn_id, style, hidden, points in DIAGRAM_LINKS:
        edge_path = "".join(f"{x}:{y};" for x, y in points)
        con.execute(
            "INSERT INTO t_diagramlinks (DiagramID, ConnectorID, Geometry, Style, Hidden, Path) VALUES (?, ?, ?, ?, ?, ?)",
            (dia_id, conn_id, EDGE_GEOMETRY, style, hidden, edge_path),
        )
    con.commit()
    con.execute("VACUUM")
    con.close()


# --------------------------------------------------------------------------
# XMI (EA 2.1 export dialect)
# --------------------------------------------------------------------------
def a(**attrs):
    """XML attribute string in keyword order; '__' in a key becomes ':' (xmi__type -> xmi:type); None is skipped."""
    parts = []
    for key, value in attrs.items():
        if value is None:
            continue
        name = key.replace("__", ":")
        parts.append(f"{name}={quoteattr(str(value))}")
    return " ".join(parts)


def end_id(assoc_id, side):
    """EA derives association end ids by overwriting the first two hex digits: EAID_4D4E... -> EAID_src4E..."""
    return assoc_id[:5] + side + assoc_id[7:]


def write_xmi(path):
    ids = {
        "root": eaid(PKG_ROOT, "EAPK"),
        "kern": eaid(PKG_KERN, "EAPK"),
        "overig": eaid(PKG_OVERIG, "EAPK"),
        "persoon": eaid(PERSOON),
        "adres": eaid(ADRES),
        "huishouden": eaid(HUISHOUDEN),
        "ingezetene": eaid(INGEZETENE),
        "grens": eaid(GRENS),
        "postcode": eaid(POSTCODE),
        "geslacht": "EAID_{" + GESLACHT_INNER.strip("{}").replace("-", "_") + "}",
        "assoc": eaid(ASSOC),
        "aggr": eaid(AGGR),
        "gen": eaid(GEN),
        "assoc_to_enum": eaid(ASSOC_TO_ENUM),
        "assoc_from_enum": eaid(ASSOC_FROM_ENUM),
    }
    obj_ids = {
        O_PERSOON: ids["persoon"],
        O_ADRES: ids["adres"],
        O_HUISHOUDEN: ids["huishouden"],
        O_INGEZETENE: ids["ingezetene"],
        O_GRENS: ids["grens"],
        O_POSTCODE: ids["postcode"],
        O_GESLACHT: ids["geslacht"],
    }
    tag_ids = iter(eaid(guid(n)) for n in range(60, 80))
    out = []
    w = out.append

    def member(tag, xmi_type, attr_id, name, type_ref=None, primitive=None):
        attr_xmi_id = eaid(attr_id) if attr_id else ""
        w(
            f"\t\t\t\t\t<{tag} "
            + a(
                xmi__type=xmi_type,
                xmi__id=attr_xmi_id,
                name=name,
                visibility="public",
                isStatic="false",
                isReadOnly="false",
                isDerived="false",
                isOrdered="false",
                isUnique="true",
                isDerivedUnion="false",
            )
            + ">"
        )
        # EA exports the bounds of a GUID-less member with empty ids as well.
        bound_id = attr_xmi_id.replace("EAID_", "EAID_LI") if attr_xmi_id else ""
        w(
            f"\t\t\t\t\t\t<lowerValue {a(xmi__type='uml:LiteralInteger', xmi__id=bound_id + ('_l' if bound_id else ''), value='1')}/>"
        )
        w(
            f"\t\t\t\t\t\t<upperValue {a(xmi__type='uml:LiteralInteger', xmi__id=bound_id + ('_u' if bound_id else ''), value='1')}/>"
        )
        if type_ref:
            w(f"\t\t\t\t\t\t<type {a(xmi__idref=type_ref)}/>")
        elif primitive:
            w(f"\t\t\t\t\t\t<type {a(xmi__idref='EAJava_' + primitive)}/>")
        w(f"\t\t\t\t\t</{tag}>")

    w("<?xml version='1.0' encoding='windows-1252' ?>")
    w(
        '<xmi:XMI xmlns:xmi="http://schema.omg.org/spec/XMI/2.1" xmi:version="2.1"'
        ' xmlns:uml="http://schema.omg.org/spec/UML/2.1">'
    )
    w('\t<xmi:Documentation exporter="Enterprise Architect" exporterVersion="6.5" exporterID="1628"/>')
    w('\t<uml:Model xmi:type="uml:Model" name="EA_Model" visibility="public">')
    w(f'\t\t<packagedElement {a(xmi__type="uml:Package", xmi__id=ids["root"], name="MiniM4", visibility="public")}>')
    w(f'\t\t\t<packagedElement {a(xmi__type="uml:Package", xmi__id=ids["kern"], name="Kern", visibility="public")}>')

    # Persoon
    w(
        f'\t\t\t\t<packagedElement {a(xmi__type="uml:Class", xmi__id=ids["persoon"], name="Persoon", visibility="public")}>'
    )
    for attr_id, obj_id, name, pos, g, typ, classifier, _ in ATTRIBUTES:
        if obj_id != O_PERSOON:
            continue
        type_ref = obj_ids.get(int(classifier)) if classifier != "0" else None
        member("ownedAttribute", "uml:Property", g, name, type_ref=type_ref, primitive=None if type_ref else typ)
    w("\t\t\t\t</packagedElement>")
    # Adres
    w(f'\t\t\t\t<packagedElement {a(xmi__type="uml:Class", xmi__id=ids["adres"], name="Adres", visibility="public")}>')
    member("ownedAttribute", "uml:Property", ATTR_POSTCODE, "postcode", type_ref=ids["postcode"])
    w("\t\t\t\t</packagedElement>")
    # Huishouden
    w(
        f'\t\t\t\t<packagedElement {a(xmi__type="uml:Class", xmi__id=ids["huishouden"], name="Huishouden", visibility="public")}/>'
    )
    # Ingezetene with generalization
    w(
        f'\t\t\t\t<packagedElement {a(xmi__type="uml:Class", xmi__id=ids["ingezetene"], name="Ingezetene", visibility="public")}>'
    )
    w(f'\t\t\t\t\t<generalization {a(xmi__type="uml:Generalization", xmi__id=ids["gen"], general=ids["persoon"])}/>')
    w("\t\t\t\t</packagedElement>")
    # Boundary: EA exports it as a plain uml:Class in the model tree
    w(f'\t\t\t\t<packagedElement {a(xmi__type="uml:Class", xmi__id=ids["grens"], name="Grens", visibility="public")}/>')
    # Enumeration with a braced id; IsLiteral=1 -> ownedLiteral, others -> ownedAttribute uml:Property
    w(
        f'\t\t\t\t<packagedElement {a(xmi__type="uml:Enumeration", xmi__id=ids["geslacht"], name="Geslacht", visibility="public")}>'
    )
    for attr_id, obj_id, name, pos, g, typ, classifier, style_ex in ATTRIBUTES:
        if obj_id != O_GESLACHT:
            continue
        if "IsLiteral=1" in style_ex:
            w(
                f'\t\t\t\t\t<ownedLiteral {a(xmi__type="uml:EnumerationLiteral", xmi__id=eaid(g), name=name, visibility="public")}/>'
            )
        else:
            member("ownedAttribute", "uml:Property", g, name)
    w("\t\t\t\t</packagedElement>")
    # Association and aggregation
    for key, name, aggregation, src, dst in (
        ("assoc", "woont op", "none", ids["persoon"], ids["adres"]),
        ("aggr", "bestaat uit", "shared", ids["persoon"], ids["huishouden"]),
        ("assoc_to_enum", "heeft", "none", ids["huishouden"], ids["geslacht"]),
        ("assoc_from_enum", "hoort bij", "none", ids["geslacht"], ids["persoon"]),
    ):
        assoc_id = ids[key]
        w(
            f'\t\t\t\t<packagedElement {a(xmi__type="uml:Association", xmi__id=assoc_id, name=name, visibility="public")}>'
        )
        for side, type_ref, agg in (("dst", dst, aggregation), ("src", src, "none")):
            w(f"\t\t\t\t\t<memberEnd {a(xmi__idref=end_id(assoc_id, side))}/>")
            w(
                "\t\t\t\t\t<ownedEnd "
                + a(
                    xmi__type="uml:Property",
                    xmi__id=end_id(assoc_id, side),
                    visibility="public",
                    association=assoc_id,
                    isStatic="false",
                    isReadOnly="false",
                    isDerived="false",
                    isOrdered="false",
                    isUnique="true",
                    isDerivedUnion="false",
                    aggregation=agg,
                )
                + ">"
            )
            w(f"\t\t\t\t\t\t<type {a(xmi__idref=type_ref)}/>")
            w(
                f'\t\t\t\t\t\t<lowerValue {a(xmi__type="uml:LiteralInteger", xmi__id=end_id(assoc_id, side)[:5] + "LI" + side, value="1")}/>'
            )
            w(
                f'\t\t\t\t\t\t<upperValue {a(xmi__type="uml:LiteralUnlimitedNatural", xmi__id=end_id(assoc_id, side)[:5] + "LU" + side, value="1")}/>'
            )
            w("\t\t\t\t\t</ownedEnd>")
        w("\t\t\t\t</packagedElement>")
    w("\t\t\t</packagedElement>")
    # Overig
    w(
        f'\t\t\t<packagedElement {a(xmi__type="uml:Package", xmi__id=ids["overig"], name="Overig", visibility="public")}>'
    )
    w(
        f'\t\t\t\t<packagedElement {a(xmi__type="uml:DataType", xmi__id=ids["postcode"], name="Postcode", visibility="public")}/>'
    )
    w("\t\t\t</packagedElement>")
    w("\t\t</packagedElement>")
    w("\t</uml:Model>")

    # ---------------------------------------------------------------- extension
    w('\t<xmi:Extension extender="Enterprise Architect" extenderID="6.5">')
    w("\t\t<elements>")

    def tags(model_element, pairs):
        if not pairs:
            w("\t\t\t\t<tags/>")
            return
        w("\t\t\t\t<tags>")
        for name, value in pairs:
            w(f"\t\t\t\t\t<tag {a(xmi__id=next(tag_ids), name=name, value=value, modelElement=model_element)}/>")
        w("\t\t\t\t</tags>")

    def project(phase="1.0"):
        w(
            f"\t\t\t\t<project {a(author=AUTHOR, version='1.0', phase=phase, created=CREATED, modified=MODIFIED, complexity='1', status='Proposed')}/>"
        )

    root_obj_pkg = {
        "kern": (O_KERN, "Kern", ids["kern"], PKG_KERN),
        "overig": (O_OVERIG, "Overig", ids["overig"], PKG_OVERIG),
    }
    w(f'\t\t\t<element {a(xmi__idref=ids["root"], xmi__type="uml:Package", name="MiniM4", scope="public")}>')
    w(
        f'\t\t\t\t<model {a(package2=eaid(PKG_ROOT), package="EAPK_25B4ECD1_9E00_4c73_A3E9_4B2D0A1B4B6F", tpos="0", ea_localid="1", ea_eleType="package")}/>'
    )
    w(
        f'\t\t\t\t<properties {a(documentation="Testmodel voor crunch_uml 0.7.0.", isSpecification="false", sType="Package", nType="0", scope="public")}/>'
    )
    w(f"\t\t\t\t<project {a(author=AUTHOR, version='1.0', created=CREATED, modified=MODIFIED)}/>")
    tags(eaid(PKG_ROOT), [])
    w("\t\t\t</element>")
    for key, (obj_id, name, pkg_id, g) in root_obj_pkg.items():
        obj = next(o for o in OBJECTS if o[0] == obj_id)
        w(f'\t\t\t<element {a(xmi__idref=pkg_id, xmi__type="uml:Package", name=name, scope="public")}>')
        w(
            f'\t\t\t\t<model {a(package2=eaid(g), package=ids["root"], tpos="0", ea_localid=str(obj_id), ea_eleType="package")}/>'
        )
        w(
            f'\t\t\t\t<properties {a(isSpecification="false", sType="Package", nType="0", scope="public", stereotype=obj[6], alias=obj[7])}/>'
        )
        project()
        tags(eaid(g), [(p, v) for o, p, v in OBJECT_TAGS if o == obj_id])
        w("\t\t\t</element>")

    for obj_id, obj_type, name, pkg, g, note, stereo, alias, phase, _ in OBJECTS:
        if obj_type == "Package":
            continue
        element_id = obj_ids[obj_id]
        xmi_type = {
            "Class": "uml:Class",
            "DataType": "uml:DataType",
            "Enumeration": "uml:Enumeration",
            "Boundary": "uml:Boundary",
        }[obj_type]
        package_id = ids["kern"] if pkg == 2 else ids["overig"]
        w(f'\t\t\t<element {a(xmi__idref=element_id, xmi__type=xmi_type, name=name, scope="public")}>')
        w(f'\t\t\t\t<model {a(package=package_id, tpos="0", ea_localid=str(obj_id), ea_eleType="element")}/>')
        w(
            f'\t\t\t\t<properties {a(documentation=note, isSpecification="false", sType=obj_type, nType="0", scope="public", stereotype=stereo)}/>'
        )
        project()
        tags(element_id, [(p, v) for o, p, v in OBJECT_TAGS if o == obj_id])
        members = [row for row in ATTRIBUTES if row[1] == obj_id]
        if members:
            w("\t\t\t\t<attributes>")
            for attr_id, _, attr_name, pos, attr_guid, typ, classifier, style_ex in members:
                # EA writes no xmi:idref for members without a GUID.
                w(
                    f"\t\t\t\t\t<attribute {a(xmi__idref=eaid(attr_guid) if attr_guid else None, name=attr_name, scope='Public')}>"
                )
                w("\t\t\t\t\t\t<initial/>")
                w("\t\t\t\t\t\t<documentation/>")
                w(f"\t\t\t\t\t\t<model {a(ea_localid=str(attr_id), ea_guid=attr_guid)}/>")
                w(
                    f"\t\t\t\t\t\t<properties {a(type=typ, collection='false', static='0', duplicates='0', changeability='changeable')}/>"
                )
                w(f"\t\t\t\t\t\t<containment {a(containment='Not Specified', position=str(pos))}/>")
                w("\t\t\t\t\t\t<stereotype/>")
                w(f"\t\t\t\t\t\t<bounds {a(lower='1', upper='1')}/>")
                w(f"\t\t\t\t\t\t<styleex {a(value=style_ex)}/>")
                tag_pairs = [(p, v) for e, p, v in ATTRIBUTE_TAGS if e == attr_id]
                if tag_pairs:
                    w("\t\t\t\t\t\t<tags>")
                    for tag_name, tag_value in tag_pairs:
                        w(
                            f"\t\t\t\t\t\t\t<tag {a(xmi__id=next(tag_ids), name=tag_name, value=tag_value, modelElement=eaid(attr_guid))}/>"
                        )
                    w("\t\t\t\t\t\t</tags>")
                else:
                    w("\t\t\t\t\t\t<tags/>")
                w("\t\t\t\t\t</attribute>")
            w("\t\t\t\t</attributes>")
        w("\t\t\t</element>")
    w("\t\t</elements>")

    w("\t\t<connectors>")
    for conn_id, name, typ, start, end, g in CONNECTORS:
        conn_xmi = eaid(g)
        w(f"\t\t\t<connector {a(xmi__idref=conn_xmi, name=name)}>")
        for role, obj_id in (("source", start), ("target", end)):
            w(f"\t\t\t\t<{role} {a(xmi__idref=obj_ids[obj_id])}>")
            obj_type = next(o[1] for o in OBJECTS if o[0] == obj_id)
            w(f"\t\t\t\t\t<model {a(ea_localid=str(obj_id), type=obj_type)}/>")
            w("\t\t\t\t\t<role visibility=\"Public\" targetScope=\"instance\"/>")
            aggregation = "shared" if (typ == "Aggregation" and role == "target") else "none"
            w(f"\t\t\t\t\t<type {a(aggregation=aggregation, containment='Unspecified')}/>")
            w("\t\t\t\t\t<documentation/>")
            w("\t\t\t\t\t<tags/>")
            w(f"\t\t\t\t</{role}>")
        w(f"\t\t\t\t<model {a(ea_localid=str(conn_id))}/>")
        w(f"\t\t\t\t<properties {a(ea_type=typ, direction='Source -> Destination')}/>")
        w("\t\t\t\t<documentation/>")
        if name:
            w(f"\t\t\t\t<labels {a(mt=name)}/>")
        tag_pairs = [(p, v) for e, p, v in CONNECTOR_TAGS if e == conn_id]
        if tag_pairs:
            w("\t\t\t\t<tags>")
            for tag_name, tag_value in tag_pairs:
                w(f"\t\t\t\t\t<tag {a(xmi__id=next(tag_ids), name=tag_name, value=tag_value, modelElement=conn_xmi)}/>")
            w("\t\t\t\t</tags>")
        else:
            w("\t\t\t\t<tags/>")
        w("\t\t\t</connector>")
    w("\t\t</connectors>")

    # Diagrams: <style1> carries PDATA in the XMI dialect, <style2> StyleEx.
    def xmi_style1(pdata):
        return (
            pdata.replace("HideEStereo", "HideElemStereo").replace("HideRel=", "HideRelationships=")
            + "ShowPublic=1;ShowPrivate=1;ShowProtected=1;Zoom=100;"
        )

    w("\t\t<diagrams>")
    for dia_id, pkg, typ, name, g, pdata, style_ex in DIAGRAMS:
        package_id = ids["kern"] if pkg == 2 else ids["overig"]
        w(f"\t\t\t<diagram {a(xmi__id=eaid(g))}>")
        w(f"\t\t\t\t<model {a(package=package_id, localID=str(dia_id), owner=package_id)}/>")
        w(f"\t\t\t\t<properties {a(name=name, type=typ)}/>")
        w(f"\t\t\t\t<project {a(author=AUTHOR, version='1.0', created=CREATED, modified=MODIFIED)}/>")
        w(f"\t\t\t\t<style1 {a(value=xmi_style1(pdata))}/>")
        w(f"\t\t\t\t<style2 {a(value=style_ex)}/>")
        w("\t\t\t\t<elements>")
        for d, obj_id, x, y, width, height, seq, style in DIAGRAM_OBJECTS:
            if d != dia_id:
                continue
            geometry = f"Left={x};Top={y};Right={x + width};Bottom={y + height};"
            w(f"\t\t\t\t\t<element {a(geometry=geometry, subject=obj_ids[obj_id], seqno=str(seq), style=style)}/>")
        for d, conn_id, style, hidden, points in DIAGRAM_LINKS:
            if d != dia_id:
                continue
            conn_xmi = eaid(next(c[5] for c in CONNECTORS if c[0] == conn_id))
            edge_path = "".join(f"{px}:{py}$" for px, py in points)
            w(
                f"\t\t\t\t\t<element {a(geometry=EDGE_GEOMETRY + 'Path=' + edge_path + ';', subject=conn_xmi, style=style + f'Hidden={hidden};')}/>"
            )
        w("\t\t\t\t</elements>")
        w("\t\t\t</diagram>")
    w("\t\t</diagrams>")
    w("\t</xmi:Extension>")
    w("</xmi:XMI>")
    with open(path, "w", encoding="windows-1252", newline="\n") as f:
        f.write("\n".join(out) + "\n")


if __name__ == "__main__":
    write_qea(QEA_OUT)
    write_xmi(XMI_OUT)
    for path in (QEA_OUT, XMI_OUT):
        print(f"{path}: {os.path.getsize(path)} bytes")
