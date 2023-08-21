from abc import ABC, abstractmethod
from crunch_uml import db
from crunch_uml import const
from crunch_uml.db import Database
import xml.etree.ElementTree as ET
import logging
logger = logging.getLogger()


class Parser(ABC):
    @abstractmethod
    def parse(self, args, database: db.Database):
        pass



class XMIParser(Parser):

    # Recursieve functie om de parsetree te doorlopen
    def process_package(self, node, database: db.Database, parent_package_id=None):
        tp = node.get('{' + const.NS_XMI + '}type')
        if tp == 'uml:Package':
            package = db.Package(
                id=node.get('{' + const.NS_XMI + '}id'), name=node.get('name'), parent_package_id=parent_package_id
            )
            logger.info(f'Package {package.name} ingelezen met id {package.id}')
            logger.debug(f'Package {package.name} met inhoud {vars(package)}')

            database.add_package(package)
            for childnode in node:
                self.process_package(childnode, database, package.id)

        elif tp == 'uml:Class':
            clazz = db.Class(id=node.get('{' + const.NS_XMI + '}id'), name=node.get('name'), package_id=parent_package_id)
            logger.debug(f'Class {clazz.name} met id {clazz.id} ingelezen met inhoud: {clazz}')
            database.add_class(clazz)

            for childnode in node:
                sub_tp = childnode.get('{' + const.NS_XMI + '}type')
                if sub_tp == 'uml:Property':
                    attribute = db.Attribute(
                        id=childnode.get('{' + const.NS_XMI + '}id'), name=childnode.get('name'), clazz_id=clazz.id
                    )
                    logger.debug(
                        f'Attribute {attribute.name} met id {attribute.id} ingelezen met inhoud: {vars(attribute)}'
                    )
                    database.add_attribute(attribute)

        elif tp == 'uml:Enumeration':
            enum = db.Enumeratie(
                id=node.get('{' + const.NS_XMI + '}id'), name=node.get('name'), package_id=parent_package_id
            )
            logger.debug(f'Enumeratie {enum.name} met id {enum.id} ingelezen met inhoud: {enum}')
            database.add_enumeratie(enum)

            for childnode in node:
                sub_tp = childnode.get('{' + const.NS_XMI + '}type')
                if sub_tp == 'uml:EnumerationLiteral':
                    enumliteral = db.EnumerationLiteral(
                        id=childnode.get('{' + const.NS_XMI + '}id'), name=childnode.get('name'), enumeratie_id=enum.id
                    )
                    logger.debug(
                        f'EnumerationLiteral {enumliteral.name} met id {enumliteral.id} ingelezen met inhoud:'
                        f' {vars(enumliteral)}'
                    )
                    database.add_enumeratieliteral(enumliteral)

        else:
            for childnode in node:
                logger.debug(f'Parsing something with tag {node.tag}, no handling implemented yet values: {node}')
                self.process_package(childnode, database, parent_package_id)



    def parse(self, args, database: db.Database):
        logger.info(f'Parsing file with name {args.file}...')
        logger.debug(f'Parsing with XMIParser...')
        root = ET.parse(args.file).getroot()
        if root is not None:
            self.process_package(root, database)
