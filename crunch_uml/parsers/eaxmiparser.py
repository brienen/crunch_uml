import logging

from crunch_uml import db
from crunch_uml.parsers.parser import ParserRegistry, copy_values, fixtag
from crunch_uml.parsers.xmiparser import XMIParser

logger = logging.getLogger()


@ParserRegistry.register(
    "eaxmi", descr='XMI-Parser that parses EA (Enterprise Architect) specific extensions. Tested on XMI v2.1 spec '
)
class EAXMIParser(XMIParser):
    def phase3_process_extra(self, node, ns, database: db.Database):
        '''
        third and last phase of parsing XMI-documents. Parsing extra propriatary data: addons to allready found data.
        Starts at <xmi:Extension extender="Enterprise Architect" extenderID="6.5">
        '''
        logger.info('Entering third phase parsing for EAParser: extras')
        extensions = node.xpath('//xmi:Extension', namespaces=ns)
        if len(extensions) < 1:
            logger.warning(
                "Trying to parse input as EA XMI, no 'Extensions' node was found. Appears to strict XMI file."
            )
            return
        extension = extensions[0]  # type: ignore

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

            if clazz is not None:
                properties = clazzref.xpath('./properties')[0]
                if properties is not None:
                    clazz.definitie = properties.get('documentation')
                project = clazzref.xpath('./project')
                copy_values(project, clazz)
                stereotype = clazzref.xpath('./stereotype')
                copy_values(stereotype, clazz)

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
                properties = attrref.xpath('./properties')
                copy_values(properties, attr)
                documentation = attrref.xpath('./properties')[0]
                if documentation is not None:
                    attr.definitie = documentation.get('documentation')
                stereotype = attrref.xpath('./stereotype')
                copy_values(stereotype, attr)

                database.save(attr)

        connectorrefs = extension.xpath(".//connector[@xmi:idref and properties/@ea_type='Association']", namespaces=ns)  # type: ignore
        for connectorref in connectorrefs:
            idref = connectorref.get('{' + ns['xmi'] + '}idref')
            # sourceref = connectorref.xpath('./source/@xmi:idref', namespaces=ns)[0]
            # targetref = connectorref.xpath('./target/@xmi:idref', namespaces=ns)[0]
            association = database.get_association(idref)
            if association is not None:
                # association.src_class = sourceref
                # association.dst_class = targetref

                documentation = connectorref.xpath('./documentation')
                if len(documentation) == 1:
                    association.definitie = documentation[0].get('value')

                database.save(association)
