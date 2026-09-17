import logging
import os
import re
from collections import defaultdict

import chardet
import requests

import crunch_uml.schema as sch
from crunch_uml import const, db, ea_ids, xmlsafe
from crunch_uml.exceptions import CrunchException
from crunch_uml.parsers.parser import Parser, ParserRegistry

logger = logging.getLogger()

_DECLARED_ENCODING_RE = re.compile(br'<\?xml[^>]*encoding=["\']([^"\']+)["\']')
_HEADER_ENCODING_RE = re.compile(r'(<\?xml[^>]*encoding=["\'])([^"\']+)(["\'])', flags=re.IGNORECASE)

# Elements that become rows; only these get a synthetic id when EA exported them
# with xmi:id="" (their lowerValue/upperValue children are not stored).
_ROW_ELEMENT_TAGS = ("packagedElement", "ownedAttribute", "ownedLiteral", "ownedEnd", "generalization")
# A quoted EA id whose GUID carried braces: "EAID_{X}" or "EAID_{{X}}" -> "EAID_X".
_BRACED_ID_RE = re.compile(rb'"(EA(?:ID|PK)_)\{+([^"{}<>]*)\}+"')


def extract_declared_encoding(xml_bytes):
    # The XML declaration is at the very start of the document: never scan
    # the whole file for it.
    match = _DECLARED_ENCODING_RE.search(xml_bytes[: xmlsafe.SNIFF_BYTES])
    if match:
        return match.group(1).decode("ascii")
    return None


def detect_encoding(raw):
    """Guess the encoding from at most the first 64 KiB.

    chardet over a complete multi-megabyte model costs tens of seconds of CPU
    and makes the parse cost depend on a header an uploader controls.
    """
    return chardet.detect(raw[: xmlsafe.SNIFF_BYTES])["encoding"]


def load_xmi(source):
    if source.startswith("http://") or source.startswith("https://"):
        response = requests.get(source)
        raw = response.content
    else:
        with open(source, "rb") as f:
            raw = f.read()

    declared_encoding = extract_declared_encoding(raw)
    # Only detect when the declaration names no encoding; the detected value
    # is also needed further down when the declared one fails.
    detected_encoding = None if declared_encoding else detect_encoding(raw)
    used_encoding = declared_encoding or detected_encoding or const.ENCODING

    try:
        text = raw.decode(used_encoding).lstrip('\ufeff')
    except Exception as e:
        if detected_encoding is None:
            # Uitzonderingspad: hier is de detectie de moeite waard, want ze
            # vertelt waarom de gedeclareerde encoding niet werkte.
            detected_encoding = detect_encoding(raw)
        raise RuntimeError(
            f"Probleem met XMI inlezen (declared: {declared_encoding}, detected: {detected_encoding}): {e}"
        )
    del raw
    xmlsafe.reject_doctype(text=text)
    # Corrigeer header: the text is re-encoded as UTF-8 below, so the
    # declaration must say so. Only the declaration itself, never content.
    header = _HEADER_ENCODING_RE.search(text, 0, xmlsafe.SNIFF_BYTES)
    if header:
        text = text[: header.start(2)] + "utf-8" + text[header.end(2) :]
    utf8_bytes = text.encode(const.ENCODING)
    del text
    utf8_bytes = normalize_braced_ids(utf8_bytes)
    return xmlsafe.parse_bytes(utf8_bytes, encoding=const.ENCODING)


def normalize_braced_ids(data):
    """Rewrite quoted ``"EAID_{X}"``/``"EAID_{{X}}"`` values to ``"EAID_X"`` in UTF-8 document bytes.

    EA exports an element whose GUID carries a doubled brace pair with a
    braced id, while the QEA parser (and EA's own id scheme) yield the
    brace-less form. Normalizing every occurrence - the id and all references
    to it - keeps both formats in step. Done on the bytes before parsing: a
    regular expression over a GGM-sized export takes ~0.04 s, an XPath scan of
    every attribute of the parsed tree ~0.6 s. The result is assembled from
    memoryview slices in one allocation, so no pile of intermediate copies
    raises the peak memory of the parse.
    """
    view = memoryview(data)
    pieces = []
    position = 0
    for match in _BRACED_ID_RE.finditer(data):
        pieces.append(view[position : match.start()])
        pieces.append(b'"' + match.group(1) + match.group(2) + b'"')
        position = match.end()
    if not pieces:
        return data
    pieces.append(view[position:])
    count = len(pieces) // 2
    normalized = b"".join(pieces)
    del pieces
    view.release()
    logger.info(f"Normalized {count} braced EA ids (EAID_{{...}}) to EAID_...")
    return normalized


