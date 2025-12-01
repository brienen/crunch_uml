import os
import shutil
import sqlite3

import pytest

from crunch_uml import cli

EA_DB = "./test/output/InkomenMIM_Processed.qea"


def getRecordFromEARepository(table, ea_guid, key="ea_guid"):

    # Test eerst de waarde in de EA Repository
    # Verbinding maken met de Monumenten.qea SQLite database
    conn = sqlite3.connect(EA_DB)

    # Instellen van de row factory om resultaten als dictionaries te krijgen
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table} WHERE {key} = '{ea_guid}'")
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
        ("./test/data/InkomenMIM.qea", EA_DB),
    ]

    # Zorg ervoor dat de testdata-map bestaat
    os.makedirs("./test/output", exist_ok=True)

    # Kopieer de bestanden naar de testdata-map
    for source, destination in source_files:
        shutil.copyfile(source, destination)

    yield  # Test wordt uitgevoerd na deze yield

    # Opruimen na de test als dat nodig is
    # Bijvoorbeeld: os.remove(destination)


@pytest.mark.slow
def test_import_monumenten():

    # eerst monumenten importeren
    test_args = [
        "import",
        "-f",
        "./test/data/InkomenMIM.xml",
        "-t",
        "eaxmi",
        "-db_create",
    ]
    cli.main(test_args)

    test_args = ["export", "-f", EA_DB, "-t", "eamimrepo", "--tag_strategy", "upsert"]
    cli.main(test_args)

    print("Test import_monumenten passed.")
