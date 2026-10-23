"""
Tests voor de reparaties van de LOD-renderer, geverifieerd op de GGM v3.0.0-export
(oktober 2026):

1. generalisaties stonden verkeerd om (``X rdfs:subClassOf X``; de echte
   generalisaties ontbraken);
2. spaties en haakjes in model-IRI's (``%20``, ``%28``) en een basis-URI met
   pad die door ``urljoin`` werd weggegooid;
3. 'model' werd overal uit de modelnaam geknipt, zodat het package ``Model``
   een lege naam kreeg;
4. gelijknamige associaties en attributen vielen samen tot één property met
   meerdere ranges;
5. technische packages (``Diagram``, ``Tekenwijze``, ``View*``) en klassen
   zonder stereotype kwamen in de ontologie terecht;
6. gelijknamige modelpakketten deelden één namespace;
7. lege of afwijkende identifiers bleven onopgemerkt.

Het testmodel wordt programmatisch opgebouwd (geen EA-fixture), zodat elke
situatie klein en expliciet is.
"""

import logging
import os

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SH, XSD

import crunch_uml.schema as sch
from crunch_uml import cli, const, db
from crunch_uml.renderers.lodrenderer import model_segment_name

SCHEMA = "lod_fixes"
# Basis-URI mét pad: urljoin(base, "/slug/") gooide dat pad weg.
BASE = "https://voorbeeld.nl/lod/"
OUTPUT = "./test/output/lod_fixes.ttl"