def mint_missing_ids(model, ns, source_label):
    """Give every row element exported with ``xmi:id=""`` a deterministic synthetic id.

    The owner is the nearest ancestor with an id; see :mod:`crunch_uml.ea_ids`.
    Returns the number of minted ids.
    """
    xmi_id = "{" + ns["xmi"] + "}id"
    minter = ea_ids.SyntheticIdMinter(source_label)
    condition = " or ".join(f"self::{tag}" for tag in _ROW_ELEMENT_TAGS)
    for element in model.xpath(f".//*[@xmi:id=''][{condition}]", namespaces=ns):
        owner_id = None
        for ancestor in element.iterancestors():
            owner_id = ancestor.get(xmi_id)
            if owner_id:
                break
        element.set(xmi_id, minter.mint(owner_id, element.get("name"), kind=element.tag))
    return minter.count


def get_end_value(endpoint, tag):
    """Waarde van het eerste kindelement ``tag`` van een association-end.

    Eén XPath-evaluatie per aanroep: de vorige inline-variant evalueerde
    dezelfde expressie tweemaal (eenmaal om te tellen, eenmaal om te lezen).
    """
    nodes = endpoint.xpath(f"./{tag}")
    return nodes[0].get("value") if nodes else None


def remove_EADatatype(input_string):
    pattern = r"^EA[\d\w]+_"
    return re.sub(pattern, "", input_string)


def zetOpLeeg():
    return ""


