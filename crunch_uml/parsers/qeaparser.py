import logging
import os
import sqlite3
from urllib.parse import quote

import sqlalchemy as sa

import crunch_uml.db as db
import crunch_uml.schema as sch
from crunch_uml import const
from crunch_uml import ea_geometry as geo
from crunch_uml import ea_ids
from crunch_uml.parsers.parser import Parser, ParserRegistry, fixtag

logger = logging.getLogger()

# EA GUID format in QEA: {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}
# In XMI these become: EAID_XXXXXXXX_XXXX_XXXX_XXXX_XXXXXXXXXXXX (for objects)
#                  and EAPK_XXXXXXXX_XXXX_XXXX_XXXX_XXXXXXXXXXXX (for packages)
# Some repositories carry a doubled brace pair ({{...}}); every variant maps
# onto the same id, see crunch_uml.ea_ids.

# Connector types imported as associations. An aggregation is an association
# with a diamond end; the XMI export writes it as a uml:Association as well.
ASSOCIATION_CONNECTOR_TYPES = ("Association", "Aggregation", "Realisation")
MODEL_OBJECT_TYPES = ("Class", "DataType", "Enumeration")


def _sql_list(values):
    return ", ".join(f"'{value}'" for value in values)


def guid_to_eaid(guid):
    """Convert EA GUID {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX} to EAID_ format.

    Returns None when guid is None/empty so callers can supply a fallback id.
    """
    return ea_ids.guid_to_ea_id(guid, "EAID")


def guid_to_eapk(guid):
    """Convert EA GUID {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX} to EAPK_ format.

    Returns None when guid is None/empty so callers can supply a fallback id.
    """
    return ea_ids.guid_to_ea_id(guid, "EAPK")


def normalize_newlines(text):
    """EA stores Windows line endings in Notes columns. The XMI export of the
    same model yields plain \\n because the XML spec normalizes CR/LF in
    attribute values; normalize here so both parsers produce identical data."""
    if isinstance(text, str):
        return text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def open_readonly_engine(path):
    """SQLAlchemy engine on a .qea file, opened read-only and immutable.

    ``mode=ro`` guarantees the parser never writes to the file it reads, and
    ``immutable=1`` keeps SQLite from taking locks or creating journal, WAL or
    SHM files next to it. The path is percent-encoded into a ``file:`` URI, so
    spaces, '?' and '#' in file names are safe.
    """
    uri = "file:" + quote(os.path.abspath(path)) + "?mode=ro&immutable=1"
    return sa.create_engine("sqlite://", creator=lambda: sqlite3.connect(uri, uri=True))


