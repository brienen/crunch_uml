import json
import logging
import os

import pandas as pd
import requests

import crunch_uml.schema as sch
from crunch_uml import const, db
from crunch_uml.exceptions import CrunchException
from crunch_uml.parsers.parser import Parser, ParserRegistry

logger = logging.getLogger()


class TransformableParser(Parser):
    column_mapper: dict[str, str] = {}
    update_only = False

    def store_data(self, entity_name, data, schema, update_only=False):
        # session = SessionLocal()
        # Retrieve all models dynamically
        base = db.Base
        session = schema.get_session()

        logger.debug(f"Parsing {len(data)} entities with name {entity_name}")
        # Model class associated with the table
        entity = base.model_lookup_by_table_name(entity_name)
        if not entity:
            logger.warning(f"Entity not found with tablename: {entity_name}.")
            return
        columns = db.getColumnNames(entity_name)

        # Als er een ID in de data aanwezig is, zoek dan naar een bestaand record
        if "id" in data:
            if existing_entity := session.query(entity).filter_by(id=data["id"], schema_id=schema.schema_id).first():
                for key, value in data.items():
                    if value is not None and value != "" and key != "id" and key in columns:
                        setattr(existing_entity, key, value)
                logger.debug(f"Updated {entity_name} with ID {data['id']}.")
                schema.save(existing_entity)
            else:
                if not update_only:
                    # ID was aanwezig, maar geen overeenkomstige record werd gevonden
                    logger.debug(f"No {entity_name} found with ID {data['id']}, creating a new record.")
                    filtered_data = {k: v for k, v in data.items() if k in columns}
                    new_entity = entity(**filtered_data)
                    schema.save(new_entity)
        else:
            if not update_only:
                logger.debug(
                    f"Could not save entity with table '{entity_name}' to schema {schema.schema_id}: no column id present:"
                    f" {data}."
                )
                new_entity = entity(**data)
                schema.save(new_entity)

    def map_record(self, column_mapper, record):
        """
        Hernoem kolomnamen in het record volgens de opgegeven mapper.
        :param record: Dictionary met originele data.
        :return: Getransformeerd record met hernoemde kolommen.
        """
        if column_mapper:
            try:
                column_mapper = json.loads(column_mapper)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON for mapper: {column_mapper}. Error: {e}")

            if len(column_mapper) > 0:
                record = {column_mapper.get(k, k): v for k, v in record.items()}
            else:
                logger.warning("Empty mapper provided, no columns will be renamed and original record saved.")

        # Controleer en transformeer het 'id' veld
        if "id" in record and isinstance(record["id"], str):
            id_value = record["id"]
            if id_value.startswith("{") and id_value.endswith("}"):
                # Eerst testen of het om een package gaat
                if "parent_package_id" in record:
                    suffix = "EAPK_"
                else:
                    suffix = "EAID_"

                # Voer een transformatie uit (bijvoorbeeld: verwijder { en })
                record["id"] = suffix + (id_value[1:-1]).replace("-", "_")  # Verwijdert de { en }
                logger.debug(f"Transformed 'id' field: {id_value} -> {record['id']}")

        return record


@ParserRegistry.register(
    "json",
    descr="Generic parser that parses JSON-files, and looks for table and column definitions.",
)
class JSONParser(TransformableParser):

    def get_data_subset(self, data, args):
        return data

    def parse(self, args, schema: sch.Schema):
        logger.info(f"Starting parsing JSON file {args.inputfile}")
        # sourcery skip: raise-specific-error
        try:
            if args.inputfile is not None:
                with open(args.inputfile, "r") as f:
                    parsed_data = json.load(f)
            elif args.url is not None:
                response = requests.get(args.url)
                response.raise_for_status()  # Zorg dat we een fout krijgen als de download mislukt
                parsed_data = response.json()  #
            parsed_data = self.get_data_subset(parsed_data, args)

            tables = db.getTables()
            # Ga ervan uit dat het JSON-bestand een structuur heeft zoals eerder beschreven
            for entity_name, records in parsed_data.items():
                if entity_name in tables and entity_name != "schemas":
                    for record in records:
                        record = self.map_record(args.mapper, record)
                        self.store_data(entity_name, record, schema, update_only=args.update_only)
        except json.JSONDecodeError as ex:
            msg = f"File with name {args.inputfile} is not a valid JSON-file, aborting with message {ex.msg}"
            logger.error(msg)
            raise CrunchException(msg) from ex
        logger.info(f"Ended parsing JSON file {args.inputfile} with success")


