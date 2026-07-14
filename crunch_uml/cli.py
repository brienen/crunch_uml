import argparse
import logging
import os
import sys

import crunch_uml.db as db
import crunch_uml.parsers.parser as parsers
import crunch_uml.renderers.renderer as renderers
import crunch_uml.schema as sch
import crunch_uml.transformers.transformer as transformers
from crunch_uml import const
from crunch_uml.db import Database
from crunch_uml.parsers.eaxmiparser import EAXMIParser  # noqa: F401
from crunch_uml.parsers.multiple_parsers import CSVParser  # noqa: F401
from crunch_uml.parsers.multiple_parsers import I18nParser  # noqa: F401
from crunch_uml.parsers.multiple_parsers import JSONParser  # noqa: F401
from crunch_uml.parsers.multiple_parsers import XLXSParser  # noqa: F401
from crunch_uml.parsers.qeaparser import QEAParser  # noqa: F401
from crunch_uml.parsers.xmiparser import XMIParser  # noqa: F401
from crunch_uml.renderers.earepoupdater import EAMIMRepoUpdater  # noqa: F401
from crunch_uml.renderers.earepoupdater import EARepoUpdater  # noqa: F401
from crunch_uml.renderers.jinja2renderer import GGM_MDRenderer  # noqa: F401
from crunch_uml.renderers.jinja2renderer import Jinja2Renderer  # noqa: F401
from crunch_uml.renderers.jinja2renderer import JSON_SchemaRenderer  # noqa: F401
from crunch_uml.renderers.lodrenderer import JSONLDRenderer  # noqa: F401
from crunch_uml.renderers.lodrenderer import RDFRenderer  # noqa: F401
from crunch_uml.renderers.lodrenderer import TTLRenderer  # noqa: F401
from crunch_uml.renderers.pandasrenderer import CSVRenderer  # noqa: F401
from crunch_uml.renderers.pandasrenderer import I18nRenderer  # noqa: F401
from crunch_uml.renderers.pandasrenderer import JSONRenderer  # noqa: F401
from crunch_uml.renderers.pandasrenderer import SchemaDiffMarkdownRenderer  # noqa: F401
from crunch_uml.renderers.sqlarenderer import SQLARenderer  # noqa: F401
from crunch_uml.renderers.xlsxrenderer import XLSXRenderer  # noqa: F401
from crunch_uml.renderers.xmirenderer import XMIRenderer  # noqa: F401
from crunch_uml.transformers.copytransformer import CopyTransformer  # noqa: F401
from crunch_uml.transformers.plugintransformer import PluginTransformer  # noqa: F401

# Configureer logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger()


# Mapping of (CLI arg name → env-var name) for the i18n translation backend.
# An arg value of None means "not specified" → leave the env-var untouched
# so externally exported env-vars and the baked-in defaults still apply.
_TRANSLATE_ENV_MAP = [
    ("translate_backend", "CRUNCH_UML_TRANSLATE_BACKEND"),
    ("ollama_model", "CRUNCH_UML_OLLAMA_MODEL"),
    ("ollama_url", "CRUNCH_UML_OLLAMA_URL"),
    ("ollama_timeout", "CRUNCH_UML_OLLAMA_TIMEOUT"),
    ("translate_workers", "CRUNCH_UML_TRANSLATE_WORKERS"),
    # Pipeline backend (zie crunch_uml/translation en docs/technisch/vertaalpijplijn.md)
    ("termbanks", "CRUNCH_UML_TERMBANKS"),
    ("llm_workhorses", "CRUNCH_UML_LLM_WORKHORSES"),
    ("llm_heavy", "CRUNCH_UML_LLM_HEAVY"),
    ("nmt_model", "CRUNCH_UML_NMT_MODEL"),
]


def _propagate_translate_args_to_env(args):
    """Push any explicitly-set translation CLI args into ``os.environ`` so
    deeper modules see them without needing args threaded through."""
    for attr, env_var in _TRANSLATE_ENV_MAP:
        value = getattr(args, attr, None)
        if value is not None:
            os.environ[env_var] = str(value)
    # Boolean flags — only force-on when explicitly passed.
    if getattr(args, "translate_context", False):
        os.environ["CRUNCH_UML_TRANSLATE_CONTEXT"] = "1"
    if getattr(args, "translate_allow_online", False):
        os.environ["CRUNCH_UML_TRANSLATE_ALLOW_ONLINE"] = "1"