def bouw_model():
    database = db.Database(const.DATABASE_URL, db_create=True)
    schema = sch.Schema(database, SCHEMA)

    def pkg(id, name, parent=None):
        schema.save(db.Package(id=id, name=name, parent_package_id=parent))

    def cls(id, name, package, stereotype="Objecttype", **kwargs):
        schema.save(db.Class(id=id, name=name, package_id=package, stereotype=stereotype, **kwargs))

    def attr(id, name, clazz, primitive=None, type_class=None):
        schema.save(db.Attribute(id=id, name=name, clazz_id=clazz, primitive=primitive, type_class_id=type_class))

    def assoc(id, name, src, dst, src_role=None):
        schema.save(db.Association(id=id, name=name, src_class_id=src, dst_class_id=dst, src_role=src_role))

    def gener(id, sub, sup):
        schema.save(db.Generalization(id=id, subclass_id=sub, superclass_id=sup))

    pkg("EAPK_ROOT", "Gegevensmodel Test")

    # 1. Generalisaties: Medewerker en Burger zijn subklassen van Persoon.
    pkg("EAPK_KERN", "Kern", "EAPK_ROOT")
    cls("EAID_PERSOON", "Persoon", "EAPK_KERN")
    cls("EAID_MEDEWERKER", "Medewerker", "EAPK_KERN")
    cls("EAID_BURGER", "Burger", "EAPK_KERN")
    gener("EAID_GEN1", "EAID_MEDEWERKER", "EAID_PERSOON")
    gener("EAID_GEN2", "EAID_BURGER", "EAID_PERSOON")
    attr("EAID_PERSOON_NAAM", "naam", "EAID_PERSOON", "AN80")

    # 2. Spaties en haakjes in de modelnaam.
    pkg("EAPK_RGBZ", "Model Kern (RGBZ)", "EAPK_ROOT")
    cls("EAID_ZAAK", "Zaak", "EAPK_RGBZ")
    attr("EAID_ZAAK_ID", "identificatie", "EAID_ZAAK", "AN40")

    # 3. Naamopschoning: 'Model' kaal, 'Model' als deel van een woord, 'Model' achteraan.
    pkg("EAPK_MODEL", "Model", "EAPK_ROOT")
    cls("EAID_PERIODE", "Periode", "EAPK_MODEL")
    attr("EAID_PERIODE_START", "datum start", "EAID_PERIODE", "Datum")
    pkg("EAPK_WONEN", "Gegevensmodel Wonen", "EAPK_ROOT")
    cls("EAID_WONING", "Woning", "EAPK_WONEN")
    pkg("EAPK_ARCHIEF", "Archief", "EAPK_ROOT")
    pkg("EAPK_ARCHIEF_MODEL", "Archief Model", "EAPK_ARCHIEF")
    cls("EAID_ARCHIEFSTUK", "Archiefstuk", "EAPK_ARCHIEF_MODEL")

    # 4. Unieke relatie-URI's: gelijknamige associaties naar verschillende
    #    doelen, een associatie met de naam van een attribuut, naamloze
    #    associaties en dubbele attribuutnamen binnen één klasse.
    pkg("EAPK_PROJ", "Projecten", "EAPK_ROOT")
    cls("EAID_PROJECT", "Project", "EAPK_PROJ")
    cls("EAID_ACTIVITEIT", "Activiteit", "EAPK_PROJ")
    cls("EAID_LOCATIE", "Locatie", "EAPK_PROJ")
    attr("EAID_PROJ_NAAM", "naam", "EAID_PROJECT", "AN80")
    attr("EAID_PROJ_OID1", "objectidentificatie", "EAID_PROJECT", "AN40")
    attr("EAID_PROJ_OID2", "objectidentificatie", "EAID_PROJECT", type_class="EAID_LOCATIE")
    assoc("EAID_AS_HEEFT1", "heeft", "EAID_PROJECT", "EAID_ACTIVITEIT")
    assoc("EAID_AS_HEEFT2", "heeft", "EAID_PROJECT", "EAID_LOCATIE")
    assoc("EAID_AS_NAAM", "naam", "EAID_PROJECT", "EAID_ACTIVITEIT")
    assoc("EAID_AS_NAAMLOOS1", None, "EAID_PROJECT", "EAID_LOCATIE")
    assoc("EAID_AS_NAAMLOOS2", None, "EAID_PROJECT", "EAID_ACTIVITEIT", src_role="uitvoerder")
    assoc("EAID_AS_BETREFT", "betreft", "EAID_PROJECT", "EAID_LOCATIE")

    # 5. Technische packages en klassen zonder stereotype.
    pkg("EAPK_DIAGRAM", "Diagram", "EAPK_KERN")
    cls("EAID_PROXY", "ProxyConnector", "EAPK_DIAGRAM", stereotype=None)
    cls("EAID_DIAGRAMOBJECT", "Zaakdiagramobject", "EAPK_DIAGRAM")
    pkg("EAPK_TEKENWIJZE", "Tekenwijze", "EAPK_ROOT")
    cls("EAID_OBJECTTYPE_A", "ObjecttypeA", "EAPK_TEKENWIJZE")
    pkg("EAPK_VIEW", "View Betrokkene", "EAPK_ROOT")
    cls("EAID_RSGB", "RSGB", "EAPK_VIEW", stereotype=None)
    pkg("EAPK_INTERN", "Diagrammen intern gebruik", "EAPK_ROOT")
    pkg("EAPK_SEMANTISCH", "Semantische relaties", "EAPK_INTERN")
    cls("EAID_DETAILLERING", "DetailleringSubjecten", "EAPK_SEMANTISCH")
    cls("EAID_ZONDER", "Zonder stereotype", "EAPK_KERN", stereotype=None)
    # Een datatype-klasse heeft van nature geen Objecttype-stereotype en blijft.
    cls("EAID_TYPEBEDRAG", "TypeBedrag", "EAPK_KERN", stereotype=None, is_datatype=True)
    attr("EAID_TYPEBEDRAG_BEDRAG", "bedrag", "EAID_TYPEBEDRAG", "Bedrag")
    attr("EAID_PERSOON_VERMOGEN", "vermogen", "EAID_PERSOON", type_class="EAID_TYPEBEDRAG")

    # 6. Namespace-botsingen: twee modelpakketten 'Groepattribuutsoort' onder
    #    verschillende ouders, en twee domeinen 'Archief'/'archief'.
    pkg("EAPK_RGBZ_OUDER", "RGBZ", "EAPK_ROOT")
    pkg("EAPK_GAS1", "Groepattribuutsoort", "EAPK_RGBZ_OUDER")
    cls("EAID_VERBLIJFSADRES", "Verblijfsadres", "EAPK_GAS1")
    pkg("EAPK_RSGB_OUDER", "RSGB", "EAPK_ROOT")
    pkg("EAPK_GAS2", "Groepattribuutsoort", "EAPK_RSGB_OUDER")
    cls("EAID_CORRESPONDENTIEADRES", "Correspondentieadres", "EAPK_GAS2")
    pkg("EAPK_ARCHIEF2", "archief", "EAPK_ROOT")
    pkg("EAPK_DEPOT_MODEL", "Model Depot", "EAPK_ARCHIEF2")
    cls("EAID_DEPOT", "Depot", "EAPK_DEPOT_MODEL")

    # 7. Identifiers: één leeg, één zonder EAID_-prefix.
    attr("", "priotype", "EAID_ZAAK", "AN10")
    cls("12345", "Afwijkend", "EAPK_KERN")

    database.commit()


