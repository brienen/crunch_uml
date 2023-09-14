import logging
from abc import ABC, abstractmethod

from crunch_uml import const, db, util
from crunch_uml.db import Class, Package
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
    output_subparser.add_argument(
        '-ldns', '--linked_data_namespace', type=util.urlparse, help='Namespace for linked data renderers'
    )

    # Set the epilog help text
    entries = RendererRegistry.entries()
    items = [f'"{item}": {RendererRegistry.getDescription(item)}' for item in entries]
    epilog = 'More informaation on the importe types that are supported:\n\n' + '\n'.join(items)
    output_subparser.epilog = epilog


class Renderer(ABC):
    @abstractmethod
    def render(self, args, database: db.Database):
        pass


class ModelRenderer(Renderer):
    '''
    Abstract class that Renders all model packages
    A model package is a package with at least 1 class inside
    '''

    def getModels(self, args, database):
        lst = []
        if args.output_exclude_package_ids is not None:
            # Get package_ids to include
            excl_packageids = args.output_exclude_package_ids.split(',')
            excl_packageids = [elem.strip() for elem in excl_packageids]
        if args.output_package_ids is not None:
            # Get package_ids to include
            packageids = args.output_package_ids.split(',')
            packageids = [elem.strip() for elem in packageids]

            # subtract exclude list
            if args.output_exclude_package_ids:
                packageids = [pid for pid in packageids if pid not in excl_packageids]

        # Now find packages
        lst = []
        if args.output_package_ids is not None:
            # If list of p[ackage ids is supplied return query
            lst = database.get_session().query(Package).join(Class).filter(Package.id.in_(packageids)).distinct().all()
        elif args.output_exclude_package_ids is not None:
            # If only list of excluded model supplied return query
            lst = (
                database.get_session()
                .query(Package)
                .join(Class)
                .filter(Package.id.notin_(excl_packageids))
                .distinct()
                .all()
            )
        else:
            # If nothing is supplied return all model packages
            lst = database.get_session().query(Package).join(Class).distinct().all()
        if len(lst) == 0:
            logger.warning("Could not find any model packages to render ")
        return lst
