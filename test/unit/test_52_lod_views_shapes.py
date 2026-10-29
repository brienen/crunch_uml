"""
Tests voor de views (deelmodellen per diagram) en de gescheiden SHACL-shapes
van de LOD-export (``--lod_views_dir``, ``--lod_views_exclude``,
``--lod_shapes_file``), plus de bijbehorende IRI-regels: volgnummers vallen
uit pakketsegmenten ('99 Kern' -> kern, '3 Economie' -> economie) en de
versie blijft leesbaar in owl:versionIRI en de view-IRI's (v1.0, niet v1-0).

Het testmodel wordt programmatisch opgebouwd, met de EA-conventies van het
GGM: een modelknoop met een naamgenoot eronder, domeinpakketten met een
volgnummer, en de diagrammen in packages 'Diagram'.
"""

import logging
import os
import shutil

import pytest
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SH, SKOS, XSD

import crunch_uml.schema as sch
from crunch_uml import cli, const, db
from crunch_uml.renderers.lod_mim import MIM
from crunch_uml.renderers.lodrenderer import strip_order_prefix
from crunch_uml.renderers.mim import version_segment

SCHEMA = "lod_views"
BASE = "https://voorbeeld.nl/lod/"
OUTPUT = "./test/output/lod_views.ttl"
SHAPES = "./test/output/lod_views-shapes.ttl"
VIEWS = "./test/output/lod_views_views"
SHAPES_IRI = URIRef(BASE + "shapes/")

BAG = BASE + "kern/bag/"
ECO = BASE + "economie/"
PAND = URIRef(BAG + "pand")
VERBLIJFSOBJECT = URIRef(BAG + "verblijfsobject")
ONDERZOEK = URIRef(BAG + "onderzoek")
GEBOUWD_OBJECT = URIRef(BAG + "gebouwd-object")
WOONPLAATS = URIRef(BAG + "woonplaats")
TYPE_STATUS = URIRef(BAG + "typestatus")
ENERGIELABEL = URIRef(BAG + "energielabel")
KERN_ENUMS = BASE + "kern/enumeratiesoort/"
INDICATIE = URIRef(KERN_ENUMS + "indicatie")
AANTAL = URIRef(BAG + "aantal")
VESTIGING = URIRef(ECO + "vestiging")
GEO_WKT = URIRef("http://www.opengis.net/ont/geosparql#wktLiteral")


