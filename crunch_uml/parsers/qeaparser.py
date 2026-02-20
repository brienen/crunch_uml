import logging

import sqlalchemy as sa

import crunch_uml.db as db
import crunch_uml.schema as sch
from crunch_uml.parsers.parser import Parser, ParserRegistry, fixtag

logger = logging.getLogger()

# EA GUID format in QEA: {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}
# In XMI these become: EAID_XXXXXXXX_XXXX_XXXX_XXXX_XXXXXXXXXXXX (for objects)
#                  and EAPK_XXXXXXXX_XXXX_XXXX_XXXX_XXXXXXXXXXXX (for packages)


def guid_to_eaid(guid: str) -> str:
    """Convert EA GUID {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX} to EAID_ format."""
    clean = guid.strip("{}").replace("-", "_")
    return f"EAID_{clean}"


def guid_to_eapk(guid: str) -> str:
    """Convert EA GUID {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX} to EAPK_ format."""
    clean = guid.strip("{}").replace("-", "_")
    return f"EAPK_{clean}"


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

        logger.info(
            f"QEA import done: {schema.count_package()} packages, "
            f"{schema.count_class()} classes, "
            f"{schema.count_attribute()} attributes, "
            f"{schema.count_enumeratie()} enumerations, "
            f"{schema.count_enumeratieliteral()} enumeration literals, "
            f"{schema.count_association()} associations, "
            f"{schema.count_generalizations()} generalizations."
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
                obj_id, obj_type, name, package_id, ea_guid,
                note, stereotype, author, version, created, modified,
                status, alias,
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

        logger.info(
            f"Phase 2 done: {schema.count_class()} classes, "
            f"{schema.count_enumeratie()} enumerations"
        )

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

        for row in rows:
            (
                attr_id, obj_id, name, attr_type, classifier,
                lower, upper, notes, ea_guid, scope,
                stereotype, parent_type,
            ) = row

            eaid = guid_to_eaid(ea_guid)
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

        for row in rows:
            (
                conn_id, name, conn_type, src_card, dst_card,
                start_obj_id, end_obj_id, ea_guid, notes, stereotype,
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

        logger.info(
            f"Phase 4 done: {schema.count_association()} associations, "
            f"{schema.count_generalizations()} generalizations"
        )

    def _phase5_tagged_values(self, conn, schema: sch.Schema):
        """Apply tagged values from t_objectproperties, t_attributetag, t_connectortag."""
        logger.info("Phase 5: applying tagged values")

        # Object tagged values (classes, enumerations)
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
            obj = schema.get_class(eaid)
            if obj is None:
                obj = schema.get_enumeration(eaid)
            if obj is not None and hasattr(obj, field):
                setattr(obj, field, value)
                schema.save(obj)

        # Attribute tagged values
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
            # Find attribute by matching numeric ID via ea_guid lookup
            attr_rows2 = conn.execute(
                sa.text("SELECT ea_guid FROM t_attribute WHERE ID = :id"),
                {"id": elem_id},
            ).fetchone()
            if attr_rows2 is None:
                continue
            eaid = guid_to_eaid(attr_rows2[0])
            field = fixtag(prop)
            attr = schema.get_attribute(eaid)
            if attr is not None and hasattr(attr, field):
                setattr(attr, field, value)
                schema.save(attr)

        # Connector tagged values (associations)
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
            conn_row = conn.execute(
                sa.text("SELECT ea_guid FROM t_connector WHERE Connector_ID = :id"),
                {"id": elem_id},
            ).fetchone()
            if conn_row is None:
                continue
            eaid = guid_to_eaid(conn_row[0])
            field = fixtag(prop)
            assoc = schema.get_association(eaid)
            if assoc is not None and hasattr(assoc, field):
                setattr(assoc, field, value)
                schema.save(assoc)

        logger.info("Phase 5 done: tagged values applied")

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
