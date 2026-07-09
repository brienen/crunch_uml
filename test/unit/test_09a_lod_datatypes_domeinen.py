"""
Tests voor de verbeterde LOD-rendering: echte datatypes en de
domeinhiërarchie.

Aanleiding (GGM v3.0.0): alle attributen kregen ``rdfs:range xsd:string``,
ongeacht hun type (Datum, Bedrag, AN200, boolean, geometrie), en de
pakket-/domeinstructuur van het model ontbrak volledig in de output.

Gedekt:

* :func:`map_datatype` — de pure mapping van GGM/EA-primitieven naar XSD en
  GeoSPARQL, inclusief AN<n> (met maximumlengte), N<n> en alle
  spellingsvarianten uit het echte GGM;
* integratie op het Monumenten-testmodel: ranges volgen de datatypes,
  AN-types krijgen ``sh:maxLength``, klasse-getypeerde attributen worden
  ``owl:ObjectProperty``, en de pakkethiërarchie verschijnt als
  ``owl:Ontology``- en ``Domein``-entiteiten met ``dcterms:isPartOf``.
"""

import os

import pytest
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SH, SKOS, XSD

from crunch_uml import cli, const
from crunch_uml.renderers.lodrenderer import GEO, map_datatype

OUTPUTFILE = "./test/output/Monumenten_datatypes.ttl"


# ---------------------------------------------------------------------------
# map_datatype (puur, geen database nodig)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "primitive,expected_type,expected_maxlength",
    [
        # AN<n>: alfanumeriek met maximumlengte, ook met spatie.
        ("AN200", XSD.string, 200),
        ("an40", XSD.string, 40),
        ("AN 80", XSD.string, 80),
        # N<n>: numeriek.
        ("N2", XSD.integer, None),
        ("N6,2", XSD.integer, None),
        # Datums in alle in het GGM voorkomende spellingen.
        ("Date", XSD.date, None),
        ("DATUM", XSD.date, None),
        ("datum", XSD.date, None),
        ("DateTime", XSD.dateTime, None),
        ("Datetime", XSD.dateTime, None),
        # Numeriek en logisch.
        ("int", XSD.integer, None),
        ("integer", XSD.integer, None),
        ("Boolean", XSD.boolean, None),
        ("bool", XSD.boolean, None),
        ("Indicatie", XSD.boolean, None),
        # Geld.
        ("Bedrag", XSD.decimal, None),
        ("bedrag", XSD.decimal, None),
        # Tekstvarianten.
        ("CharacterString", XSD.string, None),
        ("Text", XSD.string, None),
        ("Varchar", XSD.string, None),
        ("GUID", XSD.string, None),
        ("NEN3610ID", XSD.string, None),
        # Onvolledige datum past niet in xsd:date.
        ("OnvolledigeDatum", XSD.string, None),
        # Geometrie -> GeoSPARQL.
        ("Point", GEO.wktLiteral, None),
        ("Surface", GEO.wktLiteral, None),
        ("MultiSurface", GEO.wktLiteral, None),
        ("Curve", GEO.wktLiteral, None),
    ],
)
def test_map_datatype_known_types(primitive, expected_type, expected_maxlength):
    assert map_datatype(primitive) == (expected_type, expected_maxlength)


def test_map_datatype_unknown_and_empty_returns_none():
    """Onbekende types (zoals klassenamen 'Medewerker') beslist de renderer:
    klasse-referentie of terugval op string mét waarschuwing."""
    assert map_datatype("Medewerker") == (None, None)
    assert map_datatype("") == (None, None)
    assert map_datatype(None) == (None, None)


# ---------------------------------------------------------------------------
# Integratie: Monumenten-model -> TTL -> graf-inspectie
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def monumenten_graph():
    cli.main(["import", "-f", "./test/data/GGM_Monumenten_EA2.1.xml", "-t", "eaxmi", "-db_create"])
    cli.main(["export", "-f", OUTPUTFILE, "-t", "ttl"])
    graph = Graph()
    graph.parse(OUTPUTFILE, format="turtle")
    yield graph
    os.remove(OUTPUTFILE)


def test_attribute_ranges_follow_datatypes(monumenten_graph):
    """Niet langer alles xsd:string: het Monumenten-model heeft int- en
    AN200-attributen, dus beide ranges moeten voorkomen."""
    ranges = set(monumenten_graph.objects(None, RDFS.range))
    assert XSD.integer in ranges, "int-attributen moeten xsd:integer als range hebben"
    assert XSD.string in ranges


def test_an_types_get_shacl_maxlength(monumenten_graph):
    """AN200-attributen krijgen sh:datatype xsd:string mét sh:maxLength 200."""
    maxlengths = set(monumenten_graph.objects(None, SH.maxLength))
    assert Literal(200) in maxlengths


def test_shacl_datatypes_match_ranges(monumenten_graph):
    """De SHACL-shapes gebruiken dezelfde mapping als rdfs:range."""
    shacl_types = set(monumenten_graph.objects(None, SH.datatype))
    assert XSD.integer in shacl_types
    assert shacl_types != {XSD.string}, "SHACL-datatypes mogen niet allemaal string zijn"


