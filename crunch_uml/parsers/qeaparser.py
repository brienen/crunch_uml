import logging

import sqlalchemy as sa

import crunch_uml.db as db
import crunch_uml.schema as sch
from crunch_uml import ea_geometry as geo
from crunch_uml.parsers.parser import Parser, ParserRegistry, fixtag

logger = logging.getLogger()

# EA GUID format in QEA: {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}
# In XMI these become: EAID_XXXXXXXX_XXXX_XXXX_XXXX_XXXXXXXXXXXX (for objects)
#                  and EAPK_XXXXXXXX_XXXX_XXXX_XXXX_XXXXXXXXXXXX (for packages)


def guid_to_eaid(guid):
    """Convert EA GUID {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX} to EAID_ format.

    Returns None when guid is None/empty so callers can supply a fallback id.
    """
    if not guid:
        return None
    clean = guid.strip("{}").replace("-", "_")
    return f"EAID_{clean}"


def guid_to_eapk(guid):
    """Convert EA GUID {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX} to EAPK_ format.

    Returns None when guid is None/empty so callers can supply a fallback id.
    """
    if not guid:
        return None
    clean = guid.strip("{}").replace("-", "_")
    return f"EAPK_{clean}"


def synth_attr_eaid(attr_id) -> str:
    """Synthetic id for a t_attribute row that has no ea_guid set in the QEA.

    EA itself produces a generated identifier for these rows when exporting to
    XMI; we mirror that approach with a stable, collision-free format.
    """
    return f"EAID_attr_{attr_id}"


