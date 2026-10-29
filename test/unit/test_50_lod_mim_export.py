"""
Integratietests voor de MIM 1.2-laag van de LOD-export op het testmodel
test/data/MIM_LOD_Fixture.xml (EA XMI 2.1): typering en metagegevens
(onderdeel 1), kardinaliteit uit de bron (2), taal en versie (3), bijzondere
typen (4) en validatie tegen mim-shapes.ttl met pyshacl (5).
"""

import os

import pytest
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SH, SKOS, XSD

from crunch_uml import cli
from crunch_uml.renderers.lod_mim import MIM

try:
    import pyshacl  # noqa: F401

    HEEFT_PYSHACL = True
except ImportError:  # pragma: no cover
    HEEFT_PYSHACL = False

FIXTURE = "./test/data/MIM_LOD_Fixture.xml"
SCHEMA = "mim_lod"
BASE = "https://voorbeeld.nl/lod/"
OUTPUT = "./test/output/mim_lod.ttl"
# Het pad volgt de pakketboom: Testmodel Zorg (wortel) > Domein Zorg > Model Zorg.
ZORG = Namespace(BASE + "domein-zorg/zorg/")
GROEP = Namespace(BASE + "domein-zorg/groepattribuutsoort/")
CDT = Namespace(BASE + "domein-zorg/complex-datatype/")
SHAPES = Namespace(BASE + "shapes/")
INFORMATIEMODEL = URIRef(BASE)
DOMEIN = URIRef(BASE + "domein-zorg/")


@pytest.fixture(scope="module")
def graaf():
    cli.main(["-sch", SCHEMA, "import", "-f", FIXTURE, "-t", "eaxmi", "-db_create"])
    cli.main(
        [
            "-sch",
            SCHEMA,
            "export",
            "-f",
            OUTPUT,
            "-t",
            "ttl",
            "--linked_data_namespace",
            BASE,
            "--lod_version",
            "v1.2.3",
            "--lod_title",
            "Testmodel Zorg (LOD)",
            "--lod_publisher",
            "https://www.delft.nl/",
            "--lod_license",
            "https://creativecommons.org/licenses/by/4.0/",
            "--lod_informatiedomein",
            "Zorg",
        ]
    )
    graph = Graph()
    graph.parse(OUTPUT, format="turtle")
    yield graph
    os.remove(OUTPUT)


def shape_van(graph, prop):
    """De PropertyShape (blank node) met sh:path prop."""
    shapes = list(graph.subjects(SH.path, prop))
    assert len(shapes) == 1, f"verwacht één property shape voor {prop}, gevonden {shapes}"
    return shapes[0]


# ---------------------------------------------------------------------------
# 3. Informatiemodel, domeinen, taal en versie
# ---------------------------------------------------------------------------


def test_wortelpakket_is_informatiemodel_met_versie_en_mim_metadata(graaf):
    assert (INFORMATIEMODEL, RDF.type, OWL.Ontology) in graaf
    assert (INFORMATIEMODEL, RDF.type, MIM.Informatiemodel) in graaf
    assert (INFORMATIEMODEL, MIM.basisUri, Literal(BASE, datatype=XSD.anyURI)) in graaf
    assert (INFORMATIEMODEL, MIM.identificatie, Literal(BASE, datatype=XSD.anyURI)) in graaf
    assert (INFORMATIEMODEL, MIM.naam, Literal("Testmodel Zorg", lang="nl")) in graaf
    assert (INFORMATIEMODEL, DCTERMS.title, Literal("Testmodel Zorg (LOD)", lang="nl")) in graaf
    assert (INFORMATIEMODEL, DCTERMS.identifier, Literal("EAPK_00000001_0000_4000_8000_00000000A001")) in graaf
    assert (INFORMATIEMODEL, MIM.mimversie, Literal("1.2")) in graaf
    assert (INFORMATIEMODEL, MIM.mimtaal, Literal("nl")) in graaf
    assert (INFORMATIEMODEL, MIM.informatiemodeltype, MIM.LogischInformatiemodel) in graaf
    assert (INFORMATIEMODEL, MIM.relatiemodelleringstype, MIM.RelatiesoortLeidend) in graaf
    assert (INFORMATIEMODEL, MIM.informatiedomein, Literal("Zorg")) in graaf
    assert (INFORMATIEMODEL, MIM.datumOpname, Literal("2024-01-15", datatype=XSD.date)) in graaf
    assert (INFORMATIEMODEL, OWL.versionInfo, Literal("v1.2.3")) in graaf
    assert (INFORMATIEMODEL, OWL.versionIRI, URIRef(BASE + "v1.2.3/")) in graaf
    assert (INFORMATIEMODEL, DCTERMS.modified, Literal("2026-10-01", datatype=XSD.date)) in graaf
    assert (INFORMATIEMODEL, DCTERMS.publisher, URIRef("https://www.delft.nl/")) in graaf
    assert (INFORMATIEMODEL, DCTERMS.license, URIRef("https://creativecommons.org/licenses/by/4.0/")) in graaf
    assert (INFORMATIEMODEL, DCTERMS.creator, Literal("Testauteur")) in graaf


