import logging
from datetime import datetime

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import sessionmaker

import crunch_uml.schema as sch
from crunch_uml import const, util
from crunch_uml.exceptions import CrunchException
from crunch_uml.renderers.renderer import ModelRenderer, RendererRegistry

logger = logging.getLogger()


@RendererRegistry.register(
    "earepo",
    descr='Updates as Enterprise Architect v16 repository. '
    + 'Only updates existing Classes and attributes, Enumerations and literals, Packages and Associations. '
    + 'Does not add new things, updates only.'
    + 'provide the EA Repo through the --file parameter.',
)
class EARepoUpdater(ModelRenderer):
    '''
    Connects to an Enterprise Architect repository by treating it as a database
    Usualy SQLlite with the .qua extension.
    '''

    def get_database_session(self, database_url):
        # Als er geen volledige URL wordt meegegeven, behandel het als een SQLite-database
        if not database_url.startswith(('sqlite://', 'postgresql://', 'mysql://', 'oracle://')):
            if not database_url.endswith('.qea'):
                database_url += '.qea'
            database_url = f'sqlite:///{database_url}'

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
            major, minor = map(int, version.split('.'))

            if version_type == const.VERSION_STEP_MAJOR:
                major += 1
                minor = 0
            elif version_type == const.VERSION_STEP_MINOR:
                minor += 1
            return f"{major}.{minor}"
        except ValueError:
            logger.warning(f"Version '{version}' is not in the correct format.")
            return version

    def map_fields(self, data_dict, field_mapper):
        """
        Past de veldnamen in data_dict aan op basis van de field_mapper.
        """
        return {field_mapper.get(k, k): v for k, v in data_dict.items()}

    def update_existing_record(self, data_dict, table_name, session, metadata, version_type=None, field_mapper=None):
        ea_guid = const.EA_REPO_MAPPER['id']

        try:
            # Haal de tabelstructuur op
            table = self.get_table_structure(table_name, metadata)
            columns = table.columns.keys()

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
                logger.error(f"Kan record nu updaten, {ea_guid} is vereist in de data dictionary")
                return

            guid_value = util.fromEAGuid(data_dict[ea_guid])

            # Zoek naar het bestaande record op basis van GUID
            existing_record = session.query(table).filter_by(**{ea_guid: guid_value}).first()

            if existing_record:
                # Filter de data_dict om alleen kolommen in te voegen die bestaan in de tabel
                valid_data = {col: data_dict[col] for col in data_dict if col in table.columns.keys()}

                # Check of er iets is veranderd
                changes = {}
                for key, value in valid_data.items():
                    if getattr(existing_record, key) != value and key not in [
                        ea_guid,
                        const.EA_REPO_MAPPER['modified'],
                    ]:
                        changes[key] = value

                # Alleen updaten als er daadwerkelijk wijzigingen zijn
                if len(changes) > 0:
                    # Update het modified veld
                    if const.EA_REPO_MAPPER['modified'] in columns:
                        changes[const.EA_REPO_MAPPER['modified']] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    # Update het versienummer indien van toepassing
                    if const.EA_REPO_MAPPER['version'] in columns and version_type is not None:
                        current_version = getattr(existing_record, const.EA_REPO_MAPPER['version'])
                        new_version = self.increment_version(current_version, version_type)
                        changes[const.EA_REPO_MAPPER['version']] = new_version

                    # Voer de update uit
                    session.query(table).filter_by(**{ea_guid: guid_value}).update(changes)
                    # session.commit()
                    logger.debug(f"Record with GUID {guid_value} has been updated.")
                else:
                    logger.debug(f"No changes detected for record with GUID {guid_value}.")
            else:
                logger.info(f"No record found with GUID {guid_value}. No update performed.")
        except Exception as e:
            logger.error(f"Error while updating record with GUID {guid_value} with message: {e}")
            raise CrunchException(f"Error while updating record with GUID {guid_value} with message: {e}")

    def process_batch(
        self,
        source_data,
        target_table_name,
        target_session,
        target_metadata,
        version_type=None,
        field_mapper=None,
        batch_size=100,
    ):
        # Verwerk de data in batches
        for i in range(0, len(source_data), batch_size):
            batch = source_data[i : i + batch_size]
            for record in batch:
                self.update_existing_record(
                    record, target_table_name, target_session, target_metadata, version_type, field_mapper
                )

    def render(self, args, schema: sch.Schema):

        # Check to see if a list of Package ids is provided
        # if self.enforce_output_package_ids and args.output_package_ids is None:
        #    msg = "Usage of parameter --output_package_ids is enforced for this renderer. Not provided, exiting."
        #    logger.error(msg)
        #    raise CrunchException(msg)
        target_session, target_metadata = self.get_database_session(args.outputfile)
        if target_session and target_metadata:
            version_type = args.version_type
            logger.info(f"Updating EA Repository {args.outputfile} with version type {version_type}...")

            try:
                # Process all classes
                logger.info("Updating classes...")
                classes = schema.get_all_classes()
                dict_classes = [record.to_dict() for record in classes]
                self.process_batch(
                    dict_classes,
                    't_object',
                    target_session,
                    target_metadata,
                    version_type=version_type,
                    field_mapper=const.EA_REPO_MAPPER,
                )

                # Process all attributes
                logger.info("Updating attributes...")
                attributes = schema.get_all_attributes()
                dict_attributes = [record.to_dict() for record in attributes]
                self.process_batch(
                    dict_attributes,
                    't_attribute',
                    target_session,
                    target_metadata,
                    version_type=version_type,
                    field_mapper=const.EA_REPO_MAPPER_ATTRIBUTES,
                )

                # Process all literals
                logger.info("Updating literals...")
                literals = schema.get_all_literals()
                dict_literals = [record.to_dict() for record in literals]
                self.process_batch(
                    dict_literals,
                    't_attribute',
                    target_session,
                    target_metadata,
                    version_type=version_type,
                    field_mapper=const.EA_REPO_MAPPER_LITERALS,
                )

                # Process all enumerations
                logger.info("Updating enumerations...")
                enums = schema.get_all_enumerations()
                dict_enums = [record.to_dict() for record in enums]
                self.process_batch(
                    dict_enums,
                    't_object',
                    target_session,
                    target_metadata,
                    version_type=version_type,
                    field_mapper=const.EA_REPO_MAPPER,
                )

                # Process all packages
                logger.info("Updating packages...")
                packages = schema.get_all_packages()
                dict_packages = [record.to_dict() for record in packages]
                self.process_batch(
                    dict_packages,
                    't_object',
                    target_session,
                    target_metadata,
                    version_type=version_type,
                    field_mapper=const.EA_REPO_MAPPER,
                )
                self.process_batch(
                    dict_packages,
                    't_package',
                    target_session,
                    target_metadata,
                    version_type=version_type,
                    field_mapper=const.EA_REPO_MAPPER,
                )

                # Process all associations
                logger.info("Updating associations...")
                associations = schema.get_all_associations()
                dict_associations = [record.to_dict() for record in associations]
                self.process_batch(
                    dict_associations,
                    't_connector',
                    target_session,
                    target_metadata,
                    version_type=version_type,
                    field_mapper=const.EA_REPO_MAPPER_ASSOCIATION,
                )

                # Process all diagrams
                logger.info("Updating diagrams...")
                diagrams = schema.get_all_diagrams()
                dict_diagrams = [record.to_dict() for record in diagrams]
                self.process_batch(
                    dict_diagrams,
                    't_diagram',
                    target_session,
                    target_metadata,
                    version_type=version_type,
                    field_mapper=const.EA_REPO_MAPPER,
                )

                logger.info(f"All data updated in repo {args.outputfile}, commiting...")
                target_session.commit()
            except Exception as e:
                msg = f"Rolling back changes.... Error while updating classes with message: {e}."
                logger.error(msg)

                target_session.rollback()
                raise CrunchException(msg)
