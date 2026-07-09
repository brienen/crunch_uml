import logging
import os
import re
from typing import Optional, Tuple
from urllib.parse import quote, urljoin, urlunparse

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SH, XSD

import crunch_uml.schema as sch
from crunch_uml import const, util
from crunch_uml.exceptions import CrunchException
from crunch_uml.renderers.renderer import ModelRenderer, RendererRegistry

logger = logging.getLogger()

# GeoSPARQL: geometrische datatypes worden als WKT-literal gemodelleerd.
GEO = Namespace("http://www.opengis.net/ont/geosparql#")


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# ---------------------------------------------------------------------------
# Datatype-mapping: GGM/EA-primitieven -> XSD (of GeoSPARQL)
# ---------------------------------------------------------------------------

# Alfanumeriek met maximumlengte (AN200, AN 40) en numeriek (N2, N6,2).
_AN_RE = re.compile(r"^an\s*(\d+)$")
_N_RE = re.compile(r"^n\s*(\d+)([.,]\d+)?$")

# Genormaliseerd (casefold, zonder randspaties) -> XSD-datatype. Dekt de
# spellingsvarianten die in de praktijk in GGM/EA-modellen voorkomen.
_XSD_TYPEMAP = {
    "string": XSD.string,
    "an": XSD.string,  # kaal 'AN' zonder lengte
    "blob": XSD.base64Binary,
    "text": XSD.string,
    "characterstring": XSD.string,
    "varchar": XSD.string,
    "char": XSD.string,
    "guid": XSD.string,
    "nen3610id": XSD.string,
    # Een onvolledige datum (alleen jaar, of jaar+maand bekend) past niet in
    # xsd:date; xsd:string behoudt de informatie zonder te liegen.
    "onvolledigedatum": XSD.string,
    "date": XSD.date,
    "datum": XSD.date,
    "datetime": XSD.dateTime,
    "datumtijd": XSD.dateTime,
    "timestamp": XSD.dateTime,
    "time": XSD.time,
    "tijd": XSD.time,
    "jaar": XSD.gYear,
    "year": XSD.gYear,
    "int": XSD.integer,
    "integer": XSD.integer,
    "aantal": XSD.integer,
    "count": XSD.integer,
    "bedrag": XSD.decimal,
    "geldbedrag": XSD.decimal,
    "decimal": XSD.decimal,
    "percentage": XSD.decimal,
    "double": XSD.double,
    "float": XSD.float,
    "real": XSD.double,
    "boolean": XSD.boolean,
    "bool": XSD.boolean,
    "indicatie": XSD.boolean,
}

# GML-/geometrietypen -> geo:wktLiteral (GeoSPARQL).
_GEOMETRY_TYPES = {
    "point",
    "multipoint",
    "curve",
    "multicurve",
    "line",
    "linestring",
    "multilinestring",
    "surface",
    "multisurface",
    "polygon",
    "multipolygon",
    "geometry",
    "geometrie",
    "geometriecollectie",
    "geometrycollection",
    "punt",
    "vlak",
    "lijn",
}


def map_datatype(primitive: Optional[str]) -> Tuple[Optional[URIRef], Optional[int]]:
    """Map een GGM/EA-primitief type naar (RDF-datatype, maximumlengte).

    * ``AN<n>`` -> (xsd:string, n) — alfanumeriek met maximumlengte;
    * ``N<n>``  -> (xsd:integer, None) — numeriek;
    * bekende namen (alle spellingsvarianten) -> bijbehorend XSD-type;
    * geometrie -> geo:wktLiteral (GeoSPARQL);
    * onbekend  -> (None, None): de aanroeper beslist (klasse-referentie of
      terugval op xsd:string met waarschuwing).
    """
    if not primitive:
        return None, None
    norm = primitive.strip().casefold()
    if m := _AN_RE.match(norm):
        return XSD.string, int(m.group(1))
    if _N_RE.match(norm):
        return XSD.integer, None
    if norm in _GEOMETRY_TYPES:
        return GEO.wktLiteral, None
    return _XSD_TYPEMAP.get(norm), None


