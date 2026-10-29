"""
Tests voor de MIM-annotatielaag (crunch_uml/renderers/lod_mim.py) los van de
LOD-renderer: met een lege graaf en eenvoudige modelobjecten wordt per
MIM-metaklasse gecontroleerd welke triples erbij komen en wat als ontbrekend
of onvertaalbaar wordt geteld.
"""

from types import SimpleNamespace

import pytest
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SH, SKOS, XSD

from crunch_uml.renderers import mim
from crunch_uml.renderers.lod_mim import MIM, MimAnnotator

BASE = "https://voorbeeld.nl/lod/"
NS = Namespace(BASE + "zorg/")
GEO = Namespace("http://www.opengis.net/ont/geosparql#")


def nieuw():
    graph = Graph()
    return graph, MimAnnotator(graph, BASE, "nl")


def attribuut(**kwargs):
    velden = dict(
        name="naam",
        definitie="De naam.",
        herkomst="BRP",
        herkomst_definitie="BRP",
        datum_opname="2016-05-01",
        toelichting=None,
        begrip=None,
        mult_start="1",
        mult_end="1",
        mogelijk_geen_waarde="Nee",
        lengte=None,
        patroon=None,
        formeel_patroon=None,
        indicatie_formele_historie="Nee",
        indicatie_materiele_historie="Nee",
        heeft_tijdlijn_geldigheid="Nee",
        heeft_tijdlijn_registratie="Nee",
        indicatie_classificerend=None,
        authentiek="Authentiek",
        eenheid=None,
        minimumwaarde_inclusief=None,
        minimumwaarde_exclusief=None,
        maximumwaarde_inclusief=None,
        maximumwaarde_exclusief=None,
        primitive="AN80",
    )
    velden.update(kwargs)
    return SimpleNamespace(**velden)


# ---------------------------------------------------------------------------
# Packages
# ---------------------------------------------------------------------------


def test_informatiemodel_krijgt_versie_en_mim_metadata():
    graph, ann = nieuw()
    pkg = SimpleNamespace(
        name="Testmodel Zorg",
        id="EAPK_ROOT",
        definitie="Testmodel.",
        created="2024-01-15 10:00:00",
        modified="2026-10-01 12:00:00",
        version="1.0.0",
        author="Testauteur",
    )
    uri = URIRef(BASE)
    ann.annotate_informatiemodel(
        uri,
        pkg,
        versie="v3.0.0",
        titel="Gemeentelijk Gegevensmodel",
        uitgever="https://www.delft.nl/",
        licentie="https://creativecommons.org/licenses/by/4.0/",
        informatiedomein="Gemeentelijke overheid",
        informatiemodeltype="logisch",
    )
    assert (uri, RDF.type, OWL.Ontology) in graph
    assert (uri, RDF.type, MIM.Informatiemodel) in graph
    assert (uri, MIM.identificatie, Literal(BASE, datatype=XSD.anyURI)) in graph
    assert (uri, MIM.basisUri, Literal(BASE, datatype=XSD.anyURI)) in graph
    assert (uri, MIM.naam, Literal("Testmodel Zorg", lang="nl")) in graph
    assert (uri, DCTERMS.title, Literal("Gemeentelijk Gegevensmodel", lang="nl")) in graph
    assert (uri, MIM.mimversie, Literal("1.2")) in graph
    assert (uri, MIM.mimtaal, Literal("nl")) in graph
    assert (uri, MIM.informatiemodeltype, MIM.LogischInformatiemodel) in graph
    assert (uri, MIM.relatiemodelleringstype, MIM.RelatiesoortLeidend) in graph
    assert (uri, MIM.informatiedomein, Literal("Gemeentelijke overheid")) in graph
    assert (uri, MIM.datumOpname, Literal("2024-01-15", datatype=XSD.date)) in graph
    assert (uri, OWL.versionInfo, Literal("v3.0.0")) in graph
    assert (uri, OWL.versionIRI, URIRef(BASE + "v3.0.0/")) in graph
    assert (uri, DCTERMS.modified, Literal("2026-10-01", datatype=XSD.date)) in graph
    assert (uri, DCTERMS.publisher, URIRef("https://www.delft.nl/")) in graph
    assert (uri, DCTERMS.license, URIRef("https://creativecommons.org/licenses/by/4.0/")) in graph
    assert (uri, DCTERMS.creator, Literal("Testauteur")) in graph
    assert not ann.ontbrekend


