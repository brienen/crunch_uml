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


def countTagsOfObject(object_id):
    # Verbinding maken met de Monumenten.qea SQLite database
    conn = sqlite3.connect(EA_DB)

    # Instellen van de row factory om resultaten als dictionaries te krijgen
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()
    # Voer een COUNT(*) query uit om het aantal tags te tellen
    cursor.execute(
        "SELECT COUNT(*) as tag_count FROM t_objectproperties WHERE Object_ID = ?",
        (object_id,),
    )
    result = cursor.fetchone()

    # Database verbinding sluiten
    conn.close()

    # Retourneer het aantal tags
    return result["tag_count"] if result else 0


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

    record = getRecordFromEARepository("t_object", "{54944273-F312-44b2-A78D-43488F915429}")
    # Testen of de records schoon in de database staan
    assert record is not None, "Record met de naam 'MonumentNaam' niet gevonden."
    assert record[const.EA_REPO_MAPPER["name"]] == "Ambacht"
    assert (
        record[const.EA_REPO_MAPPER["definitie"]]
        == "Beroep waarbij een handwerker met gereedschap eindproducten maakt."
    )
    assert record[const.EA_REPO_MAPPER["author"]] == "Arjen Brienen"
    assert record[const.EA_REPO_MAPPER["stereotype"]] is None
    assert record[const.EA_REPO_MAPPER["alias"]] is None
    modified = util.parse_date(str(record[const.EA_REPO_MAPPER["modified"]]))
    version = record[const.EA_REPO_MAPPER["version"]]
    major_original, minor_original = map(int, version.split("."))

    # record ophalen wat niet aangepast wordt
    unchange_bouwtype = getRecordFromEARepository("t_object", "{5E9DAFBB-C9B5-4706-A43D-07AD4979DED4}")
    assert unchange_bouwtype is not None

    # Import Monumenten.json met changes
    # import json to clean database
    inputfile = "./test/data/Monumenten_test_15.json"

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

    database = db.Database(const.DATABASE_URL, db_create=False)
    ambacht = schema.get_class("EAID_54944273_F312_44b2_A78D_43488F915429")  # Diagram Package
    assert ambacht is not None
    assert ambacht.name == "test-Ambacht"

    # Voer nu de changes door en kijk of de waarden zijn aangepast
    # export to json
    test_args = ["export", "-f", EA_DB, "-t", "earepo", "--tag_strategy", "update"]
    cli.main(test_args)

    # Testen of het record voldoet aan bepaalde voorwaarden
    record = getRecordFromEARepository("t_object", "{54944273-F312-44b2-A78D-43488F915429}")
    assert record is not None, "Record met de naam 'MonumentNaam' niet gevonden."
    assert record[const.EA_REPO_MAPPER["name"]] == "test-Ambacht"
    assert (
        record[const.EA_REPO_MAPPER["definitie"]]
        == "test-Beroep waarbij een handwerker met gereedschap eindproducten maakt."
    )
    assert record[const.EA_REPO_MAPPER["author"]] == "test-Arjen Brienen"
    assert record[const.EA_REPO_MAPPER["stereotype"]] == "test-"
    assert record[const.EA_REPO_MAPPER["alias"]] == "test-"
    assert util.parse_date(str(record[const.EA_REPO_MAPPER["modified"]])) > util.parse_date(str(modified))
    version = record[const.EA_REPO_MAPPER["version"]]
    major, minor = map(int, version.split("."))
    assert minor == minor_original + 1
    assert countTagsOfObject(record["Object_ID"]) == 17

    # Testen van tags
    tag = getRecordFromEARepository("t_objectproperties", "{5BAA8E81-480F-405D-A818-A3F79725AFE3}")
    assert tag is not None
    assert tag["Value"] == "test_"

    # Packages testen eerste
    record = getRecordFromEARepository("t_object", "{F7651B45-2B64-4197-A6E5-BFC56EC98466}")
    assert record is not None
    assert record[const.EA_REPO_MAPPER["name"]] == "test-Model Monumenten"

    # Packages testen tweede
    record = getRecordFromEARepository("t_package", "{F7651B45-2B64-4197-A6E5-BFC56EC98466}")
    assert record is not None
    assert record[const.EA_REPO_MAPPER["name"]] == "test-Model Monumenten"

    # Enumeratie testen
    record = getRecordFromEARepository("t_object", "{5C808AC9-CB09-4f4d-813E-821829856BA8}")
    assert record is not None
    assert record[const.EA_REPO_MAPPER["name"]] == "test-TypeMonument"

    # Literal testen
    record = getRecordFromEARepository("t_attribute", "{B2AE8AFC-C1D5-4d83-BFD3-EBF1663F3468}")
    assert record is not None
    assert record[const.EA_REPO_MAPPER_LITERALS["name"]] == "test-rijksmonument"

    # Attribute testen
    record = getRecordFromEARepository("t_attribute", "{200B84E0-1D73-4608-9258-12338B5EC034}")
    assert record is not None
    assert record[const.EA_REPO_MAPPER_ATTRIBUTES["name"]] == "test-verbijzondering"
    assert record[const.EA_REPO_MAPPER_ATTRIBUTES["definitie"]] == "test-"
    assert record[const.EA_REPO_MAPPER_ATTRIBUTES["primitive"]] == "test-AN200"

    # Associations testen
    record = getRecordFromEARepository("t_connector", "{8E18F665-2A86-44fd-AD55-3E435A282BDF}")
    assert record is not None
    assert record[const.EA_REPO_MAPPER_ATTRIBUTES["name"]] == "test-monument ambacht"
    assert record[const.EA_REPO_MAPPER_ATTRIBUTES["definitie"]] == "test-"

    # Associations testen
    record = getRecordFromEARepository("t_diagram", "{7429E175-1CBE-4336-BF92-6C5029395E69}")
    assert record is not None
    assert record[const.EA_REPO_MAPPER_ATTRIBUTES["name"]] == "test-Diagram Monumenten"

    # record ophalen wat niet aangepast wordt
    bouwtype = getRecordFromEARepository("t_object", "{5E9DAFBB-C9B5-4706-A43D-07AD4979DED4}")
    assert bouwtype is not None
    assert unchange_bouwtype[const.EA_REPO_MAPPER["name"]] == "Bouwtype"
    assert unchange_bouwtype[const.EA_REPO_MAPPER["modified"]] == bouwtype[const.EA_REPO_MAPPER["modified"]]
    assert unchange_bouwtype[const.EA_REPO_MAPPER["version"]] == bouwtype[const.EA_REPO_MAPPER["version"]]

    # Nog even andere tag update strategien testen
    # export to json
    test_args = ["export", "-f", EA_DB, "-t", "earepo", "--tag_strategy", "upsert"]
    cli.main(test_args)
    record = getRecordFromEARepository("t_object", "{54944273-F312-44b2-A78D-43488F915429}")
    assert countTagsOfObject(record["Object_ID"]) == 26

    # Testen van tags
    tag = getRecordFromEARepository("t_objectproperties", "{5BAA8E81-480F-405D-A818-A3F79725AFE3}")
    assert tag is not None
    assert tag["Value"] == "test_"

    # Nog even andere tag update strategien testen
    # export to json
    test_args = ["export", "-f", EA_DB, "-t", "earepo", "--tag_strategy", "replace"]
    cli.main(test_args)
    record = getRecordFromEARepository("t_object", "{54944273-F312-44b2-A78D-43488F915429}")
    assert countTagsOfObject(record["Object_ID"]) == 11

    # Testen van tags
    tag = getRecordFromEARepository("t_objectproperties", "{5BAA8E81-480F-405D-A818-A3F79725AFE3}")
    assert tag is not None
    assert tag["Value"] == "test_"
