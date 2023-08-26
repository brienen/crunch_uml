import argparse
import logging
import sys

import crunch_uml.const as const
import crunch_uml.db as db
import crunch_uml.parsers.parser as parsers
from crunch_uml.db import Database
from crunch_uml.parsers.eaxmiparser import EAXMIParser  # noqa: F401
from crunch_uml.parsers.xmiparser import XMIParser  # noqa: F401

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
    args = argumentparser.parse_args(args)

    # Bepaal het logniveau op basis van commandline argumenten
    if args.debug:
        logger.setLevel(logging.DEBUG)
    elif args.verbose:
        logger.setLevel(logging.INFO)

    database = Database(const.DATABASE_URL, db_create=args.database_create_new)
    try:
        parser = parsers.ParserRegistry.getinstance(args.inputtype)
        # if args.inputtype == 'eaxmi':
        #    parser = XMIParser()
        # elif args.inputtype == 'xmi':
        #    parser = EAXMIParser()
        # else:
        #    raise (f"Parser error: unknown inputtype {args.inputtype}, use 'xmi' or 'eaxmi'")

        parser.parse(args, database)
        database.commit()
        logger.info("Succes! parsed all data and saved it in database")
    except Exception as ex:
        logger.error(f"Error while parsing file and writing data tot database with message: {ex}")
        database.rollback()
        raise
    finally:
        database.close()


if __name__ == '__main__':
    main()