def test_pakketten_zijn_domeinen_met_imports_en_ispartof(graaf):
    """Domein Zorg en de drie modelpakketten zijn owl:Ontology + mim:Domein;
    de ouder importeert het kind (MIM 6.4.9.40), het kind is deel van de ouder."""
    assert (DOMEIN, RDF.type, OWL.Ontology) in graaf
    assert (DOMEIN, RDF.type, MIM.Domein) in graaf
    assert (DOMEIN, MIM.basisUri, Literal(str(DOMEIN), datatype=XSD.anyURI)) in graaf
    assert (DOMEIN, MIM.datumOpname, Literal("2024-01-15", datatype=XSD.date)) in graaf
    assert (DOMEIN, DCTERMS.isPartOf, INFORMATIEMODEL) in graaf
    assert (INFORMATIEMODEL, OWL.imports, DOMEIN) in graaf
    for model in (URIRef(str(ZORG)), URIRef(str(GROEP)), URIRef(str(CDT))):
        assert (model, RDF.type, MIM.Domein) in graaf, model
        assert (model, MIM.basisUri, Literal(str(model), datatype=XSD.anyURI)) in graaf
        assert (model, DCTERMS.isPartOf, DOMEIN) in graaf
        assert (DOMEIN, OWL.imports, model) in graaf
    assert (URIRef(str(ZORG)), OWL.versionInfo, Literal("2.1.0")) in graaf
    # De zelf gedeclareerde klasse 'Domein' bestaat niet meer.
    assert (None, RDF.type, URIRef(BASE + "Domein")) not in graaf
    assert set(graaf.subjects(RDF.type, MIM.Informatiemodel)) == {INFORMATIEMODEL}


def test_alle_labels_en_definities_hebben_de_taaltag(graaf):
    for predicaat in (
        RDFS.label,
        RDFS.comment,
        SKOS.prefLabel,
        SKOS.definition,
        SH.name,
        SH.description,
        MIM.naam,
        MIM.definitie,
    ):
        waarden = list(graaf.objects(None, predicaat))
        assert waarden, predicaat
        zonder = [w for w in waarden if getattr(w, "language", None) != "nl"]
        assert zonder == [], f"{predicaat}: literals zonder @nl: {zonder[:5]}"


def test_taal_is_instelbaar():
    bestand = "./test/output/mim_lod_en.ttl"
    try:
        cli.main(
            [
                "-sch",
                SCHEMA,
                "export",
                "-f",
                bestand,
                "-t",
                "ttl",
                "--linked_data_namespace",
                BASE,
                "--lod_language",
                "en",
            ]
        )
        graph = Graph().parse(bestand, format="turtle")
        assert (ZORG.patient, RDFS.label, Literal("Patient", lang="en")) in graph
        assert (INFORMATIEMODEL, MIM.mimtaal, Literal("en")) in graph
        cli.main(
            [
                "-sch",
                SCHEMA,
                "export",
                "-f",
                bestand,
                "-t",
                "ttl",
                "--linked_data_namespace",
                BASE,
                "--lod_language",
                "",
            ]
        )
        graph = Graph().parse(bestand, format="turtle")
        assert (ZORG.patient, RDFS.label, Literal("Patient")) in graph
        assert list(graph.objects(INFORMATIEMODEL, MIM.mimtaal)) == []
    finally:
        if os.path.exists(bestand):
            os.remove(bestand)


