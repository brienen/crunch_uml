import json
import os

import jsonschema
from jsonschema import validate

# import crunch_uml.schema as sch
from crunch_uml import cli


def test_importAndTransform_schuldhulp():
    dir = "./test/output/"

    # Inlezen model Sociaal Domein
    test_args = [
        "import",
        "-t",
        "eaxmi",
        "-f",
        "./test/data/Gemeentelijk Gegevensmodel XMI2.1 Sociaal Domein.xml",
        "-db_create",
    ]
    cli.main(test_args)

    # database = db.Database(const.DATABASE_URL, db_create=False)
    # schema = sch.Schema(database)
    # assert schema.count_package() == 3
    # assert schema.count_enumeratie() == 5
    # assert schema.count_class() == 61
    # assert schema.count_attribute() == 127
    # assert schema.count_enumeratieliteral() == 20

    # Transformeren datamodel naar informatiemodel Schuldhulpverlening
    test_args = [
        "transform",
        "-ttp",
        "plugin",
        "-sch_to",
        "schuldhulp_informatiemodel",
        "-rt_pkg",
        "EAPK_06C51790_1F81_4ac4_8E16_5177352EF2E1",
        "--plugin_class_name",
        "DDASPluginInformatiemodel",
        "--plugin_file_name",
        "./test/data/ddasplugin_informatiemodel.py",
    ]
    cli.main(test_args)

    # database = db.Database(const.DATABASE_URL, db_create=False)
    # schema = sch.Schema(database, 'schuldhulp_informatiemodel')
    # assert schema.count_package() == 1
    # assert schema.count_enumeratie() == 5
    # assert schema.count_class() == 32
    # assert schema.count_attribute() == 127
    # assert schema.count_enumeratieliteral() == 20

    # Transformeren datamodel naar informatiemodel Schuldhulpverlening
    test_args = [
        "transform",
        "-ttp",
        "plugin",
        "-sch_from",
        "schuldhulp_informatiemodel",
        "-sch_to",
        "schuldhulp_uitwisselmodel",
        "-rt_pkg",
        "EAPK_06C51790_1F81_4ac4_8E16_5177352EF2E1",
        "--plugin_class_name",
        "DDASPluginUitwisselmodel",
        "--plugin_file_name",
        "./test/data/ddasplugin_uitwisselmodel.py",
    ]
    cli.main(test_args)

    # database = db.Database(const.DATABASE_URL, db_create=False)
    # schema = sch.Schema(database, 'schuldhulp_uitwisselmodel')
    # assert schema.count_package() == 1
    # assert schema.count_enumeratie() == 5
    # assert schema.count_class() == 32
    # assert schema.count_attribute() == 127
    # assert schema.count_enumeratieliteral() == 20

    # Exporteer JSON-definitie van schuldhulp
    test_args = [
        "-sch",
        "schuldhulp_uitwisselmodel",
        "export",
        "-t",
        "json_schema",
        "-f",
        "./test/output/schema.json",
        "--output_class_id",
        "EAID_6b4326e3_eb4e_41d2_902b_0bff06604f63",
        "-js_url",
        "https://raw.githubusercontent.com/brienen/ddas/main/json_schema_Uitwisselmodel.json",
    ]
    cli.main(test_args)
    validate_json_schema(dir)

    # Exporteer JSON-definitie van schuldhulp
    test_args = [
        "-sch",
        "schuldhulp_informatiemodel",
        "export",
        "-t",
        "jinja2",
        "--output_jinja2_template",
        "ddas_markdown.j2",
        "-f",
        "./test/output/def.md",
    ]

    cli.main(test_args)

    monfilename = f'{dir}def_Model Schuldhulpverlening.md'
    assert os.path.exists(monfilename)
    assert (
        open(monfilename, 'r')
        .read()
        .find(
            'Begeleiding voor clienten in het kader van schuldhulpdienstverlening, die kan bestaan uit: 1. budgetbeheer'
            ' 2. beschermingsbewind 3. budgetcoaching'
        )
    )
    assert open(monfilename, 'r').read().find('### Schuldhulptraject')


def validate_json_schema(dir):
    def load_json_file(file_path):
        with open(file_path, 'r') as file:
            return json.load(file)

    # Path to the JSON schema file to be tested
    file_path = f"{dir}schema_Uitwisselmodel.json"

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
