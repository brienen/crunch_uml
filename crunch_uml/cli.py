import argparse
import logging
import os
import sys

import crunch_uml.db as db
import crunch_uml.parsers.parser as parsers
import crunch_uml.renderers.renderer as renderers
from crunch_uml import const
from crunch_uml.db import Database
from crunch_uml.parsers.eaxmiparser import EAXMIParser  # noqa: F401
from crunch_uml.parsers.multiple_parsers import (  # noqa: F401
    CSVParser,
    JSONParser,
    XLXSParser,
)
from crunch_uml.parsers.xmiparser import XMIParser  # noqa: F401
from crunch_uml.renderers.jinja2renderer import GGM_MDRenderer  # noqa: F401
from crunch_uml.renderers.jinja2renderer import Jinja2Renderer  # noqa: F401
from crunch_uml.renderers.pandasrenderer import CSVRenderer  # noqa: F401
from crunch_uml.renderers.pandasrenderer import JSONRenderer  # noqa: F401
from crunch_uml.renderers.xlsxrenderer import XLSXRenderer  # noqa: F401

# Configureer logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%d-%b-%y %H:%M:%S',
    stream=sys.stderr,
)
logger = logging.getLogger()


def main(args=None):
    """The main entrypoint for this script used in the setup.py file."""
    argumentparser = argparse.ArgumentParser(description="Parse XMI to SQLite DB using SQLAlchemy")
    argumentparser.add_argument('-v', '--verbose', action='store_true', help='zet logniveau op INFO')
    argumentparser.add_argument('-d', '--debug', action='store_true', help='zet logniveau op DEBUG')

    # Voeg subparsers toe aan het hoofdparser-object
    subparsers = argumentparser.add_subparsers(dest="command", help="Beschikbare subcommando's.")
    subparser_dict = {
        const.CMD_IMPORT: subparsers.add_parser(
            const.CMD_IMPORT, help='Import data to Crunch UML database', formatter_class=argparse.RawTextHelpFormatter
        ),
        const.CMD_EXPORT: subparsers.add_parser(
            const.CMD_EXPORT, help='Export data from Crunch UML database', formatter_class=argparse.RawTextHelpFormatter
        ),
    }

    # let sub modules add there own arguments
    db.add_args(argumentparser, subparser_dict)
    parsers.add_args(argumentparser, subparser_dict)
    renderers.add_args(argumentparser, subparser_dict)
    args = argumentparser.parse_args(args)

    # Bepaal het logniveau op basis van commandline argumenten
    if args.debug:
        logger.setLevel(logging.DEBUG)
    elif args.verbose:
        logger.setLevel(logging.INFO)

    # Parse input
    if args.command == const.CMD_IMPORT:
        if args.inputfile is not None and not os.path.exists(args.inputfile):
            logger.error(f"Inputfile with {args.inputfile} does not exist, stopping.")
            return

        # Get daatbase and optionaly create new one
        database = Database(args.database_url, db_create=args.database_create_new)
        try:
            # First open database, select parser and parse into database
            logger.info(f"Starting parsing with inputtype {args.inputtype}")
            parser = parsers.ParserRegistry.getinstance(args.inputtype)
            parser.parse(args, database)
            database.commit()
            logger.info("Succes! parsed all data and saved it in database")
        except Exception as ex:
            logger.error(
                f"Error while parsing file, writing data to database with message: {ex}. Exiting and"
                " descarding all changes to datbase."
            )
            database.rollback()
            raise
        finally:
            database.close()

    # Render Output
    elif args.command == const.CMD_EXPORT:
        database = Database(args.database_url, db_create=False)
        logger.info(f"Starting rendering with outputtype {args.outputtype}")
        renderer = renderers.RendererRegistry.getinstance(args.outputtype)
        renderer.render(args, database)
        logger.info(f"Succes! rendered output from database wtih renderer {renderer}")
    else:
        logger.error("Unknown command: this should never happen!")


if __name__ == '__main__':
    main()