@ParserRegistry.register(
    "qea",
    descr="Parser for Enterprise Architect repository files (.qea/.qeax). These are SQLite databases.",
)
class QEAParser(Parser):
    def parse(self, args, schema: sch.Schema):
        inputfile = args.inputfile
        logger.info(f"Opening QEA repository: {inputfile}")

        engine = sa.create_engine(f"sqlite:///{inputfile}")

        with engine.connect() as conn:
            self._phase1_packages(conn, schema)
            self._phase2_objects(conn, schema)
            self._phase3_attributes(conn, schema)
            self._phase4_connectors(conn, schema)
            self._phase5_tagged_values(conn, schema)
            self._phase6_diagrams(conn, schema)

        logger.info(
            f"QEA import done: {schema.count_package()} packages, "
            f"{schema.count_class()} classes, "
            f"{schema.count_attribute()} attributes, "
            f"{schema.count_enumeratie()} enumerations, "
            f"{schema.count_enumeratieliteral()} enumeration literals, "
            f"{schema.count_association()} associations, "
            f"{schema.count_generalizations()} generalizations, "
            f"{schema.count_diagrams()} diagrams."
        )

    def _phase1_packages(self, conn, schema: sch.Schema):
        """Parse t_package into Package objects."""
        logger.info("Phase 1: parsing packages")
        rows = conn.execute(
            sa.text(
                "SELECT Package_ID, Name, Parent_ID, ea_guid, Notes, Version, "
                "CreatedDate, ModifiedDate FROM t_package ORDER BY Package_ID"
            )
        ).fetchall()

        # Build lookup: Package_ID -> ea_guid (EAPK_ format id)
        self._pkg_id_map = {}  # Package_ID (int) -> EAPK_ string
        for row in rows:
            pkg_id = row[0]
            ea_guid = row[3]
            eapk_id = guid_to_eapk(ea_guid)
            self._pkg_id_map[pkg_id] = eapk_id

        for row in rows:
            pkg_id, name, parent_id, ea_guid, notes, version, created, modified = row
            eapk_id = guid_to_eapk(ea_guid)
            parent_eapk = self._pkg_id_map.get(parent_id) if parent_id else None

            # Skip the root model package (parent_id = 0 or None)
            package = db.Package(
                id=eapk_id,
                name=name,
                parent_package_id=parent_eapk,
                definitie=notes,
                version=version,
                created=created,
                modified=modified,
            )
            logger.debug(f"Package {name} met id {eapk_id}")
            schema.save(package)

        logger.info(f"Phase 1 done: {schema.count_package()} packages")

    def _phase2_objects(self, conn, schema: sch.Schema):
        """Parse t_object into Class and Enumeratie objects."""
        logger.info("Phase 2: parsing classes and enumerations")
        rows = conn.execute(
            sa.text(
                "SELECT Object_ID, Object_Type, Name, Package_ID, ea_guid, "
                "Note, Stereotype, Author, Version, CreatedDate, ModifiedDate, "
                "Status, Alias "
                "FROM t_object "
                "WHERE Object_Type IN ('Class', 'DataType', 'Enumeration') "
                "ORDER BY Object_ID"
            )
        ).fetchall()

        # Build lookup: Object_ID (int) -> EAID_ string
        self._obj_id_map = {}  # Object_ID -> EAID_ string
        for row in rows:
            obj_id = row[0]
            ea_guid = row[4]
            self._obj_id_map[obj_id] = guid_to_eaid(ea_guid)

        for row in rows:
            (
                obj_id,
                obj_type,
                name,
                package_id,
                ea_guid,
                note,
                stereotype,
                author,
                version,
                created,
                modified,
                status,
                alias,
            ) = row

            eaid = guid_to_eaid(ea_guid)
            pkg_eapk = self._pkg_id_map.get(package_id)

            if obj_type == "Enumeration":
                enum = db.Enumeratie(
                    id=eaid,
                    name=name,
                    package_id=pkg_eapk,
                    definitie=note,
                    stereotype=stereotype,
                    author=author,
                    version=version,
                    created=created,
                    modified=modified,
                    status=status,
                    alias=alias,
                )
                logger.debug(f"Enumeration {name} met id {eaid}")
                schema.save(enum)
            else:
                clazz = db.Class(
                    id=eaid,
                    name=name,
                    package_id=pkg_eapk,
                    is_datatype=(obj_type == "DataType"),
                    definitie=note,
                    stereotype=stereotype,
                    author=author,
                    version=version,
                    created=created,
                    modified=modified,
                    status=status,
                    alias=alias,
                )
                logger.debug(f"Class {name} ({obj_type}) met id {eaid}")
                schema.save(clazz)

        logger.info(f"Phase 2 done: {schema.count_class()} classes, " f"{schema.count_enumeratie()} enumerations")

    def _phase3_attributes(self, conn, schema: sch.Schema):
        """Parse t_attribute into Attribute and EnumerationLiteral objects."""
        logger.info("Phase 3: parsing attributes and enumeration literals")

        rows = conn.execute(
            sa.text(
                "SELECT a.ID, a.Object_ID, a.Name, a.Type, a.Classifier, "
                "a.LowerBound, a.UpperBound, a.Notes, a.ea_guid, a.Scope, "
                "a.Stereotype, o.Object_Type "
                "FROM t_attribute a "
                "JOIN t_object o ON a.Object_ID = o.Object_ID "
                "WHERE o.Object_Type IN ('Class', 'DataType', 'Enumeration') "
                "ORDER BY a.Object_ID, a.Pos"
            )
        ).fetchall()

        # Attribute numeric ID -> eaid (used by phase 5 to apply tagged values)
        self._attr_id_map = {}
        missing_guid_count = 0

        for row in rows:
            (
                attr_id,
                obj_id,
                name,
                attr_type,
                classifier,
                lower,
                upper,
                notes,
                ea_guid,
                scope,
                stereotype,
                parent_type,
            ) = row

            eaid = guid_to_eaid(ea_guid)
            if eaid is None:
                # EA leaves ea_guid NULL for some attributes/enum literals; mint a
                # stable synthetic id so the row can still be imported and later
                # matched by tagged-value processing.
                eaid = synth_attr_eaid(attr_id)
                missing_guid_count += 1
            self._attr_id_map[attr_id] = eaid
            parent_eaid = self._obj_id_map.get(obj_id)

            if parent_type == "Enumeration":
                literal = db.EnumerationLiteral(
                    id=eaid,
                    name=name,
                    enumeratie_id=parent_eaid,
                    definitie=notes,
                    stereotype=stereotype,
                )
                logger.debug(f"EnumerationLiteral {name} met id {eaid}")
                schema.save(literal)
            else:
                # Determine type_class_id or enumeration_id from classifier
                type_class_id = None
                enumeration_id = None
                if classifier and classifier != 0:
                    classifier_eaid = self._obj_id_map.get(int(classifier))
                    if classifier_eaid is not None:
                        # Determine if classifier is Class or Enumeration
                        classifier_obj = schema.get_class(classifier_eaid)
                        if classifier_obj is not None:
                            type_class_id = classifier_eaid
                        else:
                            enum_obj = schema.get_enumeration(classifier_eaid)
                            if enum_obj is not None:
                                enumeration_id = classifier_eaid

                attribute = db.Attribute(
                    id=eaid,
                    name=name,
                    clazz_id=parent_eaid,
                    primitive=attr_type if not type_class_id and not enumeration_id else None,
                    type_class_id=type_class_id,
                    enumeration_id=enumeration_id,
                    definitie=notes,
                    stereotype=stereotype,
                )
                logger.debug(f"Attribute {name} met id {eaid}")
                schema.save(attribute)

        if missing_guid_count:
            logger.info(
                f"Phase 3: {missing_guid_count} attributes/literals had NULL ea_guid; " "synthetic ids assigned."
            )
        logger.info(
            f"Phase 3 done: {schema.count_attribute()} attributes, "
            f"{schema.count_enumeratieliteral()} enumeration literals"
        )

    def _phase4_connectors(self, conn, schema: sch.Schema):
        """Parse t_connector into Association and Generalization objects."""
        logger.info("Phase 4: parsing connectors")

        rows = conn.execute(
            sa.text(
                "SELECT Connector_ID, Name, Connector_Type, SourceCard, DestCard, "
                "Start_Object_ID, End_Object_ID, ea_guid, Notes, Stereotype "
                "FROM t_connector "
                "WHERE Connector_Type IN ('Association', 'Generalization', 'Realisation') "
                "ORDER BY Connector_ID"
            )
        ).fetchall()

        # Imported connector ids, used by phase 6 to route diagram links to
        # the right junction table (and skip links to connectors that were
        # not imported, such as aggregations or connectors to unknown objects).
        self._assoc_ids = set()
        self._gen_ids = set()

        for row in rows:
            (
                conn_id,
                name,
                conn_type,
                src_card,
                dst_card,
                start_obj_id,
                end_obj_id,
                ea_guid,
                notes,
                stereotype,
            ) = row

            eaid = guid_to_eaid(ea_guid)
            src_eaid = self._obj_id_map.get(start_obj_id)
            dst_eaid = self._obj_id_map.get(end_obj_id)

            # Skip connectors to unknown objects
            if src_eaid is None or dst_eaid is None:
                logger.debug(
                    f"Connector {conn_id} ({name}) verwijst naar onbekende objecten: "
                    f"src={start_obj_id}, dst={end_obj_id} - overgeslagen"
                )
                continue

            if conn_type == "Generalization":
                gen = db.Generalization(
                    id=eaid,
                    name=name or "",
                    superclass_id=dst_eaid,
                    subclass_id=src_eaid,
                    definitie=notes,
                    stereotype=stereotype,
                )
                logger.debug(f"Generalization {name} met id {eaid}")
                schema.save(gen)
                self._gen_ids.add(eaid)
            else:
                # Association or Realisation
                src_mult_start, src_mult_end = self._parse_cardinality(src_card)
                dst_mult_start, dst_mult_end = self._parse_cardinality(dst_card)

                assoc = db.Association(
                    id=eaid,
                    name=name or "",
                    src_class_id=src_eaid,
                    dst_class_id=dst_eaid,
                    src_mult_start=src_mult_start,
                    src_mult_end=src_mult_end,
                    dst_mult_start=dst_mult_start,
                    dst_mult_end=dst_mult_end,
                    definitie=notes,
                    stereotype=stereotype,
                )
                logger.debug(f"Association {name} met id {eaid}")
                schema.save(assoc)
                self._assoc_ids.add(eaid)

        logger.info(
            f"Phase 4 done: {schema.count_association()} associations, "
            f"{schema.count_generalizations()} generalizations"
        )

    def _phase5_tagged_values(self, conn, schema: sch.Schema):
        """Apply tagged values from t_objectproperties, t_attributetag, t_connectortag.

        Performance note: previously this phase did ``schema.get_*(id)`` + a
        per-row ``schema.save(obj)`` (which flushes), turning every tagged
        value into a SQL round-trip. We now preload one dict per entity type,
        mutate attached objects in place (which marks them dirty), and let a
        single ``session.flush()`` at the end of the phase write everything in
        one batch. On GGM v2.5.1 (~6k tagged values) this brings phase 5 from
        ~53s down to a few seconds.
        """
        logger.info("Phase 5: applying tagged values")

        # Pre-load identity maps for the entities touched in this phase.
        classes_by_id = {c.id: c for c in schema.get_all_classes()}
        classes_by_id.update({c.id: c for c in schema.get_all_datatypes()})
        enums_by_id = {e.id: e for e in schema.get_all_enumerations()}
        attrs_by_id = {a.id: a for a in schema.get_all_attributes()}
        assocs_by_id = {a.id: a for a in schema.get_all_associations()}

        # Pre-resolve connector numeric ID -> ea_guid once (was a per-row
        # subquery before).
        connector_eaid_by_id = {
            row[0]: guid_to_eaid(row[1])
            for row in conn.execute(sa.text("SELECT Connector_ID, ea_guid FROM t_connector")).fetchall()
        }

        # Object tagged values (classes, datatypes, enumerations).
        rows = conn.execute(
            sa.text(
                "SELECT op.Object_ID, op.Property, op.Value "
                "FROM t_objectproperties op "
                "JOIN t_object o ON op.Object_ID = o.Object_ID "
                "WHERE o.Object_Type IN ('Class', 'DataType', 'Enumeration') "
                "ORDER BY op.Object_ID, op.PropertyID"
            )
        ).fetchall()

        for obj_id, prop, value in rows:
            eaid = self._obj_id_map.get(obj_id)
            if eaid is None:
                continue
            field = fixtag(prop)
            obj = classes_by_id.get(eaid) or enums_by_id.get(eaid)
            if obj is not None and hasattr(obj, field):
                setattr(obj, field, value)

        # Attribute tagged values.
        attr_rows = conn.execute(
            sa.text(
                "SELECT at.ElementID, at.Property, at.VALUE "
                "FROM t_attributetag at "
                "JOIN t_attribute a ON at.ElementID = a.ID "
                "JOIN t_object o ON a.Object_ID = o.Object_ID "
                "WHERE o.Object_Type IN ('Class', 'DataType') "
                "ORDER BY at.ElementID, at.PropertyID"
            )
        ).fetchall()

        for elem_id, prop, value in attr_rows:
            eaid = self._attr_id_map.get(elem_id)
            if eaid is None:
                continue
            field = fixtag(prop)
            attr = attrs_by_id.get(eaid)
            if attr is not None and hasattr(attr, field):
                setattr(attr, field, value)

        # Connector tagged values (associations / realisations).
        conn_rows = conn.execute(
            sa.text(
                "SELECT ct.ElementID, ct.Property, ct.VALUE "
                "FROM t_connectortag ct "
                "JOIN t_connector c ON ct.ElementID = c.Connector_ID "
                "WHERE c.Connector_Type IN ('Association', 'Realisation') "
                "ORDER BY ct.ElementID, ct.PropertyID"
            )
        ).fetchall()

        for elem_id, prop, value in conn_rows:
            eaid = connector_eaid_by_id.get(elem_id)
            if eaid is None:
                continue
            field = fixtag(prop)
            assoc = assocs_by_id.get(eaid)
            if assoc is not None and hasattr(assoc, field):
                setattr(assoc, field, value)

        # One batched write for all in-memory mutations of this phase.
        schema.database.session.flush()

        logger.info("Phase 5 done: tagged values applied")

    def _phase6_diagrams(self, conn, schema: sch.Schema):
        """Parse t_diagram, t_diagramobjects and t_diagramlinks into Diagram
        objects with membership and geometry.

        Geometry conversions follow :mod:`crunch_uml.ea_geometry`: RectTop and
        RectBottom are negative in the QEA database, the Path column uses ';'
        between x:y pairs with negative y, and Hidden/Path live in separate
        columns (unlike the XMI export, where they are folded into the style
        and geometry strings).
        """
        logger.info("Phase 6: parsing diagrams")

        rows = conn.execute(
            sa.text(
                "SELECT Diagram_ID, ea_guid, Name, Package_ID, Author, Version, "
                "CreatedDate, ModifiedDate, Notes FROM t_diagram ORDER BY Diagram_ID"
            )
        ).fetchall()

        diagrams_by_local_id = {}
        for row in rows:
            diagram_id, ea_guid, name, package_id, author, version, created, modified, notes = row
            eaid = guid_to_eaid(ea_guid)
            pkg_eapk = self._pkg_id_map.get(package_id)
            if eaid is None or pkg_eapk is None:
                logger.debug(f"Diagram {diagram_id} ({name}) has no ea_guid or unknown package: skipped")
                continue
            diagram = db.Diagram(
                id=eaid,
                name=name,
                package_id=pkg_eapk,
                author=author,
                version=version,
                created=created,
                modified=modified,
                definitie=notes,
            )
            logger.debug(f"Diagram {name} met id {eaid}")
            schema.add(diagram)
            diagrams_by_local_id[diagram_id] = diagram

        # Diagram objects (nodes): route to the class or enumeration junction
        # table based on the object type; other types (Notes, Packages, ...)
        # are not part of the model and are skipped.
        object_rows = conn.execute(
            sa.text(
                "SELECT d.Diagram_ID, o.Object_Type, o.ea_guid, d.RectLeft, d.RectTop, "
                "d.RectRight, d.RectBottom, d.Sequence, d.ObjectStyle "
                "FROM t_diagramobjects d "
                "JOIN t_object o ON o.Object_ID = d.Object_ID "
                "ORDER BY d.Diagram_ID, d.Sequence"
            )
        ).fetchall()

        seen_nodes = set()
        for row in object_rows:
            diagram_id, obj_type, ea_guid, rect_left, rect_top, rect_right, rect_bottom, sequence, style = row
            node_diagram = diagrams_by_local_id.get(diagram_id)
            element_id = guid_to_eaid(ea_guid)
            if node_diagram is None or element_id is None:
                continue
            if obj_type not in ("Class", "DataType", "Enumeration"):
                logger.debug(f"Diagram object of type {obj_type} on diagram {node_diagram.name}: skipped")
                continue
            if (diagram_id, element_id) in seen_nodes:
                # Same element twice on one diagram: composite PK cannot hold
                # both. Known limitation: the first instance wins.
                logger.warning(
                    f"Element {element_id} appears more than once on diagram {node_diagram.name}: keeping the"
                    " first occurrence only."
                )
                continue
            seen_nodes.add((diagram_id, element_id))

            node_geometry = geo.parse_qea_rect(rect_left, rect_top, rect_right, rect_bottom) or {}
            membership_kwargs = dict(
                diagram_id=node_diagram.id,
                schema_id=schema.schema_id,
                z_order=sequence,
                ea_style=style,
                **node_geometry,
            )
            if obj_type == "Enumeration":
                node_diagram.diagram_enumerations.append(
                    db.DiagramEnumeration(enumeration_id=element_id, **membership_kwargs)
                )
            else:
                node_diagram.diagram_classes.append(db.DiagramClass(class_id=element_id, **membership_kwargs))

        # Diagram links (edges): only connectors that were imported in phase 4
        # get membership; others (NoteLinks, aggregations, connectors with
        # unknown endpoints) are skipped.
        link_rows = conn.execute(
            sa.text(
                "SELECT l.DiagramID, c.ea_guid, l.Geometry, l.Style, l.Hidden, l.Path "
                "FROM t_diagramlinks l "
                "JOIN t_connector c ON c.Connector_ID = l.ConnectorID "
                "ORDER BY l.DiagramID, l.Instance_ID"
            )
        ).fetchall()

        seen_edges = set()
        for row in link_rows:
            diagram_id, ea_guid, geometry, style, hidden, path = row
            edge_diagram = diagrams_by_local_id.get(diagram_id)
            element_id = guid_to_eaid(ea_guid)
            if edge_diagram is None or element_id is None:
                continue
            edge_is_assoc = element_id in self._assoc_ids
            if not edge_is_assoc and element_id not in self._gen_ids:
                logger.debug(
                    f"Diagram link to connector {element_id} on diagram {edge_diagram.name}: not in model, skipped"
                )
                continue
            if (diagram_id, element_id) in seen_edges:
                logger.warning(
                    f"Connector {element_id} appears more than once on diagram {edge_diagram.name}: keeping the"
                    " first occurrence only."
                )
                continue
            seen_edges.add((diagram_id, element_id))

            waypoints = geo.parse_path(path, geo.QEA_PATH_SEPARATOR)
            membership_kwargs = dict(
                diagram_id=edge_diagram.id,
                schema_id=schema.schema_id,
                waypoints=geo.waypoints_to_json(waypoints),
                hidden=bool(hidden),
                ea_geometry=geometry,
                ea_style=style,
            )
            if edge_is_assoc:
                edge_diagram.diagram_associations.append(
                    db.DiagramAssociation(association_id=element_id, **membership_kwargs)
                )
            else:
                edge_diagram.diagram_generalizations.append(
                    db.DiagramGeneralization(generalization_id=element_id, **membership_kwargs)
                )

        schema.database.session.flush()
        logger.info(f"Phase 6 done: {schema.count_diagrams()} diagrams")

    @staticmethod
    def _parse_cardinality(card: str):
        """Parse '0..*' into (start, end) tuple, e.g. ('0', '*')."""
        if not card:
            return None, None
        card = card.strip()
        if ".." in card:
            parts = card.split("..")
            return parts[0], parts[1]
        return card, card
