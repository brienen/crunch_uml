import json
import os

import crunch_uml.schema as sch
from crunch_uml import cli, const, db


def are_json_files_equal(file1_path, file2_path):
    try:
        # Open en laad het eerste JSON-bestand
        with open(file1_path, 'r') as file1:
            data1 = json.load(file1)

        # Open en laad het tweede JSON-bestand
        with open(file2_path, 'r') as file2:
            data2 = json.load(file2)

        # Vergelijk de twee JSON-structuren
        return data1 == data2

    except Exception as e:
        print(f"Er is een fout opgetreden tijdens het vergelijken van de bestanden: {str(e)}")
        return False


def test_json_parser_renderer():
    # sourcery skip: extract-duplicate-method, move-assign-in-block
    inputfile = "./test/output/Monumenten_import.json"
    outputfile = "./test/output/Monumenten_export.json"

    # import monumenten into clean database
    test_args = ["import", "-f", "./test/data/GGM_Monumenten_EA2.1.xml", "-t", "eaxmi", "-db_create"]
    cli.main(test_args)

    # Check if content is correctly loaded
    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)

    assert schema.count_package() == 3
    assert schema.count_enumeratie() == 1
    assert schema.count_class() == 10
    assert schema.count_attribute() == 40
    assert schema.count_enumeratieliteral() == 2

    # export to json
    test_args = ["export", "-f", inputfile, "-t", "json"]
    cli.main(test_args)
    assert os.path.exists(inputfile)

    # import json to clean database
    test_args = ["import", "-f", inputfile, "-t", "json", "-db_create"]
    cli.main(test_args)

    # Check if content is correctly loaded
    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)

    assert schema.count_package() == 3
    assert schema.count_enumeratie() == 1
    assert schema.count_class() == 10
    assert schema.count_attribute() == 40
    assert schema.count_enumeratieliteral() == 2

    # export to json
    test_args = ["export", "-f", outputfile, "-t", "json"]
    cli.main(test_args)
    assert os.path.exists(outputfile)

    # Check if the contents of the files are equal
    assert are_json_files_equal(inputfile, outputfile)

    # Cleanup
    os.remove(outputfile)


def test_json_parser_and_changes():
    inputfile = "./test/output/Monumenten_import.json"
    change_url = "https://raw.githubusercontent.com/brienen/crunch_uml/main/test/data/Monumenten_changes.json"

    # import inputfile into clean database
    test_args = ["import", "-f", inputfile, "-t", "json", "-db_create"]
    cli.main(test_args)

    # import changes into database
    test_args = ["import", "-t", "json", "-url", change_url]
    cli.main(test_args)

    # Check if content is correctly loaded
    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)

    assert schema.count_package() == 3
    assert schema.count_enumeratie() == 1
    assert schema.count_class() == 10
    assert schema.count_attribute() == 40
    assert schema.count_enumeratieliteral() == 2

    # Check if changes are correctly loaded
    clazz = schema.get_class('EAID_54944273_F312_44b2_A78D_43488F915429')
    assert clazz.toelichting == 'Hallo Test'
    package = schema.get_package('EAPK_45B88627_6F44_4b6d_BE77_3EC51BBE679E')
    assert package.definitie == 'Hallo Test'

    # Check if other things are unchanged
    clazz = schema.get_class('EAID_9775E778_DBF8_4122_94CE_551466B62F46')
    assert clazz.name == const.ORPHAN_CLASS

    # Cleanup
    os.remove(inputfile)
