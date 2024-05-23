import logging

import pandas as pd
import sqlalchemy

from crunch_uml import db
from crunch_uml.transformers.transformer import Transformer, TransformerRegistry
import crunch_uml.schema as sch
from crunch_uml.excpetions import CrunchException

logger = logging.getLogger()


@TransformerRegistry.register(
    "copy", descr='Makes a copy of (part of) a datamodel and writes it to a schema'
)
class CopyTransformer(Transformer):
    def transform(self, args, database: db.Database):

        if not args.schema_to:
            raise CrunchException("Error: cannot copy datamodel to schema with value of None, --schema_to needs to have value.")
        if args.schema_to == args.schema_from:
            raise CrunchException(f"Error: cannot copy datamodel to schema with the same name {args.schema_to}, --schema_to and --schema_from need to have different values.")
        if not args.root_package:
            raise CrunchException(f"Error: cannot copy datamodel with root package of value None, --root_package needs to have value.")

        # Retrieve all models dynamically
        schema_from = sch.Schema(database, args.schema_from)
        schema_to = sch.Schema(database, args.schema_to)

        # Get root package, make a copy and save it 
        root_package = schema_from.get_package(args.root_package)
        if not root_package:
            raise CrunchException(f"Error: cannot find root package with key {args.root_package}. Are you sure this is the key of a package?")

        kopie = root_package.get_copy(None)
        schema_to.save(kopie, recursive=True)
