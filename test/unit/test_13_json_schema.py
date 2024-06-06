import json

import jsonschema
from jsonschema import validate

import crunch_uml.schema as sch
from crunch_uml import cli, const, db


def test_import_schuldhulp():
    test_args = ["import", "-f", "./test/data/Model Schuldhulpverlening.xml", "-t", "eaxmi", "-db_create"]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)
    assert schema.count_package() == 3
    assert schema.count_enumeratie() == 5
    assert schema.count_class() == 61
    assert schema.count_attribute() == 127
    assert schema.count_enumeratieliteral() == 20

    test_args = [
        "transform",
        "-ttp",
        "copy",
        "-sch_to",
        "schuldhulp",
        "-rt_pkg",
        "EAPK_06C51790_1F81_4ac4_8E16_5177352EF2E1",
    ]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database, 'schuldhulp')
    assert schema.count_package() == 1
    assert schema.count_enumeratie() == 5
    assert schema.count_class() == 32
    assert schema.count_attribute() == 127
    assert schema.count_enumeratieliteral() == 20

    test_args = [
        "-sch",
        "schuldhulp",
        "export",
        "-t",
        "json_schema",
        "--output_class_id",
        "EAID_839017B2_0F95_42d0_AB2B_E873636340DA",
        "-f",
        "./test/output/json_schema.json",
    ]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database, 'schuldhulp')
    assert schema.count_package() == 1


def test_validate_json_schema():
    def load_json_file(file_path):
        with open(file_path, 'r') as file:
            return json.load(file)

    # Path to the JSON schema file to be tested
    file_path = "./test/output/json_schema_Schuldhulptraject.json"

    # Load the JSON schema from the file
    json_schema = load_json_file(file_path)

    # Load the meta-schema from the local file
    meta_schema_file_path = "./test/data/meta-schema.json"
    meta_schema = load_json_file(meta_schema_file_path)

    # Use try-except to catch ValidationError and print detailed error message
    try:
        validate(instance=json_schema, schema=meta_schema)
    except jsonschema.exceptions.ValidationError as e:
        print(f"Validation error: {e.message}")
        print(f"Schema path: {e.schema_path}")
        print(f"Instance path: {e.path}")
        assert False, f"Validation failed: {e.message}"
    except jsonschema.exceptions.SchemaError as e:
        print(f"Schema error: {e.message}")
        assert False, f"Schema contains errors: {e.message}"
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        assert False, f"Unexpected error occurred: {str(e)}"
    else:
        assert True