def bouw_model():
    database = db.Database(const.DATABASE_URL, db_create=True)
    schema = sch.Schema(database, SCHEMA)

    def pkg(id, name, parent=None):
        schema.save(db.Package(id=id, name=name, parent_package_id=parent))

    def cls(id, name, package, stereotype="Objecttype", **kwargs):
        schema.save(db.Class(id=id, name=name, package_id=package, stereotype=stereotype, **kwargs))

    def attr(id, name, clazz, primitive=None, enumeration=None, type_class=None):
        schema.save(
            db.Attribute(
                id=id,
                name=name,
                clazz_id=clazz,
                primitive=primitive,
                enumeration_id=enumeration,
                type_class_id=type_class,
            )
        )

    def assoc(id, name, src, dst):
        schema.save(db.Association(id=id, name=name, src_class_id=src, dst_class_id=dst))

    def gener(id, sub, sup):
        schema.save(db.Generalization(id=id, subclass_id=sub, superclass_id=sup))

    # EA-modelknoop en het informatiemodelpakket met dezelfde naam.
    pkg("EAPK_ROOT", "Gegevensmodel Test")
    pkg("EAPK_TOP", "Gegevensmodel Test", "EAPK_ROOT")

    # Domein '99 Kern' met model 'Model BAG'; de diagrammen in 'Diagram'.
    pkg("EAPK_KERN", "99 Kern", "EAPK_TOP")
    pkg("EAPK_BAG", "Model BAG", "EAPK_KERN")
    pkg("EAPK_BAG_DIAGRAM", "Diagram", "EAPK_BAG")
    cls("EAID_GEBOUWD", "Gebouwd object", "EAPK_BAG")
    cls("EAID_PAND", "Pand", "EAPK_BAG")
    cls("EAID_VBO", "Verblijfsobject", "EAPK_BAG")
    cls("EAID_ONDERZOEK", "Onderzoek", "EAPK_BAG")
    cls("EAID_WOONPLAATS", "Woonplaats", "EAPK_BAG")
    # Zonder stereotype maar met EA-objecttype 'class': een gewone klasse (Aantal in
    # het GGM); een ProxyConnector met objecttype blijft technisch, ook mét stereotype.
    cls("EAID_AANTAL", "Aantal", "EAPK_BAG", stereotype=None, object_type="class")
    cls("EAID_PROXY", "Proxy", "EAPK_BAG", stereotype="Objecttype", object_type="proxyconnector")
    schema.save(db.Enumeratie(id="EAID_TYPESTATUS", name="TypeStatus", package_id="EAPK_BAG"))
    schema.save(db.EnumerationLiteral(id="EAID_LIT_ACTIEF", name="actief", enumeratie_id="EAID_TYPESTATUS"))
    # Spatie aan het eind, zoals EA die bewaart.
    schema.save(db.EnumerationLiteral(id="EAID_LIT_VERVALLEN", name="vervallen ", enumeratie_id="EAID_TYPESTATUS"))
    # Waarden met dezelfde slug: A, A+ en A++ worden a, a-2, a-3.
    schema.save(db.Enumeratie(id="EAID_ENERGIELABEL", name="Energielabel", package_id="EAPK_BAG"))
    for lid, naam in (("EAID_LIT_APP", "A++"), ("EAID_LIT_A", "A"), ("EAID_LIT_AP", "A+"), ("EAID_LIT_B", "B")):
        schema.save(db.EnumerationLiteral(id=lid, name=naam, enumeratie_id="EAID_ENERGIELABEL"))
    attr("EAID_PAND_ID", "identificatie", "EAID_PAND", "AN16")
    attr("EAID_PAND_STATUS", "status", "EAID_PAND", enumeration="EAID_TYPESTATUS")
    attr("EAID_PAND_LABEL", "energielabel", "EAID_PAND", enumeration="EAID_ENERGIELABEL")
    # Attributen getypeerd via de classifier naar DataType-elementen met de naam van
    # een primitief datatype (MIM11 CharacterString, GML GM_Point): datatype-properties.
    pkg("EAPK_MIM11", "MIM11 Primitieve datatypen", "EAPK_TOP")
    cls(
        "EAID_CHARACTERSTRING",
        "CharacterString",
        "EAPK_MIM11",
        stereotype=None,
        is_datatype=True,
        object_type="datatype",
    )
    pkg("EAPK_GML", "GML3", "EAPK_ROOT")
    cls("EAID_GM_POINT", "GM_Point", "EAPK_GML", stereotype=None, is_datatype=True, object_type="datatype")
    attr("EAID_PAND_NAAM", "naam", "EAID_PAND", "CharacterString", type_class="EAID_CHARACTERSTRING")
    attr("EAID_PAND_PUNT", "punt", "EAID_PAND", "GM_Point", type_class="EAID_GM_POINT")
    attr("EAID_VBO_OPP", "oppervlakte", "EAID_VBO", "N6")
    # Pakket met alleen enumeraties naast het model (GGM: 'Enumeratiesoort'): ook een model,
    # met IRI's langs de pakketboom; Woonplaats gebruikt zo'n enumeratie.
    pkg("EAPK_KERN_ENUMS", "Enumeratiesoort", "EAPK_KERN")
    schema.save(db.Enumeratie(id="EAID_INDICATIE", name="Indicatie", package_id="EAPK_KERN_ENUMS"))
    for lid, naam in (("EAID_LIT_JA", "ja"), ("EAID_LIT_NEE", "nee")):
        schema.save(db.EnumerationLiteral(id=lid, name=naam, enumeratie_id="EAID_INDICATIE"))
    attr("EAID_WOONPLAATS_IND", "indicatie", "EAID_WOONPLAATS", enumeration="EAID_INDICATIE")
    attr("EAID_ONDERZOEK_DATUM", "datum", "EAID_ONDERZOEK", "Datum")
    assoc("EAID_AS_HEEFT", "heeft", "EAID_PAND", "EAID_VBO")
    assoc("EAID_AS_BETREFT", "betreft", "EAID_ONDERZOEK", "EAID_PAND")
    assoc("EAID_AS_LIGT_IN", "ligt in", "EAID_PAND", "EAID_WOONPLAATS")
    gener("EAID_GEN_PAND", "EAID_PAND", "EAID_GEBOUWD")

    # Model '3 Economie' direct onder het informatiemodel, diagram in het modelpakket zelf.
    pkg("EAPK_ECO", "3 Economie", "EAPK_TOP")
    cls("EAID_VESTIGING", "Vestiging", "EAPK_ECO")
    attr("EAID_VESTIGING_KVK", "kvknummer", "EAID_VESTIGING", "AN8")

    # EA-conventie 'Mobiliteit' > 'Model Mobiliteit': het model gaat op in zijn ouder.
    pkg("EAPK_MOB", "Mobiliteit", "EAPK_TOP")
    pkg("EAPK_MOB_MODEL", "Model Mobiliteit", "EAPK_MOB")
    cls("EAID_WEG", "Weg", "EAPK_MOB_MODEL")

    # Diagrammen intern gebruik: standaard uitgesloten.
    pkg("EAPK_INTERN", "Diagrammen intern gebruik", "EAPK_TOP")

    session = schema.get_session()

    def diagram(id, name, package, classes=(), enums=(), hidden_assocs=(), hidden_gens=()):
        d = db.Diagram(id=id, name=name, package_id=package, schema_id=SCHEMA)
        for class_id in classes:
            d.diagram_classes.append(db.DiagramClass(diagram_id=id, schema_id=SCHEMA, class_id=class_id))
        for enum_id in enums:
            d.diagram_enumerations.append(
                db.DiagramEnumeration(diagram_id=id, schema_id=SCHEMA, enumeration_id=enum_id)
            )
        for assoc_id in hidden_assocs:
            d.diagram_associations.append(
                db.DiagramAssociation(diagram_id=id, schema_id=SCHEMA, association_id=assoc_id, hidden=True)
            )
        for gener_id in hidden_gens:
            d.diagram_generalizations.append(
                db.DiagramGeneralization(diagram_id=id, schema_id=SCHEMA, generalization_id=gener_id, hidden=True)
            )
        session.add(d)

    # 'Onderzoek': drie klassen en de enumeratie; 'heeft' is op dit diagram verborgen,
    # Woonplaats en Gebouwd object staan er niet op.
    diagram(
        "EAID_DIA_ONDERZOEK",
        "Onderzoek",
        "EAPK_BAG_DIAGRAM",
        classes=("EAID_ONDERZOEK", "EAID_PAND", "EAID_VBO"),
        enums=("EAID_TYPESTATUS",),
        hidden_assocs=("EAID_AS_HEEFT",),
    )
    # 'BAG': de generalisatie staat erop.
    diagram(
        "EAID_DIA_BAG", "BAG", "EAPK_BAG_DIAGRAM", classes=("EAID_GEBOUWD", "EAID_PAND", "EAID_VBO", "EAID_WOONPLAATS")
    )
    # Een naamgenoot in hetzelfde pakket: zelfde pad, wordt overgeslagen.
    diagram("EAID_DIA_ONDERZOEK2", "Onderzoek", "EAPK_BAG_DIAGRAM", classes=("EAID_WOONPLAATS",))
    # Economie: 'KVK' en een diagram met de naam van een klasse.
    diagram("EAID_DIA_KVK", "KVK", "EAPK_ECO", classes=("EAID_VESTIGING",))
    diagram("EAID_DIA_VESTIGING", "Vestiging", "EAPK_ECO", classes=("EAID_VESTIGING",))
    # Leeg (alleen pakketten) en intern: geen view.
    diagram("EAID_DIA_LEEG", "Overzicht", "EAPK_KERN")
    diagram("EAID_DIA_INTERN", "Intern", "EAPK_INTERN", classes=("EAID_PAND",))

    database.commit()


