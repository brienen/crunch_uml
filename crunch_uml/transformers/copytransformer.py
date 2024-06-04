import logging

from crunch_uml.transformers.transformer import Transformer, TransformerRegistry

logger = logging.getLogger()


@TransformerRegistry.register("copy", descr='Makes a copy of (part of) a datamodel and writes it to a schema')
class CopyTransformer(Transformer):
    def transformLogic(self, args, root_package, schema_from, schema_to):
        logger.info(f"Transforming {root_package} from {schema_from} to {schema_to}")
        materialize_generalizations = True if args.materialize_generalizations == "True" else False
        kopie = root_package.get_copy(None, materialize_generalizations=materialize_generalizations)
        schema_to.add(kopie, recursive=True)
