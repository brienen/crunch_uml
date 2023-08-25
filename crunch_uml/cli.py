import argparse
import logging
import sys

import crunch_uml.const as const
from crunch_uml.db import Database
from crunch_uml.parsers.parser import EAXMIParser, XMIParser  # type: ignore

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
    parser = argparse.ArgumentParser(description="Parse XMI to SQLite DB using SQLAlchemy")
    parser.add_argument('-f', '--file', type=str, help="Path to the XMI file", required=True)
    parser.add_argument('-v', '--verbose', action='store_true', help='zet logniveau op INFO')
    parser.add_argument('-d', '--debug', action='store_true', help='zet logniveau op DEBUG')
    parser.add_argument(
        '-t',
        '--inputtype',
        type=str,
        # action='store_true',
        help='geeft inputtype aan, (xmi, eaxmi).',
        default='xmi',
    )
    parser.add_argument(
        '-db_create',
        '--database_create_new',
        action='store_true',
        help='maak altijd een nieuwe database aan',
        default=True,
    )
    args = parser.parse_args(args)

    # Bepaal het logniveau op basis van commandline argumenten
    if args.debug:
        logger.setLevel(logging.DEBUG)
    elif args.verbose:
        logger.setLevel(logging.INFO)

    database = Database(const.DATABASE_URL, db_create=args.database_create_new)
    try:
        if args.inputtype == 'eaxmi':
            parser = XMIParser()
        elif args.inputtype == 'xmi':
            parser = EAXMIParser()
        else:
            raise (f"Parser error: unknown inputtype {args.inputtype}, use 'xmi' or 'eaxmi'")

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
