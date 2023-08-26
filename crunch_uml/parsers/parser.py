import logging
from abc import ABC, abstractmethod

from crunch_uml import db

logger = logging.getLogger()


class ParserRegistry:
    _registry = {}  # type: ignore

    @classmethod
    def register(cls, name=None):  # sourcery skip: or-if-exp-identity
        def inner(registered_class):
            class_name = name if name else registered_class.__name__
            if class_name in cls._registry:
                raise ValueError(f"Class name {class_name} already registered!")
            cls._registry[class_name] = registered_class
            return registered_class

        return inner

    @classmethod
    def display_registry(cls):
        for name, reg_class in cls._registry.items():
            print(name, "->", reg_class.__name__)

    @classmethod
    def entries(cls):
        return list(cls._registry.keys())

    @classmethod
    def getinstance(cls, name):
        clazz = cls._registry.get(name)
        return clazz()


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