def exporteer(outputfile=OUTPUT, extra=()):
    cli.main(
        [
            "-sch",
            SCHEMA,
            "export",
            "-f",
            outputfile,
            "-t",
            "ttl",
            "--linked_data_namespace",
            BASE,
            "--lod_language",
            "",
            *extra,
        ]
    )
    graph = Graph()
    graph.parse(outputfile, format="turtle")
    return graph


def lees(path):
    graph = Graph()
    graph.parse(path, format="turtle")
    return graph


def kopregel(path):
    with open(path, encoding="utf-8") as file:
        return file.readline().rstrip("\n")


@pytest.fixture(scope="module")
def export():
    """Eén export met versie, gescheiden shapes en views; daarnaast de
    ongesplitste export om de verdeling te controleren."""
    bouw_model()
    shutil.rmtree(VIEWS, ignore_errors=True)
    volledig = exporteer("./test/output/lod_views_volledig.ttl", ["--lod_version", "v1.0"])
    ontologie = exporteer(
        OUTPUT,
        ["--lod_version", "v1.0", "--lod_shapes_file", SHAPES, "--lod_views_dir", VIEWS],
    )
    yield {"volledig": volledig, "ontologie": ontologie, "shapes": lees(SHAPES)}
    for path in (OUTPUT, SHAPES, "./test/output/lod_views_volledig.ttl"):
        if os.path.exists(path):
            os.remove(path)
    shutil.rmtree(VIEWS, ignore_errors=True)


