import logging
import re

import requests
from lxml import etree

import crunch_uml.schema as sch
from crunch_uml import const, db, util
from crunch_uml.exceptions import CrunchException
from crunch_uml.parsers.parser import Parser, ParserRegistry

logger = logging.getLogger()


def remove_EADatatype(input_string):
    pattern = r"^EA[\d\w]+_"
    return re.sub(pattern, '', input_string)


@ParserRegistry.register(
    "xmi",
    descr='XMI-Parser for strict XMI files. No extensions (like EA extensions) are parsed. Tested on XMI v2.1 spec ',
)
class XMIParser(Parser):
    # Recursieve functie om de parsetree te doorlopen
    def phase1_process_packages_classes(self, node, ns, schema: sch.Schema, parent_package_id=None):
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

                schema.save(package)
                for childnode in node:
                    self.phase1_process_packages_classes(childnode, ns, schema, package.id)
            else:
                logger.debug(f'Package with {name} does not have id value: discarded')

        elif tp == 'uml:Class':
            clazz = db.Class(id=node.get('{' + ns['xmi'] + '}id'), name=node.get('name'), package_id=parent_package_id)
            logger.debug(f'Class {clazz.name} met id {clazz.id} ingelezen met inhoud: {clazz}')
            schema.save(clazz)

            for childnode in node:
                sub_tp = childnode.get('{' + ns['xmi'] + '}type')
                if sub_tp == 'uml:Property':
                    attribute = db.Attribute(
                        id=childnode.get('{' + ns['xmi'] + '}id'), name=childnode.get('name'), clazz_id=clazz.id
                    )
                    datatypes = childnode.xpath('./type')
                    if len(datatypes) != 0:
                        datatype = datatypes[0].get('{' + ns['xmi'] + '}idref')
                        if datatype is not None and not datatype.startswith(
                            'EAID_'
                        ):  # Remove references to other classes
                            attribute.primitive = remove_EADatatype(datatype)
                    logger.debug(
                        f'Attribute {attribute.name} met id {attribute.id} ingelezen met inhoud: {vars(attribute)}'
                    )
                    schema.save(attribute)

        elif tp == 'uml:Enumeration':
            enum = db.Enumeratie(
                id=node.get('{' + ns['xmi'] + '}id'), name=node.get('name'), package_id=parent_package_id
            )
            logger.debug(f'Enumeratie {enum.name} met id {enum.id} ingelezen met inhoud: {enum}')
            schema.save(enum)

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
                    schema.save(enumliteral)

        else:
            for childnode in node:
                logger.debug(f'Parsing something with tag {node.tag}, no handling implemented yet values: {node}')
                self.phase1_process_packages_classes(childnode, ns, schema, parent_package_id)

    def phase2_process_connectors(self, node, ns, schema: sch.Schema):
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
                    if len(endpoints) == 0:
                        clsid = util.getEAGuid()
                        msg = (
                            f"Association '{association.name}' with {association.id} only has information on one edge:"
                            f" generating placeholder class with uudi {clsid}."
                        )
                        logger.debug(msg)

                        clazz = db.Class(id=clsid, name=const.ORPHAN_CLASS, definitie=msg)
                        schema.save(clazz)
                        if 'src' in id:
                            association.src_class_id = clsid  # type: ignore
                        else:
                            association.dst_class_id = clsid  # type: ignore

                    elif len(endpoints) > 0:
                        if len(endpoints) > 1:
                            logger.debug(
                                f"Association {association.name} with {association.id} has more than two endpoints."
                            )

                        endpoint = endpoints[0]
                        getval = lambda x, endpoint: (  # noqa
                            endpoint.xpath(f'./{x}')[0].get('value') if len(endpoint.xpath(f'./{x}')) else None  # noqa
                        )  # noqa
                        typenode = endpoint.xpath('./type')
                        if len(typenode) == 0:
                            clsid = util.getEAGuid()
                            msg = (
                                f"Association '{association.name}' with {association.id} only has information on one"
                                f" edge: generating placeholder class with uudi {clsid}."
                            )
                            logger.debug(msg)
                            cls = db.Class(id=clsid, name=const.ORPHAN_CLASS, definitie=msg)
                            schema.save(cls)
                            if 'src' in id:
                                association.src_class_id = clsid  # type: ignore
                            else:
                                association.dst_class_id = clsid  # type: ignore
                        else:
                            clsid = endpoint.xpath('./type')[0].get('{' + ns['xmi'] + '}idref')
                            cls = schema.get_class(clsid)
                            if cls is None:
                                clazz = db.Class(id=clsid, name=const.ORPHAN_CLASS)
                                schema.save(clazz)
                            if 'src' in id:
                                association.src_class_id = clsid  # type: ignore
                                association.src_mult_start = getval('lowerValue', endpoint)
                                association.src_mult_end = getval('upperValue', endpoint)
                            else:
                                association.dst_class_id = clsid  # type: ignore
                                association.dst_mult_start = getval('lowerValue', endpoint)
                                association.dst_mult_end = getval('upperValue', endpoint)
                    else:
                        err = f"Association {association.name} with {association.id} has more than two endpoints. panic"
                        logger.error(err)
                        raise CrunchException(err)

                schema.save(association)

            '''
            Process all generalisations like so
            <packagedElement xmi:type="uml:Class" xmi:id="EAID_69DD8935_F54B_42dd_BD6E_B9D43C179992" name="Class E" visibility="public">
                <generalization xmi:type="uml:Generalization" xmi:id="EAID_7C4B53BC_DCF3_47a5_8D44_E0F23E9FA511" general="EAID_5BD99AAE_7857_495b_BA1A_80E1AAF525CE" isSubstitutable="true"/>
            </packagedElement>
            '''
            generalisations_xmi = node.xpath(".//generalization[@xmi:type='uml:Generalization']", namespaces=ns)  # type: ignore
            for generalisation_xmi in generalisations_xmi:
                id = generalisation_xmi.get('{' + ns['xmi'] + '}id')
                superclass = generalisation_xmi.get('general')
                subclass = generalisation_xmi.getparent().get('{' + ns['xmi'] + '}id')
                generalization = db.Generalization(id=id, superclass_id=superclass, subclass_id=subclass)
                schema.save(generalization)

        except Exception as ex:
            logger.error(f"Error in phase 2 of parsing with message: {ex}")
            raise ex

        '''
        Next look for all properties that ar ebound to a asscociation. They look lik eso:
        <ownedAttribute xmi:type="uml:Property" xmi:id="EAID_dstC391C5_3370_4bd4_A64E_C08369C7E2A6" name="wijst naar B" visibility="public" association="EAID_8FC391C5_3370_4bd4_A64E_C08369C7E2A6" isStatic="false" isReadOnly="false" isDerived="false" isOrdered="false" isUnique="true" isDerivedUnion="false" aggregation="none">
            <type xmi:idref="EAID_48A02EC8_683B_414f_B8A7_7518B789C8F5"/>
            <lowerValue xmi:type="uml:LiteralInteger" xmi:id="EAID_LI000007__3370_4bd4_A64E_C08369C7E2A6" value="0"/>
            <upperValue xmi:type="uml:LiteralUnlimitedNatural" xmi:id="EAID_LI000008__3370_4bd4_A64E_C08369C7E2A6" value="-1"/>
        </ownedAttribute>

        '''
        properties = node.xpath(".//ownedAttribute[@xmi:type='uml:Property' and @association]", namespaces=ns)  # type: ignore
        for property in properties:
            id = property.get('{' + ns['xmi'] + '}id')
            attribute = schema.get_attribute(id)
            if not attribute:
                continue

            clsrefs = property.xpath('./type[@xmi:idref]', namespaces=ns)
            if len(clsrefs) == 1:
                clsid = clsrefs[0].get('{' + ns['xmi'] + '}idref')
                cls = schema.get_class(clsid)
                if cls is None:
                    next
                attribute.type_class_id = cls.id
            schema.save(attribute)

        # Last of all set enumerations
        enums = schema.get_all_enumerations()
        for enum in enums:
            enumverws = node.xpath(".//type[@xmi:idref='" + enum.id + "']", namespaces=ns)
            for enumverw in enumverws:
                property = enumverw.getparent()
                if property.tag == 'ownedAttribute' and property.get('{' + ns['xmi'] + '}type') == 'uml:Property':
                    id = property.get('{' + ns['xmi'] + '}id')
                    attribute = schema.get_attribute(id)
                    if attribute is not None:
                        attribute.enumeration_id = enum.id
                        schema.save(attribute)

    def phase3_process_extra(self, node, ns, schema: sch.Schema):
        '''
        third and last phase of parsing XMI-documents. Parsing extra propriatary data: addons to allready found data
        '''
        logger.info('Entering third phase parsing: extras')
        pass

    def parse(self, args, schema: sch.Schema):
        logger.debug('Parsing with XMIParser')

        if args.inputfile is not None:
            # Parseer het XML-bestand
            logger.info(f'Parsing file with name {args.inputfile}')
            tree = etree.parse(args.inputfile)
            root = tree.getroot()
        elif args.url is not None:
            # Haal de inhoud van de URL op
            logger.info(f'Parsing url: {args.url}')
            response = requests.get(args.url)
            response.raise_for_status()  # controleer of het verzoek succesvol was

            # Gebruik lxml.etree om de inhoud te parsen
            root = etree.fromstring(response.content)

        ns = root.nsmap
        if 'xmi' not in ns.keys():
            logger.warning(f'missing namespace "xmi" in file {args.inputfile}: trying "{const.NS_XMI}"')
            ns['xmi'] = const.NS_XMI
        if 'uml' not in ns.keys():
            logger.warning(f'missing namespace "uml" in file {args.inputfile}: trying "{const.NS_UML}"')
            ns['xmi'] = const.NS_UML

        if root is not None:
            self.checkSupport(root, ns)

            model = root.xpath('//uml:Model[@xmi:type="uml:Model"][1]', namespaces=ns)[0]  # type: ignore
            self.phase1_process_packages_classes(model, ns, schema)
            if not args.skip_xmi_relations:
                self.phase2_process_connectors(model, ns, schema)
            self.phase3_process_extra(root, ns, schema)
        else:
            logger.warning('No content was read from XMI-file')

    def checkSupport(self, root, ns):
        innerclasses = root.xpath("//nestedClassifier", namespaces=ns)
        if len(innerclasses) > 0:
            id = innerclasses[0].get('{' + ns['xmi'] + '}id')
            name = innerclasses[0].get('name')
            msg = f"Error innerclasses not supported, found innerclass with id {id} and name {name}."
            logger.error(msg)
            raise CrunchException(msg)
