import logging
import os
import re
from urllib.parse import quote, urljoin, urlunparse

from rdflib import BNode, Graph, Literal, Namespace
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SH, XSD

import crunch_uml.schema as sch
from crunch_uml import const, util
from crunch_uml.exceptions import CrunchException
from crunch_uml.renderers.renderer import ModelRenderer, RendererRegistry

logger = logging.getLogger()


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


class LodRenderer(ModelRenderer):
    """
    Renders all model packages using jinja2 and a template.
    A model package is a package with at least 1 class inside
    """

    def writeToFile(self, graph, args):
        pass

    def render(self, args, zchema: sch.Schema):
        try:
            TYPEMAP = {
                "string": XSD.string,
                "integer": XSD.integer,
                "boolean": XSD.boolean,
                "date": XSD.date,
            }

            if args.linked_data_namespace is None:
                logger.warning(
                    f'No namespace provided via parameter "linked_data_namespace", using default {const.DEFAULT_LOD_NS}'
                )
                args.linked_data_namespace = const.DEFAULT_LOD_NS
            elif not isinstance(args.linked_data_namespace, str):
                args.linked_data_namespace = urlunparse(args.linked_data_namespace)

            # sourcery skip: raise-specific-error
            MYNS = Namespace(args.linked_data_namespace)  # noqa: F841
            schema = Namespace("http://schema.org/")  # noqa: F841

            # Create graph
            g = Graph()

            # Add SHACL shapes namespace and bindings
            shape_ns = Namespace(
                args.linked_data_namespace + ("" if args.linked_data_namespace.endswith("/") else "/") + "shapes/"
            )
            g.bind("sh", SH)
            g.bind("shape", shape_ns)

            # Get list of packages that are to be rendered
            models = self.getModels(args, zchema)
            if not models:
                msg = "Geen modellen gevonden om te renderen. Controleer of het schema pakketten met klassen bevat."
                logger.error(msg)
                raise CrunchException(msg)

            class_dict = {}  # used to find all classes by guid
            # First add all classes
            try:
                for model in models:
                    modelname = util.remove_substring(model.name, "model").lower()
                    ns = Namespace(urljoin(str(args.linked_data_namespace), f"/{quote(modelname)}/"))

                    for cls in model.classes:
                        if not cls.name:
                            logger.warning(f"Klasse zonder naam gevonden: {cls.id}")
                            continue
                        class_uri = ns[slugify(cls.name)]
                        # Werk eerst de dict bij
                        class_dict[cls.id] = class_uri

                        # Voeg de klasse toe
                        g.add((class_uri, RDF.type, OWL.Class))
                        g.add((class_uri, RDFS.label, Literal(cls.name)))
                        g.add((class_uri, DCTERMS.identifier, Literal(cls.id)))
                        if cls.definitie is not None:
                            g.add((class_uri, RDFS.comment, Literal(cls.definitie)))

                        for attribute in cls.attributes:
                            if attribute.name is not None and attribute.primitive is not None:
                                attr_uri = (
                                    ns[slugify(cls.name) + "/" + slugify(attribute.name)]
                                    if attribute.name
                                    else ns[slugify(cls.name) + "/" + slugify(attribute.id)]
                                )
                                g.add((attr_uri, RDF.type, OWL.DatatypeProperty))
                                g.add((attr_uri, RDFS.domain, class_uri))
                                g.add((attr_uri, RDFS.label, Literal(attribute.name)))
                                g.add((attr_uri, RDFS.range, XSD.string))
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
                        class_uri = ns[slugify(cls.name)]
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
                                shacl_type = TYPEMAP.get(attribute.primitive.lower(), XSD.string)
                                g.add((prop_bnode, SH.datatype, shacl_type))
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