# ---------------------------------------------------------------------------
# IRI-regels: volgnummers en versiesegment
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "naam, verwacht",
    [
        ("99 Kern", "Kern"),
        ("3 Economie", "Economie"),
        ("0 Bestuur, Politiek en Ondersteuning", "Bestuur, Politiek en Ondersteuning"),
        ("10. Dienstverlening", "Dienstverlening"),
        ("Kern", "Kern"),
        ("2024", "2024"),
        ("3D Model", "3D Model"),
        ("", ""),
        (None, ""),
    ],
)
def test_volgnummer_valt_uit_pakketnaam(naam, verwacht):
    assert strip_order_prefix(naam) == verwacht


@pytest.mark.parametrize(
    "versie, verwacht",
    [("v3.0.0", "v3.0.0"), ("3.0.0", "3.0.0"), ("v1.2 (concept)", "v1.2-concept"), ("  ", None), (None, None)],
)
def test_versiesegment(versie, verwacht):
    assert version_segment(versie) == verwacht


def test_pakketsegmenten_zonder_volgnummer_en_versie_iri(export):
    ontologie = export["ontologie"]
    assert (VESTIGING, RDF.type, OWL.Class) in ontologie
    assert (PAND, RDF.type, OWL.Class) in ontologie
    assert (URIRef(BASE + "kern/"), RDF.type, MIM.Domein) in ontologie
    assert (URIRef(BAG), DCTERMS.isPartOf, URIRef(BASE + "kern/")) in ontologie
    # De naamgenoot van de wortel ('Gegevensmodel Test' onder 'Gegevensmodel Test') is transparant.
    assert (URIRef(BASE + "kern/"), DCTERMS.isPartOf, URIRef(BASE)) in ontologie
    assert (URIRef(BASE + "mim11-primitieve-datatypen/"), RDF.type, OWL.Ontology) in ontologie
    # 'Mobiliteit' > 'Model Mobiliteit' wordt één segment; het model vertegenwoordigt het pakket.
    assert (URIRef(BASE + "mobiliteit/weg"), RDF.type, OWL.Class) in ontologie
    assert (URIRef(BASE + "mobiliteit/weg"), RDFS.isDefinedBy, URIRef(BASE + "mobiliteit/")) in ontologie
    assert set(ontologie.objects(URIRef(BASE + "mobiliteit/"), DCTERMS.identifier)) == {Literal("EAPK_MOB_MODEL")}
    assert (URIRef(BASE + "mobiliteit/"), DCTERMS.isPartOf, URIRef(BASE)) in ontologie
    assert (URIRef(BASE), OWL.imports, URIRef(BASE + "mobiliteit/")) in ontologie
    assert (None, DCTERMS.identifier, Literal("EAPK_MOB")) not in ontologie
    assert (URIRef(BASE + "mobiliteit/mobiliteit/"), None, None) not in ontologie
    assert (URIRef(BASE), OWL.versionIRI, URIRef(BASE + "v1.0/")) in ontologie
    assert not [s for s in ontologie.subjects() if "99-kern" in str(s) or "3-economie" in str(s)]


# ---------------------------------------------------------------------------
# SHACL-shapes apart
# ---------------------------------------------------------------------------


def test_ontologie_bevat_geen_shacl(export):
    ontologie = export["ontologie"]
    sh_prefix = str(SH)
    assert not [p for p in ontologie.predicates() if str(p).startswith(sh_prefix)]
    assert not [s for s in ontologie.subjects() if isinstance(s, BNode)]
    assert not [s for s in ontologie.subjects() if str(s).startswith(str(SHAPES_IRI))]
    assert (None, RDF.type, SH.NodeShape) not in ontologie
    # De inhoud is er nog wel: klassen, properties, MIM-metagegevens.
    assert (PAND, RDF.type, MIM.Objecttype) in ontologie
    assert (URIRef(BAG + "pand/identificatie"), RDF.type, OWL.DatatypeProperty) in ontologie
    assert (URIRef(BAG + "pand/identificatie"), MIM.kardinaliteit, Literal("1..1")) in ontologie


