import argparse
import logging
import sys

import crunch_uml.const as const
import crunch_uml.db as db
import crunch_uml.parsers.parser as parsers
import crunch_uml.renderers.renderer as renderers
from crunch_uml.db import Database
from crunch_uml.parsers.eaxmiparser import EAXMIParser  # noqa: F401
from crunch_uml.parsers.jsonparser import JSONParser  # noqa: F401
from crunch_uml.parsers.xlsxparser import XLSXParser  # noqa: F401
from crunch_uml.parsers.xmiparser import XMIParser  # noqa: F401
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
    db.add_args(argumentparser)
    parsers.add_args(argumentparser)
    renderers.add_args(argumentparser)
    args = argumentparser.parse_args(args)

    # Bepaal het logniveau op basis van commandline argumenten
    if args.debug:
        logger.setLevel(logging.DEBUG)
    elif args.verbose:
        logger.setLevel(logging.INFO)

    database = Database(const.DATABASE_URL, db_create=args.database_create_new)
    try:
        # First open database, select parser and parse into database
        if args.inputtype is not None:
            logger.info(f"Starting parsing with inputtype {args.inputtype}")
            parser = parsers.ParserRegistry.getinstance(args.inputtype)
            parser.parse(args, database)
            database.commit()
            logger.info("Succes! parsed all data and saved it in database")
        else:
            logger.info("No inputtype provided parsing is skipped, continue")

        # Secondly perform checking (implentation later)

        # Thridy render to output
        if args.outputtype is not None:
            logger.info(f"Starting rendering with outputtype {args.outputtype}")
            renderer = renderers.RendererRegistry.getinstance(args.outputtype)
            renderer.render(args, database)
            logger.info(f"Succes! rendered output from database wtih renderer {renderer}")
        else:
            logger.info("No outputtype provided rendering is skipped")

    except Exception as ex:
        logger.error(f"Error while parsing file and writing data tot database with message: {ex}")
        database.rollback()
        raise
    finally:
        database.close()


if __name__ == '__main__':
    main()
