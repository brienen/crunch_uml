import xml.etree.ElementTree as ET
import argparse
import logging
import sys
from crunch_uml.db import Database
import crunch_uml.db as db
import crunch_uml.const as const


# Configureer logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%d-%b-%y %H:%M:%S',
    stream=sys.stderr
)
logger = logging.getLogger()


#Recursieve functie om de parsetree te doorlopen
def process_package(node, database, parent_package_id=None):
    tp = node.get('{'+const.NS_XMI+'}type')
    if tp == 'uml:Package':
        package = db.Package(id=node.get('{'+const.NS_XMI+'}id'), name=node.get('name'), parent_package_id=parent_package_id)
        logger.info(f'Package {package.name} ingelezen met id {package.id}')
        logger.debug(f'Package {package.name} met inhoud {vars(package)}')

        database.add_package(package)
        for childnode in node:
            process_package(childnode, database, package.id)

    elif tp == 'uml:Class':
        clazz = db.Class(id=node.get('{'+const.NS_XMI+'}id'), name=node.get('name'), package_id=parent_package_id)
        logger.debug(f'Class {clazz.name} met id {clazz.id} ingelezen met inhoud: {clazz}')
        database.add_class(clazz)

        for childnode in node:
            sub_tp = childnode.get('{'+const.NS_XMI+'}type')
            if sub_tp == 'uml:Property':    
                attribute = db.Attribute(id=childnode.get('{'+const.NS_XMI+'}id'), name=childnode.get('name'), clazz_id=clazz.id)
                logger.debug(f'Attribute {attribute.name} met id {attribute.id} ingelezen met inhoud: {vars(attribute)}')
                database.add_attribute(attribute)

    elif tp == 'uml:Enumeration':
        enum = db.Enumeratie(id=node.get('{'+const.NS_XMI+'}id'), name=node.get('name'), package_id=parent_package_id)
        logger.debug(f'Enumeratie {enum.name} met id {enum.id} ingelezen met inhoud: {enum}')
        database.add_enumeratie(enum)

        for childnode in node:
            sub_tp = childnode.get('{'+const.NS_XMI+'}type')
            if sub_tp == 'uml:EnumerationLiteral':    
                enumliteral = db.EnumerationLiteral(id=childnode.get('{'+const.NS_XMI+'}id'), name=childnode.get('name'), enumeratie_id=enum.id)
                logger.debug(f'EnumerationLiteral {enumliteral.name} met id {enumliteral.id} ingelezen met inhoud: {vars(enumliteral)}')
                database.add_enumeratieliteral(enumliteral)

    else:
        for childnode in node:
            logger.debug(f'Parsing something with tag {node.tag}, no handling implemented yet values: {node}') 
            process_package(childnode, database, parent_package_id)
        




def main(args=None):
    """The main entrypoint for this script used in the setup.py file."""
    parser = argparse.ArgumentParser(description="Parse XMI to SQLite DB using SQLAlchemy")
    parser.add_argument('-f', '--file', type=str, help="Path to the XMI file", required=True)
    parser.add_argument('-v', '--verbose', action='store_true', help='zet logniveau op INFO')
    parser.add_argument('-d', '--debug', action='store_true', help='zet logniveau op DEBUG')
    args = parser.parse_args(args)

    # Bepaal het logniveau op basis van commandline argumenten
    if args.debug:
        logger.setLevel(logging.DEBUG)
    elif args.verbose:
        logger.setLevel(logging.INFO)


    database = Database(const.DATABASE_URL, db_create=True)
    try:
        root = ET.parse(args.file).getroot()
        main_package = root.find(".//{*}Model")
        if root is not None:
            process_package(root, database)
    except Exception as ex:
        logger.error(f"Error while parsing file and writing data tot database with message: {ex}") 
    finally:
        database.commit()
        database.close()


if __name__ == '__main__':
    main()