def test_model_packages_are_ontologies_with_defined_classes(monumenten_graph):
    """Elk modelpakket is een owl:Ontology en de klassen verwijzen ernaar
    met rdfs:isDefinedBy."""
    ontologies = set(monumenten_graph.subjects(RDF.type, OWL.Ontology))
    assert ontologies, "modelpakketten moeten als owl:Ontology in de graaf staan"
    defined_by = set(monumenten_graph.objects(None, RDFS.isDefinedBy))
    assert defined_by & ontologies, "klassen moeten met rdfs:isDefinedBy naar hun model verwijzen"
    # Ontologieën dragen label en identifier (GUID) voor traceerbaarheid.
    for ontology in ontologies:
        assert list(monumenten_graph.objects(ontology, RDFS.label))
        assert list(monumenten_graph.objects(ontology, DCTERMS.identifier))


def test_domain_hierarchy_is_rendered(monumenten_graph):
    """Bovenliggende pakketten verschijnen als Domein-entiteiten en de
    hiërarchie is navigeerbaar via dcterms:isPartOf."""
    myns = Namespace(const.DEFAULT_LOD_NS)
    domein_cls = myns["Domein"]
    domains = set(monumenten_graph.subjects(RDF.type, domein_cls))
    assert domains, "bovenliggende pakketten moeten als Domein-entiteit bestaan"

    part_of = list(monumenten_graph.subject_objects(DCTERMS.isPartOf))
    assert part_of, "de pakkethiërarchie moet via dcterms:isPartOf gelegd zijn"
    # Elke isPartOf wijst naar een bestaande entiteit (Domein of Ontology).
    ontologies = set(monumenten_graph.subjects(RDF.type, OWL.Ontology))
    for _, parent in part_of:
        assert parent in domains | ontologies


def test_domain_entities_carry_labels(monumenten_graph):
    myns = Namespace(const.DEFAULT_LOD_NS)
    for domain in monumenten_graph.subjects(RDF.type, myns["Domein"]):
        assert isinstance(domain, URIRef)
        assert list(monumenten_graph.objects(domain, RDFS.label))
        assert list(monumenten_graph.objects(domain, DCTERMS.identifier))


# ---------------------------------------------------------------------------
# Enumeraties
# ---------------------------------------------------------------------------


def test_enumeration_is_conceptscheme_with_concepts(monumenten_graph):
    """Het Monumenten-model heeft één enumeratie (TypeMonument, 2 waarden):
    die moet als owl:Class + skos:ConceptScheme in de graaf staan, met de
    waarden als skos:Concept-en in het scheme."""
    schemes = set(monumenten_graph.subjects(RDF.type, SKOS.ConceptScheme))
    assert len(schemes) == 1
    scheme = schemes.pop()
    assert (scheme, RDF.type, OWL.Class) in monumenten_graph
    assert list(monumenten_graph.objects(scheme, RDFS.label))

    concepts = set(monumenten_graph.subjects(SKOS.inScheme, scheme))
    assert len(concepts) == 2
    for concept in concepts:
        assert (concept, RDF.type, SKOS.Concept) in monumenten_graph
        # Het concept is ook instantie van de enumeratieklasse (OWL-range).
        assert (concept, RDF.type, scheme) in monumenten_graph
        assert (concept, SKOS.topConceptOf, scheme) in monumenten_graph
        assert list(monumenten_graph.objects(concept, SKOS.prefLabel))
        assert list(monumenten_graph.objects(concept, DCTERMS.identifier))


def test_enum_typed_attribute_is_objectproperty_with_enum_range(monumenten_graph):
    """Attributen met een enumeratie als type verwijzen als ObjectProperty
    naar het ConceptScheme in plaats van terug te vallen op xsd:string."""
    scheme = next(iter(monumenten_graph.subjects(RDF.type, SKOS.ConceptScheme)))
    enum_props = [s for s, _, o in monumenten_graph.triples((None, RDFS.range, scheme))]
    assert enum_props, "minstens één attribuut moet de enumeratie als range hebben"
    for prop in enum_props:
        assert (prop, RDF.type, OWL.ObjectProperty) in monumenten_graph


def test_enum_shacl_shape_lists_allowed_values(monumenten_graph):
    """De SHACL-shape van een enum-attribuut somt de toegestane concepten op
    via sh:in (RDF-lijst met beide waarden)."""
    scheme = next(iter(monumenten_graph.subjects(RDF.type, SKOS.ConceptScheme)))
    concepts = set(monumenten_graph.subjects(SKOS.inScheme, scheme))

    sh_in_lists = []
    for prop_bnode, list_node in monumenten_graph.subject_objects(SH["in"]):
        items = set(monumenten_graph.items(list_node))
        sh_in_lists.append(items)
    assert sh_in_lists, "minstens één shape moet sh:in gebruiken"
    assert concepts in sh_in_lists, "de sh:in-lijst moet precies de enum-concepten bevatten"