def test_shapes_bevat_alle_shacl_en_importeert_de_ontologie(export):
    shapes = export["shapes"]
    pand_shape = URIRef(BASE + "shapes/kern/bag/pand")
    assert (pand_shape, RDF.type, SH.NodeShape) in shapes
    assert (pand_shape, SH.targetClass, PAND) in shapes
    paden = {o for s in shapes.objects(pand_shape, SH.property) for o in shapes.objects(s, SH.path)}
    assert paden == {
        URIRef(BAG + "pand/identificatie"),
        URIRef(BAG + "pand/status"),
        URIRef(BAG + "pand/energielabel"),
        URIRef(BAG + "pand/naam"),
        URIRef(BAG + "pand/punt"),
        URIRef(BAG + "pand/heeft"),
        URIRef(BAG + "pand/ligt-in"),
    }
    # sh:in-lijst van de enumeratie-attribuut staat in de shapes.
    status_shape = next(s for s in shapes.subjects(SH.path, URIRef(BAG + "pand/status")))
    assert (status_shape, SH["in"], None) in shapes
    # Zelfbeschrijving en verwijzing.
    assert (SHAPES_IRI, RDF.type, OWL.Ontology) in shapes
    assert (SHAPES_IRI, OWL.imports, URIRef(BASE)) in shapes
    assert (SHAPES_IRI, OWL.versionInfo, Literal("v1.0")) in shapes
    assert (SHAPES_IRI, RDFS.label, Literal("Gegevensmodel Test (SHACL)")) in shapes
    assert (URIRef(BASE), RDFS.seeAlso, SHAPES_IRI) in export["ontologie"]
    # Geen ontologie-inhoud in de shapes.
    assert (PAND, RDF.type, OWL.Class) not in shapes
    assert (PAND, RDFS.label, None) not in shapes


def test_ontologie_plus_shapes_is_de_volledige_export(export):
    samen = Graph()
    samen += export["ontologie"]
    samen += export["shapes"]
    samen.remove((SHAPES_IRI, None, None))
    samen.remove((URIRef(BASE), RDFS.seeAlso, SHAPES_IRI))
    assert isomorphic(samen, export["volledig"])


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


def test_welke_views_er_zijn(export):
    paden = sorted(
        os.path.relpath(os.path.join(root, name), VIEWS) for root, _, names in os.walk(VIEWS) for name in names
    )
    assert paden == ["economie/kvk.ttl", "economie/vestiging.ttl", "kern/bag/bag.ttl", "kern/bag/onderzoek.ttl"]


def test_view_onderzoek_inhoud(export):
    path = os.path.join(VIEWS, "kern", "bag", "onderzoek.ttl")
    assert kopregel(path) == f"# graph: <{BASE}v1.0/kern/bag/onderzoek>"
    view = lees(path)
    view_iri = URIRef(BASE + "v1.0/kern/bag/onderzoek")

    # Zelfbeschrijving.
    assert (view_iri, RDF.type, OWL.Ontology) in view
    assert (view_iri, RDFS.label, Literal("Onderzoek")) in view
    assert (view_iri, DCTERMS.identifier, Literal("EAID_DIA_ONDERZOEK")) in view
    assert (view_iri, DCTERMS.isPartOf, URIRef(BASE)) in view
    assert (view_iri, OWL.versionInfo, Literal("v1.0")) in view

    # Klassen op het diagram met dezelfde IRI's en typering als de ontologie.
    for klasse in (ONDERZOEK, PAND, VERBLIJFSOBJECT):
        assert (klasse, RDF.type, OWL.Class) in view, klasse
        assert (klasse, RDF.type, MIM.Objecttype) in view, klasse
    assert (WOONPLAATS, None, None) not in view
    assert (GEBOUWD_OBJECT, None, None) not in view
    assert (VESTIGING, None, None) not in view

    # Al hun attributen, ook die naar iets buiten het diagram verwijzen (als referentie).
    assert (URIRef(BAG + "pand/identificatie"), RDFS.domain, PAND) in view
    assert (URIRef(BAG + "pand/status"), RDFS.range, TYPE_STATUS) in view
    assert (URIRef(BAG + "verblijfsobject/oppervlakte"), RDFS.domain, VERBLIJFSOBJECT) in view
    assert (URIRef(BAG + "onderzoek/datum"), RDFS.domain, ONDERZOEK) in view

    # Relaties: 'betreft' (beide op het diagram) wel, 'heeft' ook al is die op dit
    # diagram verborgen (de view volgt de elementen, niet de tekenwijze), 'ligt in'
    # (Woonplaats niet op het diagram) niet.
    assert (URIRef(BAG + "onderzoek/betreft"), RDF.type, OWL.ObjectProperty) in view
    assert (URIRef(BAG + "onderzoek/betreft"), MIM.doel, PAND) in view
    assert (URIRef(BAG + "pand/heeft"), RDFS.range, VERBLIJFSOBJECT) in view
    assert (URIRef(BAG + "pand/ligt-in"), None, None) not in view

    # Generalisatie naar een klasse buiten het diagram valt weg.
    assert (PAND, RDFS.subClassOf, GEBOUWD_OBJECT) not in view

    # Enumeratie met waarden (label zonder de spatie uit EA).
    assert (TYPE_STATUS, RDF.type, SKOS.ConceptScheme) in view
    assert (URIRef(BAG + "typestatus/actief"), SKOS.inScheme, TYPE_STATUS) in view
    assert (URIRef(BAG + "typestatus/vervallen"), RDF.type, MIM.Enumeratiewaarde) in view
    assert (URIRef(BAG + "typestatus/vervallen"), SKOS.prefLabel, Literal("vervallen")) in view

    # Geen SHACL en geen pakketten.
    assert not [p for p in view.predicates() if str(p).startswith(str(SH))]
    assert not [s for s in view.subjects() if isinstance(s, BNode)]
    assert (URIRef(BASE), None, None) not in view
    assert (URIRef(BAG), None, None) not in view