# ---------------------------------------------------------------------------
# 1. Typering en metagegevens
# ---------------------------------------------------------------------------


def test_objecttype_met_metagegevens(graaf):
    patient = ZORG.patient
    assert (patient, RDF.type, OWL.Class) in graaf
    assert (patient, RDF.type, MIM.Objecttype) in graaf
    assert (patient, MIM.identificatie, Literal(str(patient), datatype=XSD.anyURI)) in graaf
    assert (patient, RDFS.label, Literal("Patient", lang="nl")) in graaf
    assert (patient, MIM.naam, Literal("Patient", lang="nl")) in graaf
    assert (patient, MIM.alias, Literal("Zorgvrager", lang="nl")) in graaf
    assert (
        patient,
        RDFS.comment,
        Literal("Een natuurlijk persoon die zorg ontvangt van een zorgverlener.", lang="nl"),
    ) in graaf
    assert (
        patient,
        MIM.definitie,
        Literal("Een natuurlijk persoon die zorg ontvangt van een zorgverlener.", lang="nl"),
    ) in graaf
    # '#NOTES#'-notities van de tagdefinitie zijn weggehaald.
    assert (patient, MIM.herkomst, Literal("BRP")) in graaf
    assert (patient, MIM.herkomstDefinitie, Literal("BRP")) in graaf
    assert (patient, MIM.datumOpname, Literal("2016-05-01", datatype=XSD.date)) in graaf
    assert (patient, MIM.toelichting, Literal("Alleen ingeschreven patienten tellen mee.", lang="nl")) in graaf
    assert (patient, MIM.populatie, Literal("Alle patienten van de praktijk.")) in graaf
    assert (patient, MIM.kwaliteit, Literal("Dagelijks bijgewerkt vanuit de BRP.")) in graaf
    assert (patient, MIM.indicatieAbstractObject, Literal(False)) in graaf
    begrip = URIRef("https://begrippen.example.org/id/begrip/patient")
    assert (patient, DCTERMS.subject, begrip) in graaf
    assert (patient, MIM.begrip, begrip) in graaf
    assert (begrip, RDF.type, SKOS.Concept) in graaf
    assert (patient, RDFS.isDefinedBy, URIRef(str(ZORG))) in graaf
    assert (patient, MIM.attribuut, ZORG["patient/naam"]) in graaf
    assert (patient, MIM.gegevensgroep, ZORG["patient/adres"]) in graaf
    # Een objecttype met andere datumnotaties in de bron.
    assert (ZORG.zorgverlener, MIM.datumOpname, Literal("2009-04-24", datatype=XSD.date)) in graaf
    assert (ZORG.huisarts, MIM.datumOpname, Literal("2009-04-24", datatype=XSD.date)) in graaf


