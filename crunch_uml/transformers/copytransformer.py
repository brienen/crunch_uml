import logging

import crunch_uml.schema as sch
from crunch_uml import db
from crunch_uml.excpetions import CrunchException
from crunch_uml.transformers.transformer import Transformer, TransformerRegistry

logger = logging.getLogger()


@TransformerRegistry.register("copy", descr='Makes a copy of (part of) a datamodel and writes it to a schema')
class CopyTransformer(Transformer):
    def transform(self, args, database: db.Database):
        # First do logic of super type
        super().transform(args, database)

        if not args.root_package:
            raise CrunchException(
                "Error: cannot copy datamodel with root package of value None, --root_package needs to have value."
            )
        materialize_generalizations = True if args.materialize_generalizations == "True" else False

        # Retrieve all models dynamically
        schema_from = sch.Schema(database, args.schema_from)
        schema_to = sch.Schema(database, args.schema_to)

        # Get root package, make a copy and save it
        root_package = schema_from.get_package(args.root_package)
        if not root_package:
            raise CrunchException(
                f"Error: cannot find root package with key {args.root_package}. Are you sure this is the key of a"
                " package?"
            )

        kopie = root_package.get_copy(None, materialize_generalizations=materialize_generalizations)
        schema_to.add(kopie, recursive=True)