def test_informatiemodel_zonder_opties_valt_terug_op_het_pakket_en_telt_gaten():
    graph, ann = nieuw()
    pkg = SimpleNamespace(
        name="Model", id="EAPK_ROOT", definitie=None, created=None, modified=None, version="2.5.0", author=None
    )
    uri = URIRef(BASE)
    ann.annotate_informatiemodel(uri, pkg)
    assert (uri, OWL.versionInfo, Literal("2.5.0")) in graph
    assert (uri, DCTERMS.title, Literal("Model", lang="nl")) in graph
    assert ann.ontbrekend[("Informatiemodel", "informatiedomein")] == 1
    assert ann.ontbrekend[("Informatiemodel", "datumOpname")] == 1
    assert list(graph.objects(uri, DCTERMS.publisher)) == []


def test_domein_is_ontology_en_mim_domein_met_basis_uri():
    graph, ann = nieuw()
    pkg = SimpleNamespace(
        name="Model Zorg", definitie="Zorg.", created="2024-01-15 10:00:00", version="2.1.0", alias=None
    )
    uri = URIRef(str(NS))
    ann.annotate_domein(uri, pkg, namespace=str(NS))
    ann.imports(URIRef(BASE), uri)
    assert (uri, RDF.type, OWL.Ontology) in graph
    assert (uri, RDF.type, MIM.Domein) in graph
    assert (uri, MIM.basisUri, Literal(str(NS), datatype=XSD.anyURI)) in graph
    assert (uri, MIM.datumOpname, Literal("2024-01-15", datatype=XSD.date)) in graph
    assert (uri, OWL.versionInfo, Literal("2.1.0")) in graph
    assert (URIRef(BASE), OWL.imports, uri) in graph


# ---------------------------------------------------------------------------
# Klassen
# ---------------------------------------------------------------------------


def test_objecttype_metagegevens_worden_opgeschoond_en_getypeerd():
    graph, ann = nieuw()
    cls = SimpleNamespace(
        name="Patient",
        definitie="Een persoon die zorg ontvangt.",
        herkomst="BRP#NOTES#Description: De registratie waaraan ...",
        herkomst_definitie=None,
        datum_opname="1 mei 2016",
        toelichting="Alleen ingeschreven patienten.",
        alias="Zorgvrager",
        begrip="https://begrippen.example.org/id/begrip/patient",
        populatie="Alle patienten.",
        kwaliteit="Dagelijks bijgewerkt.",
    )
    uri = NS.patient
    assert ann.annotate_class(uri, cls, mim.OBJECTTYPE) == MIM.Objecttype
    assert (uri, RDF.type, MIM.Objecttype) in graph
    assert (uri, MIM.identificatie, Literal(str(uri), datatype=XSD.anyURI)) in graph
    assert (uri, MIM.naam, Literal("Patient", lang="nl")) in graph
    assert (uri, MIM.definitie, Literal("Een persoon die zorg ontvangt.", lang="nl")) in graph
    assert (uri, MIM.herkomst, Literal("BRP")) in graph, "notities van de tagdefinitie moeten weg"
    assert (uri, MIM.datumOpname, Literal("2016-05-01", datatype=XSD.date)) in graph
    assert (uri, MIM.toelichting, Literal("Alleen ingeschreven patienten.", lang="nl")) in graph
    assert (uri, MIM.alias, Literal("Zorgvrager", lang="nl")) in graph
    assert (uri, MIM.populatie, Literal("Alle patienten.")) in graph
    assert (uri, MIM.kwaliteit, Literal("Dagelijks bijgewerkt.")) in graph
    assert (uri, MIM.indicatieAbstractObject, Literal(False)) in graph
    begrip = URIRef("https://begrippen.example.org/id/begrip/patient")
    assert (uri, MIM.begrip, begrip) in graph
    assert (uri, DCTERMS.subject, begrip) in graph
    assert (begrip, RDF.type, SKOS.Concept) in graph
    # Alleen herkomst definitie ontbrak.
    assert dict(ann.ontbrekend) == {("Objecttype", "herkomstDefinitie"): 1}


