import logging
from abc import ABC, abstractmethod
from lxml import etree
from crunch_uml import const, db

logger = logging.getLogger()


def fixtag(tag):
    return tag.replace('-', '_')

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
            id = node.get('{' + ns['xmi'] + '}id')
            name = node.get('name')
            if id:
                package = db.Package(id=id, name=name, parent_package_id=parent_package_id)
                logger.info(f'Package {package.name} ingelezen met id {package.id}')
                logger.debug(f'Package {package.name} met inhoud {vars(package)}')

                database.save_package(package)
                for childnode in node:
                    self.phase1_process_packages_classes(childnode, ns, database, package.id)
            else:
                logger.debug(f'Package with {name} does not have id value: discarded')

        elif tp == 'uml:Class':
            clazz = db.Class(id=node.get('{' + ns['xmi'] + '}id'), name=node.get('name'), package_id=parent_package_id)
            logger.debug(f'Class {clazz.name} met id {clazz.id} ingelezen met inhoud: {clazz}')
            database.save_class(clazz)

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
        logger.info('Entering second phase parsing: connectors')
        pass

    def phase3_process_extra(self, node, ns, database: db.Database):
        '''
        third and last phase of parsing XMI-documents. Parsing extra propriatary data: addons to allready found data
        '''
        logger.info('Entering third phase parsing: extras')
        pass

    def parse(self, args, database: db.Database):
        logger.info(f'Parsing file with name {args.file}')
        logger.debug('Parsing with XMIParser')

        # Parseer het XML-bestand
        tree = etree.parse(args.file)
        root = tree.getroot()
        ns = root.nsmap
        if 'xmi' not in ns.keys():
            logger.warning(f'missing namespace "xmi" in file {args.file}: trying "{const.NS_XMI}"')
            ns['xmi'] = const.NS_XMI
        if 'uml' not in ns.keys():
            logger.warning(f'missing namespace "uml" in file {args.file}: trying "{const.NS_UML}"')
            ns['xmi'] = const.NS_UML

        if root is not None:
            model = root.xpath('//uml:Model[@xmi:type="uml:Model"][1]', namespaces=ns)[0]  # type: ignore
            self.phase1_process_packages_classes(model, ns, database)
            self.phase2_process_connectors(model, ns, database)
            self.phase3_process_extra(root, ns, database)
        else:
            logger.warning('No content was read from XMI-file')



