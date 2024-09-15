import json
import os
import shutil
import sqlite3

import pytest

import crunch_uml.schema as sch
from crunch_uml import cli, const, db, util

EA_DB = "./test/output/Monumenten.qea"


def getRecordFromEARepository(table, ea_guid):

    # Test eerst de waarde in de EA Repository
    # Verbinding maken met de Monumenten.qea SQLite database
    conn = sqlite3.connect(EA_DB)

    # Instellen van de row factory om resultaten als dictionaries te krijgen
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table} WHERE ea_guid = '{ea_guid}'")
    record = cursor.fetchone()

    # Database verbinding sluiten
    conn.close()

    return record


@pytest.fixture(scope="function", autouse=True)
def copy_test_files():
    # Pad naar de bronbestanden
    source_files = [
        ("./test/data/Monumenten.qea", EA_DB),
    ]

    # Zorg ervoor dat de testdata-map bestaat
    os.makedirs("./test/output", exist_ok=True)

    # Kopieer de bestanden naar de testdata-map
    for source, destination in source_files:
        shutil.copyfile(source, destination)

    yield  # Test wordt uitgevoerd na deze yield

    # Opruimen na de test als dat nodig is
    # Bijvoorbeeld: os.remove(destination)


def test_import_monumenten():
    outputfile = "./test/output/Monumenten.i18n.json"
    duitse_vertaling = "./test/data/Monumenten.i18n.json"

    test_args = [
        "import",
        "-f",
        "./test/data/GGM_Monumenten_EA2.1.xml",
        "-t",
        "eaxmi",
        "-db_create",
    ]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)
    assert schema.count_package() == 3
    assert schema.count_enumeratie() == 1
    assert schema.count_class() == 10
    assert schema.count_attribute() == 40
    assert schema.count_enumeratieliteral() == 2

    # export to json
    test_args = ["export", "-f", outputfile, "-t", "i18n", "--language", "nl"]
    cli.main(test_args)
    test_args = [
        "export",
        "-f",
        outputfile,
        "-t",
        "i18n",
        "--language",
        "en",
        "--translate",
        "True",
        "--from_language",
        "nl",
    ]
    cli.main(test_args)
    assert os.path.exists(outputfile)
    assert util.is_valid_i18n_file(outputfile)
    print("test_import_monumenten passed")

    # Open en laad het eerste JSON-bestand
    data = None
    with open(outputfile, "r") as file1:
        data = json.load(file1)
        ambacht = data["nl"]["classes"][0]["EAID_54944273_F312_44b2_A78D_43488F915429"]
        ambacht["name"] = "Ambacht_name"
        ambacht["alias"] = "Ambacht_alias"
        ambacht["definitie"] = "Ambacht_definitie"
        ambacht["toelichting"] = "Ambacht_toelichting"
        ambacht["stereotype"] = "Ambacht_stereotype"
        ambacht["synoniemen"] = "Ambacht_synoniemen"
        data["nl"]["classes"][0]["EAID_54944273_F312_44b2_A78D_43488F915429"] = ambacht

    with open(outputfile, "w") as json_file:
        json.dump(data, json_file, ensure_ascii=False, indent=4, default=str)

    test_args = ["import", "-f", outputfile, "-t", "i18n", "--language", "nl"]
    cli.main(test_args)
    print("data saved")

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)
    clazz = schema.get_class("EAID_54944273_F312_44b2_A78D_43488F915429")
    assert clazz.name == "Ambacht_name"
    assert clazz.alias == "Ambacht_alias"
    assert clazz.definitie == "Ambacht_definitie"
    assert clazz.toelichting == "Ambacht_toelichting"
    assert clazz.stereotype == "Ambacht_stereotype"
    assert clazz.synoniemen == "Ambacht_synoniemen"
    print("test_import_monumenten passed")

    # Lees Duitse vertaling in
    test_args = ["import", "-f", duitse_vertaling, "-t", "i18n", "--language", "no"]
    cli.main(test_args)

    # Voer nu de changes door en kijk of de waarden zijn aangepast
    # export to json
    test_args = ["export", "-f", EA_DB, "-t", "earepo", "--tag_strategy", "update"]
    cli.main(test_args)
    print("test_import_monumenten passed")

    # Testen of het record voldoet aan bepaalde voorwaarden
    record = getRecordFromEARepository("t_object", "{54944273-F312-44b2-A78D-43488F915429}")
    assert record is not None, "Record met de naam 'MonumentNaam' niet gevonden."
    assert record[const.EA_REPO_MAPPER["name"]] == "Håndverk_name"
