import inspect
import logging
from datetime import datetime

from sqlalchemy import Column, MetaData, and_, create_engine, func, insert, or_, text
from sqlalchemy.orm import sessionmaker

import crunch_uml.schema as sch
from crunch_uml import const, util
from crunch_uml.db import (
    UMLTags,
    UMLTagsAttribute,
    UMLTagsGeneralization,
    UMLTagsLiteral,
    UMLTagsRelation,
)
from crunch_uml.exceptions import CrunchException
from crunch_uml.renderers.renderer import ModelRenderer, RendererRegistry

logger = logging.getLogger()


@RendererRegistry.register(
    "earepo",
    descr="Updates as Enterprise Architect v16+ repository. "
    + "Only updates existing Classes and attributes, Enumerations and literals, Packages and Associations. "
    + "Does not add new things, updates only."
    + "provide the EA Repo through the --file parameter.",
)
class EARepoUpdater(ModelRenderer):
    """
    Connects to an Enterprise Architect repository by treating it as a database
    Usualy SQLlite with the .qua extension.
    """

    def get_database_session(self, database_url):
        # Als er geen volledige URL wordt meegegeven, behandel het als een SQLite-database
        if not database_url.startswith(("sqlite://", "postgresql://", "mysql://", "oracle://")):
            if not database_url.endswith(".qea"):
                database_url += ".qea"
            database_url = f"sqlite:///{database_url}"

        try:
            # Verbind met de database
            engine = create_engine(database_url)
            Session = sessionmaker(bind=engine)
            session = Session()

            # Laad de metadata van de database
            # Creëer een MetaData object zonder 'bind'
            metadata = MetaData()

            # Of direct tabellen reflecteren zonder expliciet 'bind' te gebruiken
            metadata.reflect(bind=engine)

            return session, metadata
        except Exception as e:
            msg = f"Error while connecting to the EA Repository in EARepoUpdater: {e}"
            logger.error(msg)
            raise CrunchException(msg)

    def get_table_structure(self, table_name, metadata):
        # Haal de tabel op uit de metadata
        if table_name in metadata.tables:
            table = metadata.tables[table_name]
            return table
        else:
            logger.warning(f"Tabel '{table_name}' niet gevonden in de database.")
            return None

    def fetch_data_from_source(self, source_session, source):
        # Haal alle records op uit de bron-database tabel
        records = source_session.query(source).all()
        return [dict(record) for record in records]

    def increment_version(self, version, version_type):
        try:
            parts = version.split(".")
            while len(parts) < 3:
                parts.append("0")  # minimaal major.minor.patch
            major = int(parts[0])
            minor = int(parts[1])
            # patch = int(parts[2])
            if version_type == const.VERSION_STEP_MAJOR:
                major += 1
                minor = 0
                # patch = 0
            elif version_type == const.VERSION_STEP_MINOR:
                minor += 1
                # patch = 0
            # Always return three-part version
            return f"{major}.{minor}.0"
        except ValueError:
            logger.warning(f"Version '{version}' is not in the correct format.")
            return version

    def map_fields(self, data_dict, field_mapper):
        """
        Past de veldnamen in data_dict aan op basis van de field_mapper.
        """
        return {field_mapper.get(k, k): v for k, v in data_dict.items()}

    def get_tablefields(self, table):
        if table == "t_objectproperties":
            return "Object_ID", "Object_ID", "Property", "Value", "ea_guid"
        elif table == "t_attributetag":
            return "ID", "ElementID", "Property", "VALUE", "ea_guid"
        else:
            return None, None, None, None, None

    def update_sequence(self, session, sequence_name, increment=1):
        try:
            # Controleer of de sequence al bestaat
            result = session.execute(
                text("SELECT seq FROM sqlite_sequence WHERE name = :name"),
                {"name": sequence_name},
            )
            row = result.fetchone()

            if row is None:
                # Als de sequence niet bestaat, voeg deze dan toe met een startwaarde van 0
                current_value = 0
                session.execute(
                    text("INSERT INTO sqlite_sequence (name, seq) VALUES (:name, :seq)"),
                    {"name": sequence_name, "seq": current_value},
                )
            else:
                current_value = row[0]

            # Verhoog de waarde van de sequence
            new_value = current_value + increment
            session.execute(
                text("UPDATE sqlite_sequence SET seq = :new_value WHERE name = :name"),
                {"new_value": new_value, "name": sequence_name},
            )

            return new_value
        except Exception as e:
            msg = f"Error while updating sequence {sequence_name} with message: {e}"
            logger.error(msg)
            raise CrunchException(msg)

    def update_repo(self, update_dict, session, table_name, metadata, object_id):
        table = self.get_table_structure(table_name, metadata)
        (
            tag_id_parent_column,
            tag_id_child_column,
            tag_property_column,
            tag_value_column,
            ea_guid_column,
        ) = self.get_tablefields(table_name)

        for key, value in update_dict.items():
            session.query(table).filter_by(**{ea_guid_column: key}).update({tag_value_column: value})

    def insert_repo(self, insert_dict, session, table_name, metadata, object_id):
        table = self.get_table_structure(table_name, metadata)
        (
            tag_id_parent_column,
            tag_id_child_column,
            tag_property_column,
            tag_value_column,
            ea_guid_column,
        ) = self.get_tablefields(table_name)

        for key, value in insert_dict.items():
            seq = self.update_sequence(session, table_name)

            insert_item = {
                "PropertyID": seq,
                tag_id_child_column: object_id,
                tag_property_column: key,
                tag_value_column: value,
                "ea_guid": util.get_repo_guid(),
            }
            # Voer de insert statement uit
            session.execute(insert(table).values(insert_item))

    def delete_repo(self, delete_dict, session, table_name, metadata, object_id):
        table = self.get_table_structure(table_name, metadata)
        (
            tag_id_parent_column,
            tag_id_child_column,
            tag_property_column,
            tag_value_column,
            ea_guid_column,
        ) = self.get_tablefields(table_name)

        for key, value in delete_dict.items():
            session.query(table).filter_by(**{ea_guid_column: key}).delete()

    def check_and_update_record(
        self,
        data_dict,
        table_name,
        session,
        metadata,
        version_type=None,
        field_mapper=None,
        tag_table=None,
        tag_strategy=const.TAG_STRATEGY_REPLACE,
        recordtype=None,
    ):
        ea_guid = const.EA_REPO_MAPPER["id"]

        try:
            # Haal de tabelstructuur op
            table = self.get_table_structure(table_name, metadata)
            # columns = table.columns.keys()

            if table is None:
                logger.warning(
                    f"Kan geen update uitvoeren voor tabel '{table_name}': tabel niet gevonden of structuur onbekend."
                )
                return

            # Pas veldnamen aan met de field_mapper indien aanwezig
            if field_mapper:
                data_dict = self.map_fields(data_dict, field_mapper)

            # Check of GUID aanwezig is in de data
            if ea_guid not in data_dict:
                logger.error(f"Kan record niet updaten, {ea_guid} is vereist in de data dictionary")
                return

            guid_value = util.fromEAGuid(data_dict[ea_guid])

            # Zoek naar het bestaande record op basis van GUID
            existing_record = session.query(table).filter_by(**{ea_guid: guid_value}).first()

            if existing_record:
                self.update_existing_record(
                    data_dict,
                    table_name,
                    session,
                    metadata,
                    version_type,
                    field_mapper,
                    tag_table,
                    tag_strategy,
                    recordtype=recordtype,
                )
            else:
                logger.debug(
                    f"No record found with GUID {guid_value} in table {table} and data dict {data_dict}. No update performed."
                )
        except Exception as e:
            logger.error(f"Error while updating record with GUID {guid_value} with message: {e}")
            raise CrunchException(f"Error while updating record with GUID {guid_value} with message: {e}")

    def update_existing_record(
        self,
        data_dict,
        table_name,
        session,
        metadata,
        version_type=None,
        field_mapper=None,
        tag_table=None,
        tag_strategy=const.TAG_STRATEGY_REPLACE,
        recordtype=None,
    ):
        ea_guid = const.EA_REPO_MAPPER["id"]
        logger.debug(f"Updating recordtype '{recordtype}' in table '{table_name}'...")
        try:
            table = self.get_table_structure(table_name, metadata)
            columns = table.columns.keys()
            guid_value = util.fromEAGuid(data_dict[ea_guid])
            existing_record = session.query(table).filter_by(**{ea_guid: guid_value}).first()
            # Filter de data_dict om alleen kolommen in te voegen die bestaan in de tabel
            valid_data = {
                col: data_dict[col] for col in data_dict if col in table.columns.keys() and data_dict[col] is not None
            }

            changed = False
            (
                tag_id_parent_column,
                tag_id_child_column,
                tag_property_column,
                tag_value_column,
                ea_guid_column,
            ) = self.get_tablefields(tag_table)
            if tag_table and tag_id_parent_column and tag_id_child_column and tag_property_column and tag_value_column:
                # Haal de bestaande tags op uit de definities
                if recordtype in [const.RECORDTYPE_CLASS, const.RECORDTYPE_ENUMERATION]:
                    uml_tag_names = [name for name, attr in inspect.getmembers(UMLTags) if isinstance(attr, Column)]
                elif recordtype == const.RECORDTYPE_ATTRIBUTE:
                    uml_tag_names = [
                        name for name, attr in inspect.getmembers(UMLTagsAttribute) if isinstance(attr, Column)
                    ]
                elif recordtype in [const.RECORDTYPE_ASSOCIATION]:
                    uml_tag_names = [
                        name for name, attr in inspect.getmembers(UMLTagsRelation) if isinstance(attr, Column)
                    ]
                elif recordtype in [const.RECORDTYPE_GENERALIZATION]:
                    uml_tag_names = [
                        name for name, attr in inspect.getmembers(UMLTagsGeneralization) if isinstance(attr, Column)
                    ]
                elif recordtype in [const.RECORDTYPE_LITERAL]:
                    uml_tag_names = [
                        name for name, attr in inspect.getmembers(UMLTagsLiteral) if isinstance(attr, Column)
                    ]
                else:
                    # Voor andere recordtypes, gebruik de standaard UMLTags
                    uml_tag_names = []

                # Haal de bestaande tags op uit de database
                db_tags_query = (
                    session.query(self.get_table_structure(tag_table, metadata))
                    .filter_by(**{tag_id_child_column: getattr(existing_record, tag_id_parent_column)})
                    .all()
                )
                db_tags = {getattr(tag, tag_property_column): getattr(tag, tag_value_column) for tag in db_tags_query}
                db_tags = {util.map_field_name_from_EARepo(k, const.EA_REPO_MAPPER): v for k, v in db_tags.items()}

                db_tags_keys = {getattr(tag, tag_property_column): getattr(tag, 'ea_guid') for tag in db_tags_query}
                db_tags_keys = {
                    util.map_field_name_from_EARepo(k, const.EA_REPO_MAPPER): v for k, v in db_tags_keys.items()
                }
                # Nog even de veldnaam in de goed stijl zetten
                for name, guid in db_tags_keys.items():
                    session.query(self.get_table_structure(tag_table, metadata)).filter_by(ea_guid=guid).update(
                        {tag_property_column: util.map_field_name_to_EARepo(name)}
                    )

                # Bepaal welke tags zijn gewijzigd
                tags_changed = {
                    db_tags_keys[col]: data_dict[col]
                    for col in data_dict
                    if col in uml_tag_names and col in db_tags.keys() and data_dict[col] != db_tags[col]
                }
                tags_new = {
                    util.map_field_name_to_EARepo(col): data_dict[col]
                    for col in data_dict
                    if col in uml_tag_names and col not in db_tags.keys()
                }
                tags_deleted = {db_tags_keys[col]: db_tags[col] for col in db_tags if col not in data_dict.keys()}

                if tag_strategy == const.TAG_STRATEGY_UPSERT:
                    self.update_repo(
                        tags_changed,
                        session,
                        tag_table,
                        metadata,
                        getattr(existing_record, tag_id_parent_column),
                    )
                    self.insert_repo(
                        tags_new,
                        session,
                        tag_table,
                        metadata,
                        getattr(existing_record, tag_id_parent_column),
                    )
                    changed = len(tags_changed) > 0 or len(tags_new) > 0
                elif tag_strategy == const.TAG_STRATEGY_UPDATE:
                    self.update_repo(
                        tags_changed,
                        session,
                        tag_table,
                        metadata,
                        getattr(existing_record, tag_id_parent_column),
                    )
                    changed = len(tags_changed) > 0
                elif tag_strategy == const.TAG_STRATEGY_REPLACE:
                    self.update_repo(
                        tags_changed,
                        session,
                        tag_table,
                        metadata,
                        getattr(existing_record, tag_id_parent_column),
                    )
                    self.delete_repo(
                        tags_deleted,
                        session,
                        tag_table,
                        metadata,
                        getattr(existing_record, tag_id_parent_column),
                    )
                    self.insert_repo(
                        tags_new,
                        session,
                        tag_table,
                        metadata,
                        getattr(existing_record, tag_id_parent_column),
                    )
                    changed = len(tags_changed) > 0 or len(tags_new) > 0 or len(tags_deleted) > 0

            # Check of er iets is veranderd
            changes = {}
            for key, value in valid_data.items():
                if getattr(existing_record, key) != value and key not in [
                    ea_guid,
                    const.EA_REPO_MAPPER["modified"],
                ]:
                    changes[key] = value

            changed = changed or len(changes) > 0
            # Alleen updaten als er daadwerkelijk wijzigingen zijn
            if changed:
                # Update het modified veld
                if const.EA_REPO_MAPPER["modified"] in columns:
                    changes[const.EA_REPO_MAPPER["modified"]] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Update het versienummer indien van toepassing
                if const.EA_REPO_MAPPER["version"] in columns and version_type is not None:
                    current_version = getattr(existing_record, const.EA_REPO_MAPPER["version"])
                    new_version = self.increment_version(current_version, version_type)
                    changes[const.EA_REPO_MAPPER["version"]] = new_version

                if len(changes) > 0:
                    session.query(table).filter_by(**{ea_guid: guid_value}).update(changes)
                    logger.debug(f"Record with GUID {guid_value} has been updated with version info.")
                else:
                    logger.debug(f"No version info detected for record with GUID {guid_value}.")
            else:
                logger.debug(f"No changes detected for record with GUID {guid_value}.")

        except Exception as e:
            logger.error(f"Error while updating record with GUID {guid_value} with message: {e} for changes {changes}")
            raise CrunchException(f"Error while updating record with GUID {guid_value} with message: {e}")

    def process_batch(
        self,
        source_data,
        target_table_name,
        target_session,
        target_metadata,
        version_type=None,
        field_mapper=None,
        tag_table=None,
        batch_size=100,
        tag_strategy=const.TAG_STRATEGY_REPLACE,
        recordtype=None,
    ):
        # Verwerk de data in batches
        for i in range(0, len(source_data), batch_size):
            batch = source_data[i : i + batch_size]
            for record in batch:
                self.check_and_update_record(
                    record,
                    target_table_name,
                    target_session,
                    target_metadata,
                    version_type,
                    field_mapper,
                    tag_table,
                    tag_strategy=tag_strategy,
                    recordtype=recordtype,
                )

    def deduplicate_tags(
        self, session, metadata, tag_table, tag_id_child_column, tag_property_column, tag_value_column
    ):
        """
        Verwijder dubbele tags uit de tag-tabel (t_objectproperties of t_attributetag).
        Houdt alleen het eerste (laagste ID) record per (child_id, property).
        """
        try:
            table = self.get_table_structure(tag_table, metadata)
            if table is None:
                logger.warning(f"Tabel '{tag_table}' niet gevonden in metadata voor deduplicatie.")
                return

            # Bepaal het ID veld voor de tabel
            id_column = None
            if tag_table == "t_objectproperties":
                id_column = "PropertyID"
            elif tag_table == "t_attributetag":
                id_column = "PropertyID"
            else:
                logger.warning(f"Deduplicatie niet geïmplementeerd voor tabel '{tag_table}'.")
                return

            required_columns = {id_column, tag_id_child_column, tag_property_column}
            missing_columns = required_columns - set(c.name for c in table.columns)
            if missing_columns:
                logger.warning(
                    f"Deduplicatie afgebroken. Vereiste kolommen ontbreken in tabel '{tag_table}': {missing_columns}"
                )
                return

            # Zoek dubbele (child_id, property) combinaties
            subquery = (
                session.query(
                    getattr(table.c, tag_id_child_column).label("child_id"),
                    getattr(table.c, tag_property_column).label("property"),
                    func.min(getattr(table.c, id_column)).label("min_id"),
                )
                .group_by(getattr(table.c, tag_id_child_column), getattr(table.c, tag_property_column))
                .subquery()
            )

            # Vind alle id's die NIET de min_id zijn (dus duplicaten)
            duplicates = (
                session.query(getattr(table.c, id_column))
                .join(
                    subquery,
                    and_(
                        getattr(table.c, tag_id_child_column) == subquery.c.child_id,
                        getattr(table.c, tag_property_column) == subquery.c.property,
                        getattr(table.c, id_column) != subquery.c.min_id,
                    ),
                )
                .order_by(getattr(table.c, id_column).desc())
                .all()
            )

            duplicate_ids = [row[0] for row in duplicates]
            if duplicate_ids:
                session.query(table).filter(getattr(table.c, id_column).in_(duplicate_ids)).delete(
                    synchronize_session=False
                )
                logger.info(f"Deduplicatie uitgevoerd op '{tag_table}': {len(duplicate_ids)} dubbele tags verwijderd.")
            else:
                logger.debug(f"Geen dubbele tags gevonden in '{tag_table}'.")

        except Exception as e:
            logger.error(f"Fout tijdens deduplicatie van '{tag_table}': {e}")

    def render(self, args, schema: sch.Schema):

        # Check to see if a list of Package ids is provided
        # if self.enforce_output_package_ids and args.output_package_ids is None:
        #    msg = "Usage of parameter --output_package_ids is enforced for this renderer. Not provided, exiting."
        #    logger.error(msg)
        #    raise CrunchException(msg)
        target_session, target_metadata = self.get_database_session(args.outputfile)
        if target_session and target_metadata:
            version_type = args.version_type
            tag_strategy = args.tag_strategy
            logger.info(
                f"Updating EA Repository {args.outputfile} with version type {version_type} and tag_strategy"
                f" {tag_strategy}..."
            )

            try:
                # First fix duplicate tags
                self.deduplicate_tags(
                    target_session,
                    target_metadata,
                    tag_table="t_objectproperties",
                    tag_id_child_column="Object_ID",
                    tag_property_column="Property",
                    tag_value_column="Value",
                )
                self.deduplicate_tags(
                    target_session,
                    target_metadata,
                    tag_table="t_attributetag",
                    tag_id_child_column="ElementID",
                    tag_property_column="Property",
                    tag_value_column="VALUE",
                )

                # Process all classes
                logger.info("Updating classes...")
                classes = schema.get_all_classes()
                dict_classes = [record.to_dict() for record in classes]
                self.process_batch(
                    dict_classes,
                    "t_object",
                    target_session,
                    target_metadata,
                    version_type=version_type,
                    tag_table="t_objectproperties",
                    field_mapper=const.EA_REPO_MAPPER,
                    tag_strategy=tag_strategy,
                    recordtype=const.RECORDTYPE_CLASS,
                )

                # Process all attributes
                logger.info("Updating attributes...")
                attributes = schema.get_all_attributes()
                dict_attributes = [record.to_dict() for record in attributes]
                self.process_batch(
                    dict_attributes,
                    "t_attribute",
                    target_session,
                    target_metadata,
                    version_type=version_type,
                    field_mapper=const.EA_REPO_MAPPER_ATTRIBUTES,
                    tag_table="t_attributetag",
                    tag_strategy=tag_strategy,
                    recordtype=const.RECORDTYPE_ATTRIBUTE,
                )

                # Process all literals
                logger.info("Updating literals...")
                literals = schema.get_all_literals()
                dict_literals = [record.to_dict() for record in literals]
                self.process_batch(
                    dict_literals,
                    "t_attribute",
                    target_session,
                    target_metadata,
                    version_type=version_type,
                    field_mapper=const.EA_REPO_MAPPER_LITERALS,
                    tag_table="t_attributetag",
                    tag_strategy=tag_strategy,
                    recordtype=const.RECORDTYPE_LITERAL,
                )

                # Process all enumerations
                logger.info("Updating enumerations...")
                enums = schema.get_all_enumerations()
                dict_enums = [record.to_dict() for record in enums]
                self.process_batch(
                    dict_enums,
                    "t_object",
                    target_session,
                    target_metadata,
                    version_type=version_type,
                    field_mapper=const.EA_REPO_MAPPER,
                    tag_table="t_objectproperties",
                    tag_strategy=tag_strategy,
                    recordtype=const.RECORDTYPE_ENUMERATION,
                )

                # Process all packages
                logger.info("Updating packages...")
                packages = schema.get_all_packages()
                dict_packages = [record.to_dict() for record in packages]
                self.process_batch(
                    dict_packages,
                    "t_object",
                    target_session,
                    target_metadata,
                    version_type=version_type,
                    field_mapper=const.EA_REPO_MAPPER,
                    tag_table="t_objectproperties",
                    tag_strategy=tag_strategy,
                    recordtype=const.RECORDTYPE_PACKAGE,
                )
                self.process_batch(
                    dict_packages,
                    "t_package",
                    target_session,
                    target_metadata,
                    version_type=version_type,
                    field_mapper=const.EA_REPO_MAPPER,
                    tag_strategy=tag_strategy,
                    recordtype=const.RECORDTYPE_PACKAGE,
                )

                # Process all associations
                logger.info("Updating associations...")
                associations = schema.get_all_associations()
                dict_associations = [record.to_dict() for record in associations]
                self.process_batch(
                    dict_associations,
                    "t_connector",
                    target_session,
                    target_metadata,
                    version_type=version_type,
                    field_mapper=const.EA_REPO_MAPPER_ASSOCIATION,
                    tag_strategy=tag_strategy,
                    recordtype=const.RECORDTYPE_ASSOCIATION,
                )

                # Process all generalizations
                logger.info("Updating generalizations...")
                generalizations = schema.get_all_generalizations()
                dict_generalizations = [record.to_dict() for record in generalizations]
                self.process_batch(
                    dict_generalizations,
                    "t_connector",
                    target_session,
                    target_metadata,
                    version_type=version_type,
                    field_mapper=const.EA_REPO_MAPPER_GENERALIZATION,
                    tag_strategy=tag_strategy,
                    recordtype=const.RECORDTYPE_GENERALIZATION,
                )

                # Process all diagrams
                logger.info("Updating diagrams...")
                diagrams = schema.get_all_diagrams()
                dict_diagrams = [record.to_dict() for record in diagrams]
                self.process_batch(
                    dict_diagrams,
                    "t_diagram",
                    target_session,
                    target_metadata,
                    version_type=version_type,
                    field_mapper=const.EA_REPO_MAPPER,
                    tag_strategy=tag_strategy,
                    recordtype=const.RECORDTYPE_DIAGRAM,
                )

                logger.info(f"All data updated in repo {args.outputfile}, commiting...")
                target_session.commit()
            except Exception as e:
                msg = f"Rolling back changes.... Error while updating classes with message: {e}."
                logger.error(msg)

                target_session.rollback()
                raise CrunchException(msg)


