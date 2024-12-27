import logging
from abc import ABC, abstractmethod

import crunch_uml.schema as sch
from crunch_uml import const, db
from crunch_uml.registry import Registry

logger = logging.getLogger()


class ParserRegistry(Registry):
    _registry = {}  # type: ignore
    _descr_registry = {}  # type: ignore


def add_args(argumentparser, subparser_dict):
    import_subparser = subparser_dict.get(const.CMD_IMPORT)

    # Creëer een mutually exclusive group en add options
    group = import_subparser.add_mutually_exclusive_group(required=True)
    group.add_argument("-f", "--inputfile", type=str, help="Path to import file")
    group.add_argument("-url", type=str, help="URL to import file")

    import_subparser.add_argument(
        "-t",
        "--inputtype",
        type=str,
        choices=ParserRegistry.entries(),
        help=f"geeft inputtype aan: {ParserRegistry.entries()}.",
    )
    import_subparser.add_argument(
        "--skip_xmi_relations",
        default=False,
        action="store_true",
        help="Skip parsing relations for XMI files only)",
    )
    import_subparser.add_argument(
        "-lan",
        "--language",
        type=str,
        default=const.DEFAULT_LANGUAGE,
        help="Used only for i18n parser. Defines the language of the input file."
        + f" Default is {const.DEFAULT_LANGUAGE}.",
    )
    import_subparser.add_argument(
        "--update_only",
        default=False,
        action="store_true",
        help="Only update records that already exist. Do not add new ones to avoid errors.",
    )
    import_subparser.add_argument(
        "--mapper",
        type=str,
        default="{}",
        help="JSON-string voor het hernoemen van kolommen, bijvoorbeeld: '{\"old_col\": \"new_col\"}'",
    )
    import_subparser.add_argument(
        "--entity_name",
        type=str,
        help=f"Naam van de entiteit die wordt geïmporteerd. Alleen te gebruiken bij CSV-parser. Mogelijke waarden: {db.getTables()}",
    )

    # Set the epilog help text
    entries = ParserRegistry.entries()
    items = [f'"{item}": {ParserRegistry.getDescription(item)}' for item in entries]
    epilog = "More informaation on the export types that are supported:\n\n" + "\n".join(items)
    epilog = f"{epilog}\n\nThe following tables are suported: {db.getTables()}"
    import_subparser.epilog = epilog


def fixtag(tag):
    return tag.replace("-", "_").replace(" ", "_").lower()


def copy_values(node, obj):
    """
    Copies all values from attributes of node to obj,
    if obj has an attribute with the same name.
    Fix for '-' symbol to '_'
    """
    if node is not None:
        if isinstance(node, list):
            for item in node:
                for key in item.keys():  # Dynamic set values of package
                    if hasattr(obj, fixtag(key)):
                        setattr(obj, fixtag(key), item.get(key))
        else:
            for key in node.keys():  # Dynamic set values of package
                if hasattr(obj, fixtag(key)):
                    setattr(obj, fixtag(key), node.get(key))


class Parser(ABC):
    @abstractmethod
    def parse(self, args, schema: sch.Schema):
        pass
