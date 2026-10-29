"""MIM 1.2-laag van de LOD-export: typering en metagegevens op de resources
die :class:`~crunch_uml.renderers.lodrenderer.LodRenderer` aanmaakt.

De normatieve transformatie (MIM 1.2, bijlage 6.4) vertaalt een MIM-model
naar RDFS/OWL/SHACL. De renderer maakt die RDFS/OWL/SHACL-resources; deze
module zet op *dezelfde* resources de MIM-metaklasse (``a mim:Objecttype``
naast ``owl:Class``) en de MIM-metagegevens (``mim:herkomst``,
``mim:kardinaliteit``, ...), zodat de export zowel als gewone ontologie als
als MIM-model leesbaar is en tegen mim-shapes.ttl te valideren is.

Wat de bron niet levert, wordt niet verzonnen: ontbrekende verplichte
metagegevens worden geteld (:meth:`MimAnnotator.samenvatting`) en blijven
over als SHACL-meldingen die aan de brondata liggen. Alleen voor de
MIM-defaults (booleans ``false``, kardinaliteit ``1..1``, ``unidirectioneel
true``, ``aggregatietype mim:Geen``) wordt de default uitgeschreven.
"""

import logging
import re
from collections import Counter
from typing import Dict, Optional

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SH, SKOS, XSD

from crunch_uml.renderers import mim

logger = logging.getLogger()

MIM = mim.MIM
# SI Digital Framework: de shapes verwachten een eenheid als si:MeasurementUnit.
SI = Namespace("https://si-digital-framework.org/SI#")
# Relatiemodellering in GGM-modellen: de relatiesoort (associatie) is leidend.
RELATIEMODELLERINGSTYPE = MIM.RelatiesoortLeidend

_URI_RE = re.compile(r"^https?://\S+$")


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


