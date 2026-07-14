"""Renderer that writes the model as XMI 2.1 with the Enterprise Architect
extension section — the mirror image of what the ``eaxmi`` parser reads.

The strict part contains the ``uml:Model`` tree (packages, classes with
attributes, enumerations with literals, associations with ends and
cardinalities, generalizations); the extension part carries the EA-specific
data (documentation, project metadata, tagged values, connector roles) and
the diagrams including their geometry. Geometry is converted back from the
canonical database form via :mod:`crunch_uml.ea_geometry` — the exact
inverse of the phase-2 parser conversions (including the y-sign flip for
edge waypoints).

Deviations from the XMI spec in favour of EA compatibility are documented in
``crunch_uml/renderers/EA_QUIRKS.md``.
"""

import logging
import re

from lxml import etree

import crunch_uml.schema as sch
from crunch_uml import const
from crunch_uml import ea_geometry as geo
from crunch_uml.renderers.renderer import Renderer, RendererRegistry

logger = logging.getLogger()

NS_XMI = "http://schema.omg.org/spec/XMI/2.1"
NS_UML = "http://schema.omg.org/spec/UML/2.1"
NSMAP = {"xmi": NS_XMI, "uml": NS_UML}

XMI = "{%s}" % NS_XMI
UML = "{%s}" % NS_UML

# Columns that are represented structurally or by dedicated XML attributes;
# everything else that holds a string value is written as a tagged value so
# the eaxmi parser puts it back on the same column (fixtag is the identity
# for our snake_case column names).
_NON_TAG_COLUMNS = {
    "id",
    "schema_id",
    "name",
    "definitie",
    "stereotype",
    "author",
    "version",
    "phase",
    "status",
    "created",
    "modified",
    "visibility",
    "alias",
    "kopie",
    "package_id",
    "parent_package_id",
    "clazz_id",
    "enumeratie_id",
    "enumeration_id",
    "type_class_id",
    "primitive",
    "is_datatype",
    "verplicht",
    "src_class_id",
    "dst_class_id",
    "src_mult_start",
    "src_mult_end",
    "dst_mult_start",
    "dst_mult_end",
    "src_role",
    "dst_role",
    "superclass_id",
    "subclass_id",
}

# EA derives the xmi:id of association ends from the association id by
# replacing the first three hex characters with src/dst, e.g.
# EAID_333AC8C9_... -> EAID_src3AC8C9_... / EAID_dst3AC8C9_...
_ASSOCIATION_END_RE = re.compile(r"^EAID_(src|dst)")


def _association_end_id(association_id, end):
    if association_id and association_id.startswith("EAID_") and len(association_id) > 8:
        return f"EAID_{end}{association_id[8:]}"
    return f"EAID_{end}_{association_id}"


def is_association_end_attribute(attribute_id):
    """Attributes with an EAID_src/EAID_dst id are artifacts of navigable
    association ends in EA exports; the renderer represents those ends as
    ownedEnd elements on the association instead (see EA_QUIRKS.md)."""
    return bool(attribute_id and _ASSOCIATION_END_RE.match(attribute_id))


# Characters that are not allowed in XML 1.0 documents at all; lxml raises
# on them. They can enter the database through json/xlsx imports.
_INVALID_XML_CHARS_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _xml_safe(value):
    cleaned = _INVALID_XML_CHARS_RE.sub("", value)
    if cleaned != value:
        logger.warning("Removed XML-incompatible control characters from a value during XMI rendering.")
    return cleaned


def _set_attrs(element, **attrs):
    for key, value in attrs.items():
        if value is not None:
            element.set(key, _xml_safe(str(value)))


def _add_tags(parent, obj, include=()):
    """Write the remaining string-valued columns of ``obj`` as tagged
    values. The eaxmi parser maps a tag back onto the column with the same
    (fixtag-normalized) name. Columns in ``include`` are written even when
    they are normally represented elsewhere (e.g. connector stereotypes,
    which have no dedicated place in the EA connector extension)."""
    tags = etree.SubElement(parent, "tags")
    for column, value in sorted(obj.to_dict().items()):
        if column in _NON_TAG_COLUMNS and column not in include:
            continue
        if not isinstance(value, str) or value == "":
            continue
        tag = etree.SubElement(tags, "tag")
        _set_attrs(tag, name=column, value=value, modelElement=obj.id)
    return tags