def exporteer(outputfile=OUTPUT, extra=()):
    cli.main(["-sch", SCHEMA, "export", "-f", outputfile, "-t", "ttl", "--linked_data_namespace", BASE, *extra])
    graph = Graph()
    graph.parse(outputfile, format="turtle")
    return graph


@pytest.fixture(scope="module")
def graaf():
    bouw_model()
    graph = exporteer()
    yield graph
    os.remove(OUTPUT)


def klassen_met_label(graph, label):
    return [s for s in graph.subjects(RDFS.label, Literal(label)) if (s, RDF.type, OWL.Class) in graph]


def klasse(graph, label):
    """De owl:Class met dit label (de SHACL-shape draagt hetzelfde label)."""
    kandidaten = klassen_met_label(graph, label)
    assert len(kandidaten) == 1, f"verwacht precies één klasse '{label}', gevonden: {kandidaten}"
    return kandidaten[0]


# ---------------------------------------------------------------------------
# 1. Generalisaties
# ---------------------------------------------------------------------------


def test_generalisaties_wijzen_van_sub_naar_superklasse(graaf):
    persoon, medewerker, burger = (klasse(graaf, naam) for naam in ("Persoon", "Medewerker", "Burger"))
    assert (medewerker, RDFS.subClassOf, persoon) in graaf
    assert (burger, RDFS.subClassOf, persoon) in graaf


def test_geen_klasse_is_haar_eigen_superklasse(graaf):
    zelf = [(s, o) for s, o in graaf.subject_objects(RDFS.subClassOf) if s == o]
    assert zelf == [], f"klasse mag niet haar eigen superklasse zijn: {zelf}"


# ---------------------------------------------------------------------------
# 2. Spaties en haakjes in IRI's; basis-URI met pad
# ---------------------------------------------------------------------------


def test_modelsegment_is_slug_en_basispad_blijft_behouden(graaf):
    """'Model Kern (RGBZ)' werd 'kern%20%28rgbz%29' en het pad '/lod/' van de
    basis-URI viel weg; nu 'kern-rgbz' achter de volledige basis."""
    assert klasse(graaf, "Zaak") == URIRef(BASE + "kern-rgbz/zaak")
    assert (URIRef(BASE + "kern-rgbz/zaak/identificatie"), RDF.type, OWL.DatatypeProperty) in graaf
    assert (URIRef(BASE + "kern-rgbz/"), RDF.type, OWL.Ontology) in graaf


def test_geen_procent_codering_in_eigen_iris(graaf):
    eigen = {
        t for triple in graaf for t in triple if isinstance(t, URIRef) and str(t).startswith("https://voorbeeld.nl/")
    }
    assert eigen, "er moeten eigen IRI's zijn"
    fout = sorted(str(i) for i in eigen if "%" in str(i))
    assert fout == [], f"IRI's met procent-codering: {fout}"
    buiten = sorted(str(i) for i in eigen if not str(i).startswith(BASE))
    assert buiten == [], f"IRI's buiten de basis-URI: {buiten}"