def test_view_bag_houdt_generalisatie_en_relatie(export):
    view = lees(os.path.join(VIEWS, "kern", "bag", "bag.ttl"))
    assert (PAND, RDFS.subClassOf, GEBOUWD_OBJECT) in view
    assert (URIRef(BAG + "pand/heeft"), RDFS.range, VERBLIJFSOBJECT) in view
    assert (URIRef(BAG + "pand/ligt-in"), RDFS.range, WOONPLAATS) in view
    assert (ONDERZOEK, None, None) not in view
    assert (URIRef(BASE + "v1.0/kern/bag/bag"), RDFS.label, Literal("BAG")) in view
    # De enumeraties staan niet op dit diagram maar zijn het type van een attribuut
    # van Pand: ze gaan mee, met hun waarden.
    assert (TYPE_STATUS, RDF.type, SKOS.ConceptScheme) in view
    assert (URIRef(BAG + "typestatus/actief"), SKOS.inScheme, TYPE_STATUS) in view
    assert (URIRef(BAG + "energielabel/a-3"), SKOS.prefLabel, Literal("A++")) in view


def test_waarden_met_dezelfde_slug_krijgen_een_volgnummer(export):
    """A, A+ en A++ van Energielabel werden alle drie {enum}/a; nu a, a-2, a-3,
    alfabetisch, en de sh:in-lijst van het attribuut noemt alle vier de waarden."""
    ontologie = export["ontologie"]
    assert (URIRef(BAG + "energielabel/a"), SKOS.prefLabel, Literal("A")) in ontologie
    assert (URIRef(BAG + "energielabel/a-2"), SKOS.prefLabel, Literal("A+")) in ontologie
    assert (URIRef(BAG + "energielabel/a-3"), SKOS.prefLabel, Literal("A++")) in ontologie
    assert (URIRef(BAG + "energielabel/b"), SKOS.prefLabel, Literal("B")) in ontologie
    assert len(set(ontologie.subjects(SKOS.inScheme, ENERGIELABEL))) == 4
    shapes = export["shapes"]
    label_shape = next(s for s in shapes.subjects(SH.path, URIRef(BAG + "pand/energielabel")))
    lijst = next(shapes.objects(label_shape, SH["in"]))
    from rdflib.collection import Collection

    assert set(Collection(shapes, lijst)) == {
        URIRef(BAG + "energielabel/a"),
        URIRef(BAG + "energielabel/a-2"),
        URIRef(BAG + "energielabel/a-3"),
        URIRef(BAG + "energielabel/b"),
    }


def test_typeklasse_met_naam_van_primitief_datatype_is_datatype_property(export):
    """Een attribuut dat via zijn classifier naar het DataType-element CharacterString
    of GM_Point verwijst (zo staan de MIM11- en GML-datatypen in het GGM) wordt een
    owl:DatatypeProperty met het XSD- of GeoSPARQL-type, geen owl:ObjectProperty."""
    ontologie = export["ontologie"]
    naam = URIRef(BAG + "pand/naam")
    assert (naam, RDF.type, OWL.DatatypeProperty) in ontologie
    assert (naam, RDFS.range, XSD.string) in ontologie
    assert (naam, RDF.type, OWL.ObjectProperty) not in ontologie
    punt = URIRef(BAG + "pand/punt")
    assert (punt, RDF.type, OWL.DatatypeProperty) in ontologie
    assert (punt, RDFS.range, GEO_WKT) in ontologie
    shapes = export["shapes"]
    naam_shape = next(s for s in shapes.subjects(SH.path, naam))
    assert (naam_shape, SH.datatype, XSD.string) in shapes
    assert (naam_shape, SH.node, None) not in shapes


