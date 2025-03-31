import logging
from abc import ABC, abstractmethod

import crunch_uml.db as db
import crunch_uml.schema as sch
from crunch_uml import const, util
from crunch_uml.db import Class, Package
from crunch_uml.exceptions import CrunchException
from crunch_uml.registry import Registry

logger = logging.getLogger()


class RendererRegistry(Registry):
    _registry = {}  # type: ignore
    _descr_registry = {}  # type: ignore


def add_args(argumentparser, subparser_dict):
    output_subparser = subparser_dict.get(const.CMD_EXPORT)

    output_subparser.add_argument(
        "-f",
        "--outputfile",
        type=str,
        help="Outputfile",
        required=True,
    )
    output_subparser.add_argument(
        "-t",
        "--outputtype",
        required=True,
        choices=RendererRegistry.entries(),
        help=f"geeft outputtype aan: {RendererRegistry.entries()}.",
    )
    # argumentparser.add_argument('-orpn', '--output_root_package_names', type=str, help='List of package names separated by comma')
    output_subparser.add_argument(
        "-pi",
        "--output_package_ids",
        type=str,
        help="List of package ids separated by comma",
    )
    output_subparser.add_argument("-ci", "--output_class_id", type=str, help="ID of class to be rendered.")
    output_subparser.add_argument(
        "-xpi",
        "--output_exclude_package_ids",
        type=str,
        help="List of package ids to be excluded from output separated by comma",
    )
    output_subparser.add_argument(
        "-jtd",
        "--output_jinja2_templatedir",
        type=str,
        help="Jinja2 template directory",
    )
    output_subparser.add_argument("-jt", "--output_jinja2_template", type=str, help="Jinja2 template")
    output_subparser.add_argument(
        "-ldns",
        "--linked_data_namespace",
        type=util.urlparse,
        help="Namespace for linked data renderers",
    )
    output_subparser.add_argument(
        "-js_url",
        "--json_schema_url",
        type=str,
        help="URL for JSON schema that should be used for references to the schema.",
    )
    output_subparser.add_argument(
        "-vt",
        "--version_type",
        type=str,
        default=const.VERSION_STEP_MINOR,
        choices=[
            const.VERSION_STEP_MINOR,
            const.VERSION_STEP_MAJOR,
            const.VERSION_STEP_NONE,
        ],
        help=(
            "Used only for Enterprise Architect Repository Updater! After update should the version be updated?"
            f" {const.VERSION_STEP_MINOR} for minnor increments or {const.VERSION_STEP_MAJOR} for major increments,"
            " None for no version update."
        ),
    )
    output_subparser.add_argument(
        "-ts",
        "--tag_strategy",
        type=str,
        default=const.TAG_STRATEGY_REPLACE,
        choices=[
            const.TAG_STRATEGY_UPDATE,
            const.TAG_STRATEGY_UPSERT,
            const.TAG_STRATEGY_REPLACE,
        ],
        help=(
            "Used only for Enterprise Architect Repository Updater! Defines how changing tags of Classes, Enumerations,"
            " Attributes, Literals and Packages should be updated."
        )
        + f"{const.TAG_STRATEGY_UPDATE} for updating only existing tags, {const.TAG_STRATEGY_UPSERT} for updating"
        f" existing tags and adding new tags, {const.TAG_STRATEGY_REPLACE} for replacing all tags.",
    )
    output_subparser.add_argument(
        "-lan",
        "--language",
        type=str,
        default=const.DEFAULT_LANGUAGE,
        help="Used only for i18n renderer. Defines the language of the output file."
        + f" Default is {const.DEFAULT_LANGUAGE}.",
    )
    output_subparser.add_argument(
        "-frlan",
        "--from_language",
        default="auto",
        type=str,
        help="Used only for i18n renderer. Defines the language of the input language. Only has impact if translating.",
    )
    output_subparser.add_argument(
        "-trans",
        "--translate",
        type=bool,
        default=False,
        help=(
            "Used only for i18n renderer. When set to true the input values will be translated using automatic"
            " translating."
        )
        + f" Default is {const.DEFAULT_LANGUAGE}.",
    )
    output_subparser.add_argument(
        "--update_i18n",
        type=bool,
        default=True,
        help=(
            "Used only for i18n renderer in conjunction with '--translate' option. When set to true only missing value"
            " sin i18n file will be translated. Default is True."
        ),
    )
    output_subparser.add_argument(
        "--mapper",
        type=str,
        default="{}",
        help="JSON-string voor het hernoemen van kolommen, bijvoorbeeld: '{\"old_col\": \"new_col\"}'",
    )
    output_subparser.add_argument(
        "--filter",
        type=str,
        default="[]",
        help=(
            "Kommagescheiden lijst met kolommen die geëxporteerd moeten worden, waarbij de volgrorde ook bij de export"
            " wordt gehandhaafd, bijvoorbeeld: '[\"col1\", \"col2\"], \"col3\"'"
        ),
    )
    output_subparser.add_argument(
        "--entity_name",
        type=str,
        help=(
            "Naam van de entiteit die wordt geëxporteerd. Alleen te gebruiken bij CSV-renderer. Mogelijke waarden:"
            f" {db.getTables()}"
        ),
    )

    # Set the epilog help text
    entries = RendererRegistry.entries()
    items = [f'"{item}": {RendererRegistry.getDescription(item)}' for item in entries]
    epilog = "More information on the imported types that are supported:\n\n" + "\n".join(items)
    output_subparser.epilog = epilog


