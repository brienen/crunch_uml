import logging

import crunch_uml.db as db
import crunch_uml.schema as sch
from crunch_uml.parsers.parser import ParserRegistry, copy_values, fixtag
from crunch_uml.parsers.xmiparser import XMIParser

logger = logging.getLogger()


@ParserRegistry.register(
    "eaxmi", descr='XMI-Parser that parses EA (Enterprise Architect) specific extensions. Tested on XMI v2.1 spec '
)
class EAXMIParser(XMIParser):
    def phase3_process_extra(self, node, ns, schema: sch.Schema):
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
            package = schema.get_package(idref)
            project = packageref.xpath('./project')[0]
            copy_values(project, package)

            tags = packageref.xpath('./tags/tag')
            for tag in tags:
                if hasattr(package, fixtag(tag.get('name'))):
                    setattr(package, fixtag(tag.get('name')), tag.get('value'))

            schema.save(package)

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
            clazz = schema.get_class(idref)

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

                schema.save(clazz)

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
            attr = schema.get_attribute(idref)
            if attr is not None:
                properties = attrref.xpath('./properties')
                copy_values(properties, attr)
                documentation = attrref.xpath("./documentation")
                attr.definitie = documentation[0].get('value') if documentation is not None else None
                stereotype = attrref.xpath('./stereotype')
                copy_values(stereotype, attr)

                schema.save(attr)  # can also reference to enumeration literals
            else:
                literal = schema.get_enumeration_literal(idref)
                if literal is not None:
                    properties = attrref.xpath('./properties')
                    copy_values(properties, literal)
                    documentation = attrref.xpath("./documentation")
                    literal.definitie = documentation[0].get('value') if documentation is not None else None
                    stereotype = attrref.xpath('./stereotype')
                    copy_values(stereotype, literal)

                    schema.save(literal)

        connectorrefs = extension.xpath(".//connector[@xmi:idref and properties/@ea_type='Association']", namespaces=ns)  # type: ignore
        for connectorref in connectorrefs:
            idref = connectorref.get('{' + ns['xmi'] + '}idref')
            association = schema.get_association(idref)
            if association is not None:
                association.src_role = connectorref.xpath('./source/role', namespaces=ns)[0].get('name')
                association.dst_role = connectorref.xpath('./target/role', namespaces=ns)[0].get('name')

                documentation = connectorref.xpath('./documentation')
                if len(documentation) == 1:
                    association.definitie = documentation[0].get('value')

                schema.save(association)

        '''
        Voorbeeld van Diagram

                    <diagram xmi:id="EAID_7429E175_1CBE_4336_BF92_6C5029395E69">
                        <model package="EAPK_5B6708DC_CE09_4284_8DCE_DD1B744BB652" localID="27" owner="EAPK_5B6708DC_CE09_4284_8DCE_DD1B744BB652"/>
                        <properties name="Diagram Monumenten" type="Logical"/>
                        <project author="Arjen Brienen" version="1.0" created="2019-07-03 00:00:00" modified="2019-10-16 16:24:23"/>
                        <style1 value="ShowPrivate=1;ShowProtected=1;ShowPublic=1;HideRelationships=0;Locked=0;Border=1;HighlightForeign=1;PackageContents=1;SequenceNotes=0;ScalePrintImage=0;PPgs.cx=1;PPgs.cy=1;DocSize.cx=791;DocSize.cy=1134;ShowDetails=0;Orientation=P;Zoom=100;ShowTags=0;OpParams=1;VisibleAttributeDetail=0;ShowOpRetType=1;ShowIcons=1;CollabNums=0;HideProps=0;ShowReqs=0;ShowCons=0;PaperSize=9;HideParents=0;UseAlias=0;HideAtts=1;HideOps=1;HideStereo=0;HideElemStereo=0;ShowTests=0;ShowMaint=0;ConnectorNotation=UML 2.1;ExplicitNavigability=0;ShowShape=1;AllDockable=0;AdvancedElementProps=1;AdvancedFeatureProps=1;AdvancedConnectorProps=1;m_bElementClassifier=1;SPT=1;ShowNotes=0;SuppressBrackets=0;SuppConnectorLabels=0;PrintPageHeadFoot=0;ShowAsList=0;"/>
                        <style2 value="SaveTag=4E6278C2;ExcludeRTF=0;DocAll=0;HideQuals=0;AttPkg=1;ShowTests=0;ShowMaint=0;SuppressFOC=1;MatrixActive=0;SwimlanesActive=1;KanbanActive=0;MatrixLineWidth=1;MatrixLineClr=0;MatrixLocked=0;TConnectorNotation=UML 2.1;TExplicitNavigability=0;AdvancedElementProps=1;AdvancedFeatureProps=1;AdvancedConnectorProps=1;m_bElementClassifier=1;SPT=1;MDGDgm=;STBLDgm=;ShowNotes=0;VisibleAttributeDetail=0;ShowOpRetType=1;SuppressBrackets=0;SuppConnectorLabels=0;PrintPageHeadFoot=0;ShowAsList=0;SuppressedCompartments=;Theme=:119;"/>
                        <swimlanes value="locked=false;orientation=0;width=0;inbar=false;names=false;color=-1;bold=false;fcol=0;tcol=-1;ofCol=-1;ufCol=-1;hl=0;ufh=0;hh=0;cls=0;bw=0;hli=0;bro=0;SwimlaneFont=lfh:-21,lfw:0,lfi:0,lfu:0,lfs:0,lfface:Calibri,lfe:0,lfo:0,lfchar:1,lfop:0,lfcp:0,lfq:0,lfpf=0,lfWidth=0;"/>
                        <matrixitems value="locked=false;matrixactive=false;swimlanesactive=true;kanbanactive=false;width=1;clrLine=0;"/>
                        <extendedProperties/>
                        <xrefs/>
                        <elements>
                            <element geometry="Left=90;Top=30;Right=210;Bottom=90;" subject="EAID_78218601_F6B3_40b0_90AE_3513B4919064" seqno="1" style="DUID=740C889F;"/>
                            <element geometry="Left=648;Top=528;Right=768;Bottom=588;" subject="EAID_EBF38EE2_DAF0_4704_ADA6_705868BA7C05" seqno="2" style="DUID=7F76508F;"/>
                            <element geometry="Left=280;Top=30;Right=389;Bottom=110;" subject="EAID_32C02923_EE3A_4553_B94B_31E0C273A829" seqno="3" style="DUID=5EE10493;"/>
                            <element geometry="SX=0;SY=0;EX=0;EY=0;EDGE=4;$LLB=;LLT=;LMT=;LMB=;LRT=;LRB=;IRHS=;ILHS=;Path=;" subject="EAID_D07FFC12_AA8D_421a_A795_28E66B5E6C9C" style="Mode=3;EOID=0E0961A5;SOID=7F76508F;Color=-1;LWidth=0;Hidden=0;"/>
                            <element geometry="SX=0;SY=0;EX=0;EY=0;EDGE=3;$LLB=;LLT=;LMT=CX=28:CY=14:OX=0:OY=0:HDN=0:BLD=0:ITA=0:UND=0:CLR=-1:ALN=1:DIR=0:ROT=0;LMB=;LRT=;LRB=;IRHS=;ILHS=;Path=;" subject="EAID_59A9090E_CF7A_4e6f_91E1_592085B0DA94" style="Mode=3;EOID=0E0961A5;SOID=5EE10493;Color=-1;LWidth=0;Hidden=0;"/>
                            <element geometry="SCTR=1;SCME=1;SX=0;SY=0;EX=0;EY=0;EDGE=2;SCTR.LEFT=225;SCTR.TOP=-205;SCTR.RIGHT=256;SCTR.BOTTOM=-190;$LLB=;LLT=;LMT=;LMB=;LRT=;LRB=;IRHS=;ILHS=;Path=226:-205$256:-205$256:-190$226:-190$;" subject="EAID_EBEE5BED_D39A_4e50_ACD7_4924DF1DF463" style="Mode=3;EOID=0E0961A5;SOID=0E0961A5;Color=-1;LWidth=0;Hidden=1;"/>
                            <element geometry="EDGE=4;$LLB=;LLT=;LMT=CX=74:CY=14:OX=0:OY=0:HDN=0:BLD=0:ITA=0:UND=0:CLR=-1:ALN=1:DIR=0:ROT=0;LMB=CX=63:CY=14:OX=0:OY=0:HDN=0:BLD=0:ITA=0:UND=0:CLR=-1:ALN=1:DIR=0:ROT=0;LRT=;LRB=;IRHS=;ILHS=;Path=;" subject="EAID_CBFBC098_828D_42e9_8450_3A17680001B6" style="Mode=3;EOID=6C964D59;SOID=06807BCA;Color=-1;LWidth=0;Hidden=0;"/>
                            <element geometry="EDGE=1;$LLB=CX=17:CY=14:OX=0:OY=0:HDN=0:BLD=0:ITA=0:UND=0:CLR=-1:ALN=1:DIR=0:ROT=0;LLT=;LMT=CX=30:CY=14:OX=0:OY=0:HDN=0:BLD=0:ITA=0:UND=0:CLR=-1:ALN=1:DIR=0:ROT=0;LMB=CX=58:CY=14:OX=0:OY=0:HDN=0:BLD=0:ITA=0:UND=0:CLR=-1:ALN=1:DIR=0:ROT=0;LRT=;LRB=CX=6:CY=14:OX=0:OY=0:HDN=0:BLD=0:ITA=0:UND=0:CLR=-1:ALN=1:DIR=0:ROT=0;IRHS=;ILHS=;Path=;" subject="EAID_85187FF7_4357_4128_8E54_8EE077AD6C43" style="Mode=3;EOID=973BE7D4;SOID=FC1F7D8E;Color=-1;LWidth=0;Hidden=0;"/>
                            <element geometry="SCTR=1;SCME=1;SX=0;SY=0;EX=0;EY=0;EDGE=2;SCTR.LEFT=225;SCTR.TOP=-384;SCTR.RIGHT=256;SCTR.BOTTOM=-369;$LLB=;LLT=;LMT=;LMB=;LRT=;LRB=;IRHS=;ILHS=;Path=226:-384$256:-384$256:-369$226:-369$;" subject="EAID_9A56AD9F_136A_485a_93B1_7137FCC39416" style="Mode=3;EOID=6C964D59;SOID=6C964D59;Color=-1;LWidth=0;Hidden=1;"/>
                        </elements>
                    </diagram>
        '''

        diagramrefs = extension.xpath(".//diagram[@xmi:id]", namespaces=ns)  # type: ignore
        for diagramref in diagramrefs:
            idref = diagramref.get('{' + ns['xmi'] + '}id')
            package_id = diagramref.xpath('./model')[0].get('package')
            name = diagramref.xpath('./properties')[0].get('name')
            author = diagramref.xpath('./project')[0].get('author')
            version = diagramref.xpath('./project')[0].get('version')
            created = diagramref.xpath('./project')[0].get('created')
            modified = diagramref.xpath('./project')[0].get('modified')
            documentation = diagramref.xpath('./properties')[0].get('documentation')
            diagram = db.Diagram(
                id=idref,
                name=name,
                package_id=package_id,
                author=author,
                version=version,
                created=created,
                modified=modified,
                definitie=documentation,
            )
            schema.add(diagram)

            for element in diagramref.xpath('./elements/element'):
                element_id = element.get('subject')
                logger.debug(f'Found element with id {element.get("subject")} in diagram {name}')
                if schema.get_class(element_id) is not None:
                    diagram.classes.append(schema.get_class(element_id))
                    logger.debug(
                        f'Element {element.get("subject")} in diagram {name} is een class met naam'
                        f' {schema.get_class(element_id).name}'
                    )
                elif schema.get_association(element_id) is not None:
                    diagram.associations.append(schema.get_association(element_id))
                    logger.debug(f'Element {element.get("subject")} in diagram {name} is een association')
                elif schema.get_enumeration(element_id) is not None:
                    diagram.enumerations.append(schema.get_enumeration(element_id))
                    logger.debug(
                        f'Element {element.get("subject")} in diagram {name} is een enumeration met naam'
                        f' {schema.get_enumeration(element_id).name}'
                    )
                elif schema.get_generalization(element_id) is not None:
                    diagram.generalizations.append(schema.get_generalization(element_id))
                    logger.debug(f'Element {element.get("subject")} in diagram {name} is een generalisatie')
                else:
                    logger.info(
                        f'Element {element.get("subject")} in diagram {name} is niet gevonden in de database. Kan een'
                        ' niet geimplemneteerde type zijn zoals: Note of Constraint, of kan een relatie zij naar een'
                        ' element buiten het model.'
                    )

            logger.debug(f'Diagram {diagram.name} met id {diagram.id} ingelezen met inhoud: {diagram}')
            schema.save(diagram)