class EAXMIParser(XMIParser):

    def phase3_process_extra(self, node, ns, database: db.Database):
        '''
        third and last phase of parsing XMI-documents. Parsing extra propriatary data: addons to allready found data.
        Starts at <xmi:Extension extender="Enterprise Architect" extenderID="6.5">
        '''
        logger.info('Entering third phase parsing: extras')
        extension = node.xpath('//xmi:Extension', namespaces=ns)[0] # type: ignore

        '''
        First find all package modifiers that look like:
        	<element xmi:idref="EAPK_5B6708DC_CE09_4284_8DCE_DD1B744BB652" xmi:type="uml:Package" name="Diagram" scope="public">
				<model package2="EAID_5B6708DC_CE09_4284_8DCE_DD1B744BB652" package="EAPK_45B88627_6F44_4b6d_BE77_3EC51BBE679E" tpos="0" ea_localid="41" ea_eleType="package"/>
				<properties isSpecification="false" sType="Package" nType="0" scope="public"/>
				<project author="Arjen Brienen" version="1.0" phase="1.0" created="2019-07-03 14:46:15" modified="2019-07-03 14:46:15" complexity="1" status="Proposed"/>
				<code gentype="Java"/>
				<style appearance="BackColor=-1;BorderColor=-1;BorderWidth=-1;FontColor=-1;VSwimLanes=1;HSwimLanes=1;BorderStyle=0;"/>
				<tags/>
				<xrefs/>
				<extendedProperties tagged="0" package_name="Erfgoed: Monumenten "/>
				<packageproperties version="1.0" tpos="0"/>
				<paths/>
				<times created="2019-07-03 14:46:15" modified="2022-12-12 16:28:22" lastloaddate="2019-07-06 17:08:07" lastsavedate="2019-07-06 17:08:07"/>
				<flags iscontrolled="0" isprotected="0" batchsave="0" batchload="0" usedtd="0" logxml="0"/>
			</element>
        and set value
        '''
        packagerefs = extension.xpath("//element[@xmi:type='uml:Package' and @xmi:idref]", namespaces=ns) # type: ignore
        for packageref in packagerefs:
            idref = packageref.get('{' + ns['xmi'] + '}idref')
            package = database.get_package(idref)
            project = packageref.xpath('./project')[0]
            if project is not None:
                for key in project.keys(): # Dynamic set values of package
                    if hasattr(package, key):
                        setattr(package, key, project.get(key))

            database.save_package(package)

        '''
        Second find all class modifiers, like:
        	<element xmi:idref="EAID_54944273_F312_44b2_A78D_43488F915429" xmi:type="uml:Class" name="Ambacht" scope="public">
				<model package="EAPK_F7651B45_2B64_4197_A6E5_BFC56EC98466" tpos="0" ea_localid="382" ea_eleType="element"/>
				<properties documentation="Beroep waarbij een handwerker met gereedschap eindproducten maakt." isSpecification="false" sType="Class" nType="0" scope="public" isRoot="false" isLeaf="false" isAbstract="false" isActive="false"/>
				<project author="Arjen Brienen" version="1.0" phase="1.0" created="2019-07-03 15:42:28" modified="2022-12-12 16:28:22" complexity="1" status="Proposed"/>
				<code gentype="Java"/>
				<style appearance="BackColor=-1;BorderColor=-1;BorderWidth=-1;FontColor=-1;VSwimLanes=1;HSwimLanes=1;BorderStyle=0;"/>
				<tags>
					<tag xmi:id="EAID_E0C65F37_A2DA_4E79_BDF0_CC3F4607167C" name="archimate-type" value="Business object" modelElement="EAID_54944273_F312_44b2_A78D_43488F915429"/>
					<tag xmi:id="EAID_65401341_DD83_4620_A236_CEC4681C9708" name="bron" modelElement="EAID_54944273_F312_44b2_A78D_43488F915429"/>
					<tag xmi:id="EAID_C5257D00_86DC_4657_9CBC_1EC6C03C74C9" name="datum-tijd-export" value="28062023-11:06:06" modelElement="EAID_54944273_F312_44b2_A78D_43488F915429"/>
					<tag xmi:id="EAID_6ED287EA_0F4E_4177_AD1E_3AAF7842374A" name="domein-dcat" modelElement="EAID_54944273_F312_44b2_A78D_43488F915429"/>
					<tag xmi:id="EAID_5F5875A4_4C61_4BC6_958F_BD7A49149B10" name="domein-gemma" value="nan" modelElement="EAID_54944273_F312_44b2_A78D_43488F915429"/>
					<tag xmi:id="EAID_8CEA0788_DDCB_4399_AB94_971F87A49504" name="gemma-guid" value="id-54944273-f312-44b2-a78d-43488f915429" modelElement="EAID_54944273_F312_44b2_A78D_43488F915429"/>
					<tag xmi:id="EAID_B3E0FB89_EA91_4663_8492_3C550E53D598" name="synoniemen" modelElement="EAID_54944273_F312_44b2_A78D_43488F915429"/>
					<tag xmi:id="EAID_DCA255D6_C1C9_4222_82C1_5AE4D1347690" name="toelichting" modelElement="EAID_54944273_F312_44b2_A78D_43488F915429"/>
				</tags>
				<xrefs/>
				<extendedProperties tagged="0" package_name="Model Monumenten"/>
        '''
        clazzrefs = extension.xpath("//element[@xmi:type='uml:Class' and @xmi:idref]", namespaces=ns) # type: ignore
        for clazzref in clazzrefs:
            idref = clazzref.get('{' + ns['xmi'] + '}idref')
            clazz = database.get_class(idref)

            properties = clazzref.xpath('./properties')[0]
            if properties is not None:
                clazz.descr = properties.get('documentation')
            project = clazzref.xpath('./project')[0]
            if project is not None:
                for key in project.keys(): # Dynamic set values of clazz
                    if hasattr(clazz, key):
                        setattr(clazz, key, project.get(key))
            
            tags = clazzref.xpath('./tags/tag')
            for tag in tags:
                if hasattr(clazz, fixtag(tag.get('name'))):
                    setattr(clazz, fixtag(tag.get('name')), tag.get('value'))

            database.save_class(clazz)
