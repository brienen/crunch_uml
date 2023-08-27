import json
import os

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
    inputfile = "./test/data/Monumenten.json"
    outputfile = "./test/output/Monumenten.json"

    # import inputfile into clean database and export contents to outputfile
    test_args = ["-it", "json", "-if", inputfile, "-ot", "json", "-of", outputfile, "-db_create"]
    cli.main(test_args)
    assert os.path.exists(outputfile)

    # Check if content is correctly loaded
    database = db.Database(const.DATABASE_URL, db_create=False)
    assert database.count_package() == 3
    assert database.count_enumeratie() == 1
    assert database.count_class() == 10
    assert database.count_attribute() == 40
    assert database.count_enumeratieliteral() == 2

    # Check if the contents of the files are equal
    assert are_json_files_equal(inputfile, outputfile)

    # Cleanup
    os.remove(outputfile)


def test_json_parser_and_changes():
    inputfile = "./test/data/Monumenten.json"
    changefile = "./test/data/Monumenten_changes.json"

    # import inputfile into clean database
    test_args = ["-it", "json", "-if", inputfile, "-db_create"]
    cli.main(test_args)

    # import changes into database
    test_args = ["-it", "json", "-if", changefile]
    cli.main(test_args)

    # Check if content is correctly loaded
    database = db.Database(const.DATABASE_URL, db_create=False)
    assert database.count_package() == 3
    assert database.count_enumeratie() == 1
    assert database.count_class() == 10
    assert database.count_attribute() == 40
    assert database.count_enumeratieliteral() == 2

    # Check if changes are correctly loaded
    clazz = database.get_class('EAID_54944273_F312_44b2_A78D_43488F915429')
    assert clazz.toelichting == 'Hallo Test'
    package = database.get_package('EAPK_45B88627_6F44_4b6d_BE77_3EC51BBE679E')
    assert package.descr == 'Hallo Test'

    # Check if other things are unchanged 
    clazz = database.get_class('EAID_9775E778_DBF8_4122_94CE_551466B62F46')
    assert clazz.name == '<Orphan Class>'