def test_begripsterm_voor_een_begrip_dat_geen_uri_is():
    graph, ann = nieuw()
    cls = SimpleNamespace(
        name="Zaak",
        definitie="x",
        herkomst="x",
        herkomst_definitie="x",
        datum_opname="2016-05-01",
        begrip="zaak (RGBZ)",
    )
    ann.annotate_class(NS.zaak, cls, mim.OBJECTTYPE)
    assert (NS.zaak, MIM.begripsterm, Literal("zaak (RGBZ)", lang="nl")) in graph
    assert list(graph.objects(NS.zaak, MIM.begrip)) == []


def test_relatieklasse_is_subklasse_van_rdf_statement():
    graph, ann = nieuw()
    cls = SimpleNamespace(
        name="Behandelrelatie", definitie="x", herkomst="x", herkomst_definitie="x", datum_opname="2016-05-01"
    )
    ann.annotate_class(NS.behandelrelatie, cls, mim.RELATIEKLASSE)
    assert (NS.behandelrelatie, RDF.type, MIM.Relatieklasse) in graph
    assert (NS.behandelrelatie, RDFS.subClassOf, RDF.Statement) in graph
    assert (NS.behandelrelatie, MIM.unidirectioneel, Literal(True)) in graph
    assert (NS.behandelrelatie, MIM.aggregatietype, MIM.Geen) in graph
    assert (NS.behandelrelatie, MIM.mogelijkGeenWaarde, Literal(False)) in graph
    assert ann.ontbrekend[("Relatieklasse", "kardinaliteit")] == 1


def test_gegevensgroeptype_en_gestructureerd_datatype_typering():
    graph, ann = nieuw()
    groep = SimpleNamespace(
        name="Adres", definitie=None, herkomst=None, herkomst_definitie=None, datum_opname="2016-05-01"
    )
    ann.annotate_class(NS.adres, groep, mim.GEGEVENSGROEPTYPE)
    assert (NS.adres, RDF.type, MIM.Gegevensgroeptype) in graph
    # Definitie en herkomst zijn bij een gegevensgroeptype optioneel.
    assert ("Gegevensgroeptype", "definitie") not in ann.ontbrekend
    assert ("Gegevensgroeptype", "herkomst") not in ann.ontbrekend

    datatype = SimpleNamespace(
        name="TypeBedrag",
        definitie="Bedrag met valuta.",
        herkomst="GGM",
        herkomst_definitie=None,
        datum_opname="2016-05-01",
    )
    ann.annotate_class(NS.typebedrag, datatype, mim.GESTRUCTUREERD_DATATYPE)
    assert (NS.typebedrag, RDF.type, MIM.GestructureerdDatatype) in graph
    assert (NS.typebedrag, RDF.type, OWL.Class) not in graph


def test_referentielijst_vraagt_locatie():
    graph, ann = nieuw()
    lijst = SimpleNamespace(
        name="Land", definitie="x", herkomst="x", herkomst_definitie="x", datum_opname="2016-05-01", uri=None
    )
    ann.annotate_class(NS.land, lijst, mim.REFERENTIELIJST)
    assert (NS.land, RDF.type, MIM.Referentielijst) in graph
    assert ann.ontbrekend[("Referentielijst", "locatie")] == 1


# ---------------------------------------------------------------------------
# Attribuutsoorten en varianten
# ---------------------------------------------------------------------------