def test_attribuutsoort_met_metagegevens_en_shape(graaf):
    naam = ZORG["patient/naam"]
    assert (naam, RDF.type, OWL.DatatypeProperty) in graaf
    assert (naam, RDF.type, MIM.Attribuutsoort) in graaf
    assert (naam, RDFS.isDefinedBy, URIRef(str(ZORG))) in graaf
    assert (naam, MIM.type, MIM.CharacterString) in graaf
    assert (naam, MIM.herkomst, Literal("BRP")) in graaf
    assert (naam, MIM.datumOpname, Literal("2016-05-01", datatype=XSD.date)) in graaf
    assert (naam, MIM.toelichting, Literal("Zoals geregistreerd in de BRP.", lang="nl")) in graaf
    assert (naam, MIM.lengte, Literal("80")) in graaf
    assert (naam, MIM.patroon, Literal("Letters en spaties")) in graaf
    assert (naam, MIM.formeelPatroon, Literal("^[A-Za-z ]+$")) in graaf
    assert (naam, MIM.authentiek, MIM.Authentiek) in graaf
    assert (naam, MIM.indicatieFormeleHistorie, Literal(True)) in graaf
    assert (naam, MIM.indicatieMaterieleHistorie, Literal(False)) in graaf
    assert (naam, MIM.mogelijkGeenWaarde, Literal(False)) in graaf
    assert (naam, MIM.indicatieClassificerend, Literal(False)) in graaf
    assert (naam, MIM.indicatieAfleidbaar, Literal(False)) in graaf
    shape = shape_van(graaf, naam)
    assert (shape, SH.datatype, XSD.string) in graaf
    assert (shape, SH.maxLength, Literal(80)) in graaf
    assert (shape, SH.pattern, Literal("^[A-Za-z ]+$")) in graaf
    assert (shape, SH.name, Literal("naam", lang="nl")) in graaf
    assert (SHAPES["domein-zorg/zorg/patient"], SH.property, shape) in graaf


def test_waardebereik_eenheid_en_enumeratie_attribuut(graaf):
    gewicht = ZORG["patient/gewicht"]
    assert (gewicht, MIM.type, MIM.Decimal) in graaf
    minimum = graaf.value(gewicht, MIM.minimumwaardeInclusief)
    assert minimum.datatype == XSD.decimal and minimum.toPython() == 0
    eenheid = graaf.value(gewicht, MIM.eenheid)
    assert (eenheid, RDF.type, URIRef("https://si-digital-framework.org/SI#MeasurementUnit")) in graaf
    assert (eenheid, RDFS.label, Literal("kg", lang="nl")) in graaf
    shape = shape_van(graaf, gewicht)
    assert graaf.value(shape, SH.minInclusive).toPython() == 0
    maximum = graaf.value(shape, SH.maxInclusive)
    assert maximum.datatype == XSD.decimal and maximum.toPython() == 500

    status = ZORG["patient/status"]
    assert (status, RDF.type, MIM.Attribuutsoort) in graaf
    assert (status, MIM.type, ZORG.patientstatus) in graaf
    assert (status, MIM.indicatieClassificerend, Literal(True)) in graaf
    assert (shape_van(graaf, status), SH["in"], None) in graaf

    # <memo>-placeholder en 'n.v.t.' uit de bron.
    registratienummer = ZORG["zorgverlener/registratienummer"]
    assert list(graaf.objects(registratienummer, MIM.patroon)) == []
    assert (registratienummer, MIM.indicatieFormeleHistorie, Literal(False)) in graaf


# ---------------------------------------------------------------------------
# 2. Kardinaliteit uit de bron
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pad,kardinaliteit,min_count,max_count",
    [
        ("patient/naam", "1..1", 1, 1),  # verplicht, mogelijk geen waarde Nee
        ("patient/geboortedatum", "0..1", None, 1),
        ("patient/telefoonnummers", "0..*", None, None),
        ("patient/gewicht", "1..1", None, 1),  # mogelijk geen waarde Ja: minCount vervalt (6.4.9.18)
        ("patient/status", "1..1", 1, 1),
        ("zorgverlener/naam", "0..1", None, 1),  # alleen <bounds> in de EA-extensie
    ],
)
def test_kardinaliteit_van_attributen(graaf, pad, kardinaliteit, min_count, max_count):
    prop = ZORG[pad]
    assert (prop, MIM.kardinaliteit, Literal(kardinaliteit)) in graaf
    shape = shape_van(graaf, prop)
    assert graaf.value(shape, SH.minCount) == (Literal(min_count) if min_count is not None else None)
    assert graaf.value(shape, SH.maxCount) == (Literal(max_count) if max_count is not None else None)


def test_geen_vaste_mincount_0_maxcount_1_meer(graaf):
    assert (None, SH.minCount, Literal(0)) not in graaf