@RendererRegistry.register(
    "eamimrepo",
    descr="Updates as Enterprise Architect v16+ repository and applies MIM profile. "
    + "Only updates existing Classes and attributes, Enumerations and literals, Packages and Associations. "
    + "Does not add new things, updates only. Sets  MIM profile on all entities. "
    + "provide the EA Repo through the --file parameter.",
)
class EAMIMRepoUpdater(EARepoUpdater):
    """
    Connects to an Enterprise Architect repository by treating it as a database
    Usualy SQLlite with the .qua extension.
    """

    def setStereotype(self, recordtype, data_dict, metadata, session, Type, Name, FQName):
        """
        Set the stereotype for the recordtype.
        """
        try:
            ea_guid = data_dict.get("ea_guid", None)
            if ea_guid is None:
                logger.error(f"Cannot update {recordtype} without EA GUID.")
                raise CrunchException(f"Cannot update {recordtype} without EA GUID.")

            # First delete existing stereotype xrefs only
            table_name = "t_xref"
            if table_name in metadata.tables:
                table = metadata.tables[table_name]
                session.query(table).filter(
                    table.c.Client == util.fromEAGuid(ea_guid), table.c.Name == "Stereotypes"
                ).delete()
            else:
                logger.warning(f"Tabel '{table_name}' niet gevonden in metadata.")

            # Add MIM profile to the class
            insert_item = {
                "Name": 'Stereotypes',
                "Type": Type,
                "Visibility": 'Public',
                "Description": f'@STEREO;Name={Name};FQName={FQName};@ENDSTEREO;',
                "Client": util.fromEAGuid(ea_guid),
                "XrefID": util.get_repo_guid(),
            }
            stmt = insert(metadata.tables["t_xref"]).values(insert_item)
            session.execute(stmt)

            data_dict["Stereotype"] = Name
            return data_dict
        except Exception as e:
            logger.error(f"Error while updating MIM profile for {recordtype} with EA GUID {ea_guid}: {e}")
            raise CrunchException(f"Error while updating MIM profile for {recordtype} with EA GUID {ea_guid}: {e}")

    def infer_datatype(self, name):
        """
        Infer datatype based on the value.
        """
        if "datum" in name.lower() or "date" in name.lower():
            return "Date"
        elif "indicatie" in name.lower():
            return "Boolean"
        elif "aantal" in name.lower() or "number" in name.lower():
            return "Integer"
        elif "bedrag" in name.lower() or "amount" in name.lower():
            return "Bedrag"
        else:
            return "CharacterString"

    def update_existing_record(
        self,
        data_dict,
        table_name,
        session,
        metadata,
        version_type=None,
        field_mapper=None,
        tag_table=None,
        tag_strategy=const.TAG_STRATEGY_REPLACE,
        recordtype=None,
        profiel="MIM",
    ):
        if recordtype == const.RECORDTYPE_CLASS:
            data_dict = self.setStereotype(
                recordtype,
                data_dict,
                metadata,
                session,
                'element property',
                'Objecttype',
                'VNGR SIM+Grouping NL::Objecttype',
            )
        elif recordtype == const.RECORDTYPE_ATTRIBUTE:
            data_dict = self.setStereotype(
                recordtype,
                data_dict,
                metadata,
                session,
                'attribute property',
                'Attribuutsoort',
                'VNGR SIM+Grouping NL::Attribuutsoort',
            )
        elif recordtype == const.RECORDTYPE_LITERAL:
            data_dict = self.setStereotype(
                recordtype,
                data_dict,
                metadata,
                session,
                'attribute property',
                'Enumeratiewaarde',
                'VNGR SIM+Grouping NL::Enumeratiewaarde',
            )
        elif recordtype == const.RECORDTYPE_ENUMERATION:
            data_dict = self.setStereotype(
                recordtype,
                data_dict,
                metadata,
                session,
                'element property',
                'Enumeratie',
                'VNGR SIM+Grouping NL::Enumeratie',
            )
        # elif recordtype == const.RECORDTYPE_PACKAGE:
        #    data_dict = self.setStereotype(recordtype, data_dict, metadata, session, 'element property', 'Package', 'VNGR SIM+Grouping NL::Package')
        elif recordtype == const.RECORDTYPE_ASSOCIATION:
            data_dict = self.setStereotype(
                recordtype,
                data_dict,
                metadata,
                session,
                'connector property',
                'Relatiesoort',
                'VNGR SIM+Grouping NL::Relatiesoort',
            )
        elif recordtype == const.RECORDTYPE_GENERALIZATION:
            data_dict = self.setStereotype(
                recordtype,
                data_dict,
                metadata,
                session,
                'connector property',
                'Generalisatie',
                'VNGR SIM+Grouping NL::Generalisatie',
            )
        else:
            logger.debug(f"Unknown recordtype {recordtype}, not setting stereotype.")

        # If data_dict contains release set de waarde
        # Set 'Release' field case-insensitively and ensure it's written as 'Release'
        release_key = next((k for k in data_dict.keys() if k.lower() == "release"), None)
        if release_key is not None and data_dict[release_key] is None:
            data_dict["release"] = util.to_yyyymmdd(data_dict.get("ModifiedDate", "2019/06/01"))
        elif release_key is not None:
            data_dict["release"] = data_dict[release_key]

        # Set data type for attributes
        if recordtype == const.RECORDTYPE_LITERAL:
            # Set "Style" field case-insensitively from "alias"
            alias_key = next((k for k in data_dict.keys() if k.lower() == "alias"), None)
            if alias_key is not None:
                data_dict["Style"] = data_dict.get(alias_key, None)
            elif data_dict.get("Type"):
                # If "Type" is filled and "alias" is not, use "Type" value for "alias" and "Style"
                data_dict["alias"] = data_dict["Type"]
                data_dict["Style"] = data_dict["Type"]
            else:
                data_dict["Style"] = None
            # Set "Type" to None
            data_dict["Type"] = None

        # Set data type for attributes
        if recordtype == const.RECORDTYPE_ATTRIBUTE:

            # Skip values that point to a datatype
            datatype_input = data_dict.get("Type", None).lower().strip() if data_dict.get("Type", None) else None
            table = metadata.tables["t_attribute"]
            record = session.query(table).filter_by(ea_guid=util.fromEAGuid(data_dict.get("ea_guid"))).first()

            if datatype_input is not None and (
                record.Classifier is None or record.Classifier == 0 or record.Classifier == "0"
            ):
                if datatype_input.startswith("an") or datatype_input in [
                    "text",
                    "string",
                    "characterstring",
                    "tekst",
                    "memo",
                    "character",
                    "char",
                    "varchar",
                    "character varying",
                    "string text",
                ]:
                    datatype = "CharacterString"
                    data_dict["Classifier"] = self.datatype_map.get(datatype, None)
                    data_dict["Type"] = datatype
                    dt, number = util.split_number(datatype_input)
                    if number is not None:
                        data_dict["length"] = number
                        data_dict["Length"] = number
                        data_dict["lengte"] = number
                elif (
                    datatype_input.startswith("n")
                    or datatype_input.startswith("int")
                    or datatype_input
                    in [
                        "ìnt",
                        "number",
                        "integer",
                        "integer number",
                        "nummertotaal",
                        "nummertotaal integer",
                        "short",
                        "integer short",
                        "long",
                        "integer long",
                        "int",
                        "integer int",
                    ]
                ):
                    datatype = "Integer"
                    data_dict["Classifier"] = self.datatype_map.get(datatype, None)
                    data_dict["Type"] = datatype
                    dt, number = util.split_number(datatype_input)
                    if number is not None:
                        data_dict["length"] = number
                        data_dict["Length"] = number
                        data_dict["lengte"] = number
                elif datatype_input in ["date", "datum"]:
                    datatype = "Date"
                    data_dict["Classifier"] = self.datatype_map.get(datatype, None)
                    data_dict["Type"] = datatype
                elif datatype_input in ["datetime", "datumtijd"]:
                    datatype = "DateTime"
                    data_dict["Classifier"] = self.datatype_map.get(datatype, None)
                    data_dict["Type"] = datatype
                elif datatype_input in ["time", "tijd"]:
                    datatype = "Time"
                    data_dict["Classifier"] = self.datatype_map.get(datatype, None)
                    data_dict["Type"] = datatype
                elif (
                    datatype_input.startswith("bool")
                    or "stdindjn" in datatype_input
                    or datatype_input in ["boolean", "bool", "ja/nee", "ja nee", "yes no", "ja/neen", "indic"]
                ):
                    datatype = "Boolean"
                    data_dict["Classifier"] = self.datatype_map.get(datatype, None)
                    data_dict["Type"] = datatype
                elif datatype_input in ["decimal", "float", "double", "decimaal", "real"]:
                    datatype = "Decimal"
                    data_dict["Classifier"] = self.datatype_map.get(datatype, None)
                    data_dict["Type"] = datatype
                elif datatype_input in [
                    "punt",
                    "point",
                    "coordinate",
                    "coördinaat",
                    "geopunt",
                    "coordinaat",
                    'gml',
                    'locatie',
                    'spatial',
                    'geometrie',
                ]:
                    datatype = "GM_Point"
                    data_dict["Classifier"] = self.datatype_map.get(datatype, None)
                    data_dict["Type"] = datatype
                elif datatype_input in ["bedrag", "currency", "monetair", "geldbedrag"]:
                    datatype = "Bedrag"
                    data_dict["Classifier"] = self.datatype_map.get(datatype, None)
                    data_dict["Type"] = datatype
                elif datatype_input in ["blob", "binary", "byte"]:
                    datatype = "Blob"
                    data_dict["Classifier"] = self.datatype_map.get(datatype, None)
                    data_dict["Type"] = datatype
                elif datatype_input in ["guid"]:
                    datatype = "GUID"
                    data_dict["Classifier"] = self.datatype_map.get(datatype, None)
                    data_dict["Type"] = datatype
                else:
                    # Check to see if the datatype is a known geometry type
                    types = list(self.datatype_map.keys())
                    if f"GM_{data_dict.get('Type', '')}" in types:
                        datatype = f"GM_{data_dict.get('Type', '')}"
                        data_dict["Classifier"] = self.datatype_map.get(datatype, None)
                        data_dict["Type"] = datatype
                    if data_dict.get('Type', '') in types:
                        datatype = data_dict.get('Type', '')
                        data_dict["Classifier"] = self.datatype_map.get(datatype, None)
                        data_dict["Type"] = datatype
            elif datatype_input is None:
                # If the datatype is still None, we can try to infer it from the value
                name = data_dict.get("Name", "")
                if name and name != "":
                    inferred_type = self.infer_datatype(name)
                    if inferred_type:
                        datatype = inferred_type
                        data_dict["Classifier"] = self.datatype_map.get(datatype, None)
                        data_dict["Type"] = datatype
                else:
                    # If we still can't determine the type, fall back to a default
                    datatype = "CharacterString"
                    data_dict["Classifier"] = self.datatype_map.get(datatype, None)
                    data_dict["Type"] = datatype

        super().update_existing_record(
            data_dict,
            table_name,
            session,
            metadata,
            version_type,
            field_mapper,
            tag_table,
            tag_strategy,
            recordtype=recordtype,
        )
        # Speciaal voor Enumeratiewaarde: Style updaten en Type op None zetten in t_attribute
        if recordtype == const.RECORDTYPE_LITERAL:
            table = metadata.tables["t_attribute"]
            guid_value = util.fromEAGuid(data_dict.get("ea_guid"))
            update_values = {}
            if "Style" in data_dict:
                update_values["Style"] = data_dict["Style"]
            update_values["Type"] = None
            session.query(table).filter_by(ea_guid=guid_value).update(update_values)

        # Robuuste upsert voor 'Release'-tag bij packages met 'domein' stereotype
        if recordtype == const.RECORDTYPE_PACKAGE:
            try:
                stereotype = data_dict.get("Stereotype", "")
                release_value = data_dict.get("release")
                if stereotype and "domein" in stereotype.lower() and release_value:
                    table_prop = metadata.tables.get("t_objectproperties")
                    object_table = metadata.tables.get("t_object")

                    if table_prop is None or object_table is None:
                        logger.warning("Tabel 't_objectproperties' of 't_object' niet gevonden in metadata.")
                    else:
                        result = (
                            session.query(object_table).filter_by(ea_guid=util.fromEAGuid(data_dict["ea_guid"])).first()
                        )
                        if not result:
                            logger.warning(f"Geen object gevonden voor GUID {data_dict['ea_guid']}")
                        else:
                            object_id = result.Object_ID
                            existing = (
                                session.query(table_prop).filter_by(Object_ID=object_id, Property="Release").first()
                            )

                            if existing:
                                session.query(table_prop).filter_by(Object_ID=object_id, Property="Release").update(
                                    {"Value": release_value}
                                )
                                logger.debug(f"Release-tag bijgewerkt voor package met GUID {data_dict['ea_guid']}")
                            else:
                                insert_item = {
                                    "PropertyID": self.update_sequence(session, "t_objectproperties"),
                                    "Object_ID": object_id,
                                    "Property": "Release",
                                    "Value": release_value,
                                    "ea_guid": util.get_repo_guid(),
                                }
                                session.execute(insert(table_prop).values(insert_item))
                                logger.debug(f"Release-tag toegevoegd voor package met GUID {data_dict['ea_guid']}")
                else:
                    logger.debug(
                        f"Geen release-tag upsert voor package met GUID {data_dict.get('ea_guid', '<geen guid>')}: stereotype={stereotype}, release={release_value}"
                    )
            except Exception as e:
                logger.warning(f"Fout bij het toevoegen/bijwerken van de Release-tag: {e}")

    def new_method(self, value):
        inferred_type = self.infer_datatype(value)
        return inferred_type

    # Get a map of data types and their IDs from the t_object table
    def get_relevant_object_id_map(self, session, metadata):
        """
        Haalt objecten op uit t_object waar:
        - Object_Type = 'Datatype', of
        - Object_Type = 'Class' en Name begint met 'GM_'

        Retourneert een dict met {Name: Object_ID}.
        """
        table = metadata.tables.get("t_object")
        if table is None:
            logger.warning("Tabel 't_object' niet gevonden in metadata.")
            return {}

        try:
            results = (
                session.query(table.c.Name, table.c.Object_ID)
                .filter(
                    or_(
                        table.c.Object_Type == "Datatype",
                        and_(table.c.Object_Type == "Class", table.c.Name.startswith("GM_")),
                    )
                )
                .all()
            )

            return {row.Name: row.Object_ID for row in results}
        except Exception as e:
            logger.error(f"Fout bij ophalen van relevante objecten: {e}")
            return {}

    def render(self, args, schema: sch.Schema):
        target_session, target_metadata = self.get_database_session(args.outputfile)
        self.datatype_map = self.get_relevant_object_id_map(target_session, target_metadata)

        super().render(
            args,
            schema,
        )