def test_klassen_op_ea_objecttype(export):
    """Met een objecttype beslist dat: 'Aantal' zonder stereotype is een klasse,
    de ProxyConnector met stereotype niet."""
    ontologie = export["ontologie"]
    assert (AANTAL, RDF.type, OWL.Class) in ontologie
    assert (URIRef(BAG + "proxy"), None, None) not in ontologie


def test_view_is_deelgraaf_van_de_ontologie(export):
    ontologie = export["ontologie"]
    for pad in ("kern/bag/onderzoek", "kern/bag/bag", "economie/kvk"):
        view = lees(os.path.join(VIEWS, *pad.split("/")) + ".ttl")
        view.remove((URIRef(BASE + "v1.0/" + pad), None, None))
        ontbreekt = [t for t in view if t not in ontologie]
        assert not ontbreekt, (pad, ontbreekt[:5])


def test_diagram_in_modelpakket_zonder_domein(export):
    """'3 Economie' ligt direct onder het informatiemodel: pad economie/kvk,
    zonder het wortelpakket en zonder diens naamgenoot."""
    path = os.path.join(VIEWS, "economie", "kvk.ttl")
    assert kopregel(path) == f"# graph: <{BASE}v1.0/economie/kvk>"
    view = lees(path)
    assert (VESTIGING, RDF.type, OWL.Class) in view
    assert (URIRef(ECO + "vestiging/kvknummer"), RDFS.domain, VESTIGING) in view


def test_zonder_versie_geen_versiesegment_en_botsing_gemeld(caplog):
    """Zonder --lod_version staat de view op {basis}{pad}; het diagram 'Vestiging'
    in Economie botst dan met de klasse-IRI en krijgt geen zelfbeschrijving."""
    views = "./test/output/lod_views_zonder_versie"
    shutil.rmtree(views, ignore_errors=True)
    try:
        with caplog.at_level(logging.WARNING):
            exporteer("./test/output/lod_views_zv.ttl", ["--lod_views_dir", views])
        assert kopregel(os.path.join(views, "economie", "kvk.ttl")) == f"# graph: <{BASE}economie/kvk>"
        kvk = lees(os.path.join(views, "economie", "kvk.ttl"))
        assert (URIRef(BASE + "economie/kvk"), RDF.type, OWL.Ontology) in kvk
        assert (URIRef(BASE + "economie/kvk"), OWL.versionInfo, None) not in kvk
        vestiging = lees(os.path.join(views, "economie", "vestiging.ttl"))
        assert (VESTIGING, RDF.type, OWL.Class) in vestiging
        assert (VESTIGING, RDF.type, OWL.Ontology) not in vestiging
        assert any("economie/vestiging" in r.message and "al een term" in r.message for r in caplog.records)
        assert any("hetzelfde pad" in r.message and "EAID_DIA_ONDERZOEK2" in r.message for r in caplog.records)
    finally:
        shutil.rmtree(views, ignore_errors=True)
        if os.path.exists("./test/output/lod_views_zv.ttl"):
            os.remove("./test/output/lod_views_zv.ttl")


def test_uitsluiting_op_naam_en_uitzetten(export):
    """Standaard valt 'Diagrammen intern gebruik' af; met een eigen patroon
    vallen de BAG-diagrammen af; met '' wordt niets uitgesloten."""
    views = "./test/output/lod_views_excl"
    try:
        shutil.rmtree(views, ignore_errors=True)
        exporteer(
            "./test/output/lod_views_excl.ttl", ["--lod_views_dir", views, "--lod_views_exclude", "Model BAG,KVK"]
        )
        # Eigen patronen vervangen de standaardlijst, dus 'Intern' komt terug.
        paden = {os.path.relpath(os.path.join(r, n), views) for r, _, ns in os.walk(views) for n in ns}
        assert paden == {"economie/vestiging.ttl", "diagrammen-intern-gebruik/intern.ttl"}
        shutil.rmtree(views, ignore_errors=True)
        exporteer("./test/output/lod_views_excl.ttl", ["--lod_views_dir", views, "--lod_views_exclude", ""])
        paden = {os.path.relpath(os.path.join(r, n), views) for r, _, ns in os.walk(views) for n in ns}
        assert "diagrammen-intern-gebruik/intern.ttl" in paden
    finally:
        shutil.rmtree(views, ignore_errors=True)
        if os.path.exists("./test/output/lod_views_excl.ttl"):
            os.remove("./test/output/lod_views_excl.ttl")


