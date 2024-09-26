import logging
import os
from urllib.parse import quote, urljoin, urlunparse

from pyshacl import validate as shacl_validate
from rdflib import BNode, Graph, Literal, Namespace
from rdflib.namespace import OWL, RDF, RDFS, SH, XSD

import crunch_uml.schema as sch
from crunch_uml import const, util
from crunch_uml.exceptions import CrunchException
from crunch_uml.renderers.renderer import ModelRenderer, RendererRegistry

logger = logging.getLogger()


class LodRenderer(ModelRenderer):
    """
    Renders all model packages using jinja2 and a template.
    A model package is a package with at least 1 class inside
    """

    def writeToFile(self, graph, args):
        pass

    def render(self, args, zchema: sch.Schema):
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
        mim = Namespace("http://www.geostandaarden.nl/mim#")  # MIM namespace
        g = Graph()
        g.bind("mim", mim)
        g.bind("sh", Namespace("http://www.w3.org/ns/shacl#"))

        # Get list of packages that are to be rendered
        models = self.getModels(args, zchema)
        if len(models) is None:
            msg = "Cannot render output: packages does not exist"
            logger.error(msg)
            raise CrunchException(msg)

        class_dict = {}  # used to find all classes by guid
        # First add all classes
        for model in models:
            modelname = util.remove_substring(model.name, "model")
            ns = Namespace(urljoin(str(args.linked_data_namespace), f"/{quote(modelname)}/"))

            for cls in model.classes:
                class_dict[cls.id] = ns[cls.id]
                g.add((ns[cls.id], RDF.type, mim.Objecttype))  # Add stereotype

                g.add((ns[cls.id], RDF.type, OWL.Class))
                g.add((ns[cls.id], RDFS.label, Literal(cls.name)))
                if cls.definitie is not None:
                    g.add((ns[cls.id], RDFS.comment, Literal(cls.definitie)))

                # SHACL NodeShape for the class
                shape_uri = ns[cls.id + "_Shape"]
                g.add((shape_uri, RDF.type, SH.NodeShape))
                g.add((shape_uri, SH.targetNode, ns[cls.id]))

                for attribute in cls.attributes:
                    attribute_bnode = BNode()
                    datatype = XSD.string if attribute.primitive is None else attribute.primitive
                    g.add((ns[attribute.id], RDF.type, OWL.DatatypeProperty))
                    g.add((ns[attribute.id], RDFS.domain, ns[cls.id]))
                    g.add((ns[attribute.id], RDFS.label, Literal(attribute.name)))
                    g.add((ns[attribute.id], RDFS.range, datatype))
                    g.add((ns[attribute.id], Namespace("http://w3.org/ns/shacl#").datatype, datatype))  # sh:datatype
                    g.add(
                        (ns[attribute.id], Namespace("http://w3.org/ns/shacl#").path, Literal(attribute.name))
                    )  # sh:path
                    g.add((ns[attribute.id], RDF.type, mim.Attribuutsoort))  # Add attribute stereotype

                    # SHACL property structure
                    g.add((shape_uri, SH.property, attribute_bnode))
                    g.add((attribute_bnode, SH.path, ns[attribute.id]))
                    g.add((attribute_bnode, SH.datatype, datatype))
                    g.add((attribute_bnode, SH.minCount, Literal(1)))
                    g.add((attribute_bnode, SH.maxCount, Literal(1)))

                    if attribute.definitie is not None:
                        g.add((
                            ns[attribute.id],
                            RDFS.comment,
                            Literal(attribute.definitie),
                        ))

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
                    to_cls = class_dict.get(assoc.dst_class.id)

                    if from_cls is not None and to_cls is not None:
                        g.add((ns[assoc.id], RDF.type, OWL.ObjectProperty))
                        g.add((ns[assoc.id], RDFS.domain, from_cls))
                        g.add((ns[assoc.id], RDFS.range, to_cls))
                        g.add((ns[assoc.id], RDFS.label, Literal(assoc.name)))
                        g.add((ns[assoc.id], RDF.type, mim.Relatiesoort))  # Add stereotype for relationship
                        if assoc.definitie is not None:
                            g.add((ns[assoc.id], RDFS.comment, Literal(assoc.definitie)))

        conforms, results_graph, results_text = shacl_validate(
            g,
            inference='rdfs',
            serialize_report_graph=True,
        )
        if not conforms:
            logger.warning("SHACL validation failed:")
            logger.warning(results_text)

        self.writeToFile(g, args)


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