@RendererRegistry.register(
    "xmi",
    descr=(
        "Renders the complete schema as XMI 2.1 with the Enterprise Architect extension section,"
        " including diagrams with geometry. The output can be re-imported with the eaxmi parser"
        " and imported into Sparx Enterprise Architect."
    ),
)
class XMIRenderer(Renderer):
    def render(self, args, schema: sch.Schema):
        logger.info(f"Rendering XMI file {args.outputfile}")

        root = etree.Element(XMI + "XMI", nsmap=NSMAP)
        root.set(XMI + "version", "2.1")
        documentation = etree.SubElement(root, XMI + "Documentation")
        # EA only accepts XMI it recognizes as its own export (see EA_QUIRKS.md).
        _set_attrs(documentation, exporter="Enterprise Architect", exporterVersion="6.5")

        model = etree.SubElement(root, UML + "Model")
        model.set(XMI + "type", "uml:Model")
        _set_attrs(model, name="EA_Model", visibility="public")

        packages = schema.get_all_packages()
        package_ids = {package.id for package in packages}
        root_packages = sorted(
            (
                package
                for package in packages
                if package.parent_package_id is None or package.parent_package_id not in package_ids
            ),
            key=lambda p: p.id,
        )

        # Group associations by the package of their source class. EA nests
        # associations in that package; associations whose source class is
        # not rendered (orphan placeholders for elements outside the model)
        # fall back to the first root package so they are not lost — their
        # dangling type idrefs make the eaxmi parser recreate the orphan
        # placeholders with the same ids.
        self._assocs_by_package: dict = {}
        fallback_package_id = root_packages[0].id if root_packages else None
        for assoc in sorted(schema.get_all_associations(), key=lambda a: a.id):
            src = assoc.src_class
            if src is not None and src.name != const.ORPHAN_CLASS and src.package_id in package_ids:
                self._assocs_by_package.setdefault(src.package_id, []).append(assoc)
            elif fallback_package_id is not None:
                self._assocs_by_package.setdefault(fallback_package_id, []).append(assoc)
            else:
                logger.warning(f"Association {assoc.id} could not be placed in any package: not rendered.")

        # Classes and enumerations whose package is missing or dangling
        # (possible via json/xlsx imports; foreign keys are not enforced on
        # SQLite) would otherwise be lost: place them in the first root
        # package rather than dropping them.
        self._extra_classes: list = []
        self._extra_enums: list = []
        self._fallback_package_id = fallback_package_id
        for clazz in sorted(schema.get_all_classes() + schema.get_all_datatypes(), key=lambda c: c.id):
            if clazz.name != const.ORPHAN_CLASS and (clazz.package_id is None or clazz.package_id not in package_ids):
                logger.warning(
                    f"Class {clazz.name} ({clazz.id}) has no package in the schema:"
                    " placed in the first root package."
                )
                self._extra_classes.append(clazz)
        for enum in sorted(schema.get_all_enumerations(), key=lambda e: e.id):
            if enum.package_id is None or enum.package_id not in package_ids:
                logger.warning(
                    f"Enumeration {enum.name} ({enum.id}) has no package in the schema:"
                    " placed in the first root package."
                )
                self._extra_enums.append(enum)

        for package in root_packages:
            self._render_package_strict(model, package)

        extension = etree.SubElement(root, XMI + "Extension")
        _set_attrs(extension, extender="Enterprise Architect", extenderID="6.5")
        self._render_extension(extension, schema)

        tree = etree.ElementTree(root)
        tree.write(args.outputfile, pretty_print=True, xml_declaration=True, encoding="UTF-8")
        logger.info(f"Rendering XMI file {args.outputfile} success")

    # ------------------------------------------------------------------
    # Strict uml:Model part
    # ------------------------------------------------------------------

    def _render_package_strict(self, parent, package):
        package_el = etree.SubElement(parent, "packagedElement")
        package_el.set(XMI + "type", "uml:Package")
        package_el.set(XMI + "id", package.id)
        _set_attrs(package_el, name=package.name, visibility="public")

        classes = sorted(package.classes, key=lambda c: c.id)
        enums = sorted(package.enumerations, key=lambda e: e.id)
        if package.id == self._fallback_package_id:
            classes += self._extra_classes
            enums += self._extra_enums

        for clazz in classes:
            if clazz.name == const.ORPHAN_CLASS:
                # Orphan placeholders are not part of the model; associations
                # that reference them keep their (dangling) type idref so the
                # eaxmi parser recreates the placeholder with the same id.
                continue
            self._render_class_strict(package_el, clazz)

        for enum in enums:
            self._render_enumeration_strict(package_el, enum)

        for assoc in self._assocs_by_package.get(package.id, []):
            self._render_association_strict(package_el, assoc)

        for subpackage in sorted(package.subpackages, key=lambda p: p.id):
            self._render_package_strict(package_el, subpackage)

    def _render_class_strict(self, parent, clazz):
        class_el = etree.SubElement(parent, "packagedElement")
        class_el.set(XMI + "type", "uml:DataType" if clazz.is_datatype else "uml:Class")
        class_el.set(XMI + "id", clazz.id)
        _set_attrs(class_el, name=clazz.name, visibility="public")

        for attribute in sorted(clazz.attributes, key=lambda a: a.id):
            if is_association_end_attribute(attribute.id):
                continue
            attr_el = etree.SubElement(class_el, "ownedAttribute")
            attr_el.set(XMI + "type", "uml:Property")
            attr_el.set(XMI + "id", attribute.id)
            _set_attrs(attr_el, name=attribute.name, visibility="public")
            type_ref = None
            if attribute.type_class_id is not None:
                type_ref = attribute.type_class_id
            elif attribute.enumeration_id is not None:
                type_ref = attribute.enumeration_id
            elif attribute.primitive:
                # remove_EADatatype in the parser strips the EA prefix again.
                type_ref = f"EAJava_{attribute.primitive}"
            if type_ref is not None:
                type_el = etree.SubElement(attr_el, "type")
                type_el.set(XMI + "idref", type_ref)

        for gener in sorted(clazz.superclasses, key=lambda g: g.id):
            gener_el = etree.SubElement(class_el, "generalization")
            gener_el.set(XMI + "type", "uml:Generalization")
            gener_el.set(XMI + "id", gener.id)
            _set_attrs(gener_el, general=gener.superclass_id)

    def _render_enumeration_strict(self, parent, enum):
        enum_el = etree.SubElement(parent, "packagedElement")
        enum_el.set(XMI + "type", "uml:Enumeration")
        enum_el.set(XMI + "id", enum.id)
        _set_attrs(enum_el, name=enum.name, visibility="public")
        for literal in sorted(enum.literals, key=lambda lit: lit.id):
            literal_el = etree.SubElement(enum_el, "ownedLiteral")
            literal_el.set(XMI + "type", "uml:EnumerationLiteral")
            literal_el.set(XMI + "id", literal.id)
            _set_attrs(literal_el, name=literal.name)

    def _render_association_strict(self, parent, assoc):
        assoc_el = etree.SubElement(parent, "packagedElement")
        assoc_el.set(XMI + "type", "uml:Association")
        assoc_el.set(XMI + "id", assoc.id)
        _set_attrs(assoc_el, name=assoc.name, visibility="public")

        src_end_id = _association_end_id(assoc.id, "src")
        dst_end_id = _association_end_id(assoc.id, "dst")
        for end_id in (dst_end_id, src_end_id):
            member_el = etree.SubElement(assoc_el, "memberEnd")
            member_el.set(XMI + "idref", end_id)

        ends = (
            (src_end_id, assoc.src_class_id, assoc.src_mult_start, assoc.src_mult_end, assoc.src_role),
            (dst_end_id, assoc.dst_class_id, assoc.dst_mult_start, assoc.dst_mult_end, assoc.dst_role),
        )
        for end_id, class_id, mult_start, mult_end, role in ends:
            end_el = etree.SubElement(assoc_el, "ownedEnd")
            end_el.set(XMI + "type", "uml:Property")
            end_el.set(XMI + "id", end_id)
            _set_attrs(end_el, name=role, association=assoc.id)
            if class_id is not None:
                type_el = etree.SubElement(end_el, "type")
                type_el.set(XMI + "idref", class_id)
            if mult_start is not None and mult_start != "None":
                lower_el = etree.SubElement(end_el, "lowerValue")
                lower_el.set(XMI + "type", "uml:LiteralInteger")
                lower_el.set(XMI + "id", f"EAID_LI_lower_{end_id[5:]}")
                _set_attrs(lower_el, value=mult_start)
            if mult_end is not None and mult_end != "None":
                upper_el = etree.SubElement(end_el, "upperValue")
                upper_el.set(XMI + "type", "uml:LiteralUnlimitedNatural")
                upper_el.set(XMI + "id", f"EAID_LI_upper_{end_id[5:]}")
                _set_attrs(upper_el, value=mult_end)

    # ------------------------------------------------------------------
    # EA extension part
    # ------------------------------------------------------------------

    def _render_extension(self, extension, schema: sch.Schema):
        elements = etree.SubElement(extension, "elements")
        for package in sorted(schema.get_all_packages(), key=lambda p: p.id):
            self._render_element_extension(elements, package, "uml:Package")
        for clazz in sorted(schema.get_all_classes(), key=lambda c: c.id):
            if clazz.name != const.ORPHAN_CLASS:
                self._render_element_extension(elements, clazz, "uml:Class")
        for datatype in sorted(schema.get_all_datatypes(), key=lambda c: c.id):
            self._render_element_extension(elements, datatype, "uml:DataType")
        for enum in sorted(schema.get_all_enumerations(), key=lambda e: e.id):
            self._render_element_extension(elements, enum, "uml:Enumeration")

        connectors = etree.SubElement(extension, "connectors")
        for assoc in sorted(schema.get_all_associations(), key=lambda a: a.id):
            self._render_connector_extension(
                connectors,
                assoc,
                ea_type="Association",
                src_id=assoc.src_class_id,
                dst_id=assoc.dst_class_id,
                src_role=assoc.src_role,
                dst_role=assoc.dst_role,
            )
        for gener in sorted(schema.get_all_generalizations(), key=lambda g: g.id):
            # Generalization names/definitions have no place in the strict
            # part (EA does not put them there); like EA we carry the name
            # in the labels element and the rest as documentation/tags.
            self._render_connector_extension(
                connectors,
                gener,
                ea_type="Generalization",
                src_id=gener.subclass_id,
                dst_id=gener.superclass_id,
                name=gener.name or None,
            )

        diagrams = etree.SubElement(extension, "diagrams")
        for index, diagram in enumerate(sorted(schema.get_all_diagrams(), key=lambda d: d.id), start=1):
            self._render_diagram_extension(diagrams, diagram, index)

    def _render_element_extension(self, elements, obj, xmi_type):
        element = etree.SubElement(elements, "element")
        element.set(XMI + "idref", obj.id)
        element.set(XMI + "type", xmi_type)
        _set_attrs(element, name=obj.name, scope="public")

        model_el = etree.SubElement(element, "model")
        if xmi_type == "uml:Package":
            _set_attrs(model_el, package=obj.parent_package_id, ea_eleType="package")
        else:
            _set_attrs(model_el, package=obj.package_id, ea_eleType="element")

        properties = etree.SubElement(element, "properties")
        _set_attrs(
            properties,
            documentation=obj.definitie,
            sType=xmi_type.replace("uml:", ""),
            scope="public",
            stereotype=obj.stereotype,
            alias=obj.alias,
        )

        project = etree.SubElement(element, "project")
        _set_attrs(
            project,
            author=obj.author,
            version=obj.version,
            phase=obj.phase,
            status=obj.status,
            created=obj.created,
            modified=obj.modified,
        )

        _add_tags(element, obj)

        if xmi_type in ("uml:Class", "uml:DataType"):
            for attribute in sorted(obj.attributes, key=lambda a: a.id):
                if not is_association_end_attribute(attribute.id):
                    self._render_attribute_extension(element, attribute)
        elif xmi_type == "uml:Enumeration":
            for literal in sorted(obj.literals, key=lambda lit: lit.id):
                self._render_literal_extension(element, literal)

    def _render_attribute_extension(self, parent, attribute):
        attr_el = etree.SubElement(parent, "attribute")
        attr_el.set(XMI + "idref", attribute.id)
        _set_attrs(attr_el, name=attribute.name, scope="Public")
        documentation = etree.SubElement(attr_el, "documentation")
        _set_attrs(documentation, value=attribute.definitie)
        stereotype = etree.SubElement(attr_el, "stereotype")
        _set_attrs(stereotype, stereotype=attribute.stereotype)
        _add_tags(attr_el, attribute)

    def _render_literal_extension(self, parent, literal):
        literal_el = etree.SubElement(parent, "attribute")
        literal_el.set(XMI + "idref", literal.id)
        _set_attrs(literal_el, name=literal.name, scope="Public")
        documentation = etree.SubElement(literal_el, "documentation")
        _set_attrs(documentation, value=literal.definitie)
        stereotype = etree.SubElement(literal_el, "stereotype")
        _set_attrs(stereotype, stereotype=literal.stereotype)
        if literal.alias is not None:
            style = etree.SubElement(literal_el, "style")
            _set_attrs(style, value=literal.alias)
        _add_tags(literal_el, literal)

    def _render_connector_extension(
        self, connectors, relation, ea_type, src_id, dst_id, src_role=None, dst_role=None, name=None
    ):
        connector = etree.SubElement(connectors, "connector")
        connector.set(XMI + "idref", relation.id)

        source = etree.SubElement(connector, "source")
        source.set(XMI + "idref", src_id or "")
        source_role = etree.SubElement(source, "role")
        _set_attrs(source_role, name=src_role, visibility="Public")

        target = etree.SubElement(connector, "target")
        target.set(XMI + "idref", dst_id or "")
        target_role = etree.SubElement(target, "role")
        _set_attrs(target_role, name=dst_role, visibility="Public")

        properties = etree.SubElement(connector, "properties")
        _set_attrs(properties, ea_type=ea_type, direction="Source -> Destination")
        if name is not None:
            # EA carries the connector name in the middle-top label.
            labels = etree.SubElement(connector, "labels")
            _set_attrs(labels, mt=name)
        if relation.definitie is not None:
            documentation = etree.SubElement(connector, "documentation")
            _set_attrs(documentation, value=relation.definitie)
        # Connector stereotypes have no dedicated attribute the eaxmi parser
        # reads; carry them as a tagged value.
        _add_tags(connector, relation, include=("stereotype",))

    def _render_diagram_extension(self, diagrams, diagram, local_id):
        diagram_el = etree.SubElement(diagrams, "diagram")
        diagram_el.set(XMI + "id", diagram.id)

        model_el = etree.SubElement(diagram_el, "model")
        _set_attrs(model_el, package=diagram.package_id, localID=local_id, owner=diagram.package_id)
        properties = etree.SubElement(diagram_el, "properties")
        _set_attrs(properties, name=diagram.name, type="Logical", documentation=diagram.definitie)
        project = etree.SubElement(diagram_el, "project")
        _set_attrs(
            project,
            author=diagram.author,
            version=diagram.version,
            created=diagram.created,
            modified=diagram.modified,
        )

        elements = etree.SubElement(diagram_el, "elements")
        nodes = [(dc.class_id, dc) for dc in diagram.diagram_classes]
        nodes += [(de.enumeration_id, de) for de in diagram.diagram_enumerations]
        # EA orders diagram elements by seqno (z-order).
        nodes.sort(key=lambda item: (item[1].z_order if item[1].z_order is not None else 0, item[0]))
        for element_id, node in nodes:
            element = etree.SubElement(elements, "element")
            geometry = None
            if None not in (node.x, node.y, node.width, node.height):
                geometry = geo.format_xmi_node_geometry(node.x, node.y, node.width, node.height)
            _set_attrs(
                element,
                geometry=geometry,
                subject=element_id,
                seqno=node.z_order,
                style=node.ea_style,
            )

        edges = [(da.association_id, da) for da in diagram.diagram_associations]
        edges += [(dg.generalization_id, dg) for dg in diagram.diagram_generalizations]
        edges.sort(key=lambda item: item[0])
        for element_id, edge in edges:
            element = etree.SubElement(elements, "element")
            waypoints = geo.waypoints_from_json(edge.waypoints)
            _set_attrs(
                element,
                geometry=geo.compose_xmi_edge_geometry(edge.ea_geometry, waypoints),
                subject=element_id,
                style=geo.compose_xmi_edge_style(edge.ea_style, edge.hidden),
            )
