import logging
from abc import ABC

from crunch_uml import const, db
from crunch_uml.excpetions import CrunchException
from crunch_uml.registry import Registry

logger = logging.getLogger()


class TransformerRegistry(Registry):
    _registry = {}  # type: ignore
    _descr_registry = {}  # type: ignore


def add_args(argumentparser, subparser_dict):
    transformation_subparser = subparser_dict.get(const.CMD_TRANSFORM)

    transformation_subparser.add_argument(
        '-sch_from',
        '--schema_from',
        type=str,
        default=const.DEFAULT_SCHEMA,
        help=f"Schema in database to read the datamodel from, default {const.DEFAULT_SCHEMA}",
    )
    transformation_subparser.add_argument(
        '-sch_to',
        '--schema_to',
        type=str,
        required=True,
        help="Schema in database to write the tranformed datamodel to.",
    )
    # transformation_subparser.add_argument(
    #    '-sch_to_cln', '--schema_to_clean', type=str, default=True, help="Cleans the content of schema_to before transformation. Default is True"
    # )
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
        help='provides the root package that needs to be transformed',
    )
    transformation_subparser.add_argument(
        '-m_gen',
        '--materialize_generalizations',
        type=str,
        default="False",
        help=(
            'Copies all attributes of parent classes to the child classes. All strings other than "True" are'
            ' interpreted as False.'
        ),
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
    def transform(self, args, database: db.Database):
        if not args.schema_to:
            raise CrunchException(
                "Error: cannot transform datamodel to schema with value of None, --schema_to needs to have value."
            )
        if args.schema_to == args.schema_from:
            raise CrunchException(
                f"Error: cannot transform datamodel to schema with the same name {args.schema_to}, --schema_to and"
                " --schema_from need to have different values."
            )

        # if args.schema_to_clean:
        #    schema_to = sch.Schema(database, args.schema_to)
        #    schema_to.clean()
