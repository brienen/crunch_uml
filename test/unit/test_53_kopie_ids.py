"""
Tests voor de id's van de kopieën die de copy transformer maakt (0.8.3).

Elke kopie houdt het id van haar bron, ook een enumeratie of klasse van buiten het
gekopieerde pakket: zo'n enumeratie wordt één keer meegekopieerd, hoeveel attributen
en diagrammen er ook naar verwijzen. Alleen een attribuut dat uit een superklasse in
een subklasse wordt gematerialiseerd krijgt een eigen, afgeleid id. Twee runs geven
daardoor dezelfde kopie. Voorheen kreeg elke enumeratie die buiten het pakket van de
klasse lag bij elk attribuut een nieuwe kopie met een uuid4 (GGM v3.0.0: 210
enumeraties en 1.905 waarden met per run een ander id), zodat elke export en elke
diff daarop verschilde.
"""

import re

import pytest

import crunch_uml.schema as sch
from crunch_uml import cli, const, db, ea_ids

pytestmark = pytest.mark.filterwarnings(":Object of type <.*> not in session")

EA_ID = re.compile(r"^EA(ID|PK)_[0-9A-Za-z]+(_[0-9A-Za-z]+)*$")
ROOT = "EAPK_GGM"


def bouw_model():
    """Een modelknoop met het te kopiëren pakket GGM en daarnaast pakket X buiten scope.

    GGM/A: K1 (status -> Status in GGM/B, indicatie -> Indicatie in X), K2 (indicatie -> Indicatie),
           Sub (subklasse van Super in X); diagram met K1, KOut (uit X) en Indicatie.
    GGM/B: enumeratie Status.
    X:     enumeratie Indicatie, KOut (indicatie -> Indicatie), Super (naam, indicatie, status).
    """
    database = db.Database(const.DATABASE_URL, db_create=True)
    schema = sch.Schema(database)
    schema_id = schema.schema_id

    def pkg(id, name, parent=None):
        schema.save(db.Package(id=id, name=name, parent_package_id=parent))

    def cls(id, name, package):
        schema.save(db.Class(id=id, name=name, package_id=package, stereotype="Objecttype"))

    def attr(id, name, clazz, primitive=None, enumeration=None):
        schema.save(db.Attribute(id=id, name=name, clazz_id=clazz, primitive=primitive, enumeration_id=enumeration))

    def enum(id, name, package, literals):
        schema.save(db.Enumeratie(id=id, name=name, package_id=package))
        for lid, lname in literals:
            schema.save(db.EnumerationLiteral(id=lid, name=lname, enumeratie_id=id))

    pkg("EAPK_MODEL", "Model")
    pkg(ROOT, "GGM", "EAPK_MODEL")
    pkg("EAPK_A", "A", ROOT)
    pkg("EAPK_A_DIAGRAM", "Diagram", "EAPK_A")
    pkg("EAPK_B", "B", ROOT)
    pkg("EAPK_X", "X", "EAPK_MODEL")

    enum("EAID_STATUS", "Status", "EAPK_B", (("EAID_L_ACTIEF", "actief"), ("EAID_L_VERVALLEN", "vervallen")))
    enum("EAID_INDICATIE", "Indicatie", "EAPK_X", (("EAID_L_JA", "ja"), ("EAID_L_NEE", "nee")))

    cls("EAID_K1", "K1", "EAPK_A")
    attr("EAID_K1_STATUS", "status", "EAID_K1", enumeration="EAID_STATUS")
    attr("EAID_K1_IND", "indicatie", "EAID_K1", enumeration="EAID_INDICATIE")
    cls("EAID_K2", "K2", "EAPK_A")
    attr("EAID_K2_IND", "indicatie", "EAID_K2", enumeration="EAID_INDICATIE")
    cls("EAID_SUB", "Sub", "EAPK_A")
    cls("EAID_KOUT", "KOut", "EAPK_X")
    attr("EAID_KOUT_IND", "indicatie", "EAID_KOUT", enumeration="EAID_INDICATIE")
    cls("EAID_SUPER", "Super", "EAPK_X")
    attr("EAID_SUPER_NAAM", "naam", "EAID_SUPER", "AN80")
    attr("EAID_SUPER_IND", "indicatie", "EAID_SUPER", enumeration="EAID_INDICATIE")
    attr("EAID_SUPER_STATUS", "status", "EAID_SUPER", enumeration="EAID_STATUS")
    schema.save(db.Generalization(id="EAID_GEN_SUB", subclass_id="EAID_SUB", superclass_id="EAID_SUPER"))

    d = db.Diagram(id="EAID_DIA", name="Overzicht", package_id="EAPK_A_DIAGRAM", schema_id=schema_id)
    for class_id in ("EAID_K1", "EAID_KOUT"):
        d.diagram_classes.append(db.DiagramClass(diagram_id="EAID_DIA", schema_id=schema_id, class_id=class_id))
    d.diagram_enumerations.append(
        db.DiagramEnumeration(diagram_id="EAID_DIA", schema_id=schema_id, enumeration_id="EAID_INDICATIE")
    )
    schema.get_session().add(d)
    database.commit()