@ParserRegistry.register(
    "qea",
    descr="Parser for Enterprise Architect repository files (.qea/.qeax). These are SQLite databases.",
)
class QEAParser(Parser):
    def parse(self, args, schema: sch.Schema):
        inputfile = args.inputfile
        logger.info(f"Opening QEA repository (read-only): {inputfile}")

        self._minter = ea_ids.SyntheticIdMinter(f"QEA {os.path.basename(inputfile)}")
        engine = open_readonly_engine(inputfile)
        try:
            with engine.connect() as conn:
                self._phase1_packages(conn, schema)
                self._phase2_objects(conn, schema)
                self._phase3_attributes(conn, schema)
                self._phase4_connectors(conn, schema)
                self._phase5_tagged_values(conn, schema)
                self._phase6_diagrams(conn, schema)
        finally:
            engine.dispose()

        if self._minter.count:
            logger.warning(f"QEA import: {self._minter.count} elements without ea_guid got a synthetic id.")
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
        """Parse t_package into Package objects.

        Stereotype, author, status, alias and phase of a package live on its
        companion row in t_object (Object_Type 'Package', same ea_guid), not
        in t_package; the model root has no such row.
        """
        logger.info("Phase 1: parsing packages")
        rows = conn.execute(
            sa.text(
                "SELECT p.Package_ID, p.Name, p.Parent_ID, p.ea_guid, p.Notes, p.Version, "
                "p.CreatedDate, p.ModifiedDate, "
                "o.Object_ID, o.Stereotype, o.Author, o.Status, o.Alias, o.Phase "
                "FROM t_package p "
                "LEFT JOIN t_object o ON o.ea_guid = p.ea_guid AND o.Object_Type = 'Package' "
                "ORDER BY p.Package_ID, o.Object_ID"
            )
        ).fetchall()

        # One row per package, even if the join matched more than one object.
        packages: dict = {}
        for row in rows:
            packages.setdefault(row[0], row)

        # Build lookups: Package_ID -> EAPK_ id, package t_object.Object_ID -> EAPK_ id
        self._pkg_id_map = {}
        guid_ids = {pkg_id: guid_to_eapk(row[3]) for pkg_id, row in packages.items()}
        for pkg_id, row in packages.items():
            eapk_id = guid_ids[pkg_id]
            if eapk_id is None:
                eapk_id = self._minter.mint(guid_ids.get(row[2]), row[1], kind="package")
            self._pkg_id_map[pkg_id] = eapk_id
        self._pkg_obj_map = {row[8]: self._pkg_id_map[pkg_id] for pkg_id, row in packages.items() if row[8] is not None}

        for pkg_id, row in packages.items():
            (
                _,
                name,
                parent_id,
                _ea_guid,
                notes,
                version,
                created,
                modified,
                _obj_id,
                stereotype,
                author,
                status,
                alias,
                phase,
            ) = row
            eapk_id = self._pkg_id_map[pkg_id]
            parent_eapk = self._pkg_id_map.get(parent_id) if parent_id else None

            package = db.Package(
                id=eapk_id,
                name=name,
                parent_package_id=parent_eapk,
                definitie=normalize_newlines(notes),
                version=version,
                created=created,
                modified=modified,
                stereotype=stereotype or None,
                author=author,
                status=status,
                alias=alias or None,
                phase=phase,
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
                "Status, Alias, Phase "
                "FROM t_object "
                f"WHERE Object_Type IN ({_sql_list(MODEL_OBJECT_TYPES)}) "
                "ORDER BY Object_ID"
            )
        ).fetchall()

        # Build lookups: Object_ID (int) -> EAID_ string, and the ids that land
        # in `classes` (connector ends must, see _phase4_connectors).
        self._obj_id_map = {}
        self._class_ids = set()
        for row in rows:
            obj_id, obj_type, name, package_id, ea_guid = row[:5]
            eaid = guid_to_eaid(ea_guid)
            if eaid is None:
                eaid = self._minter.mint(self._pkg_id_map.get(package_id), name, kind="element")
            self._obj_id_map[obj_id] = eaid
            if obj_type != "Enumeration":
                self._class_ids.add(eaid)

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
                phase,
            ) = row

            eaid = self._obj_id_map[obj_id]
            pkg_eapk = self._pkg_id_map.get(package_id)

            if obj_type == "Enumeration":
                enum = db.Enumeratie(
                    id=eaid,
                    name=name,
                    package_id=pkg_eapk,
                    definitie=normalize_newlines(note),
                    stereotype=stereotype,
                    author=author,
                    version=version,
                    created=created,
                    modified=modified,
                    status=status,
                    alias=alias,
                    phase=phase,
                )
                logger.debug(f"Enumeration {name} met id {eaid}")
                schema.save(enum)
            else:
                clazz = db.Class(
                    id=eaid,
                    name=name,
                    package_id=pkg_eapk,
                    is_datatype=(obj_type == "DataType"),
                    definitie=normalize_newlines(note),
                    stereotype=stereotype,
                    author=author,
                    version=version,
                    created=created,
                    modified=modified,
                    status=status,
                    alias=alias,
                    phase=phase,
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
                f"WHERE o.Object_Type IN ({_sql_list(MODEL_OBJECT_TYPES)}) "
                "ORDER BY a.Object_ID, a.Pos, a.ID"
            )
        ).fetchall()

        # Attribute numeric ID -> eaid (used by phase 5 to apply tagged values)
        self._attr_id_map = {}

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

            parent_eaid = self._obj_id_map.get(obj_id)
            eaid = guid_to_eaid(ea_guid)
            if eaid is None:
                # EA leaves ea_guid NULL for some attributes/enum literals and
                # exports them with xmi:id="". Mint the id the eaxmi parser
                # mints for the same member, so both formats agree.
                eaid = self._minter.mint(parent_eaid, name, kind="attribute")
            self._attr_id_map[attr_id] = eaid

            if parent_type == "Enumeration":
                literal = db.EnumerationLiteral(
                    id=eaid,
                    name=name,
                    enumeratie_id=parent_eaid,
                    definitie=normalize_newlines(notes),
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
                        # Every object in _obj_id_map was saved in phase 2, as a
                        # Class/DataType or as an Enumeration. Route on that
                        # instead of a lookup in `classes`, which on a re-import
                        # also finds a placeholder class with an enumeration's id.
                        if classifier_eaid in self._class_ids:
                            type_class_id = classifier_eaid
                        else:
                            enumeration_id = classifier_eaid

                attribute = db.Attribute(
                    id=eaid,
                    name=name,
                    clazz_id=parent_eaid,
                    primitive=attr_type if not type_class_id and not enumeration_id else None,
                    type_class_id=type_class_id,
                    enumeration_id=enumeration_id,
                    definitie=normalize_newlines(notes),
                    stereotype=stereotype,
                )
                logger.debug(f"Attribute {name} met id {eaid}")
                schema.save(attribute)

        logger.info(
            f"Phase 3 done: {schema.count_attribute()} attributes, "
            f"{schema.count_enumeratieliteral()} enumeration literals"
        )

    def _phase4_connectors(self, conn, schema: sch.Schema):
        """Parse t_connector into Association and Generalization objects.

        Both ends of an association or generalization reference `classes`
        (foreign keys fk_src_class/fk_dst_class, enforced by Postgres). EA also
        draws associations to and from an Enumeration, which lives in
        `enumerations`; such an end gets a placeholder class, see
        _ensure_class_end.
        """
        logger.info("Phase 4: parsing connectors")

        rows = conn.execute(
            sa.text(
                "SELECT Connector_ID, Name, Connector_Type, SourceCard, DestCard, "
                "Start_Object_ID, End_Object_ID, ea_guid, Notes, Stereotype "
                "FROM t_connector "
                f"WHERE Connector_Type IN ({_sql_list(ASSOCIATION_CONNECTOR_TYPES + ('Generalization',))}) "
                "ORDER BY Connector_ID"
            )
        ).fetchall()

        # Imported connector ids, used by phase 5 (tagged values) and phase 6
        # (diagram links) to route to the right entity; connectors that were
        # not imported (connectors to unknown objects, NoteLinks, ...) are
        # absent from the map and skipped there.
        self._conn_id_map = {}
        self._assoc_ids = set()
        self._gen_ids = set()
        self._placeholder_ids: set = set()

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

            src_eaid = self._obj_id_map.get(start_obj_id)
            dst_eaid = self._obj_id_map.get(end_obj_id)

            # Skip connectors to unknown objects
            if src_eaid is None or dst_eaid is None:
                logger.debug(
                    f"Connector {conn_id} ({name}) verwijst naar onbekende objecten: "
                    f"src={start_obj_id}, dst={end_obj_id} - overgeslagen"
                )
                continue

            eaid = guid_to_eaid(ea_guid)
            if eaid is None:
                eaid = self._minter.mint(src_eaid, name, kind="connector")
            self._conn_id_map[conn_id] = eaid
            self._ensure_class_end(schema, src_eaid, conn_type, name, eaid)
            self._ensure_class_end(schema, dst_eaid, conn_type, name, eaid)

            if conn_type == "Generalization":
                gen = db.Generalization(
                    id=eaid,
                    name=name or "",
                    superclass_id=dst_eaid,
                    subclass_id=src_eaid,
                    definitie=normalize_newlines(notes),
                    stereotype=stereotype,
                )
                logger.debug(f"Generalization {name} met id {eaid}")
                schema.save(gen)
                self._gen_ids.add(eaid)
            else:
                # Association, Aggregation or Realisation
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
                    definitie=normalize_newlines(notes),
                    stereotype=stereotype,
                )
                logger.debug(f"Association {name} met id {eaid}")
                schema.save(assoc)
                self._assoc_ids.add(eaid)

        logger.info(
            f"Phase 4 done: {schema.count_association()} associations, "
            f"{schema.count_generalizations()} generalizations"
        )

    def _ensure_class_end(self, schema: sch.Schema, end_eaid, conn_type, conn_name, conn_eaid):
        """Give a connector end that is not a class a placeholder row in `classes`.

        The eaxmi parser does the same for an association end whose type is not
        a class: a class named ``<Orphan Class>`` with the id of the referenced
        element, without package. Using that rule here keeps both formats on the
        same rows, and the enumeration itself is still imported unchanged.
        Without it the association references a missing class: SQLite accepts
        that, Postgres rejects the import on fk_dst_class.
        """
        if end_eaid in self._class_ids:
            return
        logger.warning(
            f"QEA import: {conn_type} '{conn_name or ''}' ({conn_eaid}) ends on {end_eaid}, which is not a class; "
            f"it points to a placeholder class '{const.ORPHAN_CLASS}' with that id."
        )
        if end_eaid in self._placeholder_ids:
            return
        self._placeholder_ids.add(end_eaid)
        schema.save(db.Class(id=end_eaid, name=const.ORPHAN_CLASS))

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
        packages_by_id = {p.id: p for p in schema.get_all_packages()}
        classes_by_id = {c.id: c for c in schema.get_all_classes()}
        classes_by_id.update({c.id: c for c in schema.get_all_datatypes()})
        enums_by_id = {e.id: e for e in schema.get_all_enumerations()}
        attrs_by_id = {a.id: a for a in schema.get_all_attributes()}
        assocs_by_id = {a.id: a for a in schema.get_all_associations()}

        # Object tagged values (packages, classes, datatypes, enumerations).
        rows = conn.execute(
            sa.text(
                "SELECT op.Object_ID, op.Property, op.Value, o.Object_Type "
                "FROM t_objectproperties op "
                "JOIN t_object o ON op.Object_ID = o.Object_ID "
                f"WHERE o.Object_Type IN ({_sql_list(MODEL_OBJECT_TYPES + ('Package',))}) "
                "ORDER BY op.Object_ID, op.PropertyID"
            )
        ).fetchall()

        for obj_id, prop, value, obj_type in rows:
            if prop is None:
                continue
            if obj_type == "Package":
                obj = packages_by_id.get(self._pkg_obj_map.get(obj_id))
            elif obj_type == "Enumeration":
                # Not classes_by_id first: a placeholder class of phase 4 can
                # carry the same id as the enumeration.
                obj = enums_by_id.get(self._obj_id_map.get(obj_id))
            else:
                obj = classes_by_id.get(self._obj_id_map.get(obj_id))
            field = fixtag(prop)
            if obj is not None and hasattr(obj, field):
                setattr(obj, field, normalize_newlines(value))

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
            if eaid is None or prop is None:
                continue
            field = fixtag(prop)
            attr = attrs_by_id.get(eaid)
            if attr is not None and hasattr(attr, field):
                setattr(attr, field, normalize_newlines(value))

        # Connector tagged values (associations, aggregations, realisations).
        conn_rows = conn.execute(
            sa.text(
                "SELECT ct.ElementID, ct.Property, ct.VALUE "
                "FROM t_connectortag ct "
                "JOIN t_connector c ON ct.ElementID = c.Connector_ID "
                f"WHERE c.Connector_Type IN ({_sql_list(ASSOCIATION_CONNECTOR_TYPES)}) "
                "ORDER BY ct.ElementID, ct.PropertyID"
            )
        ).fetchall()

        for elem_id, prop, value in conn_rows:
            eaid = self._conn_id_map.get(elem_id)
            if eaid is None or prop is None:
                continue
            field = fixtag(prop)
            assoc = assocs_by_id.get(eaid)
            if assoc is not None and hasattr(assoc, field):
                setattr(assoc, field, normalize_newlines(value))

        # One batched write for all in-memory mutations of this phase.
        schema.database.session.flush()

        logger.info("Phase 5 done: tagged values applied")

    def _phase6_diagrams(self, conn, schema: sch.Schema):
        """Parse t_diagram, t_diagramobjects and t_diagramlinks into Diagram
        objects with membership, geometry and display settings.

        Geometry conversions follow :mod:`crunch_uml.ea_geometry`: RectTop and
        RectBottom are negative in the QEA database, the Path column uses ';'
        between x:y pairs with negative y, and Hidden/Path live in separate
        columns (unlike the XMI export, where they are folded into the style
        and geometry strings). Diagram settings come from PDATA (the XMI
        ``style1``) and StyleEx (the XMI ``style2``).
        """
        logger.info("Phase 6: parsing diagrams")

        rows = conn.execute(
            sa.text(
                "SELECT Diagram_ID, ea_guid, Name, Package_ID, Author, Version, "
                "CreatedDate, ModifiedDate, Notes, Diagram_Type, PDATA, StyleEx "
                "FROM t_diagram ORDER BY Diagram_ID"
            )
        ).fetchall()

        diagrams_by_local_id = {}
        for row in rows:
            (
                diagram_id,
                ea_guid,
                name,
                package_id,
                author,
                version,
                created,
                modified,
                notes,
                diagram_type,
                pdata,
                style_ex,
            ) = row
            pkg_eapk = self._pkg_id_map.get(package_id)
            if pkg_eapk is None:
                logger.debug(f"Diagram {diagram_id} ({name}) belongs to an unknown package: skipped")
                continue
            eaid = guid_to_eaid(ea_guid)
            if eaid is None:
                eaid = self._minter.mint(pkg_eapk, name, kind="diagram")
            hide_attributes, hide_operations = geo.parse_diagram_hide_flags(pdata)
            diagram = db.Diagram(
                id=eaid,
                name=name,
                package_id=pkg_eapk,
                author=author,
                version=version,
                created=created,
                modified=modified,
                definitie=normalize_newlines(notes),
                diagram_type=diagram_type,
                hide_attributes=hide_attributes,
                hide_operations=hide_operations,
                ea_style=pdata,
                ea_style_ex=style_ex,
            )
            logger.debug(f"Diagram {name} met id {eaid}")
            # Nog niet opslaan: de leden worden hieronder aan dit object
            # gehangen en het geheel gaat daarna in een keer naar de database.
            diagrams_by_local_id[diagram_id] = diagram

        # Diagram objects (nodes): route to the class or enumeration junction
        # table based on the object type; other types (Notes, Packages,
        # Boundaries, ...) are not part of the model and are skipped.
        object_rows = conn.execute(
            sa.text(
                "SELECT d.Diagram_ID, o.Object_Type, d.Object_ID, d.RectLeft, d.RectTop, "
                "d.RectRight, d.RectBottom, d.Sequence, d.ObjectStyle "
                "FROM t_diagramobjects d "
                "JOIN t_object o ON o.Object_ID = d.Object_ID "
                "ORDER BY d.Diagram_ID, d.Sequence"
            )
        ).fetchall()

        seen_nodes = set()
        for row in object_rows:
            diagram_id, obj_type, obj_id, rect_left, rect_top, rect_right, rect_bottom, sequence, style = row
            node_diagram = diagrams_by_local_id.get(diagram_id)
            if node_diagram is None:
                continue
            if obj_type not in MODEL_OBJECT_TYPES:
                logger.debug(f"Diagram object of type {obj_type} on diagram {node_diagram.name}: skipped")
                continue
            element_id = self._obj_id_map.get(obj_id)
            if element_id is None:
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
        # get membership; others (NoteLinks, connectors with unknown
        # endpoints) are skipped.
        link_rows = conn.execute(
            sa.text(
                "SELECT l.DiagramID, l.ConnectorID, l.Geometry, l.Style, l.Hidden, l.Path "
                "FROM t_diagramlinks l "
                "ORDER BY l.DiagramID, l.Instance_ID"
            )
        ).fetchall()

        seen_edges = set()
        for row in link_rows:
            diagram_id, connector_id, geometry, style, hidden, path = row
            edge_diagram = diagrams_by_local_id.get(diagram_id)
            if edge_diagram is None:
                continue
            element_id = self._conn_id_map.get(connector_id)
            if element_id is None:
                logger.debug(
                    f"Diagram link to connector {connector_id} on diagram {edge_diagram.name}: not in model, skipped"
                )
                continue
            edge_is_assoc = element_id in self._assoc_ids
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

        # Pas nu opslaan, mét leden: schema.save() is een insert-or-update, dus
        # een diagram dat al in de database staat wordt bijgewerkt in plaats
        # van opnieuw ingevoegd. Dat maakt een herimport in een gevulde
        # database mogelijk.
        for diagram in diagrams_by_local_id.values():
            schema.save(diagram)

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