def test_attribuutsoort_volledig():
    graph, ann = nieuw()
    attr = attribuut(
        lengte="80",
        patroon="Letters en spaties",
        formeel_patroon="^[A-Za-z ]+$",
        indicatie_formele_historie="Ja",
        toelichting="Zoals in de BRP.",
    )
    prop, shape = NS["patient/naam"], BNode()
    metaklasse = ann.annotate_attribute(
        prop,
        shape,
        attr,
        eigenaar_uri=NS.patient,
        eigenaar_soort=mim.OBJECTTYPE,
        kind="datatype",
        range_uri=XSD.string,
        max_length=80,
    )
    assert metaklasse == MIM.Attribuutsoort
    assert (prop, RDF.type, MIM.Attribuutsoort) in graph
    assert (NS.patient, MIM.attribuut, prop) in graph
    assert (prop, MIM.type, MIM.CharacterString) in graph
    assert (prop, MIM.kardinaliteit, Literal("1..1")) in graph
    assert (shape, SH.minCount, Literal(1)) in graph
    assert (shape, SH.maxCount, Literal(1)) in graph
    assert (prop, MIM.lengte, Literal("80")) in graph
    # De renderer zet sh:maxLength al vanuit AN80; geen tweede waarde.
    assert list(graph.objects(shape, SH.maxLength)) == []
    assert (prop, MIM.patroon, Literal("Letters en spaties")) in graph
    assert (prop, MIM.formeelPatroon, Literal("^[A-Za-z ]+$")) in graph
    assert (shape, SH.pattern, Literal("^[A-Za-z ]+$")) in graph
    assert (prop, MIM.indicatieFormeleHistorie, Literal(True)) in graph
    assert (prop, MIM.indicatieMaterieleHistorie, Literal(False)) in graph
    assert (prop, MIM.heeftTijdlijnGeldigheid, Literal(False)) in graph
    assert (prop, MIM.heeftTijdlijnRegistratie, Literal(False)) in graph
    assert (prop, MIM.indicatieAfleidbaar, Literal(False)) in graph
    assert (prop, MIM.indicatieClassificerend, Literal(False)) in graph
    assert (prop, MIM.mogelijkGeenWaarde, Literal(False)) in graph
    assert (prop, MIM.authentiek, MIM.Authentiek) in graph
    assert (prop, MIM.toelichting, Literal("Zoals in de BRP.", lang="nl")) in graph
    assert not ann.ontbrekend


def test_lengte_zonder_an_type_geeft_sh_maxlength():
    graph, ann = nieuw()
    attr = attribuut(lengte="50.0", primitive="String")
    prop, shape = NS["patient/opmerking"], BNode()
    ann.annotate_attribute(
        prop, shape, attr, eigenaar_uri=NS.patient, eigenaar_soort=mim.OBJECTTYPE, kind="datatype", range_uri=XSD.string
    )
    assert (prop, MIM.lengte, Literal("50")) in graph
    assert (shape, SH.maxLength, Literal(50)) in graph


def test_mogelijk_geen_waarde_laat_mincount_vervallen():
    graph, ann = nieuw()
    attr = attribuut(mogelijk_geen_waarde="Ja")
    prop, shape = NS["patient/naam"], BNode()
    ann.annotate_attribute(
        prop, shape, attr, eigenaar_uri=NS.patient, eigenaar_soort=mim.OBJECTTYPE, kind="datatype", range_uri=XSD.string
    )
    assert (prop, MIM.kardinaliteit, Literal("1..1")) in graph
    assert list(graph.objects(shape, SH.minCount)) == []
    assert (shape, SH.maxCount, Literal(1)) in graph
    assert (prop, MIM.mogelijkGeenWaarde, Literal(True)) in graph


def test_multipliciteit_nul_tot_veel_en_default():
    graph, ann = nieuw()
    attr = attribuut(mult_start="0", mult_end="-1")
    prop, shape = NS["patient/telefoonnummers"], BNode()
    ann.annotate_attribute(
        prop, shape, attr, eigenaar_uri=NS.patient, eigenaar_soort=mim.OBJECTTYPE, kind="datatype", range_uri=XSD.string
    )
    assert (prop, MIM.kardinaliteit, Literal("0..*")) in graph
    assert list(graph.objects(shape, SH.minCount)) == []
    assert list(graph.objects(shape, SH.maxCount)) == []

    onbekend = attribuut(mult_start=None, mult_end=None)
    prop2, shape2 = NS["patient/x"], BNode()
    ann.annotate_attribute(
        prop2,
        shape2,
        onbekend,
        eigenaar_uri=NS.patient,
        eigenaar_soort=mim.OBJECTTYPE,
        kind="datatype",
        range_uri=XSD.string,
    )
    assert (prop2, MIM.kardinaliteit, Literal("1..1")) in graph, "zonder bron geldt de UML/MIM-default 1..1"