def test_relatiesoort_met_kardinaliteit_en_shape_op_bronklasse(graaf):
    relatie = ZORG["patient/heeft-zorgverlener"]
    assert (relatie, RDF.type, OWL.ObjectProperty) in graaf
    assert (relatie, RDF.type, MIM.Relatiesoort) in graaf
    assert (relatie, RDFS.isDefinedBy, URIRef(str(ZORG))) in graaf
    assert (relatie, MIM.naam, Literal("heeft zorgverlener", lang="nl")) in graaf
    assert (relatie, MIM.bron, ZORG.patient) in graaf
    assert (relatie, MIM.doel, ZORG.zorgverlener) in graaf
    assert (relatie, MIM.kardinaliteit, Literal("1..1")) in graaf
    assert (relatie, MIM.kardinaliteitRelatieBron, Literal("0..*")) in graaf
    assert (relatie, MIM.unidirectioneel, Literal(True)) in graaf
    assert (relatie, MIM.aggregatietype, MIM.Geen) in graaf
    assert (relatie, MIM.authentiek, MIM.Basisgegeven) in graaf
    assert (relatie, MIM.herkomst, Literal("GGM")) in graaf
    assert (relatie, MIM.datumOpname, Literal("2016-05-01", datatype=XSD.date)) in graaf
    assert (relatie, MIM.indicatieFormeleHistorie, Literal(True)) in graaf
    assert (relatie, MIM.mogelijkGeenWaarde, Literal(False)) in graaf
    assert (relatie, MIM.definitie, Literal("De zorgverlener die de patient behandelt.", lang="nl")) in graaf
    shape = shape_van(graaf, relatie)
    assert (SHAPES["domein-zorg/zorg/patient"], SH.property, shape) in graaf
    assert (shape, SH["class"], ZORG.zorgverlener) in graaf
    assert (shape, SH.nodeKind, SH.IRI) in graaf
    assert (shape, SH.minCount, Literal(1)) in graaf
    assert (shape, SH.maxCount, Literal(1)) in graaf
    assert (shape, SH.name, Literal("heeft zorgverlener", lang="nl")) in graaf

    huisarts = ZORG["patient/heeft-huisarts"]
    assert (huisarts, MIM.kardinaliteit, Literal("0..1")) in graaf
    assert (huisarts, MIM.mogelijkGeenWaarde, Literal(True)) in graaf
    shape = shape_van(graaf, huisarts)
    assert graaf.value(shape, SH.minCount) is None
    assert (shape, SH.maxCount, Literal(1)) in graaf


# ---------------------------------------------------------------------------
# 4. Bijzondere typen
# ---------------------------------------------------------------------------


def test_gegevensgroeptype_en_gegevensgroep(graaf):
    adres = GROEP.adres
    assert (adres, RDF.type, OWL.Class) in graaf
    assert (adres, RDF.type, MIM.Gegevensgroeptype) in graaf
    assert (SHAPES["domein-zorg/groepattribuutsoort/adres"], SH.targetClass, adres) in graaf
    groep = ZORG["patient/adres"]
    assert (groep, RDF.type, OWL.ObjectProperty) in graaf
    assert (groep, RDF.type, MIM.Gegevensgroep) in graaf
    assert (groep, MIM.gegevensgroeptype, adres) in graaf
    assert (groep, MIM.kardinaliteit, Literal("0..1")) in graaf
    assert (groep, RDFS.range, adres) in graaf
    shape = shape_van(graaf, groep)
    assert (shape, SH["class"], adres) in graaf
    assert (shape, SH.nodeKind, SH.BlankNodeOrIRI) in graaf
    assert (shape, SH.maxCount, Literal(1)) in graaf


