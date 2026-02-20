"""
Test dat MonumentenMIM.qea en MonumentenMIM.xml na inlezen gelijke data opleveren.

De twee bestanden worden in aparte schema's ingelezen en daarna vergeleken.
Bekend verschil: de XMI-parser maakt extra 'ownedAttribute'-records aan voor
navigeerbare associatie-eindpunten (herkenbaar aan EAID_dst-prefix). Deze
komen niet voor in t_attribute van de QEA en worden bij de vergelijking
buiten beschouwing gelaten.
"""

import crunch_uml.db as db
import crunch_uml.schema as sch
from crunch_uml import cli, const
from sqlalchemy.orm import Session


SCHEMA_QEA = "monumentenmim_qea"
SCHEMA_XMI = "monumentenmim_xmi"


def setup_module():
    cli.main([
        "-sch", SCHEMA_QEA,
        "import",
        "-f", "./test/data/MonumentenMIM.qea",
        "-t", "qea",
        "-db_create",
    ])
    cli.main([
        "-sch", SCHEMA_XMI,
        "import",
        "-f", "./test/data/MonumentenMIM.xml",
        "-t", "eaxmi",
    ])


def get_schemas():
    database = db.Database(const.DATABASE_URL, db_create=False)
    sq = sch.Schema(database, schema_name=SCHEMA_QEA)
    sx = sch.Schema(database, schema_name=SCHEMA_XMI)
    return database, sq, sx


def test_aantallen_gelijk():
    """Packages, classes, datatypes, enumeraties, literals, associaties en
    generalizations moeten gelijk zijn. Attributen worden apart getest omdat
    de XMI-parser extra navigatie-attributen aanmaakt (EAID_dst*)."""
    _, sq, sx = get_schemas()

    assert sq.count_package() == sx.count_package()
    assert sq.count_class() == sx.count_class()
    assert sq.count_datatype() == sx.count_datatype()
    assert sq.count_enumeratie() == sx.count_enumeratie()
    assert sq.count_enumeratieliteral() == sx.count_enumeratieliteral()
    assert sq.count_association() == sx.count_association()
    assert sq.count_generalizations() == sx.count_generalizations()


def test_attributen_gelijk_zonder_dst():
    """Het aantal attributen is gelijk als EAID_dst*-records (navigatie-eindpunten
    aangemaakt door de XMI-parser) buiten beschouwing worden gelaten."""
    database, _, _ = get_schemas()

    with Session(database.engine) as session:
        qea_count = (
            session.query(db.Attribute)
            .filter(db.Attribute.schema_id == SCHEMA_QEA)
            .count()
        )
        xmi_count = (
            session.query(db.Attribute)
            .filter(
                db.Attribute.schema_id == SCHEMA_XMI,
                ~db.Attribute.id.like("EAID_dst%"),
            )
            .count()
        )
    assert qea_count == xmi_count


def test_package_ids_gelijk():
    """Alle packages hebben in beide schema's dezelfde IDs."""
    database, _, _ = get_schemas()

    with Session(database.engine) as session:
        qea_ids = {
            p.id
            for p in session.query(db.Package).filter(db.Package.schema_id == SCHEMA_QEA)
        }
        xmi_ids = {
            p.id
            for p in session.query(db.Package).filter(db.Package.schema_id == SCHEMA_XMI)
        }
    assert qea_ids == xmi_ids


def test_class_ids_gelijk():
    """Alle classes en datatypes hebben in beide schema's dezelfde IDs."""
    database, _, _ = get_schemas()

    with Session(database.engine) as session:
        qea_ids = {
            c.id
            for c in session.query(db.Class).filter(db.Class.schema_id == SCHEMA_QEA)
        }
        xmi_ids = {
            c.id
            for c in session.query(db.Class).filter(db.Class.schema_id == SCHEMA_XMI)
        }
    assert qea_ids == xmi_ids


def test_enumeratie_ids_gelijk():
    """Alle enumeraties hebben in beide schema's dezelfde IDs."""
    database, _, _ = get_schemas()

    with Session(database.engine) as session:
        qea_ids = {
            e.id
            for e in session.query(db.Enumeratie).filter(db.Enumeratie.schema_id == SCHEMA_QEA)
        }
        xmi_ids = {
            e.id
            for e in session.query(db.Enumeratie).filter(db.Enumeratie.schema_id == SCHEMA_XMI)
        }
    assert qea_ids == xmi_ids


def test_associatie_ids_en_inhoud_gelijk():
    """Alle associaties hebben in beide schema's dezelfde IDs, namen,
    source- en destination-klassen."""
    database, _, _ = get_schemas()

    with Session(database.engine) as session:
        def assoc_dict(schema_id):
            return {
                a.id: (a.name, a.src_class_id, a.dst_class_id)
                for a in session.query(db.Association).filter(
                    db.Association.schema_id == schema_id
                )
            }

        qea = assoc_dict(SCHEMA_QEA)
        xmi = assoc_dict(SCHEMA_XMI)

    assert qea == xmi


def test_class_namen_gelijk():
    """Classes hebben in beide schema's dezelfde naam."""
    database, _, _ = get_schemas()

    with Session(database.engine) as session:
        qea_namen = {
            c.id: c.name
            for c in session.query(db.Class).filter(db.Class.schema_id == SCHEMA_QEA)
        }
        xmi_namen = {
            c.id: c.name
            for c in session.query(db.Class).filter(db.Class.schema_id == SCHEMA_XMI)
        }

    for cid in qea_namen:
        assert qea_namen[cid] == xmi_namen[cid], (
            f"Class {cid}: QEA naam={qea_namen[cid]}, XMI naam={xmi_namen[cid]}"
        )


def test_class_definities_gelijk_waar_aanwezig():
    """Als beide schema's een definitie hebben voor dezelfde class, moeten
    deze gelijk zijn. Een ontbrekende definitie aan één kant is toegestaan
    omdat XMI en QEA niet altijd dezelfde velden exporteren."""
    database, _, _ = get_schemas()

    with Session(database.engine) as session:
        qea_def = {
            c.id: c.definitie
            for c in session.query(db.Class).filter(db.Class.schema_id == SCHEMA_QEA)
        }
        xmi_def = {
            c.id: c.definitie
            for c in session.query(db.Class).filter(db.Class.schema_id == SCHEMA_XMI)
        }

    for cid in qea_def:
        q, x = qea_def[cid], xmi_def.get(cid)
        if q and x:
            assert q == x, (
                f"Class {cid}: QEA definitie={q!r}, XMI definitie={x!r}"
            )


def test_tagged_values_gelijk():
    """Tagged values (gemma_type, gemma_url, definitie) zijn gelijk voor classes."""
    database, sq, sx = get_schemas()

    # Steekproef: Bouwactiviteit
    bouwactiviteit_id = "EAID_4AD539EC_A308_43da_B025_17A1647303F3"
    cq = sq.get_class(bouwactiviteit_id)
    cx = sx.get_class(bouwactiviteit_id)

    assert cq is not None and cx is not None
    assert cq.name == cx.name
    assert cq.definitie == cx.definitie
    assert cq.gemma_type == cx.gemma_type
    assert cq.gemma_url == cx.gemma_url