def kopieer(naar, materialize=False):
    args = ["transform", "-ttp", "copy", "-sch_to", naar, "-rt_pkg", ROOT]
    if materialize:
        args += ["-m_gen", "True"]
    cli.main(args)
    return sch.Schema(db.Database(const.DATABASE_URL, db_create=False), naar)


def ids(schema, model):
    return {o.id for o in schema.get_session().query(model).filter_by(schema_id=schema.schema_id)}


def inhoud(schema):
    return {
        model.__name__: ids(schema, model)
        for model in (db.Package, db.Class, db.Enumeratie, db.EnumerationLiteral, db.Attribute)
    }


def test_materialized_attribute_id_is_deterministisch():
    a = ea_ids.materialized_attribute_id("EAID_SUPER_NAAM", "EAID_SUB")
    assert a == ea_ids.materialized_attribute_id("EAID_SUPER_NAAM", "EAID_SUB")
    assert a.startswith(ea_ids.MATERIALIZED_ID_PREFIX)
    assert EA_ID.match(a), "het id moet aan het EA-GUID-patroon van de LOD-export voldoen"
    assert a != ea_ids.materialized_attribute_id("EAID_SUPER_NAAM", "EAID_SUB2")
    assert a != ea_ids.materialized_attribute_id("EAID_SUPER_IND", "EAID_SUB")


def test_kopie_houdt_ids_en_is_herhaalbaar():
    bouw_model()
    k1 = inhoud(kopieer("kopie1"))
    k2 = inhoud(kopieer("kopie2"))
    assert k1 == k2, "twee runs van de copy transformer moeten dezelfde id's geven"

    # Alles in de kopie draagt het id van de bron; niets is nieuw gemunt.
    assert k1["Package"] == {ROOT, "EAPK_A", "EAPK_A_DIAGRAM", "EAPK_B"}
    assert k1["Class"] == {"EAID_K1", "EAID_K2", "EAID_SUB", "EAID_KOUT"}  # KOut via het diagram
    assert k1["Enumeratie"] == {"EAID_STATUS", "EAID_INDICATIE"}
    assert k1["EnumerationLiteral"] == {"EAID_L_ACTIEF", "EAID_L_VERVALLEN", "EAID_L_JA", "EAID_L_NEE"}
    assert k1["Attribute"] == {"EAID_K1_STATUS", "EAID_K1_IND", "EAID_K2_IND", "EAID_KOUT_IND"}

    schema = sch.Schema(db.Database(const.DATABASE_URL, db_create=False), "kopie1")
    # Indicatie ligt buiten GGM en wordt één keer meegekopieerd (diagram, K1, K2 en KOut delen die
    # kopie); Status ligt in GGM/B en komt met de boom mee, ook voor K1 in GGM/A.
    assert schema.count_enumeratie() == 2
    assert schema.count_enumeratieliteral() == 4
    indicatie = schema.get_enumeration("EAID_INDICATIE")
    assert indicatie.package.get_root_package().id == ROOT
    assert {lit.name for lit in indicatie.literals} == {"ja", "nee"}
    assert schema.get_enumeration("EAID_STATUS").package.id == "EAPK_B"
    for attr_id, enum_id in (
        ("EAID_K1_STATUS", "EAID_STATUS"),
        ("EAID_K1_IND", "EAID_INDICATIE"),
        ("EAID_K2_IND", "EAID_INDICATIE"),
        ("EAID_KOUT_IND", "EAID_INDICATIE"),
    ):
        assert schema.get_attribute(attr_id).enumeration_id == enum_id


def test_materialiseren_geeft_afgeleid_id():
    bouw_model()
    m1 = inhoud(kopieer("mat1", materialize=True))
    m2 = inhoud(kopieer("mat2", materialize=True))
    assert m1 == m2

    verwacht = {
        naam: ea_ids.materialized_attribute_id(bron, "EAID_SUB")
        for naam, bron in (
            ("naam", "EAID_SUPER_NAAM"),
            ("indicatie", "EAID_SUPER_IND"),
            ("status", "EAID_SUPER_STATUS"),
        )
    }
    assert m1["Class"] == {"EAID_K1", "EAID_K2", "EAID_SUB", "EAID_KOUT"}  # Super zelf blijft buiten de kopie
    assert m1["Attribute"] == {"EAID_K1_STATUS", "EAID_K1_IND", "EAID_K2_IND", "EAID_KOUT_IND", *verwacht.values()}
    assert m1["Enumeratie"] == {"EAID_STATUS", "EAID_INDICATIE"}  # ook gematerialiseerd: geen extra kopieën
    assert m1["EnumerationLiteral"] == {"EAID_L_ACTIEF", "EAID_L_VERVALLEN", "EAID_L_JA", "EAID_L_NEE"}

    schema = sch.Schema(db.Database(const.DATABASE_URL, db_create=False), "mat1")
    sub = schema.get_class("EAID_SUB")
    assert {a.name: a.id for a in sub.attributes} == verwacht
    assert all(EA_ID.match(a.id) for a in sub.attributes)
    assert schema.get_attribute(verwacht["indicatie"]).enumeration_id == "EAID_INDICATIE"
    assert schema.get_attribute(verwacht["status"]).enumeration_id == "EAID_STATUS"
