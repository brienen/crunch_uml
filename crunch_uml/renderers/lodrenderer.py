import logging
import os
from urllib.parse import quote, urljoin, urlunparse

from rdflib import Graph, Literal, Namespace
from rdflib.namespace import OWL, RDF, RDFS, XSD

import crunch_uml.schema as sch
from crunch_uml import const, util
from crunch_uml.exceptions import CrunchException
from crunch_uml.renderers.renderer import ModelRenderer, RendererRegistry

logger = logging.getLogger()


class LodRenderer(ModelRenderer):
    '''
    Renders all model packages using jinja2 and a template.
    A model package is a package with at least 1 class inside
    '''

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

        # Create graph
        g = Graph()

        # Get list of packages that are to be rendered
        models = self.getModels(args, zchema)
        if len(models) is None:
            msg = "Cannot render output: packages does not exist"
            logger.error(msg)
            raise CrunchException(msg)

        class_dict = {}  # used to find all classes by guid
        # First add all classes
        for model in models:
            modelname = util.remove_substring(model.name, 'model')
            ns = Namespace(urljoin(str(args.linked_data_namespace), f"/{quote(modelname)}/"))

            for cls in model.classes:
                # Werk eerst de dict bij
                class_dict[cls.id] = ns[cls.id]

                # Voeg de klasse toe
                g.add((ns[cls.id], RDF.type, OWL.Class))
                g.add((ns[cls.id], RDFS.label, Literal(cls.name)))
                if cls.definitie is not None:
                    g.add((ns[cls.id], RDFS.comment, Literal(cls.definitie)))

                for attribute in cls.attributes:
                    # Voeg de attributen toe
                    if attribute.name is not None and attribute.primitive is not None:
                        g.add((ns[attribute.id], RDF.type, OWL.DatatypeProperty))
                        g.add((ns[attribute.id], RDFS.domain, ns[cls.id]))
                        g.add((ns[attribute.id], RDFS.label, Literal(attribute.name)))
                        g.add((ns[attribute.id], RDFS.range, XSD.string))
                        if attribute.definitie is not None:
                            g.add((ns[attribute.id], RDFS.comment, Literal(attribute.definitie)))

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
                        # Voeg properties toe
                        g.add((ns[assoc.id], RDF.type, OWL.ObjectProperty))
                        g.add((ns[assoc.id], RDFS.domain, from_cls))
                        g.add((ns[assoc.id], RDFS.range, to_cls))
                        g.add((ns[assoc.id], RDFS.label, Literal(assoc.name)))
                        if assoc.definitie is not None:
                            g.add((ns[assoc.id], RDFS.comment, Literal(assoc.definitie)))

        self.writeToFile(g, args)


@RendererRegistry.register(
    "ttl",
    descr='Renderer that renders Linked Data ontology in turtle from the supplied models, '
    + 'where a model is a package that includes at least one Class. '
    + 'Needs parameter "output_lod_url".',
)
class TTLRenderer(LodRenderer):
    '''
    Renders all model packages using jinja2 and a template.
    A model package is a package with at least 1 class inside
    '''

    def writeToFile(self, graph, args):
        # get filename
        base_name, ext = os.path.splitext(args.outputfile)
        outputfile = f'{base_name}.ttl'

        with open(outputfile, 'w') as file:
            file.write(graph.serialize(format='turtle'))


@RendererRegistry.register(
    "rdf",
    descr='Renderer that renders Linked Data ontology in RDF from the supplied models, '
    + 'where a model is a package that includes at least one Class. '
    + ' Needs parameter "output_lod_url".',
)
class RDFRenderer(LodRenderer):
    '''
    Renders all model packages using jinja2 and a template.
    A model package is a package with at least 1 class inside
    '''

    def writeToFile(self, graph, args):
        # get filename
        base_name, ext = os.path.splitext(args.outputfile)
        outputfile = f'{base_name}.rdf'

        with open(outputfile, 'w') as file:
            file.write(graph.serialize(format='xml'))


@RendererRegistry.register(
    "json-ld",
    descr='Renderer that renders Linked Data ontology in JSON-LD from the supplied models, '
    + 'where a model is a package that includes at least one Class. '
    + ' Needs parameter "output_lod_url".',
)
class JSONLDRenderer(LodRenderer):
    '''
    Renders all model packages using jinja2 and a template.
    A model package is a package with at least 1 class inside
    '''

    def writeToFile(self, graph, args):
        # get filename
        base_name, ext = os.path.splitext(args.outputfile)
        outputfile = f'{base_name}.jsonld'

        with open(outputfile, 'w') as file:
            file.write(graph.serialize(format='json-ld'))