def test_niet_ja_nee_wordt_default_en_geteld():
    graph, ann = nieuw()
    attr = attribuut(indicatie_formele_historie="n.v.t.#NOTES#Values: Ja,Nee,Zie groep,n.v.t.")
    prop = NS["patient/naam"]
    ann.annotate_attribute(
        prop,
        BNode(),
        attr,
        eigenaar_uri=NS.patient,
        eigenaar_soort=mim.OBJECTTYPE,
        kind="datatype",
        range_uri=XSD.string,
    )
    assert (prop, MIM.indicatieFormeleHistorie, Literal(False)) in graph
    assert ann.onvertaald[("indicatieFormeleHistorie", "geen ja/nee: n.v.t.")] == 1


def test_memo_placeholder_levert_geen_patroon():
    graph, ann = nieuw()
    attr = attribuut(patroon="<memo>")
    prop = NS["zorgverlener/registratienummer"]
    ann.annotate_attribute(
        prop,
        BNode(),
        attr,
        eigenaar_uri=NS.zorgverlener,
        eigenaar_soort=mim.OBJECTTYPE,
        kind="datatype",
        range_uri=XSD.string,
    )
    assert list(graph.objects(prop, MIM.patroon)) == []


def test_waardebereik_en_eenheid_in_het_datatype_van_het_attribuut():
    graph, ann = nieuw()
    attr = attribuut(
        name="gewicht", primitive="Decimal", eenheid="kg", minimumwaarde_inclusief="0", maximumwaarde_inclusief="500"
    )
    prop, shape = NS["patient/gewicht"], BNode()
    ann.annotate_attribute(
        prop,
        shape,
        attr,
        eigenaar_uri=NS.patient,
        eigenaar_soort=mim.OBJECTTYPE,
        kind="datatype",
        range_uri=XSD.decimal,
    )
    assert (prop, MIM.type, MIM.Decimal) in graph
    assert (prop, MIM.minimumwaardeInclusief, Literal("0", datatype=XSD.decimal)) in graph
    assert (shape, SH.minInclusive, Literal("0", datatype=XSD.decimal)) in graph
    assert (shape, SH.maxInclusive, Literal("500", datatype=XSD.decimal)) in graph
    eenheid = graph.value(prop, MIM.eenheid)
    assert (eenheid, RDF.type, URIRef("https://si-digital-framework.org/SI#MeasurementUnit")) in graph
    assert (eenheid, RDFS.label, Literal("kg", lang="nl")) in graph
    assert (prop, MIM.type, MIM.Decimal) in graph and (MIM.Decimal, RDF.type, MIM.PrimitiefDatatype) in graph


def test_geometrie_krijgt_eigen_primitief_datatype():
    graph, ann = nieuw()
    attr = attribuut(name="geometrie", primitive="Point")
    prop = NS["pand/geometrie"]
    ann.annotate_attribute(
        prop,
        BNode(),
        attr,
        eigenaar_uri=NS.pand,
        eigenaar_soort=mim.OBJECTTYPE,
        kind="datatype",
        range_uri=GEO.wktLiteral,
    )
    datatype = URIRef(BASE + "datatypen/point")
    assert (prop, MIM.type, datatype) in graph
    assert (datatype, RDF.type, MIM.PrimitiefDatatype) in graph
    assert (datatype, RDF.type, SH.NodeShape) in graph
    assert (datatype, SH.datatype, GEO.wktLiteral) in graph
    assert (datatype, MIM.naam, Literal("Point", lang="nl")) in graph
    # Een tweede attribuut met hetzelfde type hergebruikt de resource.
    ann.annotate_attribute(
        NS["perceel/geometrie"],
        BNode(),
        attr,
        eigenaar_uri=NS.perceel,
        eigenaar_soort=mim.OBJECTTYPE,
        kind="datatype",
        range_uri=GEO.wktLiteral,
    )
    assert len(list(graph.subjects(RDF.type, MIM.PrimitiefDatatype))) == 1