@ParserRegistry.register(
    "xmi",
    descr="XMI-Parser for strict XMI files. No extensions (like EA extensions) are parsed. Tested on XMI v2.1 spec ",
)
class XMIParser(Parser):

    # Recursieve functie om de parsetree te doorlopen
    def phase1_process_packages_classes(self, node, ns, schema: sch.Schema, parent_package_id=None):
        """
        First phase of parsing XMI-documents. Parsing recursively:
        - Packages
        - Classes incl attributes
        - Enumeration incl values
        """
        tp = node.get("{" + ns["xmi"] + "}type")
        if tp == "uml:Package":
            id = node.get("{" + ns["xmi"] + "}id")
            name = node.get("name")
            if id:
                package = db.Package(id=id, name=name, parent_package_id=parent_package_id)
                logger.info(f"Package {package.name} ingelezen met id {package.id}")
                logger.debug(f"Package {package.name} met inhoud {vars(package)}")

                schema.save(package)
                for childnode in node:
                    self.phase1_process_packages_classes(childnode, ns, schema, package.id)
            else:
                logger.debug(f"Package with {name} does not have id value: discarded")

        elif tp in ["uml:Class", "uml:DataType"]:
            clazz = db.Class(
                id=node.get("{" + ns["xmi"] + "}id"),
                name=node.get("name"),
                package_id=parent_package_id,
                is_datatype=(tp == "uml:DataType"),
            )
            logger.debug(f"Class {clazz.name} met id {clazz.id} ingelezen met inhoud: {clazz}")
            schema.save(clazz)

            for childnode in node:
                sub_tp = childnode.get("{" + ns["xmi"] + "}type")
                if sub_tp == "uml:Property":
                    attribute = db.Attribute(
                        id=childnode.get("{" + ns["xmi"] + "}id"),
                        name=childnode.get("name"),
                        clazz_id=clazz.id,
                    )
                    datatypes = childnode.xpath("./type")
                    if len(datatypes) != 0:
                        datatype = datatypes[0].get("{" + ns["xmi"] + "}idref")
                        if datatype is None:
                            pass
                        elif datatype.startswith("EAID_"):
                            # Reference to a classifier (Class / Enumeration) in the model
                            # This is NOT a primitive EA datatype.
                            # attribute.type_class_id = datatype
                            attribute.primitive = zetOpLeeg()
                        else:
                            # EA primitive datatype (e.g. EAJava_int, EASomeProfile_String, etc.)
                            attribute.primitive = remove_EADatatype(datatype)
                    logger.debug(
                        f"Attribute {attribute.name} met id {attribute.id} ingelezen met inhoud: {vars(attribute)}"
                    )
                    schema.save(attribute)

        elif tp == "uml:Enumeration":
            enum = db.Enumeratie(
                id=node.get("{" + ns["xmi"] + "}id"),
                name=node.get("name"),
                package_id=parent_package_id,
            )
            logger.debug(f"Enumeratie {enum.name} met id {enum.id} ingelezen met inhoud: {enum}")
            schema.save(enum)

            for childnode in node:
                sub_tp = childnode.get("{" + ns["xmi"] + "}type")
                # EA exports an enumeration value that lacks IsLiteral=1 as an
                # ownedAttribute of type uml:Property instead of an
                # ownedLiteral; it is still a value of the enumeration (the
                # QEA holds both kinds as t_attribute rows of the enumeration).
                is_value_property = sub_tp == "uml:Property" and childnode.get("association") is None
                if sub_tp == "uml:EnumerationLiteral" or is_value_property:
                    enumliteral = db.EnumerationLiteral(
                        id=childnode.get("{" + ns["xmi"] + "}id"),
                        name=childnode.get("name"),
                        enumeratie_id=enum.id,
                    )
                    logger.debug(
                        f"EnumerationLiteral {enumliteral.name} met id {enumliteral.id} ingelezen met inhoud:"
                        f" {vars(enumliteral)}"
                    )
                    schema.save(enumliteral)

        else:
            for childnode in node:
                logger.debug(f"Parsing something with tag {node.tag}, no handling implemented yet values: {node}")
                self.phase1_process_packages_classes(childnode, ns, schema, parent_package_id)

    def phase2_process_connectors(self, node, ns, schema: sch.Schema):
        """
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
        """
        logger.info("Entering second phase parsing: associations and generalisations")
        try:
            ns_xmi_id = "{" + ns["xmi"] + "}id"
            # Build a single dict {xmi:id -> element} for the whole subtree so
            # the per-memberEnd endpoint lookup becomes an O(1) dict access
            # instead of an O(N) xpath descent on every iteration.
            xmi_id_index = {el.get(ns_xmi_id): el for el in node.iter() if el.get(ns_xmi_id) is not None}
            associations_xmi = node.xpath(".//packagedElement[@xmi:type='uml:Association']", namespaces=ns)  # type: ignore
            for association_xp in associations_xmi:
                logger.debug(
                    f"Parsing association {association_xp.get('name')} with id"
                    f" {association_xp.get('{' + ns['xmi'] + '}id')})"
                )
                association = db.Association(
                    id=association_xp.get("{" + ns["xmi"] + "}id"),
                    name=association_xp.get("name"),
                )
                memberends = association_xp.xpath("./memberEnd", namespaces=ns)
                for memberend in memberends:
                    id = memberend.get("{" + ns["xmi"] + "}idref")
                    ep = xmi_id_index.get(id)
                    endpoints = [ep] if ep is not None else []
                    if len(endpoints) == 0:
                        clsid = ea_ids.placeholder_class_id(association.id, id)
                        msg = (
                            f"Association '{association.name}' with {association.id} only has information on one edge:"
                            f" generating placeholder class with id {clsid}."
                        )
                        logger.debug(msg)

                        clazz = db.Class(id=clsid, name=const.ORPHAN_CLASS, definitie=msg)
                        schema.save(clazz)
                        if "src" in id:
                            association.src_class_id = clsid  # type: ignore
                        else:
                            association.dst_class_id = clsid  # type: ignore

                    elif len(endpoints) > 0:
                        if len(endpoints) > 1:
                            logger.debug(
                                f"Association {association.name} with {association.id} has more than two endpoints."
                            )

                        endpoint = endpoints[0]
                        typenode = endpoint.xpath("./type")
                        if len(typenode) == 0:
                            clsid = ea_ids.placeholder_class_id(association.id, id)
                            msg = (
                                f"Association '{association.name}' with {association.id} only has information on one"
                                f" edge: generating placeholder class with id {clsid}."
                            )
                            logger.debug(msg)
                            cls = db.Class(id=clsid, name=const.ORPHAN_CLASS, definitie=msg)
                            schema.save(cls)
                            if "src" in id:
                                association.src_class_id = clsid  # type: ignore
                            else:
                                association.dst_class_id = clsid  # type: ignore
                        else:
                            clsid = typenode[0].get("{" + ns["xmi"] + "}idref")
                            cls = schema.get_class(clsid)
                            if cls is None:
                                clazz = db.Class(id=clsid, name=const.ORPHAN_CLASS)
                                schema.save(clazz)
                            if "src" in id:
                                association.src_class_id = clsid  # type: ignore
                                association.src_mult_start = str(get_end_value(endpoint, "lowerValue"))  # type: ignore
                                association.src_mult_end = str(get_end_value(endpoint, "upperValue"))  # type: ignore
                            else:
                                association.dst_class_id = clsid  # type: ignore
                                association.dst_mult_start = str(get_end_value(endpoint, "lowerValue"))  # type: ignore
                                association.dst_mult_end = str(get_end_value(endpoint, "upperValue"))  # type: ignore
                    else:
                        err = f"Association {association.name} with {association.id} has more than two endpoints. panic"
                        logger.error(err)
                        raise CrunchException(err)

                schema.save(association)

            """
            Process all generalisations like so
            <packagedElement xmi:type="uml:Class" xmi:id="EAID_69DD8935_F54B_42dd_BD6E_B9D43C179992" name="Class E" visibility="public">
                <generalization xmi:type="uml:Generalization" xmi:id="EAID_7C4B53BC_DCF3_47a5_8D44_E0F23E9FA511" general="EAID_5BD99AAE_7857_495b_BA1A_80E1AAF525CE" isSubstitutable="true"/>
            </packagedElement>
            """
            generalisations_xmi = node.xpath(".//generalization[@xmi:type='uml:Generalization']", namespaces=ns)  # type: ignore
            for generalisation_xmi in generalisations_xmi:
                id = generalisation_xmi.get("{" + ns["xmi"] + "}id")
                superclass = generalisation_xmi.get("general")
                subclass = generalisation_xmi.getparent().get("{" + ns["xmi"] + "}id")
                generalization = db.Generalization(id=id, superclass_id=superclass, subclass_id=subclass)
                schema.save(generalization)

        except Exception as ex:
            logger.error(f"Error in phase 2 of parsing with message: {ex}")
            raise ex

        """
        Next look for all properties that ar ebound to a asscociation. They look lik eso:
        <ownedAttribute xmi:type="uml:Property" xmi:id="EAID_dstC391C5_3370_4bd4_A64E_C08369C7E2A6" name="wijst naar B" visibility="public" association="EAID_8FC391C5_3370_4bd4_A64E_C08369C7E2A6" isStatic="false" isReadOnly="false" isDerived="false" isOrdered="false" isUnique="true" isDerivedUnion="false" aggregation="none">
            <type xmi:idref="EAID_48A02EC8_683B_414f_B8A7_7518B789C8F5"/>
            <lowerValue xmi:type="uml:LiteralInteger" xmi:id="EAID_LI000007__3370_4bd4_A64E_C08369C7E2A6" value="0"/>
            <upperValue xmi:type="uml:LiteralUnlimitedNatural" xmi:id="EAID_LI000008__3370_4bd4_A64E_C08369C7E2A6" value="-1"/>
        </ownedAttribute>

        """
        properties = node.xpath(".//ownedAttribute[@xmi:type='uml:Property' and @association]", namespaces=ns)  # type: ignore
        for property in properties:
            id = property.get("{" + ns["xmi"] + "}id")
            attribute = schema.get_attribute(id)
            if not attribute:
                continue

            clsrefs = property.xpath("./type[@xmi:idref]", namespaces=ns)
            if len(clsrefs) == 1:
                clsid = clsrefs[0].get("{" + ns["xmi"] + "}idref")
                cls = schema.get_class(clsid)
                if cls is None:
                    continue
                attribute.type_class_id = cls.id
            schema.save(attribute)

        # Alle type-verwijzingen in één doorloop indexeren op idref. De drie
        # lussen hierna (enumeraties, klassen, datatypes) deden elk per element
        # een eigen XPath-descent over de volledige boom: op een groot model
        # ruim duizend scans van hetzelfde document. Nu is het één scan plus
        # een dict-lookup per element.
        ns_xmi_idref = "{" + ns["xmi"] + "}idref"
        type_refs_by_idref = defaultdict(list)
        for type_node in node.xpath(".//type[@xmi:idref]", namespaces=ns):  # type: ignore
            type_refs_by_idref[type_node.get(ns_xmi_idref)].append(type_node)

        # Last of all set enumerations
        enums = schema.get_all_enumerations()
        for enum in enums:
            enumverws = type_refs_by_idref.get(enum.id, ())
            for enumverw in enumverws:
                property = enumverw.getparent()
                if property.tag == "ownedAttribute" and property.get("{" + ns["xmi"] + "}type") == "uml:Property":
                    id = property.get("{" + ns["xmi"] + "}id")
                    attribute = schema.get_attribute(id)
                    if attribute is not None:
                        attribute.enumeration_id = enum.id
                        attribute.primitive = enum.name
                        schema.save(attribute)

        # Last of all set object references
        classes = schema.get_all_classes()
        for clazz in classes:
            classverws = type_refs_by_idref.get(clazz.id, ())
            for classverw in classverws:
                property = classverw.getparent()
                if property.tag == "ownedAttribute" and property.get("{" + ns["xmi"] + "}type") == "uml:Property":
                    id = property.get("{" + ns["xmi"] + "}id")
                    attribute = schema.get_attribute(id)
                    if attribute is not None:
                        attribute.type_class_id = clazz.id
                        attribute.primitive = clazz.name
                        schema.save(attribute)

        # Last of all set object references
        datatypes = schema.get_all_datatypes()
        for dt in datatypes:
            dtverws = type_refs_by_idref.get(dt.id, ())
            for dtverw in dtverws:
                property = dtverw.getparent()
                if property.tag == "ownedAttribute" and property.get("{" + ns["xmi"] + "}type") == "uml:Property":
                    id = property.get("{" + ns["xmi"] + "}id")
                    attribute = schema.get_attribute(id)
                    if attribute is not None:
                        attribute.type_class_id = dt.id
                        attribute.primitive = dt.name
                        schema.save(attribute)

    def phase3_process_extra(self, node, ns, schema: sch.Schema):
        """
        third and last phase of parsing XMI-documents. Parsing extra propriatary data: addons to allready found data
        """
        logger.info("Entering third phase parsing: extras")
        pass

    def parse(self, args, schema: sch.Schema):
        logger.debug("Parsing with XMIParser")

        if args.inputfile is not None:
            # Parseer het XML-bestand
            logger.info(f"Parsing file with name {args.inputfile}")
            source = args.inputfile
        elif args.url is not None:
            # Haal de inhoud van de URL op
            logger.info(f"Parsing url: {args.url}")
            source = args.url
        else:
            raise CrunchException("No input file or URL provided for parsing.")

        logger.info(f"Parsing from source {source}")
        root = load_xmi(source)

        ns = dict(root.nsmap)
        if "xmi" not in ns.keys():
            logger.warning(f'missing namespace "xmi" in file {args.inputfile}: trying "{const.NS_XMI}"')
            ns["xmi"] = const.NS_XMI
        if "uml" not in ns.keys():
            logger.warning(f'missing namespace "uml" in file {args.inputfile}: trying "{const.NS_UML}"')
            ns["xmi"] = const.NS_UML

        if root is not None:
            self.checkSupport(root, ns)

            model = root.xpath('//uml:Model[@xmi:type="uml:Model"][1]', namespaces=ns)[0]  # type: ignore
            source_label = f"XMI {os.path.basename(source)}"
            minted = mint_missing_ids(model, ns, source_label)
            if minted:
                logger.warning(f"{source_label}: {minted} elements without xmi:id got a synthetic id.")
            self.phase1_process_packages_classes(model, ns, schema)
            if not args.skip_xmi_relations:
                self.phase2_process_connectors(model, ns, schema)
            self.phase3_process_extra(root, ns, schema)
        else:
            logger.warning("No content was read from XMI-file")

    def checkSupport(self, root, ns):
        innerclasses = root.xpath("//nestedClassifier", namespaces=ns)
        if len(innerclasses) > 0:
            id = innerclasses[0].get("{" + ns["xmi"] + "}id")
            name = innerclasses[0].get("name")
            msg = f"Error innerclasses not supported, found innerclass with id {id} and name {name}."
            logger.error(msg)
            raise CrunchException(msg)