def test_views_zonder_shapes_bestand_blijven_zonder_shacl(export):
    """Ook als het uitvoerbestand ontologie en shapes samen bevat, zijn de views
    deelgrafen zonder SHACL."""
    views = "./test/output/lod_views_samen"
    try:
        shutil.rmtree(views, ignore_errors=True)
        samen = exporteer("./test/output/lod_views_samen.ttl", ["--lod_views_dir", views])
        assert (None, RDF.type, SH.NodeShape) in samen
        view = lees(os.path.join(views, "kern", "bag", "bag.ttl"))
        assert not [p for p in view.predicates() if str(p).startswith(str(SH))]
        assert (PAND, RDF.type, OWL.Class) in view
    finally:
        shutil.rmtree(views, ignore_errors=True)
        if os.path.exists("./test/output/lod_views_samen.ttl"):
            os.remove("./test/output/lod_views_samen.ttl")


def test_rdf_en_jsonld_views_zonder_kopregel(export):
    """De andere linked-data-formaten schrijven views in hun eigen serialisatie,
    zonder Turtle-kopregel; de graph-IRI staat in de zelfbeschrijving."""
    views = "./test/output/lod_views_rdf"
    try:
        shutil.rmtree(views, ignore_errors=True)
        cli.main(
            [
                "-sch",
                SCHEMA,
                "export",
                "-f",
                "./test/output/lod_views_rdf.rdf",
                "-t",
                "rdf",
                "--linked_data_namespace",
                BASE,
                "--lod_version",
                "v1.0",
                "--lod_views_dir",
                views,
                "--lod_shapes_file",
                "./test/output/lod_views_rdf-shapes",
            ]
        )
        path = os.path.join(views, "kern", "bag", "bag.rdf")
        assert os.path.exists(path)
        assert not kopregel(path).startswith("# graph:")
        view = Graph().parse(path, format="xml")
        assert (URIRef(BASE + "v1.0/kern/bag/bag"), RDF.type, OWL.Ontology) in view
        assert os.path.exists("./test/output/lod_views_rdf-shapes.rdf")
        shapes = Graph().parse("./test/output/lod_views_rdf-shapes.rdf", format="xml")
        assert (SHAPES_IRI, OWL.imports, URIRef(BASE)) in shapes
    finally:
        shutil.rmtree(views, ignore_errors=True)
        for path in ("./test/output/lod_views_rdf.rdf", "./test/output/lod_views_rdf-shapes.rdf"):
            if os.path.exists(path):
                os.remove(path)


# ---------------------------------------------------------------------------
# 0.8.4: pakketten met alleen enumeraties en deterministische uitvoer
# ---------------------------------------------------------------------------


def test_enumeratiepakket_zonder_klassen_is_model(export):
    """Een pakket met alleen enumeraties ('Enumeratiesoort' naast het model) is een model:
    zijn enumeraties krijgen een IRI langs de pakketboom, niet de verzamel-IRI enumeraties/...,
    en het pakket is een ontologie in de hiërarchie."""
    ontologie, shapes = export["ontologie"], export["shapes"]
    assert (INDICATIE, RDF.type, MIM.Enumeratie) in ontologie
    assert (URIRef(KERN_ENUMS + "indicatie/ja"), SKOS.inScheme, INDICATIE) in ontologie
    assert (URIRef(KERN_ENUMS), RDF.type, OWL.Ontology) in ontologie
    assert (URIRef(BAG + "woonplaats/indicatie"), RDFS.range, INDICATIE) in ontologie
    wezen = [s for s in set(ontologie.subjects()) if str(s).startswith(BASE + "enumeraties/")]
    assert not wezen, wezen
    # De toegestane waarden staan in de sh:in-lijst van de shape van Woonplaats.
    assert (None, RDF.first, URIRef(KERN_ENUMS + "indicatie/ja")) in shapes


def test_export_is_deterministisch(export):
    """Twee exports van hetzelfde model geven byte-gelijke bestanden: de blank nodes van de
    property shapes dragen een label uit hun context, en rdflib sorteert objecten op label."""
    tweede = "./test/output/lod_views_2.ttl"
    tweede_shapes = "./test/output/lod_views_2-shapes.ttl"
    exporteer(tweede, ["--lod_version", "v1.0", "--lod_shapes_file", tweede_shapes])
    try:
        for eerste, latere in ((OUTPUT, tweede), (SHAPES, tweede_shapes)):
            with open(eerste, "rb") as fa, open(latere, "rb") as fb:
                assert fa.read() == fb.read(), f"{eerste} en {latere} verschillen"
    finally:
        for path in (tweede, tweede_shapes):
            if os.path.exists(path):
                os.remove(path)