def test_enumeratie_getypeerd_attribuut_verwijst_naar_de_enumeratie():
    graph, ann = nieuw()
    attr = attribuut(name="status", primitive="PatientStatus", indicatie_classificerend="Ja")
    prop = NS["patient/status"]
    ann.annotate_attribute(
        prop,
        BNode(),
        attr,
        eigenaar_uri=NS.patient,
        eigenaar_soort=mim.OBJECTTYPE,
        kind="enum",
        range_uri=NS.patientstatus,
    )
    assert (prop, RDF.type, MIM.Attribuutsoort) in graph
    assert (prop, MIM.type, NS.patientstatus) in graph
    assert (prop, MIM.indicatieClassificerend, Literal(True)) in graph


def test_gegevensgroep_voor_attribuut_met_gegevensgroeptype():
    graph, ann = nieuw()
    attr = attribuut(name="adres", primitive="Adres", mult_start="0", mult_end="1")
    prop, shape = NS["patient/adres"], BNode()
    metaklasse = ann.annotate_attribute(
        prop,
        shape,
        attr,
        eigenaar_uri=NS.patient,
        eigenaar_soort=mim.OBJECTTYPE,
        kind="object",
        range_uri=NS.adres,
        doel_soort=mim.GEGEVENSGROEPTYPE,
    )
    assert metaklasse == MIM.Gegevensgroep
    assert (prop, MIM.gegevensgroeptype, NS.adres) in graph
    assert (NS.patient, MIM.gegevensgroep, prop) in graph
    assert (prop, MIM.kardinaliteit, Literal("0..1")) in graph
    assert (shape, SH.maxCount, Literal(1)) in graph
    assert list(graph.objects(prop, MIM.type)) == []


def test_klasse_getypeerd_attribuut_is_relatiesoort():
    graph, ann = nieuw()
    attr = attribuut(name="document", primitive="Document")
    prop = NS["zaak/document"]
    metaklasse = ann.annotate_attribute(
        prop,
        BNode(),
        attr,
        eigenaar_uri=NS.zaak,
        eigenaar_soort=mim.OBJECTTYPE,
        kind="object",
        range_uri=NS.document,
        doel_soort=mim.OBJECTTYPE,
    )
    assert metaklasse == MIM.Relatiesoort
    assert (prop, MIM.bron, NS.zaak) in graph
    assert (prop, MIM.doel, NS.document) in graph
    assert (prop, MIM.unidirectioneel, Literal(True)) in graph
    assert (prop, MIM.aggregatietype, MIM.Geen) in graph
    assert list(graph.objects(NS.zaak, MIM.attribuut)) == []


def test_attribuut_van_gestructureerd_datatype_is_data_element():
    graph, ann = nieuw()
    attr = attribuut(name="valuta", primitive="AN3", herkomst=None, herkomst_definitie=None, mogelijk_geen_waarde="Ja")
    prop, shape = NS["typebedrag/valuta"], BNode()
    metaklasse = ann.annotate_attribute(
        prop,
        shape,
        attr,
        eigenaar_uri=NS.typebedrag,
        eigenaar_soort=mim.GESTRUCTUREERD_DATATYPE,
        kind="datatype",
        range_uri=XSD.string,
        max_length=3,
    )
    assert metaklasse == MIM.DataElement
    assert (NS.typebedrag, MIM.dataElement, prop) in graph
    assert (prop, MIM.type, MIM.CharacterString) in graph
    # Een data-element kent geen 'mogelijk geen waarde': de kardinaliteit telt gewoon.
    assert (shape, SH.minCount, Literal(1)) in graph
    assert ("DataElement", "herkomst") not in ann.ontbrekend
    assert list(graph.objects(prop, MIM.authentiek)) == []


def test_attribuut_van_referentielijst_is_referentie_element():
    graph, ann = nieuw()
    attr = attribuut(name="code", primitive="AN2")
    prop = NS["land/code"]
    assert (
        ann.annotate_attribute(
            prop,
            BNode(),
            attr,
            eigenaar_uri=NS.land,
            eigenaar_soort=mim.REFERENTIELIJST,
            kind="datatype",
            range_uri=XSD.string,
        )
        == MIM.ReferentieElement
    )
    assert (NS.land, MIM.referentieElement, prop) in graph


# ---------------------------------------------------------------------------
# Relatiesoorten
# ---------------------------------------------------------------------------