class LodRenderer(ModelRenderer):
    """
    Renders all model packages as a Linked Data ontology.
    A model package is a package with at least 1 class inside.

    Naast de klassen en properties bevat de output:

    * **echte datatypes**: attributen krijgen een ``rdfs:range`` (en SHACL
      ``sh:datatype``) op basis van :func:`map_datatype`; ``AN<n>``-types
      krijgen bovendien ``sh:maxLength``. Attributen waarvan het type de
      naam van een modelklasse is, worden ``owl:ObjectProperty`` met die
      klasse als range (``sh:class`` in de shape);
    * **de domeinhiërarchie**: elk modelpakket wordt een ``owl:Ontology``
      waar zijn klassen met ``rdfs:isDefinedBy`` naar verwijzen; de
      bovenliggende (domein)pakketten worden entiteiten van het zelf
      gedeclareerde type ``Domein``, met ``dcterms:isPartOf``-relaties die
      de pakkethiërarchie van het model volgen tot aan de wortel.
    """

    def writeToFile(self, graph, args):
        pass

    def addPackageHierarchy(self, g, models, myns, domain_ns, model_ns):
        """Voeg de pakkethiërarchie toe als Linked Data-entiteiten."""
        domein_cls = myns["Domein"]
        g.add((domein_cls, RDF.type, OWL.Class))
        g.add((domein_cls, RDFS.label, Literal("Domein", lang="nl")))
        g.add(
            (
                domein_cls,
                RDFS.comment,
                Literal("Informatiedomein: groepering van modellen binnen het gegevensmodel.", lang="nl"),
            )
        )

        seen = {}

        def entity_uri(pkg):
            # Een bovenliggend pakket kan zelf ook een model zijn: dan is de
            # ontologie-URI van dat model het ankerpunt, geen Domein-entiteit.
            if pkg.id in model_ns:
                return URIRef(str(model_ns[pkg.id][1]))
            return domain_ns[slugify(pkg.name)]

        def add_package(pkg):
            if pkg.id in seen:
                return seen[pkg.id]
            uri = entity_uri(pkg)
            seen[pkg.id] = uri
            if pkg.id in model_ns:
                g.add((uri, RDF.type, OWL.Ontology))
            else:
                g.add((uri, RDF.type, domein_cls))
            g.add((uri, RDFS.label, Literal(pkg.name)))
            g.add((uri, DCTERMS.identifier, Literal(pkg.id)))
            if pkg.definitie:
                g.add((uri, RDFS.comment, Literal(pkg.definitie)))
            parent = pkg.parent_package
            if parent is not None and parent.name:
                g.add((uri, DCTERMS.isPartOf, add_package(parent)))
            return uri

        for model in models:
            add_package(model)

    def render(self, args, zchema: sch.Schema):
        try:
            if args.linked_data_namespace is None:
                logger.warning(
                    f'No namespace provided via parameter "linked_data_namespace", using default {const.DEFAULT_LOD_NS}'
                )
                args.linked_data_namespace = const.DEFAULT_LOD_NS
            elif not isinstance(args.linked_data_namespace, str):
                args.linked_data_namespace = urlunparse(args.linked_data_namespace)

            base = args.linked_data_namespace + ("" if args.linked_data_namespace.endswith("/") else "/")
            myns = Namespace(base)

            # Create graph
            g = Graph()

            # Namespaces en bindings
            shape_ns = Namespace(base + "shapes/")
            domain_ns = Namespace(base + "domein/")
            g.bind("sh", SH)
            g.bind("shape", shape_ns)
            g.bind("domein", domain_ns)
            g.bind("geo", GEO)
            g.bind("dcterms", DCTERMS)

            # Get list of packages that are to be rendered
            models = self.getModels(args, zchema)
            if not models:
                msg = "Geen modellen gevonden om te renderen. Controleer of het schema pakketten met klassen bevat."
                logger.error(msg)
                raise CrunchException(msg)

            # Voorbereiding over ALLE modellen: namespaces en klasse-indexen,
            # zodat attribuut- en associatie-ranges ook klassen uit andere
            # modellen kunnen aanwijzen.
            model_ns: dict = {}  # package id -> (modelname, Namespace)
            class_dict: dict = {}  # class guid -> uri
            class_by_name: dict = {}  # klassenaam (casefold) -> uri
            for model in models:
                modelname = util.remove_substring(model.name, "model").lower()
                ns = Namespace(urljoin(str(args.linked_data_namespace), f"/{quote(modelname)}/"))
                model_ns[model.id] = (modelname, ns)
                for cls in model.classes:
                    if not cls.name:
                        continue
                    class_uri = ns[slugify(cls.name)]
                    class_dict[cls.id] = class_uri
                    class_by_name.setdefault(cls.name.strip().casefold(), class_uri)

            unmapped_types = set()

            def resolve_range(attribute):
                """Bepaal de range van een attribuut: ('datatype'|'object',
                range-URI, maximumlengte)."""
                dtype, max_length = map_datatype(attribute.primitive)
                if dtype is not None:
                    return "datatype", dtype, max_length
                class_uri = class_by_name.get(attribute.primitive.strip().casefold())
                if class_uri is not None:
                    return "object", class_uri, None
                unmapped_types.add(attribute.primitive)
                return "datatype", XSD.string, None

            # Domeinhiërarchie: modelpakketten als owl:Ontology, bovenliggende
            # pakketten als Domein-entiteiten met dcterms:isPartOf-relaties.
            self.addPackageHierarchy(g, models, myns, domain_ns, model_ns)

            # First add all classes
            try:
                for model in models:
                    modelname, ns = model_ns[model.id]
                    model_uri = URIRef(str(ns))

                    for cls in model.classes:
                        if not cls.name:
                            logger.warning(f"Klasse zonder naam gevonden: {cls.id}")
                            continue
                        class_uri = class_dict[cls.id]

                        # Voeg de klasse toe
                        g.add((class_uri, RDF.type, OWL.Class))
                        g.add((class_uri, RDFS.label, Literal(cls.name)))
                        g.add((class_uri, DCTERMS.identifier, Literal(cls.id)))
                        g.add((class_uri, RDFS.isDefinedBy, model_uri))
                        if cls.definitie is not None:
                            g.add((class_uri, RDFS.comment, Literal(cls.definitie)))

                        for attribute in cls.attributes:
                            if attribute.name is not None and attribute.primitive is not None:
                                attr_uri = (
                                    ns[slugify(cls.name) + "/" + slugify(attribute.name)]
                                    if attribute.name
                                    else ns[slugify(cls.name) + "/" + slugify(attribute.id)]
                                )
                                kind, range_uri, _ = resolve_range(attribute)
                                prop_type = OWL.DatatypeProperty if kind == "datatype" else OWL.ObjectProperty
                                g.add((attr_uri, RDF.type, prop_type))
                                g.add((attr_uri, RDFS.domain, class_uri))
                                g.add((attr_uri, RDFS.label, Literal(attribute.name)))
                                g.add((attr_uri, RDFS.range, range_uri))
                                g.add((attr_uri, DCTERMS.identifier, Literal(attribute.id)))
                                if attribute.definitie is not None:
                                    g.add(
                                        (
                                            attr_uri,
                                            RDFS.comment,
                                            Literal(attribute.definitie),
                                        )
                                    )

                    # Add SHACL NodeShapes for each class
                    for cls in model.classes:
                        if not cls.name:
                            logger.warning(f"SHACL-shape overgeslagen voor klasse zonder naam: {cls.id}")
                            continue
                        class_uri = class_dict[cls.id]
                        shape_uri = shape_ns[slugify(modelname) + "/" + slugify(cls.name)]
                        g.add((shape_uri, RDF.type, SH.NodeShape))
                        g.add((shape_uri, SH.targetClass, class_uri))
                        g.add((shape_uri, RDFS.label, Literal(cls.name)))
                        g.add((shape_uri, DCTERMS.identifier, Literal(f"{cls.id}")))

                        for attribute in cls.attributes:
                            if attribute.name is not None and attribute.primitive is not None:
                                prop_bnode = BNode()
                                attr_uri = (
                                    ns[slugify(cls.name) + "/" + slugify(attribute.name)]
                                    if attribute.name
                                    else ns[slugify(cls.name) + "/" + slugify(attribute.id)]
                                )
                                g.add((shape_uri, SH.property, prop_bnode))
                                g.add((prop_bnode, SH.path, attr_uri))
                                kind, range_uri, max_length = resolve_range(attribute)
                                if kind == "datatype":
                                    g.add((prop_bnode, SH.datatype, range_uri))
                                    if max_length is not None:
                                        g.add((prop_bnode, SH.maxLength, Literal(max_length)))
                                else:
                                    g.add((prop_bnode, getattr(SH, "class"), range_uri))
                                    g.add((prop_bnode, SH.nodeKind, SH.IRI))
                                g.add((prop_bnode, SH.minCount, Literal(0)))
                                g.add((prop_bnode, SH.maxCount, Literal(1)))
                                g.add((prop_bnode, SH.name, Literal(attribute.name)))
                                if attribute.definitie:
                                    g.add((prop_bnode, SH.description, Literal(attribute.definitie)))
                    logger.info(f"Aantal klassen verwerkt in model '{modelname}': {len(model.classes)}")
            except Exception as e:
                logger.exception("Fout tijdens het renderen van modellen:")
                raise CrunchException(f"Renderproces mislukt: {e}") from e

            # Then add all relations
            for model in models:
                modelname, ns = model_ns[model.id]
                for cls in model.classes:
                    # First set inheritance
                    for subclass in cls.subclasses:
                        super_cls = class_dict.get(cls.id)
                        if subclass.superclass is not None:
                            sub_cls = class_dict.get(subclass.superclass.id)

                            if super_cls is not None and sub_cls is not None:
                                g.add((sub_cls, RDFS.subClassOf, super_cls))

                    # Then set associations
                    for assoc in cls.uitgaande_associaties:
                        from_cls = class_dict.get(cls.id)
                        to_cls = class_dict.get(getattr(assoc.dst_class, "id", None))
                        if to_cls is None:
                            logger.warning(f"Doelklasse onbekend voor associatie {assoc.name or assoc.id}")
                            continue

                        if from_cls is not None and to_cls is not None:
                            assoc_uri = (
                                ns[slugify(cls.name) + "/" + slugify(assoc.name)]
                                if assoc.name
                                else ns[slugify(cls.name) + "/" + slugify(assoc.id)]
                            )
                            g.add((assoc_uri, RDF.type, OWL.ObjectProperty))
                            g.add((assoc_uri, RDFS.domain, from_cls))
                            g.add((assoc_uri, RDFS.range, to_cls))
                            g.add((assoc_uri, RDFS.label, Literal(assoc.name)))
                            g.add((assoc_uri, DCTERMS.identifier, Literal(assoc.id)))
                            if assoc.definitie is not None:
                                g.add((assoc_uri, RDFS.comment, Literal(assoc.definitie)))

            if unmapped_types:
                overview = ", ".join(sorted(unmapped_types))
                logger.warning(
                    f"Onbekende datatypes teruggevallen op xsd:string (geen mapping, geen modelklasse): {overview}"
                )

            self.writeToFile(g, args)
        except CrunchException:
            raise  # Laat eigen excepties door
        except Exception as e:
            logger.exception("Onverwachte fout in LodRenderer:")
            raise CrunchException(f"Interne fout tijdens renderen: {e}") from e