def main(args=None):
    """The main entrypoint for this script used in the setup.py file."""
    argumentparser = argparse.ArgumentParser(description=const.DESCRIPTION)
    argumentparser.add_argument("-v", "--verbose", action="store_true", help="set log level INFO")
    argumentparser.add_argument("-d", "--debug", action="store_true", help="set log level to DEBUG")
    argumentparser.add_argument(
        "-w",
        "--do_not_suppress_warnings",
        action="store_true",
        help="do not suppress warnings.",
    )

    # Voeg subparsers toe aan het hoofdparser-object
    subparsers = argumentparser.add_subparsers(dest="command", help="Available sub commands.")
    subparser_dict = {
        const.CMD_IMPORT: subparsers.add_parser(
            const.CMD_IMPORT,
            help="Import datamodel to Crunch UML database into a schema",
            formatter_class=argparse.RawTextHelpFormatter,
        ),
        const.CMD_TRANSFORM: subparsers.add_parser(
            const.CMD_TRANSFORM,
            help="Transform datamodel from one schema to another schema",
            formatter_class=argparse.RawTextHelpFormatter,
        ),
        const.CMD_EXPORT: subparsers.add_parser(
            const.CMD_EXPORT,
            help="Export datamodel from a schema in the Crunch UML database to various formats",
            formatter_class=argparse.RawTextHelpFormatter,
        ),
    }

    # let sub modules add there own arguments
    db.add_args(argumentparser, subparser_dict)
    sch.add_args(argumentparser, subparser_dict)
    parsers.add_args(argumentparser, subparser_dict)
    renderers.add_args(argumentparser, subparser_dict)
    transformers.add_args(argumentparser, subparser_dict)
    args = argumentparser.parse_args(args)

    # Propagate translation-backend CLI args into env-vars so the rest of the
    # code (lang.py, ollama_translator.py, I18nRenderer) which reads from
    # os.environ picks them up without further plumbing. CLI > env > default.
    _propagate_translate_args_to_env(args)

    # Bepaal het logniveau op basis van commandline argumenten
    if args.debug:
        logger.setLevel(logging.DEBUG)
    elif args.verbose:
        logger.setLevel(logging.INFO)

    # Show help if no command is given
    if args.command is None:
        argumentparser.print_help()
        return 1

    try:
        # Parse input
        if args.command == const.CMD_IMPORT:
            if args.inputfile is not None and not os.path.exists(args.inputfile):
                logger.error(f"Inputfile with {args.inputfile} does not exist, stopping.")
                return

            # Get daatbase and optionaly create new one
            database = Database(args.database_url, db_create=args.database_create_new)
            schema = sch.Schema(database, schema_name=args.schema_name)
            try:
                # First open database, select parser and parse into database
                logger.info(f"Starting parsing with inputtype {args.inputtype}")
                parser = parsers.ParserRegistry.getinstance(args.inputtype)
                parser.parse(args, schema)
                database.commit()
                logger.info("Succes! parsed all data and saved it in database")
            except Exception as ex:
                logger.error(
                    f"Error while parsing file, writing data to database with message: {ex}. Exiting and"
                    " descarding all changes to database."
                )
                database.rollback()
                raise
            finally:
                database.close()

        # Do transformation
        elif args.command == const.CMD_TRANSFORM:
            database = Database(args.database_url, db_create=False)
            logger.info("Starting transformation ")
            try:
                transformer = transformers.TransformerRegistry.getinstance(args.transformationtype)
                transformer.transform(args, database)
                database.commit()
                logger.info(
                    f"Succes! transformed input with transformer {transformer} from schema {args.schema_from} to schema"
                    f" {args.schema_to}"
                )
            except Exception as ex:
                logger.error(
                    f"Error while performing transformation with message: {ex}. Exiting and"
                    " descarding all changes to datbase."
                )
                database.rollback()
                raise
            finally:
                database.close()

        # Render Output
        elif args.command == const.CMD_EXPORT:
            database = Database(args.database_url, db_create=False)
            schema = sch.Schema(database, schema_name=args.schema_name)
            logger.info(f"Starting rendering with outputtype {args.outputtype}")
            renderer = renderers.RendererRegistry.getinstance(args.outputtype)
            renderer.render(args, schema)
            logger.info(f"Succes! rendered output from database wtih renderer {renderer}")
        else:
            logger.error("Unknown command: this should never happen!")
            return 1

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return 1

    # Als alles goed gaat, retourneer een succesvolle exit-status
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