def associatie(**kwargs):
    velden = dict(
        name="heeft zorgverlener",
        definitie="De zorgverlener die de patient behandelt.",
        herkomst="GGM",
        herkomst_definitie=None,
        datum_opname="2016-05-01",
        toelichting=None,
        begrip=None,
        mogelijk_geen_waarde="Nee",
        src_mult_start="0",
        src_mult_end="-1",
        dst_mult_start="1",
        dst_mult_end="1",
        dst_role="behandelaar",
        src_role=None,
        authentiek="Basisgegeven",
        indicatie_formele_historie="Ja",
        indicatie_materiele_historie="Nee",
        heeft_tijdlijn_geldigheid="Nee",
        heeft_tijdlijn_registratie="Nee",
    )
    velden.update(kwargs)
    return SimpleNamespace(**velden)


def test_relatiesoort_met_kardinaliteiten():
    graph, ann = nieuw()
    prop, shape = NS["patient/heeft-zorgverlener"], BNode()
    ann.annotate_association(prop, shape, associatie(), NS.patient, NS.zorgverlener)
    assert (prop, RDF.type, MIM.Relatiesoort) in graph
    assert (prop, MIM.naam, Literal("heeft zorgverlener", lang="nl")) in graph
    assert (prop, MIM.bron, NS.patient) in graph
    assert (prop, MIM.doel, NS.zorgverlener) in graph
    assert (prop, MIM.kardinaliteit, Literal("1..1")) in graph
    assert (prop, MIM.kardinaliteitRelatieBron, Literal("0..*")) in graph
    assert (shape, SH.minCount, Literal(1)) in graph
    assert (shape, SH.maxCount, Literal(1)) in graph
    assert (prop, MIM.unidirectioneel, Literal(True)) in graph
    assert (prop, MIM.aggregatietype, MIM.Geen) in graph
    assert (prop, MIM.authentiek, MIM.Basisgegeven) in graph
    assert (prop, MIM.indicatieFormeleHistorie, Literal(True)) in graph
    assert (prop, MIM.mogelijkGeenWaarde, Literal(False)) in graph
    assert dict(ann.ontbrekend) == {("Relatiesoort", "herkomstDefinitie"): 1}


def test_relatiesoort_mogelijk_geen_waarde_en_nul_tot_een():
    graph, ann = nieuw()
    prop, shape = NS["patient/heeft-huisarts"], BNode()
    ann.annotate_association(
        prop,
        shape,
        associatie(
            name="heeft huisarts", dst_mult_start="0", dst_mult_end="1", mogelijk_geen_waarde="Ja", authentiek=None
        ),
        NS.patient,
        NS.huisarts,
    )
    assert (prop, MIM.kardinaliteit, Literal("0..1")) in graph
    assert list(graph.objects(shape, SH.minCount)) == []
    assert (shape, SH.maxCount, Literal(1)) in graph
    assert ann.ontbrekend[("Relatiesoort", "authentiek")] == 1


def test_relatiesoort_zonder_naam_gebruikt_de_rol_en_onbruikbare_kardinaliteit_wordt_geteld():
    graph, ann = nieuw()
    prop = NS["patient/behandelaar"]
    ann.annotate_association(
        prop, BNode(), associatie(name=None, dst_mult_start="-1", dst_mult_end="-1"), NS.patient, NS.zorgverlener
    )
    assert (prop, MIM.naam, Literal("behandelaar", lang="nl")) in graph
    assert list(graph.objects(prop, MIM.kardinaliteit)) == []
    assert ann.ontbrekend[("Relatiesoort", "kardinaliteit")] == 1
    assert ann.onvertaald[("kardinaliteit", "onbruikbaar: -1..-1")] == 1


# ---------------------------------------------------------------------------
# Enumeraties
# ---------------------------------------------------------------------------


