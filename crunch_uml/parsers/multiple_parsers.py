import json
import logging
import os

import pandas as pd
import requests

from crunch_uml import db
from crunch_uml.parsers.parser import Parser, ParserRegistry

logger = logging.getLogger()


def store_data(entity_name, data, database):
    # session = SessionLocal()
    # Retrieve all models dynamically
    base = db.Base
    session = database.get_session()

    logger.debug(f"Parsing {len(data)} entities with name {entity_name}")
    # Model class associated with the table
    entity = base.model_lookup_by_table_name(entity_name)
    if not entity:
        logger.warning(f"Entity not found with tablename: {entity_name}.")
        return

    # Als er een ID in de data aanwezig is, zoek dan naar een bestaand record
    if "id" in data:
        if existing_entity := session.query(entity).filter_by(id=data["id"]).first():
            for key, value in data.items():
                if value is not None and value != '':
                    setattr(existing_entity, key, value)
            logger.debug(f"Updated {entity_name} with ID {data['id']}.")
            database.save(existing_entity)
        else:
            # ID was aanwezig, maar geen overeenkomstige record werd gevonden
            logger.debug(f"No {entity_name} found with ID {data['id']}, creating a new record.")
            new_entity = entity(**data)
            database.save(new_entity)
    else:
        logger.warning(f"Could not save entity with table '{entity_name}' to database: no imakd present: {data}.")


@ParserRegistry.register(
    "json", descr='Generic parser that parses JSON-files, and looks for table and column definitions.'
)
class JSONParser(Parser):
    def parse(self, args, database: db.Database):
        logger.info(f"Starting parsing JSON file {args.inputfile}")
        # sourcery skip: raise-specific-error
        try:
            if args.inputfile is not None:
                with open(args.inputfile, 'r') as f:
                    parsed_data = json.load(f)
            elif args.url is not None:
                response = requests.get(args.url)
                response.raise_for_status()  # Zorg dat we een fout krijgen als de download mislukt
                parsed_data = response.json()  #

            tables = db.getTables()
            # Ga ervan uit dat het JSON-bestand een structuur heeft zoals eerder beschreven
            for entity_name, records in parsed_data.items():
                if entity_name in tables:
                    for record in records:
                        store_data(entity_name, record, database)
        except json.JSONDecodeError as ex:
            msg = f"File with name {args.inputfile} is not a valid JSON-file, aborting with message {ex.msg}"
            logger.error(msg)
            raise Exception(msg) from ex
        logger.info(f"Ended parsing JSON file {args.inputfile} with success")


@ParserRegistry.register(
    "xlsx",
    descr=(
        'Generic parser that parses Excel files, and excpect one or more worksheets that correspond with the names of'
        ' one or more of the tables.'
    ),
)
class XLXSParser(Parser):
    def parse(self, args, database: db.Database):
        # sourcery skip: raise-specific-error
        logger.info(f"Starting parsing Excel file {args.inputfile}")

        try:
            # Lees het Excel-bestand
            xls = pd.ExcelFile(args.inputfile if args.inputfile is not None else args.url)

            tables = db.getTables()
            # Loop door elk tabblad in het Excel-bestand
            for sheet_name in xls.sheet_names:
                if sheet_name in tables:
                    # Lees de gegevens van het huidige tabblad als een lijst van woordenboeken
                    records = xls.parse(sheet_name).to_dict(orient='records')

                    for record in records:
                        store_data(sheet_name, record, database)

        except Exception as ex:
            msg = f"Error while parsing the Excel file {args.inputfile}: {str(ex)}"
            logger.error(msg)
            raise Exception(msg) from ex

        logger.info(f"Ended parsing Excel file {args.inputfile} with success")


@ParserRegistry.register(
    "csv", descr='Generic parser that parses one CSV file, and excpect its name to be in the list of tables.'
)
class CSVParser(Parser):
    def parse(self, args, database: db.Database):
        logger.info(f"Starting parsing CSV file {args.inputfile}")

        try:
            # Haal de entiteitsnaam uit de bestandsnaam (verwijder het .csv-deel)
            entity_name = os.path.splitext(os.path.basename(args.inputfile))[0]

            tables = db.getTables()
            if entity_name in tables:
                # Lees het CSV-bestand in een dataframe
                df = pd.read_csv(args.inputfile if args.inputfile is not None else args.url)

                # Converteer het dataframe naar een lijst van woordenboeken (records)
                records = df.to_dict(orient='records')

                for record in records:
                    store_data(entity_name, record, database)

            else:
                logger.warning(f"Could not import file: no entity found with name {entity_name}")

        except Exception as ex:
            msg = f"Error while parsing the CSV file {args.inputfile}: {str(ex)}"
            logger.error(msg)
            raise Exception(msg) from ex

        logger.info(f"Ended parsing CSV file {args.inputfile} with success")