@RendererRegistry.register(
    "ttl",
    descr="Renderer that renders Linked Data ontology in turtle from the supplied models, "
    + "where a model is a package that includes at least one Class. "
    + 'Needs parameter "output_lod_url".',
)
class TTLRenderer(LodRenderer):
    """
    Renders all model packages using jinja2 and a template.
    A model package is a package with at least 1 class inside
    """

    def writeToFile(self, graph, args):
        # get filename
        base_name, ext = os.path.splitext(args.outputfile)
        outputfile = f"{base_name}.ttl"

        with open(outputfile, "w") as file:
            file.write(graph.serialize(format="turtle"))


@RendererRegistry.register(
    "rdf",
    descr="Renderer that renders Linked Data ontology in RDF from the supplied models, "
    + "where a model is a package that includes at least one Class. "
    + ' Needs parameter "output_lod_url".',
)
class RDFRenderer(LodRenderer):
    """
    Renders all model packages using jinja2 and a template.
    A model package is a package with at least 1 class inside
    """

    def writeToFile(self, graph, args):
        # get filename
        base_name, ext = os.path.splitext(args.outputfile)
        outputfile = f"{base_name}.rdf"

        with open(outputfile, "w") as file:
            file.write(graph.serialize(format="xml"))


@RendererRegistry.register(
    "json-ld",
    descr="Renderer that renders Linked Data ontology in JSON-LD from the supplied models, "
    + "where a model is a package that includes at least one Class. "
    + ' Needs parameter "output_lod_url".',
)
class JSONLDRenderer(LodRenderer):
    """
    Renders all model packages using jinja2 and a template.
    A model package is a package with at least 1 class inside
    """

    def writeToFile(self, graph, args):
        # get filename
        base_name, ext = os.path.splitext(args.outputfile)
        outputfile = f"{base_name}.jsonld"

        with open(outputfile, "w") as file:
            file.write(graph.serialize(format="json-ld"))
