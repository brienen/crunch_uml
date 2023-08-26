import logging
from abc import ABC, abstractmethod

from crunch_uml import db
from crunch_uml.registry import Registry

logger = logging.getLogger()

class ParserRegistry(Registry):
    pass

def add_args(argumentparser):
    argumentparser.add_argument('-f', '--file', type=str, help="Path to the XMI file", required=True)
    argumentparser.add_argument(
        '-t',
        '--inputtype',
        type=str,
        # action='store_true',
        help=f'geeft inputtype aan: {ParserRegistry.entries()}.',
        default='xmi',
    )


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
