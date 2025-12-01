import os
import shutil
import sqlite3

import pytest

from crunch_uml import cli, const

EA_DB = "./test/output/MonumentenMIM.qea"


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
        ("./test/data/MonumentenMIM.qea", EA_DB),
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

    # eerst monumenten importeren
    test_args = [
        "import",
        "-f",
        "./test/data/GGM_Monumenten_EA2.1.xml",
        "-t",
        "eaxmi",
        "-db_create",
    ]
    cli.main(test_args)

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
    # modified = util.parse_date(str(record[const.EA_REPO_MAPPER["modified"]]))
    version = record[const.EA_REPO_MAPPER["version"]]
    major_original, minor_original = map(int, version.split("."))

    # record ophalen wat niet aangepast wordt
    unchange_bouwtype = getRecordFromEARepository("t_object", "{5E9DAFBB-C9B5-4706-A43D-07AD4979DED4}")
    assert unchange_bouwtype is not None

    # Nog even andere tag update strategien testen
    # export to json
    test_args = ["export", "-f", EA_DB, "-t", "eamimrepo", "--tag_strategy", "upsert"]
    cli.main(test_args)

    # Test objecttype
    record = getRecordFromEARepository("t_object", "{54944273-F312-44b2-A78D-43488F915429}")
    xref = getRecordFromEARepository("t_xref", "{54944273-F312-44b2-A78D-43488F915429}", key="Client")
    assert record["Stereotype"] == "Objecttype"
    assert xref is not None
    assert xref["Description"] == "@STEREO;Name=Objecttype;FQName=VNGR SIM+Grouping NL::Objecttype;@ENDSTEREO;"

    # Test Enumeration
    record = getRecordFromEARepository("t_object", "{5C808AC9-CB09-4f4d-813E-821829856BA8}")
    xref = getRecordFromEARepository("t_xref", "{5C808AC9-CB09-4f4d-813E-821829856BA8}", key="Client")
    assert record is not None, "Record met de naam 'Enumeratie' niet gevonden."
    assert record["Stereotype"] == "Enumeratie"
    assert xref is not None
    assert xref["Description"] == "@STEREO;Name=Enumeratie;FQName=VNGR SIM+Grouping NL::Enumeratie;@ENDSTEREO;"

    # Test Attribute
    record = getRecordFromEARepository("t_attribute", "{EBD24559-2F60-43fb-B865-2A7AAA4E3001}")
    xref = getRecordFromEARepository("t_xref", "{EBD24559-2F60-43fb-B865-2A7AAA4E3001}", key="Client")
    assert record is not None, "Record met de naam 'Attribuut' niet gevonden."
    assert record["Stereotype"] == "Attribuutsoort"
    assert xref is not None
    assert xref["Description"] == "@STEREO;Name=Attribuutsoort;FQName=VNGR SIM+Grouping NL::Attribuutsoort;@ENDSTEREO;"

    # Test Associatie
    record = getRecordFromEARepository("t_connector", "{FD27EB67-1CFA-4f40-AE79-329DE9DE6754}")
    xref = getRecordFromEARepository("t_xref", "{FD27EB67-1CFA-4f40-AE79-329DE9DE6754}", key="Client")
    assert record is not None, "Record met de naam 'Relatiesoort' niet gevonden."
    assert record["Stereotype"] == "Relatiesoort"
    assert xref is not None
    assert xref["Description"] == "@STEREO;Name=Relatiesoort;FQName=VNGR SIM+Grouping NL::Relatiesoort;@ENDSTEREO;"
