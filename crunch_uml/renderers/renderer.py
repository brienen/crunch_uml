import logging
from abc import ABC, abstractmethod

from crunch_uml import db
from crunch_uml.registry import Registry

logger = logging.getLogger()


class RendererRegistry(Registry):
    _registry = {}  # type: ignore


def add_args(argumentparser):
    argumentparser.add_argument('-of', '--output_file', type=str, help="Path to the outputfile file")
    argumentparser.add_argument(
        '-ot',
        '--outputtype',
        type=str,
        # action='store_true',
        help=f'geeft outtype aan: {RendererRegistry.entries()}.',
    )


class Renderer(ABC):
    @abstractmethod
    def render(self, args, database: db.Database):
        pass