def test_gestructureerd_datatype_is_nodeshape_zonder_klasse(graaf):
    typebedrag = CDT.typebedrag
    assert (typebedrag, RDF.type, SH.NodeShape) in graaf
    assert (typebedrag, RDF.type, MIM.GestructureerdDatatype) in graaf
    assert (typebedrag, RDF.type, OWL.Class) not in graaf
    assert (typebedrag, SH.targetClass, None) not in graaf
    assert (typebedrag, RDFS.label, Literal("TypeBedrag", lang="nl")) in graaf
    assert (typebedrag, MIM.definitie, Literal("Een geldbedrag met valuta.", lang="nl")) in graaf
    # Data-elementen hangen direct aan het datatype (6.4.6.4).
    waarde = CDT["typebedrag/waarde"]
    assert (waarde, RDF.type, OWL.DatatypeProperty) in graaf
    assert (waarde, RDF.type, MIM.DataElement) in graaf
    assert (waarde, MIM.type, MIM.Decimal) in graaf
    assert (typebedrag, MIM.dataElement, waarde) in graaf
    shape = shape_van(graaf, waarde)
    assert (typebedrag, SH.property, shape) in graaf
    assert (shape, SH.minCount, Literal(1)) in graaf
    # Een attribuut met dit type verwijst naar de structuur met sh:node.
    bijdrage = ZORG["patient/eigen-bijdrage"]
    assert (bijdrage, RDF.type, MIM.Attribuutsoort) in graaf
    assert (bijdrage, MIM.type, typebedrag) in graaf
    shape = shape_van(graaf, bijdrage)
    assert (shape, SH.node, typebedrag) in graaf
    assert (shape, SH.nodeKind, SH.BlankNodeOrIRI) in graaf
    assert (shape, SH["class"], None) not in graaf


def test_relatieklasse_en_generalisatie(graaf):
    assert (ZORG.behandelrelatie, RDF.type, MIM.Relatieklasse) in graaf
    assert (ZORG.behandelrelatie, RDFS.subClassOf, RDF.Statement) in graaf
    assert (ZORG.huisarts, RDFS.subClassOf, ZORG.zorgverlener) in graaf


def test_enumeratie_en_waarden(graaf):
    enum = ZORG.patientstatus
    assert (enum, RDF.type, OWL.Class) in graaf
    assert (enum, RDF.type, SKOS.ConceptScheme) in graaf
    assert (enum, RDF.type, MIM.Enumeratie) in graaf
    assert (enum, RDFS.subClassOf, SKOS.Concept) in graaf
    assert (enum, MIM.datumOpname, Literal("2016-05-01", datatype=XSD.date)) in graaf
    shape = SHAPES["domein-zorg/zorg/patientstatus"]
    assert (shape, RDF.type, SH.NodeShape) in graaf
    assert (shape, SH.targetClass, enum) in graaf
    actief = ZORG["patientstatus/actief"]
    assert (actief, RDF.type, SKOS.Concept) in graaf
    assert (actief, RDF.type, enum) in graaf
    assert (actief, RDF.type, MIM.Enumeratiewaarde) in graaf
    assert (actief, SKOS.inScheme, enum) in graaf
    assert (actief, SKOS.notation, Literal("1")) in graaf
    assert (actief, MIM.code, Literal("1")) in graaf
    assert (actief, SKOS.prefLabel, Literal("actief", lang="nl")) in graaf
    assert (actief, MIM.definitie, Literal("De patient is in behandeling.", lang="nl")) in graaf
    assert (enum, MIM.waarde, actief) in graaf
    assert (enum, MIM.waarde, ZORG["patientstatus/inactief"]) in graaf


def test_elke_property_heeft_mim_typering_identificatie_en_model(graaf):
    properties = set(graaf.subjects(RDF.type, OWL.ObjectProperty)) | set(graaf.subjects(RDF.type, OWL.DatatypeProperty))
    assert properties
    mim_typen = {MIM.Attribuutsoort, MIM.Gegevensgroep, MIM.Relatiesoort, MIM.DataElement, MIM.ReferentieElement}
    for prop in properties:
        assert set(graaf.objects(prop, RDF.type)) & mim_typen, prop
        assert (prop, MIM.identificatie, Literal(str(prop), datatype=XSD.anyURI)) in graaf
        assert (prop, RDFS.isDefinedBy, None) in graaf, prop
        assert (prop, MIM.kardinaliteit, None) in graaf, prop