def test_enumeratie_en_waarden():
    graph, ann = nieuw()
    enum = SimpleNamespace(
        name="PatientStatus",
        definitie="Statussen.",
        datum_opname="2016-05-01",
        toelichting=None,
        herkomst=None,
        herkomst_definitie=None,
    )
    enum_uri, shape_uri = NS.patientstatus, URIRef(BASE + "shapes/zorg/patientstatus")
    ann.annotate_enumeration(enum_uri, enum, shape_uri)
    assert (enum_uri, RDF.type, MIM.Enumeratie) in graph
    assert (enum_uri, RDFS.subClassOf, SKOS.Concept) in graph
    assert (shape_uri, RDF.type, SH.NodeShape) in graph
    assert (shape_uri, SH.targetClass, enum_uri) in graph
    paden = {graph.value(p, SH.path) for p in graph.objects(shape_uri, SH.property)}
    assert paden == {RDFS.label, SKOS.notation, SKOS.definition, RDF.type, SKOS.inScheme}
    assert ("Enumeratie", "herkomst") not in ann.ontbrekend

    literal = SimpleNamespace(name="actief", alias="1", definitie="In behandeling.")
    concept = NS["patientstatus/actief"]
    ann.annotate_enum_literal(concept, literal, enum_uri)
    assert (concept, RDF.type, MIM.Enumeratiewaarde) in graph
    assert (enum_uri, MIM.waarde, concept) in graph
    assert (concept, SKOS.notation, Literal("1")) in graph
    assert (concept, MIM.code, Literal("1")) in graph
    assert (concept, MIM.definitie, Literal("In behandeling.", lang="nl")) in graph
    assert (concept, RDFS.label, Literal("actief", lang="nl")) in graph
    assert ann.ontbrekend[("Enumeratiewaarde", "datumOpname")] == 1


# ---------------------------------------------------------------------------
# Taal en rapportage
# ---------------------------------------------------------------------------


def test_zonder_taal_geen_taaltags():
    graph = Graph()
    ann = MimAnnotator(graph, BASE, "")
    cls = SimpleNamespace(
        name="Zaak", definitie="Een zaak.", herkomst="RGBZ", herkomst_definitie="RGBZ", datum_opname="2016-05-01"
    )
    ann.annotate_class(NS.zaak, cls, mim.OBJECTTYPE)
    assert (NS.zaak, MIM.naam, Literal("Zaak")) in graph
    assert (NS.zaak, MIM.definitie, Literal("Een zaak.")) in graph
    assert ann.lit("x") == Literal("x")


def test_samenvatting_noemt_typering_en_gaten():
    graph, ann = nieuw()
    cls = SimpleNamespace(name="Zaak", definitie=None, herkomst=None, herkomst_definitie=None, datum_opname="morgen")
    ann.annotate_class(NS.zaak, cls, mim.OBJECTTYPE)
    tekst = ann.samenvatting()
    assert "Objecttype 1" in tekst
    assert "Objecttype.definitie: 1" in tekst
    assert "datum onleesbaar: morgen" in tekst


@pytest.mark.parametrize(
    "kind,eigenaar,doel,verwacht",
    [
        ("datatype", mim.OBJECTTYPE, None, MIM.Attribuutsoort),
        ("enum", mim.OBJECTTYPE, None, MIM.Attribuutsoort),
        ("object", mim.OBJECTTYPE, mim.GESTRUCTUREERD_DATATYPE, MIM.Attribuutsoort),
        ("object", mim.OBJECTTYPE, mim.REFERENTIELIJST, MIM.Attribuutsoort),
        ("object", mim.OBJECTTYPE, mim.GEGEVENSGROEPTYPE, MIM.Gegevensgroep),
        ("object", mim.OBJECTTYPE, mim.OBJECTTYPE, MIM.Relatiesoort),
        ("object", mim.GEGEVENSGROEPTYPE, mim.OBJECTTYPE, MIM.Relatiesoort),
        ("object", mim.REFERENTIELIJST, mim.OBJECTTYPE, MIM.Relatiesoort),
        ("object", mim.GESTRUCTUREERD_DATATYPE, mim.RELATIEKLASSE, MIM.Relatiesoort),
        ("datatype", mim.GESTRUCTUREERD_DATATYPE, None, MIM.DataElement),
        ("datatype", mim.REFERENTIELIJST, None, MIM.ReferentieElement),
        ("datatype", mim.CODELIJST, None, MIM.ReferentieElement),
    ],
)
def test_attribute_metaklasse(kind, eigenaar, doel, verwacht):
    _, ann = nieuw()
    assert ann.attribute_metaklasse(kind, eigenaar, doel) == verwacht
