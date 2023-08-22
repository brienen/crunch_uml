from abc import ABC, abstractmethod
from crunch_uml import db
from crunch_uml import const
from crunch_uml.db import Database
from lxml import etree
import logging

logger = logging.getLogger()


class Parser(ABC):
    @abstractmethod
    def parse(self, args, database: db.Database):
        pass


class XMIParser(Parser):
    # Recursieve functie om de parsetree te doorlopen
    def phase1_process_packages_classes(self, node, ns, database: db.Database, parent_package_id=None):
        '''
        First phase of parsing XMI-documents. Parsing recursively:
        - Packages
        - Classes incl attributes
        - Enumeration incl values 
        '''
        tp = node.get('{' + ns['xmi'] + '}type')
        if tp == 'uml:Package':
            id=node.get('{' + ns['xmi'] + '}id')
            name=node.get('name')
            if id: 
                package = db.Package(
                    id=id, name=name, parent_package_id=parent_package_id
                )
                logger.info(f'Package {package.name} ingelezen met id {package.id}')
                logger.debug(f'Package {package.name} met inhoud {vars(package)}')

                database.add_package(package)
                for childnode in node:
                    self.phase1_process_packages_classes(childnode, ns, database, package.id)
            else:
                logger.debug(f'Package with {name} does not have id value: discarded')


        elif tp == 'uml:Class':
            clazz = db.Class(
                id=node.get('{' + ns['xmi'] + '}id'), name=node.get('name'), package_id=parent_package_id
            )
            logger.debug(f'Class {clazz.name} met id {clazz.id} ingelezen met inhoud: {clazz}')
            database.add_class(clazz)

            for childnode in node:
                sub_tp = childnode.get('{' + ns['xmi'] + '}type')
                if sub_tp == 'uml:Property':
                    attribute = db.Attribute(
                        id=childnode.get('{' + ns['xmi'] + '}id'), name=childnode.get('name'), clazz_id=clazz.id
                    )
                    logger.debug(
                        f'Attribute {attribute.name} met id {attribute.id} ingelezen met inhoud: {vars(attribute)}'
                    )
                    database.add_attribute(attribute)

        elif tp == 'uml:Enumeration':
            enum = db.Enumeratie(
                id=node.get('{' + ns['xmi'] + '}id'), name=node.get('name'), package_id=parent_package_id
            )
            logger.debug(f'Enumeratie {enum.name} met id {enum.id} ingelezen met inhoud: {enum}')
            database.add_enumeratie(enum)

            for childnode in node:
                sub_tp = childnode.get('{' + ns['xmi'] + '}type')
                if sub_tp == 'uml:EnumerationLiteral':
                    enumliteral = db.EnumerationLiteral(
                        id=childnode.get('{' + ns['xmi'] + '}id'), name=childnode.get('name'), enumeratie_id=enum.id
                    )
                    logger.debug(
                        f'EnumerationLiteral {enumliteral.name} met id {enumliteral.id} ingelezen met inhoud:'
                        f' {vars(enumliteral)}'
                    )
                    database.add_enumeratieliteral(enumliteral)

        else:
            for childnode in node:
                logger.debug(f'Parsing something with tag {node.tag}, no handling implemented yet values: {node}')
                self.phase1_process_packages_classes(childnode, ns, database, parent_package_id)

    def phase2_process_connectors(self, node, ns, database: db.Database):
        '''
        second phase of parsing XMI-documents. Parsing and connecting:
        - Assosiations
        - Generalizations
        '''
        logger.info(f'Entering second phase parsing: connectors')
        pass

    def phase3_process_extra(self, node, ns, database: db.Database):
        '''
        third and last phase of parsing XMI-documents. Parsing extra propriatary data: addons to allready found data
        '''
        logger.info(f'Entering third phase parsing: extras')
        pass

    def parse(self, args, database: db.Database):
        logger.info(f'Parsing file with name {args.file}')
        logger.debug(f'Parsing with XMIParser')

        # Parseer het XML-bestand
        tree = etree.parse(args.file)
        root = tree.getroot()
        ns = root.nsmap
        if not 'xmi' in ns.keys():
            logger.warning(f'missing namespace "xmi" in file {args.file}: trying "{const.NS_XMI}"')
            ns['xmi'] = const.NS_XMI
        if not 'uml' in ns.keys():
            logger.warning(f'missing namespace "uml" in file {args.file}: trying "{const.NS_UML}"')
            ns['xmi'] = const.NS_UML

        if root is not None:
            model = root.xpath('//uml:Model[@xmi:type="uml:Model"][1]', namespaces=ns)[0]
            self.phase1_process_packages_classes(model, ns, database)
            self.phase2_process_connectors(model, ns, database)
            self.phase3_process_extra(root, ns, database)
        else:
            logger.warning(f'No content was read from XMI-file')
