#!/usr/bin/env python
#  type: ignore

import logging
from abc import ABC, abstractmethod

from lxml import etree

from crunch_uml import const, db

logger = logging.getLogger()


def fixtag(tag):
    return tag.replace('-', '_')


def copy_values(node, obj):
    '''
    Copies all values from attributes of node to obj,
    if obj has an attribute with the same name.
    Fix for '-' symbol to '_'
    '''
    if node is not None:
        for key in node.keys():  # Dynamic set values of package
            if hasattr(obj, fixtag(key)):
                setattr(obj, fixtag(key), node.get(key))


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

                database.save(package)
                for childnode in node:
                    self.phase1_process_packages_classes(childnode, ns, database, package.id)
            else:
                logger.debug(f'Package with {name} does not have id value: discarded')

        elif tp == 'uml:Class':
            clazz = db.Class(id=node.get('{' + ns['xmi'] + '}id'), name=node.get('name'), package_id=parent_package_id)
            logger.debug(f'Class {clazz.name} met id {clazz.id} ingelezen met inhoud: {clazz}')
            database.save(clazz)

            for childnode in node:
                sub_tp = childnode.get('{' + ns['xmi'] + '}type')
                if sub_tp == 'uml:Property':
                    attribute = db.Attribute(
                        id=childnode.get('{' + ns['xmi'] + '}id'), name=childnode.get('name'), clazz_id=clazz.id
                    )
                    logger.debug(
                        f'Attribute {attribute.name} met id {attribute.id} ingelezen met inhoud: {vars(attribute)}'
                    )
                    database.save(attribute)

        elif tp == 'uml:Enumeration':
            enum = db.Enumeratie(
                id=node.get('{' + ns['xmi'] + '}id'), name=node.get('name'), package_id=parent_package_id
            )
            logger.debug(f'Enumeratie {enum.name} met id {enum.id} ingelezen met inhoud: {enum}')
            database.save(enum)

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
                    database.save(enumliteral)

        else:
            for childnode in node:
                logger.debug(f'Parsing something with tag {node.tag}, no handling implemented yet values: {node}')
                self.phase1_process_packages_classes(childnode, ns, database, parent_package_id)

    def phase2_process_connectors(self, node, ns, database: db.Database):
        '''
        second phase of parsing XMI-documents. Parsing and connecting:
        - Assosiations
        - Generalizations

        Associations have this form:
        <packagedElement xmi:type="uml:Association" xmi:id="EAID_333AC8C9_7443_4a49_A875_297B65FC944C" name="heeft">
            <memberEnd xmi:idref="EAID_dst3AC8C9_7443_4a49_A875_297B65FC944C"/>
            <memberEnd xmi:idref="EAID_src3AC8C9_7443_4a49_A875_297B65FC944C"/>
            <ownedEnd xmi:type="uml:Property" xmi:id="EAID_src3AC8C9_7443_4a49_A875_297B65FC944C" association="EAID_333AC8C9_7443_4a49_A875_297B65FC944C">
                <type xmi:idref="EAID_266057AF_58BD_42e1_B4D5_16EB266B9B7A"/>
                <lowerValue xmi:type="uml:LiteralInteger" xmi:id="EAID_LI000005__7443_4a49_A875_297B65FC944C" value="1"/>
                <upperValue xmi:type="uml:LiteralUnlimitedNatural" xmi:id="EAID_LI000006__7443_4a49_A875_297B65FC944C" value="1"/>
            </ownedEnd>
            <ownedEnd xmi:type="uml:Property" xmi:id="EAID_dst3AC8C9_7443_4a49_A875_297B65FC944C" association="EAID_333AC8C9_7443_4a49_A875_297B65FC944C">
                <type xmi:idref="EAID_CFFD5F20_5FA9_4d93_AD34_6867D64A58B9"/>
                <lowerValue xmi:type="uml:LiteralInteger" xmi:id="EAID_LI000021__7443_4a49_A875_297B65FC944C" value="0"/>
                <upperValue xmi:type="uml:LiteralUnlimitedNatural" xmi:id="EAID_LI000022__7443_4a49_A875_297B65FC944C" value="*"/>
            </ownedEnd>
        </packagedElement>
        '''
        logger.info('Entering second phase parsing: connectors')
        try:
            associations_xmi = node.xpath(".//packagedElement[@xmi:type='uml:Association']", namespaces=ns)  # type: ignore

            for association_xp in associations_xmi:
                logger.debug(
                    f"Parsing association {association_xp.get('name')} with id"
                    f" {association_xp.get('{' + ns['xmi'] + '}id')})"
                )
                association = db.Association(
                    id=association_xp.get('{' + ns['xmi'] + '}id'), name=association_xp.get('name')
                )
                memberends = association_xp.xpath("./memberEnd", namespaces=ns)
                for memberend in memberends:
                    id = memberend.get('{' + ns['xmi'] + '}idref')
                    endpoints = node.xpath(f".//*[@xmi:id='{id}']", namespaces=ns)
                    for endpoint in endpoints:
                        getval = lambda x, endpoint: (
                            endpoint.xpath(f'./{x}')[0].get('value') if len(endpoint.xpath(f'./{x}')) else None
                        )
                        clsid = endpoint.xpath('./type')[0].get('{' + ns['xmi'] + '}idref')
                        cls = database.get_class(clsid)
                        if cls is None:
                            clazz = db.Class(id=clsid, name='<Orphan Class>')
                            database.save(clazz)
                        if 'src' in id:
                            association.src_class_id = clsid
                            association.src_mult_start = getval('lowerValue', endpoint)
                            association.src_mult_end = getval('upperValue', endpoint)
                        else:
                            association.dst_class_id = clsid
                            association.dst_mult_start = getval('lowerValue', endpoint)
                            association.dst_mult_end = getval('upperValue', endpoint)

                database.save(association)
        except Exception as ex:
            logger.error(f"Error in phase 2 of parsing with message: {ex}")
            raise ex

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
        logger.info('Entering third phase parsing for EAParser: extras')
        extension = node.xpath('//xmi:Extension', namespaces=ns)[0]  # type: ignore

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
        packagerefs = extension.xpath(".//element[@xmi:type='uml:Package' and @xmi:idref]", namespaces=ns)  # type: ignore
        for packageref in packagerefs:
            idref = packageref.get('{' + ns['xmi'] + '}idref')
            package = database.get_package(idref)
            project = packageref.xpath('./project')[0]
            copy_values(project, package)

            database.save(package)

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
        clazzrefs = extension.xpath(".//element[@xmi:type='uml:Class' and @xmi:idref]", namespaces=ns)  # type: ignore
        for clazzref in clazzrefs:
            idref = clazzref.get('{' + ns['xmi'] + '}idref')
            clazz = database.get_class(idref)

            properties = clazzref.xpath('./properties')[0]
            if properties is not None:
                clazz.descr = properties.get('documentation')
            project = clazzref.xpath('./project')[0]
            copy_values(project, clazz)

            tags = clazzref.xpath('./tags/tag')
            for tag in tags:
                if hasattr(clazz, fixtag(tag.get('name'))):
                    setattr(clazz, fixtag(tag.get('name')), tag.get('value'))

            database.save(clazz)

        '''
        Third find all attributes, like
            <attribute xmi:idref="EAID_B2AE8AFC_C1D5_4d83_BFD3_EBF1663F3468" name="rijksmonument" scope="Public">
                <initial/>
                <documentation/>
                <model ea_localid="3233" ea_guid="{B2AE8AFC-C1D5-4d83-BFD3-EBF1663F3468}"/>
                <properties type="1" derived="0" precision="0" collection="false" length="0" static="0" duplicates="0" changeability="changeable"/>
                <coords ordered="0" scale="0"/>
                <containment containment="Not Specified" position="0"/>
                <stereotype stereotype="enum"/>
                <bounds lower="1" upper="1"/>
                <options/>
                <style/>
                <styleex value="IsLiteral=1;volatile=0;"/>
                <tags/>
                <xrefs/>
            </attribute>
        '''
        attrrefs = extension.xpath(".//attribute[@xmi:idref]", namespaces=ns)  # type: ignore
        for attrref in attrrefs:
            idref = attrref.get('{' + ns['xmi'] + '}idref')
            attr = database.get_attribute(idref)
            if attr is not None:
                properties = attrref.xpath('./properties')[0]
                copy_values(properties, attr)
                documentation = attrref.xpath('./properties')[0]
                if documentation is not None:
                    attr.descr = documentation.get('documentation')
                stereotype = attrref.xpath('./stereotype')[0]
                copy_values(stereotype, attr)

                database.save(attr)