class Renderer(ABC):
    @abstractmethod
    def render(self, args, schema: sch.Schema):
        pass

    def get_included_columns(self, args):
        # Define the list of column names to include in the output
        # If this list is empty, all columns will be included
        if args and args.filter and len(args.filter) > 0:
            return util.parse_string_to_list(args.filter)

        return []


class ModelRenderer(Renderer):
    """
    Abstract class that Renders all model packages
    A model package is a package with at least 1 class inside
    """

    def getModels(self, args, schema: sch.Schema):
        lst = []  # type: ignore
        if args.output_exclude_package_ids is not None:
            # Get package_ids to exclude
            excl_packageids = args.output_exclude_package_ids.split(",")
            excl_packageids = [elem.strip() for elem in excl_packageids]
        if args.output_package_ids is not None:
            # Get package_ids to include
            packageids = args.output_package_ids.split(",")
            packageids = [elem.strip() for elem in packageids]

            # subtract exclude list
            if args.output_exclude_package_ids:
                packageids = [pid for pid in packageids if pid not in excl_packageids]

        # Now find packages
        lst = []
        if args.output_package_ids is not None:
            # If list of p[ackage ids is supplied return query
            lst = (
                schema.get_session()
                .query(Package)
                .join(Class)
                .filter(Package.id.in_(packageids), Package.schema_id == schema.schema_id)
                .distinct()
                .all()
            )
        elif args.output_exclude_package_ids is not None:
            # If only list of excluded model supplied return query
            lst = (
                schema.get_session()
                .query(Package)
                .join(Class)
                .filter(
                    Package.id.notin_(excl_packageids),
                    Package.schema_id == schema.schema_id,
                )
                .distinct()
                .all()
            )
        else:
            # If nothing is supplied return all model packages
            lst = (
                schema.get_session()
                .query(Package)
                .join(Class)
                .filter(Package.schema_id == schema.schema_id)
                .distinct()
                .all()
            )
        if len(lst) == 0:
            logger.warning("Could not find any model packages to render ")
        return lst


class ClassRenderer:
    """
    Mixin that Renders a single class (and possible all connected classes)
    """

    def getClass(self, args, schema: sch.Schema):
        if args.output_exclude_package_ids is not None:
            logger.warning("Parameter --output_exclude_package_ids not valid for class renderer.")
        if args.output_package_ids is not None:
            logger.warning("Parameter --output_package_ids not valid for class renderer.")
        if args.output_class_id is None:
            raise CrunchException(
                "Error: no --output_class_id in arguments. --output_class_id is compulsary for ClassRenderer."
            )

        clazz = schema.get_class(args.output_class_id)
        if not clazz:
            logger.warning(f"Rendering not possible: could not find any class with ID {args.output_class_id} ")
        return clazz