# ---------------------------------------------------------------------------
# 5. Validatie tegen de MIM-shapes
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HEEFT_PYSHACL, reason="pyshacl niet geïnstalleerd (dev_requirements)")
def test_export_valideert_tegen_mim_shapes_op_ontbrekende_brondata_na(graaf):
    """Alle meldingen van mim-shapes.ttl komen uit gaten in de brondata
    (ontbrekende verplichte metagegevens: sh:minCount, en de sh:node/sh:xone-
    meldingen die daaruit volgen), nooit uit de vorm van de export (datatype,
    class, nodeKind, maxCount, pattern, in, hasValue)."""
    shapes = Graph().parse("./test/data/mim/mim-shapes.ttl", format="turtle")
    # Het MIM-vocabulaire meemengen: de shapes controleren met sh:class op
    # mim:Datatype en met sh:hasValue op skos:inScheme van de MIM-waardelijsten.
    gemengd = Graph()
    gemengd += graaf
    gemengd.parse("./test/data/mim/mim.ttl", format="turtle")
    conformeert, resultaten, _ = pyshacl.validate(gemengd, shacl_graph=shapes, advanced=True)
    # Alleen de resultaten van het rapport zelf; geneste details (sh:detail)
    # van sh:node/sh:xone zijn ook sh:ValidationResult.
    rapport = next(resultaten.subjects(RDF.type, SH.ValidationReport))
    meldingen = [
        r
        for r in resultaten.objects(rapport, SH.result)
        if not str(resultaten.value(r, SH.focusNode)).startswith(str(MIM))  # het vocabulaire zelf telt niet
    ]
    componenten = {resultaten.value(r, SH.sourceConstraintComponent) for r in meldingen}
    toegestaan = {SH.MinCountConstraintComponent, SH.NodeConstraintComponent, SH.XoneConstraintComponent}
    assert componenten <= toegestaan, f"vormfouten in de export: {componenten - toegestaan}"
    # Elk attribuut heeft een mim:type en een kardinaliteit; alleen de
    # relatieklasse mist bron, doel en kardinaliteit (crunch_uml legt geen
    # associatieklasse vast) en shape:relatierol eist in mim-shapes.ttl een
    # relatierol die er bij relatiesoort-leidende modellering niet is.
    mincount = [
        r for r in meldingen if resultaten.value(r, SH.sourceConstraintComponent) == SH.MinCountConstraintComponent
    ]
    assert MIM.type not in {resultaten.value(r, SH.resultPath) for r in mincount}
    assert {
        resultaten.value(r, SH.focusNode) for r in mincount if resultaten.value(r, SH.resultPath) == MIM.kardinaliteit
    } == {ZORG.behandelrelatie}

    # Bekende gaten in het testmodel: enumeratiewaarden hebben in EA geen datum opname.
    paden = {(r, resultaten.value(r, SH.resultPath)) for r in meldingen}
    focus_datum = {resultaten.value(r, SH.focusNode) for r, pad in paden if pad == MIM.datumOpname}
    assert ZORG["patientstatus/actief"] in focus_datum
    # Patient zelf heeft alle verplichte metagegevens: geen directe minCount-melding.
    directe = {
        resultaten.value(r, SH.focusNode)
        for r in meldingen
        if resultaten.value(r, SH.sourceConstraintComponent) == SH.MinCountConstraintComponent
    }
    assert ZORG.patient not in directe
    assert ZORG["patient/naam"] not in directe
    assert INFORMATIEMODEL not in directe
    relatie_meldingen = {
        resultaten.value(r, SH.resultPath)
        for r in meldingen
        if resultaten.value(r, SH.focusNode) == ZORG["patient/heeft-zorgverlener"]
        and resultaten.value(r, SH.sourceConstraintComponent) == SH.MinCountConstraintComponent
    }
    assert relatie_meldingen <= {MIM.relatierol, MIM.herkomstDefinitie}