# ---------------------------------------------------------------------------
# 3. Naamopschoning van modelpakketten
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "naam,verwacht",
    [
        ("Model Kern RGBZ", "Kern RGBZ"),
        ("RSGB Model", "RSGB"),
        ("model Afval", "Afval"),
        ("Gegevensmodel Wonen", "Gegevensmodel Wonen"),
        ("Modelmatig Werken", "Modelmatig Werken"),
        ("Model", "Model"),
        ("  Model  ", "Model"),
    ],
)
def test_model_segment_name(naam, verwacht):
    assert model_segment_name(naam) == verwacht


def test_pakket_model_houdt_een_segment(graaf):
    """Het package 'Model' kreeg een lege naam en daarmee IRI's direct onder
    (of zelfs náást) de basis-URI: ...nlperiode."""
    assert klasse(graaf, "Periode") == URIRef(BASE + "model/periode")
    assert (URIRef(BASE + "model/periode/datum-start"), RDF.type, OWL.DatatypeProperty) in graaf


def test_alleen_los_woord_model_wordt_verwijderd(graaf):
    assert klasse(graaf, "Woning") == URIRef(BASE + "gegevensmodel-wonen/woning")
    assert klasse(graaf, "Archiefstuk") == URIRef(BASE + "archief/archiefstuk")


# ---------------------------------------------------------------------------
# 4. Unieke relatie-URI's
# ---------------------------------------------------------------------------


def test_gelijknamige_associaties_krijgen_eigen_uri(graaf):
    """Twee associaties 'heeft' vanuit Project (naar Activiteit en Locatie)
    vielen samen tot één ObjectProperty met twee ranges en twee identifiers."""
    project = klasse(graaf, "Project")
    heeft = [p for p in graaf.subjects(RDFS.domain, project) if (p, RDFS.label, Literal("heeft")) in graaf]
    assert {str(p) for p in heeft} == {
        BASE + "projecten/project/heeft-activiteit",
        BASE + "projecten/project/heeft-locatie",
    }
    for prop in heeft:
        assert len(set(graaf.objects(prop, RDFS.range))) == 1
        assert len(set(graaf.objects(prop, DCTERMS.identifier))) == 1


def test_associatie_botst_niet_met_gelijknamig_attribuut(graaf):
    naam_attribuut = URIRef(BASE + "projecten/project/naam")
    assert (naam_attribuut, RDF.type, OWL.DatatypeProperty) in graaf
    assert (naam_attribuut, RDF.type, OWL.ObjectProperty) not in graaf
    assert (naam_attribuut, DCTERMS.identifier, Literal("EAID_PROJ_NAAM")) in graaf
    naam_associatie = URIRef(BASE + "projecten/project/naam-activiteit")
    assert (naam_associatie, RDF.type, OWL.ObjectProperty) in graaf
    assert (naam_associatie, DCTERMS.identifier, Literal("EAID_AS_NAAM")) in graaf


def test_naamloze_associaties_heten_naar_rol_en_doelklasse(graaf):
    """Naamloze associaties kregen een GUID-slug als URI en 'None' als label."""
    assert (
        URIRef(BASE + "projecten/project/relatie-locatie"),
        DCTERMS.identifier,
        Literal("EAID_AS_NAAMLOOS1"),
    ) in graaf
    assert (
        URIRef(BASE + "projecten/project/uitvoerder-activiteit"),
        DCTERMS.identifier,
        Literal("EAID_AS_NAAMLOOS2"),
    ) in graaf
    assert (None, RDFS.label, Literal("None")) not in graaf
    assert not [s for s in graaf.subjects(RDF.type, OWL.ObjectProperty) if "eaid" in str(s).lower()]


def test_associatie_zonder_botsing_houdt_korte_uri(graaf):
    assert (URIRef(BASE + "projecten/project/betreft"), RDFS.range, klasse(graaf, "Locatie")) in graaf


