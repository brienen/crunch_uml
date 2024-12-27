import json
import logging
import os

import pandas as pd
import sqlalchemy
from sqlalchemy.ext.hybrid import hybrid_property

import crunch_uml.schema as sch
from crunch_uml import const, db, lang, util
from crunch_uml.renderers.renderer import Renderer, RendererRegistry

logger = logging.getLogger()


def object_as_dict(obj, session):
    """
    Converteert een SQLAlchemy-modelobject naar een dictionary, inclusief hybride attributen en kolommen.
    :param obj: Het SQLAlchemy-object.
    :return: Dictionary met alle kolom- en hybride attributen.
    """
    # Haal kolom-attributen op
    col_attrs = {attr.key for attr in sqlalchemy.inspect(obj).mapper.column_attrs}
    hyb_attrs = {
        attr
        for attr in dir(obj.__class__)
        if hasattr(getattr(obj.__class__, attr), 'descriptor')
        and isinstance(getattr(obj.__class__, attr).descriptor, hybrid_property)
    }
    attrs = col_attrs | hyb_attrs

    dict_obj = {key: getattr(obj, key) for key in dir(obj) if key in attrs and hasattr(obj, key)}

    # Dirty hack, but only way: set package domain name to domain_iv3
    if 'domein_iv3' in attrs and (isinstance(obj, db.Class) or isinstance(obj, db.Enumeratie)):
        package = session.query(db.Package).filter(db.Package.id == obj.package_id).one_or_none()
        dict_obj['domein_iv3'] = package.domain_name if package is not None else None

    return dict_obj


@RendererRegistry.register(
    "json",
    descr="Renders JSON document where each element corresponds to one of the tables in the datamodel.",
)
class JSONRenderer(Renderer):

    def get_included_columns(self):
        # Define the list of column names to include in the output
        # If this list is empty, all columns will be included
        return []

    def get_record_type(self):
        return const.RECORD_TYPE_RECORD

    def get_all_data(self, args, schema: sch.Schema, empty_values=True):
        # Retrieve all models dynamically
        base = db.Base
        models = base.metadata.tables
        session = schema.get_session()
        all_data = {}

        # Define the list of column names to include in the output
        # If this list is empty, all columns will be included
        included_columns = self.get_included_columns()

        for table_name, table in models.items():
            # Model class associated with the table
            model = base.model_lookup_by_table_name(table_name)
            if (
                not model or self.get_record_type() == const.RECORD_TYPE_INDEXED and "id" not in model.__table__.columns
            ):  # In case of a junction table
                continue

            records = session.query(model).filter(model.schema_id == schema.schema_id).all()
            data = [object_as_dict(record, session) for record in records]

            # Filter columns based on included_columns, unless included_columns is empty
            filtered_data = []
            for record in data:
                if included_columns and len(included_columns) > 0:
                    filtered_record = {
                        key: value
                        for key, value in record.items()
                        if key in included_columns and (empty_values or value is not None)
                    }
                else:
                    filtered_record = record  # Include all columns if included_columns is empty
                if len(filtered_record) > 0:
                    filtered_data.append(
                        filtered_record
                        if self.get_record_type() == const.RECORD_TYPE_RECORD
                        else {record["id"]: filtered_record}
                    )

            all_data[table_name] = filtered_data
        return all_data

    def rename_keys(self, input_dict, key_mapper):
        """
        Hernoem keys in een dictionary (inclusief geneste dictionaries) volgens een gegeven mapper.
        :param input_dict: De originele dictionary waarvan de keys moeten worden hernoemd.
        :param key_mapper: Een dictionary waarin oude keys worden gekoppeld aan nieuwe keys.
        :return: Een nieuwe dictionary met hernoemde keys.
        """
        if key_mapper is None or len(key_mapper) == 0:
            return input_dict

        renamed_dict = {}
        for k, v in input_dict.items():
            # Hernoem de key volgens de mapper
            new_key = key_mapper.get(k, k)

            # Controleer of de waarde een geneste dictionary is
            if isinstance(v, dict):
                # Roep de functie recursief aan voor de geneste dictionary
                renamed_dict[new_key] = self.rename_keys(v, key_mapper)
            elif isinstance(v, list):
                # Als de waarde een lijst is, controleer of elementen dictionaries zijn
                renamed_dict[new_key] = [
                    self.rename_keys(item, key_mapper) if isinstance(item, dict) else item for item in v
                ]
            else:
                # Anders gebruik de originele waarde
                renamed_dict[new_key] = v
        return renamed_dict

    def render(self, args, schema: sch.Schema):
        all_data = self.get_all_data(args, schema)
        all_data = self.rename_keys(all_data, json.loads(args.mapper))
        with open(args.outputfile, "w") as json_file:
            json.dump(all_data, json_file, default=str, indent=4, sort_keys=True)


