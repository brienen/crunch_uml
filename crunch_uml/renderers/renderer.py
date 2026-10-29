import fnmatch
import logging
from abc import ABC, abstractmethod
from typing import Optional

import crunch_uml.db as db
from sqlalchemy import or_
import crunch_uml.schema as sch
from crunch_uml import const, util
from crunch_uml.db import Package
from crunch_uml.exceptions import CrunchException
from crunch_uml.registry import Registry

logger = logging.getLogger()


class RendererRegistry(Registry):
    _registry = {}  # type: ignore
    _descr_registry = {}  # type: ignore


def str2bool(value):
    """Argparse-type for real booleans. ``type=bool`` is a classic trap:
    bool("False") is True, so '--update_i18n False' silently meant True."""
    if isinstance(value, bool):
        return value
    if value.strip().lower() in ("true", "yes", "1"):
        return True
    if value.strip().lower() in ("false", "no", "0"):
        return False
    raise ValueError(f"verwacht True of False, kreeg '{value}'")


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
        "-xpn",
        "--output_exclude_package_names",
        type=str,
        help=(
            "Kommagescheiden lijst van packagenaam-patronen (hoofdletterongevoelig, * en ? toegestaan) die met hun"
            f" subpackages uit de output worden weggelaten. De LOD-renderers gebruiken standaard '{const.LOD_EXCLUDE_PACKAGE_NAMES}';"
            " geef een lege string op om niets op naam uit te sluiten."
        ),
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
    # MIM-metadata voor de linked-data-renderers (ttl, rdf, json-ld).
    output_subparser.add_argument(
        "-ldlang",
        "--lod_language",
        type=str,
        default="nl",
        help=(
            "Taaltag (BCP 47) voor labels, definities en toelichtingen in de linked-data-renderers;"
            " een lege string geeft literals zonder taaltag. Standaard 'nl'."
        ),
    )
    output_subparser.add_argument(
        "-ldver",
        "--lod_version",
        type=str,
        help=(
            "Versie van het informatiemodel voor de linked-data-renderers (owl:versionInfo en"
            " owl:versionIRI), bijvoorbeeld v3.0.0."
        ),
    )
    output_subparser.add_argument(
        "--lod_title",
        type=str,
        help="Titel van het informatiemodel (dcterms:title); standaard de naam van het wortelpakket.",
    )
    output_subparser.add_argument(
        "--lod_publisher",
        type=str,
        help="Uitgever van het informatiemodel (dcterms:publisher), als naam of als URI.",
    )
    output_subparser.add_argument(
        "--lod_license",
        type=str,
        help="Licentie van het informatiemodel (dcterms:license), als URI.",
    )
    output_subparser.add_argument(
        "--lod_informatiedomein",
        type=str,
        help="Functioneel domein waartoe het informatiemodel behoort (mim:informatiedomein).",
    )
    output_subparser.add_argument(
        "--lod_informatiemodeltype",
        type=str,
        default="logisch",
        choices=["conceptueel", "logisch", "technisch"],
        help="MIM-informatiemodeltype van het model (mim:informatiemodeltype). Standaard 'logisch'.",
    )
    output_subparser.add_argument(
        "--lod_shapes_file",
        type=str,
        help=(
            "Linked-data-renderers: schrijf de SHACL-shapes (sh:NodeShape, sh:PropertyShape, sh:in-lijsten en"
            " alle andere sh:-triples) naar dit bestand in plaats van in het uitvoerbestand, dat dan alleen de"
            " RDFS/OWL-ontologie met de MIM-metagegevens bevat. Het shapes-bestand importeert de ontologie"
            " (owl:imports); de extensie volgt het uitvoertype."
        ),
    )
    output_subparser.add_argument(
        "--lod_views_dir",
        type=str,
        help=(
            "Linked-data-renderers: schrijf per diagram een view (deelmodel) in deze map: de klassen en"
            " enumeraties op het diagram met al hun attributen en waarden (en de enumeraties die het type van"
            " zo'n attribuut zijn), en de associaties en generalisaties tussen die elementen, als deelgraaf van"
            " de ontologie (dezelfde IRI's, zonder SHACL). Pad:"
            " {map}/{domein}/{model}/{diagram}.{ext}; graph-IRI {namespace}[{versie}/]{domein}/{model}/{diagram},"
            " in Turtle ook als kopregel '# graph: <...>'."
        ),
    )
    output_subparser.add_argument(
        "--lod_views_exclude",
        type=str,
        help=(
            "Kommagescheiden naampatronen (hoofdletterongevoelig, * en ? toegestaan) van diagrammen, en van"
            f" packages waar die diagrammen onder vallen, die geen view worden. Standaard '{const.LOD_VIEWS_EXCLUDE_NAMES}';"
            " geef een lege string op om niets uit te sluiten."
        ),
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
        "--ea_allow_insert",
        action="store_true",
        default=False,
        help=(
            "Used only for Enterprise Architect Repository Updater! "
            "When set, new Packages, Classes, Enumerations, Attributes, Literals and Relations "
            "that do not yet exist in the EA repository are inserted as new records."
        ),
    )
    output_subparser.add_argument(
        "--ea_allow_delete",
        action="store_true",
        default=False,
        help=(
            "Used only for Enterprise Architect Repository Updater! "
            "When set, Packages, Classes, Enumerations, Attributes, Literals and Relations "
            "that exist in the EA repository but are no longer present in the source model "
            "are permanently deleted from the EA repository. Use with caution."
        ),
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
        type=str2bool,
        default=False,
        help=(
            "Used only for i18n renderer. When set to true the input values will be translated using automatic"
            " translating. Default is False."
        ),
    )
    output_subparser.add_argument(
        "--update_i18n",
        type=str2bool,
        default=True,
        help=(
            "Used only for i18n renderer in conjunction with '--translate' option. True (default): only missing"
            " values in the i18n file are translated. False: the language is fully re-translated (existing"
            " translations for that language are replaced; other languages stay untouched)."
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
    # diff_md renderer (schema comparison)
    output_subparser.add_argument(
        "--compare_schema_name",
        type=str,
        help=(
            "Used only for diff_md renderer. The schema_name/schema_id to compare the current schema against. "
            "Example: --schema_name v2.5.0 --compare_schema_name v2.4.0"
        ),
    )
    output_subparser.add_argument(
        "--compare_title",
        type=str,
        help=(
            "Used only for diff_md renderer. Optional title for the Markdown diff report. "
            'Example: --compare_title "v2.4.0 vs v2.5.0"'
        ),
    )
    # i18n translation backend (mirrors the CRUNCH_UML_* env vars). When set,
    # the CLI args win over any env-var; when omitted, env-vars (and the
    # baked-in defaults) are used.
    output_subparser.add_argument(
        "--translate_backend",
        type=str,
        choices=["translators", "ollama", "pipeline"],
        default=None,
        help=(
            "i18n renderer: which translation backend to use. 'translators' (default) calls "
            "Google/Bing via the translators library; 'ollama' calls a local LLM; 'pipeline' runs "
            "the layered deterministic pipeline (termbanks + local LLMs, see docs). Overrides "
            "CRUNCH_UML_TRANSLATE_BACKEND."
        ),
    )
    output_subparser.add_argument(
        "--termbanks",
        type=str,
        default=None,
        help=(
            "i18n renderer (pipeline backend): comma-separated paths (files or directories) to "
            "termbank sources (SKOS/RDF/TTL/JSON-LD or IATE TBX); order = priority. Overrides "
            "CRUNCH_UML_TERMBANKS."
        ),
    )
    output_subparser.add_argument(
        "--llm_workhorses",
        type=str,
        default=None,
        help=(
            "i18n renderer (pipeline backend): comma-separated Ollama model prefixes; the first is "
            "the primary workhorse, the second the independent vote on names. Overrides "
            "CRUNCH_UML_LLM_WORKHORSES."
        ),
    )
    output_subparser.add_argument(
        "--llm_heavy",
        type=str,
        default=None,
        help=(
            "i18n renderer (pipeline backend): Ollama model prefix for the heavy escalation model. "
            "Overrides CRUNCH_UML_LLM_HEAVY."
        ),
    )
    output_subparser.add_argument(
        "--nmt_model",
        type=str,
        default=None,
        help=(
            "i18n renderer (pipeline backend): Hugging Face model name for the optional NMT safety "
            "net; {from}/{to} placeholders allowed. Overrides CRUNCH_UML_NMT_MODEL."
        ),
    )
    output_subparser.add_argument(
        "--translate_allow_online",
        action="store_true",
        default=False,
        help=(
            "i18n renderer (pipeline backend): allow the online translators route (Google/Bing) as "
            "last-resort fallback. Not reproducible, therefore off by default. Equivalent to "
            "CRUNCH_UML_TRANSLATE_ALLOW_ONLINE=1."
        ),
    )
    output_subparser.add_argument(
        "--ollama_model",
        type=str,
        default=None,
        help=(
            "i18n renderer (Ollama backend): model tag to use. Default 'mistral-small3.1:24b'. "
            "Overrides CRUNCH_UML_OLLAMA_MODEL."
        ),
    )
    output_subparser.add_argument(
        "--ollama_url",
        type=str,
        default=None,
        help=(
            "i18n renderer (Ollama backend): URL of the Ollama server. Default "
            "'http://localhost:11434'. Overrides CRUNCH_UML_OLLAMA_URL."
        ),
    )
    output_subparser.add_argument(
        "--ollama_timeout",
        type=int,
        default=None,
        help=(
            "i18n renderer (Ollama backend): seconds to wait per translation call. "
            "Default 120. Overrides CRUNCH_UML_OLLAMA_TIMEOUT."
        ),
    )
    output_subparser.add_argument(
        "--translate_workers",
        type=int,
        default=None,
        help=(
            "i18n renderer: number of parallel threads used to translate. Default 8. "
            "Overrides CRUNCH_UML_TRANSLATE_WORKERS."
        ),
    )
    output_subparser.add_argument(
        "--translate_context",
        action="store_true",
        default=False,
        help=(
            "i18n renderer (Ollama backend): include section/field hints in the prompt for "
            "better domain consistency. Equivalent to CRUNCH_UML_TRANSLATE_CONTEXT=1."
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

    # Packagenaam-patronen die een renderer standaard uitsluit als de gebruiker
    # --output_exclude_package_names niet opgeeft (None: niets uitsluiten).
    default_exclude_package_names: Optional[str] = None

    def excludePackagePatterns(self, args):
        """De patronen uit --output_exclude_package_names, of de renderer-default."""
        value = getattr(args, "output_exclude_package_names", None)
        if value is None:
            value = self.default_exclude_package_names
        if not value:
            return []
        return [pattern.strip().casefold() for pattern in value.split(",") if pattern.strip()]

    @staticmethod
    def isExcludedByName(package, patterns):
        """Waar als het package zelf of een bovenliggend package een patroon matcht."""
        if not patterns:
            return False
        seen = set()
        while package is not None and package.id not in seen:
            seen.add(package.id)
            name = (package.name or "").casefold()
            if any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns):
                return True
            package = package.parent_package
        return False

    def getModels(self, args, schema: sch.Schema):
        """De te renderen modelpakketten: elk pakket met klassen of enumeraties.

        Een pakket met alleen enumeraties (in het GGM 'Enumeratiesoort' naast een model, of
        'Datatypes') is ook een model: zijn enumeraties horen in de documentatie en de LOD
        een eigen plek te hebben. Tot 0.8.3 telden alleen pakketten met klassen; zulke
        enumeraties verschenen dan nergens, of als kopie in de modellen die ze gebruiken.
        Daarna: beperkt tot of zonder de opgegeven pakket-id's en zonder de op naam
        uitgesloten pakketten.
        """
        query = (
            schema.get_session()
            .query(Package)
            .filter(
                Package.schema_id == schema.schema_id,
                or_(Package.classes.any(), Package.enumerations.any()),
            )
        )
        excl_packageids = []
        if args.output_exclude_package_ids is not None:
            excl_packageids = [elem.strip() for elem in args.output_exclude_package_ids.split(",")]
        if args.output_package_ids is not None:
            packageids = [elem.strip() for elem in args.output_package_ids.split(",")]
            packageids = [pid for pid in packageids if pid not in excl_packageids]
            query = query.filter(Package.id.in_(packageids))
        elif excl_packageids:
            query = query.filter(Package.id.notin_(excl_packageids))
        lst = query.all()
        patterns = self.excludePackagePatterns(args)
        if patterns:
            excluded = [package for package in lst if self.isExcludedByName(package, patterns)]
            if excluded:
                logger.info(
                    f"{len(excluded)} modelpakketten op naam uitgesloten ({', '.join(patterns)}): "
                    + ", ".join(sorted({package.name or package.id for package in excluded}))
                )
                lst = [package for package in lst if package not in excluded]
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
