import logging
from abc import ABC, abstractmethod

import crunch_uml.schema as sch
from crunch_uml import const, db
from crunch_uml.registry import Registry

logger = logging.getLogger()


class TransformerRegistry(Registry):
    _registry = {}  # type: ignore
    _descr_registry = {}  # type: ignore


def add_args(argumentparser, subparser_dict):
    transformation_subparser = subparser_dict.get(const.CMD_TRANSFORM)

    transformation_subparser.add_argument(
        '-sch_from', '--schema_from', type=str, default=const.DEFAULT_SCHEMA, help=f"Schema in database to read the datamodel from, default {const.DEFAULT_SCHEMA}"
    )
    transformation_subparser.add_argument(
        '-sch_to', '--schema_to', type=str, required=True, help="Schema in database to write the tranformed datamodel to."
    )
    transformation_subparser.add_argument(
        '-ttp',
        '--transformationtype',
        type=str,
        choices=TransformerRegistry.entries(),
        help=f'geeft transformationtype aan: {TransformerRegistry.entries()}.',
    )
    transformation_subparser.add_argument(
        '-rt_pkg',
        '--root_package',
        type=str,
        help=f'provides the root package that needs to be transformed',
    )
    # Creëer een mutually exclusive group en add options
    group = transformation_subparser.add_mutually_exclusive_group(required=False)
    group.add_argument('-pf', '--plugin_file', type=str, help="Plugin file")
    group.add_argument('-purl', '--plugin_url', type=str, help="Plugin URL")

    # Set the epilog help text
    entries = TransformerRegistry.entries()
    items = [f'"{item}": {TransformerRegistry.getDescription(item)}' for item in entries]
    epilog = 'More informaation on the transformation types that are supported:\n\n' + '\n'.join(items)
    transformation_subparser.epilog = epilog



class Transformer(ABC):
    @abstractmethod
    def transform(self, args, database: db.Database):
        pass
