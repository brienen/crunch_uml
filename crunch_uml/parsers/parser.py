import logging
from abc import ABC, abstractmethod

from crunch_uml import const, db
from crunch_uml.registry import Registry

logger = logging.getLogger()


class ParserRegistry(Registry):
    _registry = {}  # type: ignore
    _descr_registry = {}  # type: ignore


def add_args(argumentparser, subparser_dict):
    import_subparser = subparser_dict.get(const.CMD_IMPORT)
    import_subparser.add_argument('-f', '--inputfile', type=str, help="Path to the XMI file", required=True)
    import_subparser.add_argument(
        '-t',
        '--inputtype',
        type=str,
        required=True,
        help=f'geeft inputtype aan: {ParserRegistry.entries()}.',
    )
    import_subparser.add_argument(
        '--skip_xmi_relations', default=False, action='store_true', help="Skip parsing relations for XMI files only)"
    )

    # Set the epilog help text
    entries = ParserRegistry.entries()
    items = [f'"{item}": {ParserRegistry.getDescription(item)}' for item in entries]
    epilog = 'More informaation on the export types that are supported:\n\n' + '\n'.join(items)
    import_subparser.epilog = epilog


def fixtag(tag):
    return tag.replace('-', '_')


def copy_values(node, obj):
    '''
    Copies all values from attributes of node to obj,
    if obj has an attribute with the same name.
    Fix for '-' symbol to '_'
    '''
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
    def parse(self, args, database: db.Database):
        pass
