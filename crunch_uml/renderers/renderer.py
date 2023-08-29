import logging
from abc import ABC, abstractmethod

from crunch_uml import db
from crunch_uml.registry import Registry

logger = logging.getLogger()


class RendererRegistry(Registry):
    _registry = {}  # type: ignore


def add_args(argumentparser):
    argumentparser.add_argument('-of', '--outputfile', type=str, help="Outputfile")
    argumentparser.add_argument(
        '-ot',
        '--outputtype',
        type=str,
        help=f'geeft outtype aan: {RendererRegistry.entries()}.',
    )
    #argumentparser.add_argument('-orpn', '--output_root_package_names', type=str, help='List of package names separated by comma')
    argumentparser.add_argument('-opi', '--output_package_ids', type=str, help='List of package ids separated by comma')
    argumentparser.add_argument('-oxpi', '--output_exclude_package_ids', type=str, help='List of package ids to be excluded from output separated by comma')
    argumentparser.add_argument('-ojtd', '--output_jinja2_templatedir', type=str, help='Jinja2 template directory')
    argumentparser.add_argument('-ojt', '--output_jinja2_template', type=str, help='Jinja2 template')


class Renderer(ABC):
    @abstractmethod
    def render(self, args, database: db.Database):
        pass