def test_dubbele_attribuutnamen_binnen_klasse_worden_uniek(graaf):
    """Twee attributen 'objectidentificatie' (AN40 en klasse Locatie) werden
    stilzwijgend één property met twee ranges; nu krijgt elk het type als
    achtervoegsel en zijn eigen identifier."""
    tekst = URIRef(BASE + "projecten/project/objectidentificatie-string")
    locatie = URIRef(BASE + "projecten/project/objectidentificatie-locatie")
    assert (tekst, RDFS.range, XSD.string) in graaf
    assert (tekst, DCTERMS.identifier, Literal("EAID_PROJ_OID1")) in graaf
    assert (locatie, RDFS.range, klasse(graaf, "Locatie")) in graaf
    assert (locatie, DCTERMS.identifier, Literal("EAID_PROJ_OID2")) in graaf
    assert (URIRef(BASE + "projecten/project/objectidentificatie"), None, None) not in graaf


def test_elke_property_heeft_precies_een_range_en_identifier(graaf):
    properties = set(graaf.subjects(RDF.type, OWL.ObjectProperty)) | set(graaf.subjects(RDF.type, OWL.DatatypeProperty))
    assert properties
    for prop in properties:
        assert len(set(graaf.objects(prop, RDFS.range))) == 1, prop
        assert len(set(graaf.objects(prop, RDFS.domain))) == 1, prop
        assert len(set(graaf.objects(prop, DCTERMS.identifier))) <= 1, prop


def test_shacl_paden_verwijzen_naar_gerenderde_properties(graaf):
    paden = set(graaf.objects(None, SH.path))
    assert paden
    for pad in paden:
        assert (pad, RDF.type, None) in graaf, f"sh:path {pad} wijst naar een onbekende property"


# ---------------------------------------------------------------------------
# 5. Technische packages en klassen zonder stereotype
# ---------------------------------------------------------------------------


def test_technische_packages_worden_standaard_overgeslagen(graaf):
    """Diagram, Tekenwijze, View* en alles onder 'Diagrammen intern gebruik'
    zijn EA-hulpmiddelen, geen model."""
    for naam in ("ProxyConnector", "Zaakdiagramobject", "ObjecttypeA", "RSGB", "DetailleringSubjecten"):
        assert not klassen_met_label(graaf, naam), naam
    assert Literal("Diagrammen intern gebruik") not in set(graaf.objects(None, RDFS.label))
    ontologieen = {str(o) for o in graaf.subjects(RDF.type, OWL.Ontology)}
    technisch = {o for o in ontologieen if any(w in o for w in ("diagram", "tekenwijze", "view", "semantische"))}
    assert technisch == set()


def test_klassen_zonder_stereotype_worden_overgeslagen_behalve_datatypes(graaf):
    labels = set(graaf.objects(None, RDFS.label))
    assert Literal("Zonder stereotype") not in labels
    typebedrag = klasse(graaf, "TypeBedrag")  # is_datatype, blijft
    assert (URIRef(BASE + "kern/persoon/vermogen"), RDFS.range, typebedrag) in graaf
    assert (URIRef(BASE + "kern/typebedrag/bedrag"), RDFS.range, XSD.decimal) in graaf


def test_uitsluiting_op_packagenaam_is_instelbaar(graaf):
    alles = "./test/output/lod_fixes_alles.ttl"
    eigen = "./test/output/lod_fixes_eigen.ttl"
    try:
        # Lege lijst: niets op naam uitsluiten; de stereotype-regel blijft gelden.
        labels = set(exporteer(alles, ["--output_exclude_package_names", ""]).objects(None, RDFS.label))
        assert Literal("ObjecttypeA") in labels
        assert Literal("Zaakdiagramobject") in labels
        assert Literal("ProxyConnector") not in labels
        # Eigen patronen (hoofdletterongevoelig, met jokers).
        labels = set(
            exporteer(eigen, ["--output_exclude_package_names", "project*,TEKENWIJZE"]).objects(None, RDFS.label)
        )
        assert Literal("Project") not in labels
        assert Literal("ObjecttypeA") not in labels
        assert Literal("Zaakdiagramobject") in labels
    finally:
        for bestand in (alles, eigen):
            if os.path.exists(bestand):
                os.remove(bestand)