@RendererRegistry.register(
    "i18n",
    descr=f"Renders a i18n file containing all tables with keys to the translatable fields ({const.LANGUAGE_TRANSLATE_FIELDS}) Also translates to a specified language.",
)
class I18nRenderer(JSONRenderer):

    def get_included_columns(self):
        # Define the list of column names to include in the output
        # If this list is empty, all columns will be included
        return const.LANGUAGE_TRANSLATE_FIELDS

    def get_record_type(self):
        return const.RECORD_TYPE_INDEXED

    def translate_data(self, data, to_language, from_language="auto", update_i18n=True, original_i18n={}):
        logger.info(
            f"Starting Translating data to language '{to_language}'. This may take a while: {util.count_dict_elements(data)} entries..."
        )
        translated_data = {}
        for section, entries in data.items():
            logger.info(f"Translating section {section}...")
            translated_data[section] = []
            original_i18n_section = original_i18n.get(to_language, {}).get(section, [])
            for entry in entries:
                translated_record = {}
                for key, record in entry.items():
                    original_record = [record for record in original_i18n_section if key in record]
                    original_record = original_record[0] if len(original_record) > 0 else {}
                    original_record = original_record.get(key, {})
                    for field, value in record.items():
                        if not isinstance(value, str):
                            next
                        if not (util.is_empty_or_none(value)):
                            if update_i18n:
                                # Check if the field is already translated
                                translated_value = original_record.get(field, None)
                                if translated_value is None:
                                    # Translate the value
                                    translated_value = lang.translate(
                                        value,
                                        to_language=to_language,
                                        from_language=from_language,
                                        max_retries=1,
                                    )
                                translated_record[field] = translated_value
                            else:
                                translated_record[field] = lang.translate(  #
                                    value,
                                    to_language=to_language,
                                    from_language=from_language,
                                    max_retries=1,
                                )
                translated_data[section].append({key: translated_record})

        logger.info(f"Finished translating data to language '{to_language}'.")
        return translated_data

    def render(self, args, schema: sch.Schema):

        logger.info(f"Starting rendering i18n file {args.outputfile}...")

        # Initialize the i18n structure
        i18n_data = {}
        if os.path.exists(args.outputfile):
            # If the file exists, check if it's a valid JSON (i18n) file and load it
            with open(args.outputfile, "r", encoding="utf-8") as json_file:
                try:
                    i18n_data = json.load(json_file)
                except json.JSONDecodeError:
                    raise ValueError(f"The file {args.outputfile} is not a valid JSON file.")

            if not isinstance(i18n_data, dict):
                raise ValueError(f"The file {args.outputfile} does not contain a valid i18n structure.")

        # Retrieve all data
        all_data = self.get_all_data(args, schema, empty_values=False)
        if args.translate:
            all_data = self.translate_data(
                all_data, args.language, from_language=args.from_language, update_i18n=True, original_i18n=i18n_data
            )

        # Update the i18n data with the new language entry
        i18n_data[args.language] = all_data

        # Map fields
        i18n_data = self.rename_keys(i18n_data, json.loads(args.mapper))

        # Controleer of het bestand al bestaat
        if not os.path.exists(args.outputfile):
            logger.info(f"Vertaalbestand {args.outputfile} bestaat niet, maak een nieuw bestand aan...")

        # Write the updated i18n data back to the file
        with open(args.outputfile, "w", encoding="utf-8") as json_file:
            json.dump(i18n_data, json_file, ensure_ascii=False, indent=4, default=str)

        logger.info(f"Rendering i18n file {args.outputfile} success")


@RendererRegistry.register(
    "csv",
    descr="Renders multiple CSV files where each file corresponds to one of the tables in the datamodel.",
)
class CSVRenderer(Renderer):
    def render(self, args, schema: sch.Schema):
        # Retrieve all models dynamically
        base = db.Base
        models = base.metadata.tables
        session = schema.get_session()
        entity_name = args.entity_name

        for table_name, table in models.items():
            # Model class associated with the table
            model = base.model_lookup_by_table_name(table_name)
            if not model:  # In geval van koppeltabel
                continue

            # check of entity_name is gegeven en niet gelijk is aan table_name
            if entity_name is not None and entity_name != table_name:
                continue

            # Retrieve data
            records = session.query(model).filter(model.schema_id == schema.schema_id).all()
            df = pd.DataFrame([object_as_dict(record, session) for record in records])

            # Map columns
            mapper = json.loads(args.mapper)
            if mapper is not None and len(mapper) > 0:
                df = df.rename(columns=mapper)

            df.to_csv(f"{args.outputfile}_{table_name}.csv", index=False)
