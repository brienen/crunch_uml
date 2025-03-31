import os
import shutil
import sqlite3

import pytest

from crunch_uml import cli

EA_DB = "./test/output/RSGBPlus.qea"


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
        ("./test/data/RSGBPlus.qea", EA_DB),
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
    translate_file = "./test/data/RSGBPlus.i18n.json"

    test_args = [
        "import",
        "-f",
        "./test/data/RSGBPlus.xml",
        "-t",
        "eaxmi",
        "-db_create",
    ]
    cli.main(test_args)

    test_args = [
        "transform",
        "-ttp",
        "copy",
        "-sch_to",
        "lang_en",
        "--root_package",
        "EAPK_58A5214F_E56C_4707_BE2D_AB36DD6976A3",
    ]
    cli.main(test_args)

    test_args = [
        "export",
        "-f",
        translate_file,
        "-t",
        "i18n",
        "--language",
        "en",
        "--translate",
        "True",
    ]
    # cli.main(test_args)

    test_args = [
        "-sch",
        "lang_en",
        "import",
        "-f",
        translate_file,
        "-t",
        "i18n",
        "--language",
        "en",
    ]
    cli.main(test_args)
    print("data saved")

    # database = db.Database(const.DATABASE_URL, db_create=False)
    # schema = sch.Schema(database)
    # clazz = schema.get_class('EAID_54944273_F312_44b2_A78D_43488F915429')
    # assert clazz.name == 'Ambacht_name'
    # assert clazz.alias == 'Ambacht_alias'
    # assert clazz.definitie == 'Ambacht_definitie'
    # assert clazz.toelichting == 'Ambacht_toelichting'
    # assert clazz.stereotype == 'Ambacht_stereotype'
    # assert clazz.synoniemen == 'Ambacht_synoniemen'
    # print("test_import_monumenten passed")

    # Voer nu de changes door en kijk of de waarden zijn aangepast
    # export to json
    test_args = [
        "-sch",
        "lang_en",
        "export",
        "-f",
        EA_DB,
        "-t",
        "earepo",
        "--tag_strategy",
        "update",
    ]
    cli.main(test_args)
    print("test_import_monumenten passed")

    # Testen of het record voldoet aan bepaalde voorwaarden
    # record = getRecordFromEARepository('t_object', '{54944273-F312-44b2-A78D-43488F915429}')
    # assert record is not None, "Record met de naam 'MonumentNaam' niet gevonden."
    # assert record[const.EA_REPO_MAPPER['name']] == "Håndverk_name"