@ParserRegistry.register(
    "i18n",
    descr=f"Parser that reads i18n file and stores the values in the database. Use --language to specify language. (default: {const.DEFAULT_LANGUAGE})",
)
class I18nParser(JSONParser):

    def store_data(self, entity_name, data, schema, update_only=False):
        update_only = True  # i18n records should always be updated
        super().store_data(entity_name, data, schema, update_only)

    def get_data_subset(self, data, args):
        # Bepaal welke taal moet worden verwerkt
        language = args.language if args.language else const.LANGUAGE.DEFAULT
        if language not in data:
            raise ValueError(f"Language '{language}' not found in the i18n file.")

        return data[language]

    def map_record(self, column_mapper, record):
        super().map_record(column_mapper, record)

        # i18n records always are in the form of RECORD_TYPE_INDEXED: key: {record}
        key, value = next(iter(record.items()))
        record = value
        record["id"] = key
        return record


@ParserRegistry.register(
    "xlsx",
    descr=(
        "Generic parser that parses Excel files, and excpect one or more worksheets that correspond with the names of"
        " one or more of the tables."
    ),
)
class XLXSParser(TransformableParser):
    def parse(self, args, schema: sch.Schema):
        # sourcery skip: raise-specific-error
        logger.info(f"Starting parsing Excel file {args.inputfile}")

        try:
            # Lees het Excel-bestand
            xls = pd.ExcelFile(args.inputfile if args.inputfile is not None else args.url)

            tables = db.getTables()
            # Loop door elk tabblad in het Excel-bestand
            for sheet_name in xls.sheet_names:
                if sheet_name in tables and sheet_name != "schemas":
                    # Lees de gegevens van het huidige tabblad als een lijst van woordenboeken
                    records = xls.parse(sheet_name).to_dict(orient="records")

                    for record in records:
                        record = self.map_record(args.mapper, record)
                        self.store_data(sheet_name, record, schema, update_only=args.update_only)

        except Exception as ex:
            msg = f"Error while parsing the Excel file {args.inputfile}: {str(ex)}"
            logger.error(msg)
            raise CrunchException(msg) from ex

        logger.info(f"Ended parsing Excel file {args.inputfile} with success")


@ParserRegistry.register(
    "csv",
    descr="Generic parser that parses one CSV file, and excpect its name to be in the list of tables.",
)
class CSVParser(TransformableParser):
    def parse(self, args, schema: sch.Schema):
        logger.info(f"Starting parsing CSV file {args.inputfile}")

        try:
            # Haal de entiteitsnaam uit de bestandsnaam (verwijder het .csv-deel)
            if not args.entity_name or args.entity_name == "":
                entity_name = os.path.splitext(os.path.basename(args.inputfile))[0]
            else:
                entity_name = args.entity_name

            tables = db.getTables()
            if entity_name in tables and entity_name != "schemas":
                # Lees het CSV-bestand in een dataframe
                df = pd.read_csv(args.inputfile if args.inputfile is not None else args.url)

                # Converteer het dataframe naar een lijst van woordenboeken (records)
                records = df.to_dict(orient="records")

                for record in records:
                    record = self.map_record(args.mapper, record)
                    self.store_data(entity_name, record, schema, update_only=args.update_only)

            else:
                logger.warning(f"Could not import file: no entity found with name {entity_name}")

        except Exception as ex:
            msg = f"Error while parsing the CSV file {args.inputfile}: {str(ex)}"
            logger.error(msg)
            raise CrunchException(msg) from ex

        logger.info(f"Ended parsing CSV file {args.inputfile} with success")