class MimAnnotator:
    """Zet MIM-typering en -metagegevens op de resources van één export."""

    def __init__(self, graph: Graph, base: str, lang: Optional[str] = "nl"):
        self.g = graph
        self.base = base
        self.lang = lang or None
        self.datatype_ns = Namespace(base + "datatypen/")
        self._eigen_datatypen: Dict[str, URIRef] = {}
        # (metaklasse, metagegeven) -> aantal resources waarvoor de bron geen
        # waarde had terwijl MIM er één verlangt.
        self.ontbrekend: Counter = Counter()
        # (metagegeven, reden) -> aantal waarden die wel in de bron staan maar
        # niet te vertalen zijn (onleesbare datum, onbekende authenticiteit).
        self.onvertaald: Counter = Counter()
        self.getypeerd: Counter = Counter()
        graph.bind("mim", MIM)
        graph.bind("skos", SKOS)
        graph.bind("owl", OWL)
        graph.bind("xsd", XSD)

    # ------------------------------------------------------------------
    # Basisbouwstenen
    # ------------------------------------------------------------------

    def lit(self, text) -> Literal:
        """Tekstliteral in de ingestelde taal (of zonder taaltag)."""
        return mim.lang_literal(text, self.lang)

    def _tekst(self, uri, pred, value, taal=True) -> bool:
        text = mim.clean_value(value)
        if text is None:
            return False
        self.g.add((uri, pred, self.lit(text) if taal else Literal(text)))
        return True

    def _verplicht(self, soort, veld, aanwezig: bool):
        if not aanwezig:
            self.ontbrekend[(soort, veld)] += 1

    def _bool(self, uri, pred, value, default: Optional[bool], soort, veld):
        parsed = mim.parse_bool(value)
        if parsed is None and mim.clean_value(value) is not None:
            # 'n.v.t.', 'zie groep': wel een waarde, maar geen ja/nee.
            self.onvertaald[(veld, f"geen ja/nee: {mim.clean_value(value)}")] += 1
        if parsed is None:
            parsed = default
        if parsed is None:
            self._verplicht(soort, veld, False)
            return
        self.g.add((uri, pred, Literal(parsed)))

    def _datum(self, uri, pred, value, soort, veld, verplicht=True):
        text = mim.clean_value(value)
        if text is None:
            if verplicht:
                self._verplicht(soort, veld, False)
            return
        literal = mim.date_literal(text)
        if literal is None:
            self.onvertaald[(veld, f"datum onleesbaar: {text[:40]}")] += 1
            if verplicht:
                self._verplicht(soort, veld, False)
            return
        self.g.add((uri, pred, literal))

    def _identificeer(self, uri, naam, metaklasse):
        self.g.add((uri, RDF.type, metaklasse))
        self.g.add((uri, MIM.identificatie, Literal(str(uri), datatype=XSD.anyURI)))
        if naam:
            self.g.add((uri, MIM.naam, self.lit(naam)))
        self.getypeerd[metaklasse] += 1

    def _begrip(self, uri, value):
        """mim:begrip verwijst naar een begrip (skos:Concept); volgens 6.4.9.4
        wordt dat dct:subject. Een niet-URI gaat als mim:begripsterm mee."""
        text = mim.clean_value(value)
        if text is None:
            return
        if _URI_RE.match(text):
            begrip = URIRef(text)
            self.g.add((uri, MIM.begrip, begrip))
            self.g.add((uri, DCTERMS.subject, begrip))
            self.g.add((begrip, RDF.type, SKOS.Concept))
        else:
            self.g.add((uri, MIM.begripsterm, self.lit(text)))

    def _authentiek(self, uri, value, soort):
        concept = mim.authenticiteit(value)
        if concept is None:
            text = mim.clean_value(value)
            if text is not None:
                self.onvertaald[("authentiek", f"onbekende categorie: {text[:40]}")] += 1
            self._verplicht(soort, "authentiek", False)
            return
        self.g.add((uri, MIM.authentiek, concept))

    def _algemeen(self, uri, obj, soort, definitie_verplicht=True, herkomst_verplicht=True):
        """De metagegevens die (bijna) elk modelelement heeft: definitie,
        herkomst, herkomst definitie, datum opname, toelichting, alias, begrip."""
        self._verplicht(
            soort,
            "definitie",
            self._tekst(uri, MIM.definitie, getattr(obj, "definitie", None)) or not definitie_verplicht,
        )
        self._verplicht(
            soort,
            "herkomst",
            self._tekst(uri, MIM.herkomst, getattr(obj, "herkomst", None), taal=False) or not herkomst_verplicht,
        )
        self._verplicht(
            soort,
            "herkomstDefinitie",
            self._tekst(uri, MIM.herkomstDefinitie, getattr(obj, "herkomst_definitie", None), taal=False)
            or not herkomst_verplicht,
        )
        self._datum(uri, MIM.datumOpname, getattr(obj, "datum_opname", None), soort, "datumOpname")
        self._tekst(uri, MIM.toelichting, getattr(obj, "toelichting", None))
        self._tekst(uri, MIM.alias, getattr(obj, "alias", None))
        self._begrip(uri, getattr(obj, "begrip", None))

    # ------------------------------------------------------------------
    # Packages
    # ------------------------------------------------------------------

    def annotate_informatiemodel(
        self,
        uri: URIRef,
        pkg,
        *,
        versie: Optional[str] = None,
        titel: Optional[str] = None,
        uitgever: Optional[str] = None,
        licentie: Optional[str] = None,
        informatiedomein: Optional[str] = None,
        informatiemodeltype: Optional[str] = "logisch",
        gewijzigd=None,
    ):
        """Het wortelpakket als owl:Ontology + mim:Informatiemodel met versie-
        en MIM-metadata (MIM 4, 6.4.7)."""
        g = self.g
        g.add((uri, RDF.type, OWL.Ontology))
        self._identificeer(uri, pkg.name, MIM.Informatiemodel)
        g.add((uri, MIM.basisUri, Literal(self.base, datatype=XSD.anyURI)))
        g.add((uri, RDFS.label, self.lit(pkg.name)))
        g.add((uri, DCTERMS.title, self.lit(titel or pkg.name)))
        if self._tekst(uri, RDFS.comment, pkg.definitie):
            self._tekst(uri, DCTERMS.description, pkg.definitie)
        self._tekst(uri, MIM.definitie, pkg.definitie)
        g.add((uri, MIM.mimversie, Literal(mim.MIM_VERSIE)))
        g.add((uri, MIM.relatiemodelleringstype, RELATIEMODELLERINGSTYPE))
        if self.lang:
            g.add((uri, MIM.mimtaal, Literal(self.lang)))
        modeltype = mim.informatiemodeltype(informatiemodeltype)
        self._verplicht("Informatiemodel", "informatiemodeltype", modeltype is not None)
        if modeltype is not None:
            g.add((uri, MIM.informatiemodeltype, modeltype))
        self._verplicht(
            "Informatiemodel", "informatiedomein", self._tekst(uri, MIM.informatiedomein, informatiedomein, taal=False)
        )
        # Datum opname van het model: de aanmaakdatum van het wortelpakket.
        self._datum(uri, MIM.datumOpname, getattr(pkg, "created", None), "Informatiemodel", "datumOpname")
        versie = mim.clean_value(versie) or mim.clean_value(getattr(pkg, "version", None))
        if versie:
            g.add((uri, OWL.versionInfo, Literal(versie)))
            if segment := mim.version_segment(versie):
                g.add((uri, OWL.versionIRI, URIRef(self.base + segment + "/")))
        gewijzigd_literal = mim.date_literal(gewijzigd) or mim.date_literal(getattr(pkg, "modified", None))
        if gewijzigd_literal is not None:
            g.add((uri, DCTERMS.modified, gewijzigd_literal))
        if uitgever := mim.clean_value(uitgever):
            g.add((uri, DCTERMS.publisher, URIRef(uitgever) if _URI_RE.match(uitgever) else Literal(uitgever)))
        if licentie := mim.clean_value(licentie):
            g.add((uri, DCTERMS.license, URIRef(licentie) if _URI_RE.match(licentie) else Literal(licentie)))
        if auteur := mim.clean_value(getattr(pkg, "author", None)):
            g.add((uri, DCTERMS.creator, Literal(auteur)))

    def annotate_domein(self, uri: URIRef, pkg, namespace: Optional[str] = None):
        """Een (model)pakket als owl:Ontology + mim:Domein (6.4.7.1)."""
        g = self.g
        g.add((uri, RDF.type, OWL.Ontology))
        self._identificeer(uri, pkg.name, MIM.Domein)
        g.add((uri, MIM.basisUri, Literal(namespace or str(uri), datatype=XSD.anyURI)))
        self._tekst(uri, MIM.definitie, pkg.definitie)
        self._tekst(uri, MIM.alias, getattr(pkg, "alias", None))
        self._datum(uri, MIM.datumOpname, getattr(pkg, "created", None), "Domein", "datumOpname")
        if versie := mim.clean_value(getattr(pkg, "version", None)):
            g.add((uri, OWL.versionInfo, Literal(versie)))

    def imports(self, ontology: URIRef, geimporteerd: URIRef):
        """6.4.9.40: het pakket dat een subpakket bevat importeert diens ontologie."""
        self.g.add((ontology, OWL.imports, geimporteerd))

    # ------------------------------------------------------------------
    # Klassen
    # ------------------------------------------------------------------

    def annotate_class(self, class_uri: URIRef, cls, soort: str):
        """Typeer een modelklasse naar haar MIM-soort en zet de metagegevens.

        Objecttype, Gegevensgroeptype, Relatieklasse, Referentielijst en
        Codelijst blijven owl:Class; een GestructureerdDatatype is alleen een
        sh:NodeShape (6.4.6.3) en de aanroeper maakt er dus geen owl:Class van.
        """
        g = self.g
        metaklasse = {
            mim.OBJECTTYPE: MIM.Objecttype,
            mim.GEGEVENSGROEPTYPE: MIM.Gegevensgroeptype,
            mim.GESTRUCTUREERD_DATATYPE: MIM.GestructureerdDatatype,
            mim.RELATIEKLASSE: MIM.Relatieklasse,
            mim.REFERENTIELIJST: MIM.Referentielijst,
            mim.CODELIJST: MIM.Codelijst,
        }[soort]
        self._identificeer(class_uri, cls.name, metaklasse)
        if soort == mim.RELATIEKLASSE:
            g.add((class_uri, RDFS.subClassOf, RDF.Statement))
        definitie_verplicht = soort != mim.GEGEVENSGROEPTYPE
        herkomst_verplicht = soort in (
            mim.OBJECTTYPE,
            mim.RELATIEKLASSE,
            mim.REFERENTIELIJST,
            mim.CODELIJST,
            mim.GESTRUCTUREERD_DATATYPE,
        )
        self._algemeen(class_uri, cls, soort, definitie_verplicht, herkomst_verplicht)
        if soort in (mim.OBJECTTYPE, mim.RELATIEKLASSE):
            self._tekst(class_uri, MIM.populatie, getattr(cls, "populatie", None), taal=False)
            self._tekst(class_uri, MIM.kwaliteit, getattr(cls, "kwaliteit", None), taal=False)
            # EA's isAbstract wordt niet opgeslagen; MIM-default is false.
            g.add((class_uri, MIM.indicatieAbstractObject, Literal(False)))
        if soort == mim.RELATIEKLASSE:
            # Een relatieklasse is ook een relatiesoort (mim:Relatieklasse
            # rdfs:subClassOf mim:Relatiesoort): richting, aggregatie en de
            # indicaties krijgen de MIM-defaults; bron, doel en kardinaliteit
            # kent de bron niet (crunch_uml legt geen associatieklasse vast).
            g.add((class_uri, MIM.unidirectioneel, Literal(True)))
            g.add((class_uri, MIM.aggregatietype, MIM.Geen))
            for pred in (
                MIM.heeftTijdlijnGeldigheid,
                MIM.heeftTijdlijnRegistratie,
                MIM.indicatieMaterieleHistorie,
                MIM.indicatieFormeleHistorie,
                MIM.indicatieAfleidbaar,
                MIM.mogelijkGeenWaarde,
            ):
                g.add((class_uri, pred, Literal(False)))
            for veld in ("bron", "doel", "kardinaliteit"):
                self._verplicht(soort, veld, False)
        if soort in (mim.REFERENTIELIJST, mim.CODELIJST):
            self._verplicht(
                soort, "locatie", self._tekst(class_uri, MIM.locatie, getattr(cls, "uri", None), taal=False)
            )
        return metaklasse

    # ------------------------------------------------------------------
    # Attribuutsoorten, gegevensgroepen, data-elementen
    # ------------------------------------------------------------------

    def attribute_metaklasse(self, kind: str, eigenaar_soort: str, doel_soort: Optional[str]) -> URIRef:
        """Welke MIM-metaklasse een attribuut krijgt.

        * attribuut getypeerd met een objecttype (klasse als type) -> in MIM
          een relatie, dus mim:Relatiesoort, wie de eigenaar ook is (een
          referentie-element of data-element met een objecttype als type is
          in MIM geen datatype-element);
        * attribuut van een gestructureerd datatype -> mim:DataElement;
        * attribuut van een referentielijst -> mim:ReferentieElement;
        * attribuut getypeerd met een gegevensgroeptype -> mim:Gegevensgroep;
        * anders mim:Attribuutsoort (primitief datatype, enumeratie,
          gestructureerd datatype, referentielijst).
        """
        if kind == "object" and doel_soort in (mim.OBJECTTYPE, mim.RELATIEKLASSE):
            return MIM.Relatiesoort
        if eigenaar_soort == mim.GESTRUCTUREERD_DATATYPE:
            return MIM.DataElement
        if eigenaar_soort in (mim.REFERENTIELIJST, mim.CODELIJST):
            return MIM.ReferentieElement
        if kind == "object" and doel_soort == mim.GEGEVENSGROEPTYPE:
            return MIM.Gegevensgroep
        return MIM.Attribuutsoort

    def annotate_attribute(
        self,
        prop_uri: URIRef,
        shape_node,
        attribute,
        *,
        eigenaar_uri: URIRef,
        eigenaar_soort: str,
        kind: str,
        range_uri: URIRef,
        doel_soort: Optional[str] = None,
        max_length: Optional[int] = None,
    ) -> URIRef:
        """MIM-typering en -metagegevens voor een attribuut; zet ook
        sh:minCount/sh:maxCount, sh:minLength/sh:maxLength, sh:pattern en de
        waardebereik-constraints op de PropertyShape."""
        g = self.g
        metaklasse = self.attribute_metaklasse(kind, eigenaar_soort, doel_soort)
        soort = str(metaklasse).rsplit("#", 1)[-1]
        self._identificeer(prop_uri, attribute.name, metaklasse)
        self._algemeen(
            prop_uri,
            attribute,
            soort,
            herkomst_verplicht=metaklasse in (MIM.Attribuutsoort, MIM.Gegevensgroep, MIM.Relatiesoort),
        )

        # Verbinding met de eigenaar (6.4.9.37/38 en de datatype-varianten).
        eigenaar_relatie = {
            MIM.Attribuutsoort: MIM.attribuut,
            MIM.Gegevensgroep: MIM.gegevensgroep,
            MIM.DataElement: MIM.dataElement,
            MIM.ReferentieElement: MIM.referentieElement,
        }.get(metaklasse)
        if eigenaar_relatie is not None:
            g.add((eigenaar_uri, eigenaar_relatie, prop_uri))

        # Kardinaliteit (6.4.9.15/18); zonder bron is de UML/MIM-default 1..1.
        kard = mim.kardinaliteit(getattr(attribute, "mult_start", None), getattr(attribute, "mult_end", None)) or "1..1"
        mogelijk_geen_waarde = mim.parse_bool(getattr(attribute, "mogelijk_geen_waarde", None))
        g.add((prop_uri, MIM.kardinaliteit, Literal(kard)))
        self._counts(shape_node, kard, mogelijk_geen_waarde if metaklasse != MIM.DataElement else None)

        if metaklasse == MIM.Relatiesoort:
            g.add((prop_uri, MIM.bron, eigenaar_uri))
            g.add((prop_uri, MIM.doel, range_uri))
            g.add((prop_uri, MIM.unidirectioneel, Literal(True)))
            g.add((prop_uri, MIM.aggregatietype, MIM.Geen))
        elif metaklasse == MIM.Gegevensgroep:
            g.add((prop_uri, MIM.gegevensgroeptype, range_uri))
        else:
            self._type(prop_uri, attribute, kind, range_uri)
            self._lengte_patroon(prop_uri, shape_node, attribute, max_length)
            self._waardebereik(prop_uri, shape_node, attribute, range_uri if kind == "datatype" else None)

        if metaklasse in (MIM.Attribuutsoort, MIM.Relatiesoort):
            self._bool(
                prop_uri,
                MIM.heeftTijdlijnGeldigheid,
                getattr(attribute, "heeft_tijdlijn_geldigheid", None),
                False,
                soort,
                "heeftTijdlijnGeldigheid",
            )
            self._bool(
                prop_uri,
                MIM.heeftTijdlijnRegistratie,
                getattr(attribute, "heeft_tijdlijn_registratie", None),
                False,
                soort,
                "heeftTijdlijnRegistratie",
            )
            self._bool(
                prop_uri,
                MIM.indicatieMaterieleHistorie,
                getattr(attribute, "indicatie_materiele_historie", None),
                False,
                soort,
                "indicatieMaterieleHistorie",
            )
            self._bool(
                prop_uri,
                MIM.indicatieFormeleHistorie,
                getattr(attribute, "indicatie_formele_historie", None),
                False,
                soort,
                "indicatieFormeleHistorie",
            )
            g.add((prop_uri, MIM.indicatieAfleidbaar, Literal(False)))
            self._bool(prop_uri, MIM.mogelijkGeenWaarde, mogelijk_geen_waarde, False, soort, "mogelijkGeenWaarde")
        if metaklasse == MIM.Attribuutsoort:
            self._bool(
                prop_uri,
                MIM.indicatieClassificerend,
                getattr(attribute, "indicatie_classificerend", None),
                False,
                soort,
                "indicatieClassificerend",
            )
        if metaklasse in (MIM.Attribuutsoort, MIM.Gegevensgroep, MIM.Relatiesoort):
            self._authentiek(prop_uri, getattr(attribute, "authentiek", None), soort)
        return metaklasse

    def _counts(self, shape_node, kard: str, mogelijk_geen_waarde: Optional[bool]):
        if shape_node is None:
            return
        min_count, max_count = mim.min_max_count(kard, mogelijk_geen_waarde)
        if min_count is not None:
            self.g.add((shape_node, SH.minCount, Literal(min_count)))
        if max_count is not None:
            self.g.add((shape_node, SH.maxCount, Literal(max_count)))

    def _type(self, prop_uri, attribute, kind, range_uri):
        """mim:type (6.4.9.20): standaarddatatype uit het MIM-vocabulaire,
        anders een eigen primitief datatype; enumeraties, gestructureerde
        datatypen en referentielijsten verwijzen naar de eigen resource."""
        if kind == "datatype":
            datatype = mim.mim_datatype(range_uri)
            if datatype is not None:
                # 6.4.6.2: de standaarddatatypen zijn mim:PrimitiefDatatype; de
                # export zegt dat zelf, zodat sh:class mim:Datatype ook zonder
                # mim.ttl klopt (dat bestand typeert mim:Decimal bovendien per
                # abuis als 'mim:PrititiefDatatype').
                self.g.add((datatype, RDF.type, MIM.PrimitiefDatatype))
            else:
                datatype = self.eigen_primitief_datatype(attribute.primitive, range_uri)
        else:
            datatype = range_uri
        self.g.add((prop_uri, MIM.type, datatype))

    def eigen_primitief_datatype(self, naam, xsd_type) -> URIRef:
        """Een primitief datatype zonder MIM-tegenhanger (bijv. geometrie als
        geo:wktLiteral) wordt een eigen mim:PrimitiefDatatype met de naam uit
        het bronmodel en een sh:NodeShape met sh:datatype (6.4.6.1)."""
        sleutel = slugify(naam) or slugify(str(xsd_type).rsplit("#", 1)[-1]) or "datatype"
        if sleutel not in self._eigen_datatypen:
            uri = self.datatype_ns[sleutel]
            self._eigen_datatypen[sleutel] = uri
            label = (naam or str(xsd_type).rsplit("#", 1)[-1]).strip()
            self._identificeer(uri, label, MIM.PrimitiefDatatype)
            self.g.add((uri, RDF.type, SH.NodeShape))
            self.g.add((uri, SH.datatype, xsd_type))
            self.g.add((uri, RDFS.label, self.lit(label)))
            self.g.add(
                (
                    uri,
                    MIM.definitie,
                    self.lit(
                        f"Primitief datatype '{label}' uit het bronmodel, uitgedrukt als {str(xsd_type).rsplit('#', 1)[-1]}."
                    ),
                )
            )
            self.ontbrekend[("PrimitiefDatatype", "herkomst")] += 1
            self.ontbrekend[("PrimitiefDatatype", "datumOpname")] += 1
        return self._eigen_datatypen[sleutel]

    def _lengte_patroon(self, prop_uri, shape_node, attribute, max_length):
        g = self.g
        lengte = mim.normalize_number(getattr(attribute, "lengte", None))
        if lengte is not None:
            g.add((prop_uri, MIM.lengte, Literal(lengte)))
            min_length, max_from_tag = mim.lengte_bounds(lengte)
            if shape_node is not None:
                if min_length is not None:
                    g.add((shape_node, SH.minLength, Literal(min_length)))
                if max_from_tag is not None and max_length is None:
                    g.add((shape_node, SH.maxLength, Literal(max_from_tag)))
        self._tekst(prop_uri, MIM.patroon, getattr(attribute, "patroon", None), taal=False)
        formeel = mim.clean_value(getattr(attribute, "formeel_patroon", None))
        if formeel is not None:
            g.add((prop_uri, MIM.formeelPatroon, Literal(formeel)))
            if shape_node is not None:
                g.add((shape_node, SH.pattern, Literal(formeel)))

    def _waardebereik(self, prop_uri, shape_node, attribute, datatype):
        """6.4.9.41-44: minimum-/maximumwaarde als mim:-literal en als
        sh:minInclusive e.d. in het datatype van het attribuut; 6.4.9.46:
        eenheid."""
        g = self.g
        grenzen = (
            ("minimumwaarde_inclusief", MIM.minimumwaardeInclusief, SH.minInclusive),
            ("minimumwaarde_exclusief", MIM.minimumwaardeExclusief, SH.minExclusive),
            ("maximumwaarde_inclusief", MIM.maximumwaardeInclusief, SH.maxInclusive),
            ("maximumwaarde_exclusief", MIM.maximumwaardeExclusief, SH.maxExclusive),
        )
        for veld, mim_pred, sh_pred in grenzen:
            waarde = mim.clean_value(getattr(attribute, veld, None))
            if waarde is None:
                continue
            literal = Literal(waarde, datatype=datatype) if datatype is not None else Literal(waarde)
            g.add((prop_uri, mim_pred, literal))
            if shape_node is not None:
                g.add((shape_node, sh_pred, literal))
        eenheid = mim.clean_value(getattr(attribute, "eenheid", None))
        if eenheid is not None:
            if _URI_RE.match(eenheid):
                g.add((prop_uri, MIM.eenheid, URIRef(eenheid)))
            else:
                # Een tekstuele eenheid ('kg') wordt een meeteenheid-node met
                # die tekst als label; de shapes verwachten si:MeasurementUnit.
                unit = BNode()
                g.add((prop_uri, MIM.eenheid, unit))
                g.add((unit, RDF.type, SI.MeasurementUnit))
                g.add((unit, RDFS.label, self.lit(eenheid)))

    # ------------------------------------------------------------------
    # Relatiesoorten
    # ------------------------------------------------------------------

    def annotate_association(
        self, prop_uri: URIRef, shape_node, assoc, bron_uri: URIRef, doel_uri: URIRef, naam: Optional[str] = None
    ):
        """Associatie als mim:Relatiesoort (6.4.5.6) met bron, doel,
        kardinaliteit (doelzijde) en kardinaliteit relatie bron (bronzijde)."""
        g = self.g
        soort = "Relatiesoort"
        naam = naam or assoc.name or getattr(assoc, "dst_role", None) or getattr(assoc, "src_role", None)
        self._identificeer(prop_uri, naam, MIM.Relatiesoort)
        self._algemeen(prop_uri, assoc, soort)
        g.add((prop_uri, MIM.bron, bron_uri))
        g.add((prop_uri, MIM.doel, doel_uri))
        # Richting en aggregatie worden niet ingelezen: MIM-defaults.
        g.add((prop_uri, MIM.unidirectioneel, Literal(True)))
        g.add((prop_uri, MIM.aggregatietype, MIM.Geen))
        mogelijk_geen_waarde = mim.parse_bool(getattr(assoc, "mogelijk_geen_waarde", None))
        kard = mim.kardinaliteit(assoc.dst_mult_start, assoc.dst_mult_end)
        if kard is not None:
            g.add((prop_uri, MIM.kardinaliteit, Literal(kard)))
            self._counts(shape_node, kard, mogelijk_geen_waarde)
        else:
            self._verplicht(soort, "kardinaliteit", False)
            if mim.clean_value(assoc.dst_mult_start) or mim.clean_value(assoc.dst_mult_end):
                self.onvertaald[("kardinaliteit", f"onbruikbaar: {assoc.dst_mult_start}..{assoc.dst_mult_end}")] += 1
        kard_bron = mim.kardinaliteit(assoc.src_mult_start, assoc.src_mult_end)
        if kard_bron is not None:
            g.add((prop_uri, MIM.kardinaliteitRelatieBron, Literal(kard_bron)))
        self._bool(
            prop_uri,
            MIM.heeftTijdlijnGeldigheid,
            getattr(assoc, "heeft_tijdlijn_geldigheid", None),
            False,
            soort,
            "heeftTijdlijnGeldigheid",
        )
        self._bool(
            prop_uri,
            MIM.heeftTijdlijnRegistratie,
            getattr(assoc, "heeft_tijdlijn_registratie", None),
            False,
            soort,
            "heeftTijdlijnRegistratie",
        )
        self._bool(
            prop_uri,
            MIM.indicatieMaterieleHistorie,
            getattr(assoc, "indicatie_materiele_historie", None),
            False,
            soort,
            "indicatieMaterieleHistorie",
        )
        self._bool(
            prop_uri,
            MIM.indicatieFormeleHistorie,
            getattr(assoc, "indicatie_formele_historie", None),
            False,
            soort,
            "indicatieFormeleHistorie",
        )
        g.add((prop_uri, MIM.indicatieAfleidbaar, Literal(False)))
        self._bool(prop_uri, MIM.mogelijkGeenWaarde, mogelijk_geen_waarde, False, soort, "mogelijkGeenWaarde")
        self._authentiek(prop_uri, getattr(assoc, "authentiek", None), soort)

    # ------------------------------------------------------------------
    # Enumeraties
    # ------------------------------------------------------------------

    def annotate_enumeration(self, enum_uri: URIRef, enum, shape_uri: URIRef):
        """Enumeratie (6.4.5.12): owl:Class rdfs:subClassOf skos:Concept,
        skos:ConceptScheme en mim:Enumeratie, met een NodeShape die de
        waarden beschrijft."""
        g = self.g
        self._identificeer(enum_uri, enum.name, MIM.Enumeratie)
        g.add((enum_uri, RDFS.subClassOf, SKOS.Concept))
        self._algemeen(enum_uri, enum, "Enumeratie", herkomst_verplicht=False)

        g.add((shape_uri, RDF.type, SH.NodeShape))
        g.add((shape_uri, SH.targetClass, enum_uri))
        g.add((shape_uri, RDFS.label, self.lit(enum.name)))
        for pad in (RDFS.label, SKOS.notation, SKOS.definition):
            prop = BNode()
            g.add((shape_uri, SH.property, prop))
            g.add((prop, SH.path, pad))
        for pad, waarde in ((RDF.type, enum_uri), (SKOS.inScheme, enum_uri)):
            prop = BNode()
            g.add((shape_uri, SH.property, prop))
            g.add((prop, SH.path, pad))
            g.add((prop, SH.hasValue, waarde))

    def annotate_enum_literal(self, concept_uri: URIRef, literal, enum_uri: URIRef):
        """Enumeratiewaarde (6.4.5.13): instantie van de enumeratieklasse in
        het scheme, code als skos:notation (6.4.9.34)."""
        g = self.g
        self._identificeer(concept_uri, literal.name, MIM.Enumeratiewaarde)
        g.add((enum_uri, MIM.waarde, concept_uri))
        if literal.name:
            g.add((concept_uri, RDFS.label, self.lit(literal.name)))
        self._tekst(concept_uri, MIM.definitie, literal.definitie)
        self._tekst(concept_uri, MIM.toelichting, getattr(literal, "toelichting", None))
        # EA bewaart de code van een enumeratiewaarde als initiële waarde; de
        # parsers zetten die in `alias`.
        code = mim.clean_value(getattr(literal, "alias", None))
        if code is not None:
            g.add((concept_uri, SKOS.notation, Literal(code)))
            g.add((concept_uri, MIM.code, Literal(code)))
        self._datum(
            concept_uri, MIM.datumOpname, getattr(literal, "datum_opname", None), "Enumeratiewaarde", "datumOpname"
        )

    # ------------------------------------------------------------------
    # Rapportage
    # ------------------------------------------------------------------

    def samenvatting(self) -> str:
        regels = [
            "MIM-typering: "
            + ", ".join(
                f"{str(k).rsplit('#', 1)[-1]} {n}" for k, n in sorted(self.getypeerd.items(), key=lambda kv: str(kv[0]))
            )
        ]
        if self.ontbrekend:
            regels.append(
                "Verplichte MIM-metagegevens zonder waarde in de bron (soort.metagegeven: aantal): "
                + ", ".join(f"{soort}.{veld}: {n}" for (soort, veld), n in sorted(self.ontbrekend.items()))
            )
        if self.onvertaald:
            regels.append(
                "Bronwaarden die niet te vertalen waren (metagegeven, reden: aantal): "
                + "; ".join(f"{veld} ({reden}): {n}" for (veld, reden), n in sorted(self.onvertaald.items()))
            )
        return "\n".join(regels)
