import logging
from abc import ABC, abstractmethod

from crunch_uml import const, db
from crunch_uml.registry import Registry

logger = logging.getLogger()


class RendererRegistry(Registry):
    _registry = {}  # type: ignore
    _descr_registry = {}  # type: ignore


def add_args(argumentparser, subparser_dict):
    output_subparser = subparser_dict.get(const.CMD_EXPORT)

    output_subparser.add_argument(
        '-f',
        '--outputfile',
        type=str,
        help="Outputfile",
        required=True,
    )
    output_subparser.add_argument(
        '-t',
        '--outputtype',
        required=True,
        choices=RendererRegistry.entries(),
        help=f'geeft outtype aan: {RendererRegistry.entries()}.',
    )
    # argumentparser.add_argument('-orpn', '--output_root_package_names', type=str, help='List of package names separated by comma')
    output_subparser.add_argument(
        '-pi', '--output_package_ids', type=str, help='List of package ids separated by comma'
    )
    output_subparser.add_argument(
        '-xpi',
        '--output_exclude_package_ids',
        type=str,
        help='List of package ids to be excluded from output separated by comma',
    )
    output_subparser.add_argument('-jtd', '--output_jinja2_templatedir', type=str, help='Jinja2 template directory')
    output_subparser.add_argument('-jt', '--output_jinja2_template', type=str, help='Jinja2 template')

    # Set the epilog help text
    entries = RendererRegistry.entries()
    items = [f'"{item}": {RendererRegistry.getDescription(item)}' for item in entries]
    epilog = 'More informaation on the importe types that are supported:\n\n' + '\n'.join(items)
    output_subparser.epilog = epilog


class Renderer(ABC):
    @abstractmethod
    def render(self, args, database: db.Database):
        pass
