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


def countObjectsByType(object_type):
    """Telt het aantal t_object records van een bepaald type in de EA repository."""
    conn = sqlite3.connect(EA_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) as cnt FROM t_object WHERE Object_Type = ?",
        (object_type,),
    )
    result = cursor.fetchone()
    conn.close()
    return result["cnt"] if result else 0


def countConnectorsByType(connector_type):
    """Telt het aantal t_connector records van een bepaald type in de EA repository."""
    conn = sqlite3.connect(EA_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) as cnt FROM t_connector WHERE Connector_Type = ?",
        (connector_type,),
    )
    result = cursor.fetchone()
    conn.close()
    return result["cnt"] if result else 0


def countAttributesOfObject(object_id):
    """Telt het aantal t_attribute records voor een gegeven Object_ID."""
    conn = sqlite3.connect(EA_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) as cnt FROM t_attribute WHERE Object_ID = ?",
        (object_id,),
    )
    result = cursor.fetchone()
    conn.close()
    return result["cnt"] if result else 0


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
    # major, minor = map(int, version.split("."))
    # major = int(version.split(".")[0])
    minor = int(version.split(".")[1])
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

    # Literal testenx
    record = getRecordFromEARepository("t_attribute", "{B2AE8AFC-C1D5-4d83-BFD3-EBF1663F3468}")
    assert record is not None
    assert record[const.EA_REPO_MAPPER_LITERALS["name"]] == "test-rijksmonument"

    # Attribute testen
    record = getRecordFromEARepository("t_attribute", "{200B84E0-1D73-4608-9258-12338B5EC034}")
    assert record is not None
    assert record[const.EA_REPO_MAPPER_ATTRIBUTES["name"]] == "test-verbijzondering"
    assert record[const.EA_REPO_MAPPER_ATTRIBUTES["definitie"]] == "test-"
    assert record[const.EA_REPO_MAPPER_ATTRIBUTES["primitive"]] == "test-AN200"

    # Attributen met class primitive testen
    record = getRecordFromEARepository("t_attribute", "{04B5CEE9-8929-4729-A545-FEEB5604B5C8}")
    assert record is not None
    assert record['Classifier'] == '6'

    record = getRecordFromEARepository("t_attribute", "{0E956D19-44D9-42f6-9C44-15FDAAF5AEF1}")
    assert record is not None
    assert record['Classifier'] == '12'

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
    assert countTagsOfObject(record["Object_ID"]) == 24

    # Testen van tags
    tag = getRecordFromEARepository("t_objectproperties", "{5BAA8E81-480F-405D-A818-A3F79725AFE3}")
    assert tag is not None
    assert tag["Value"] == "test_"

    # Nog even andere tag update strategien testen
    # export to json
    test_args = ["export", "-f", EA_DB, "-t", "earepo", "--tag_strategy", "replace"]
    cli.main(test_args)
    record = getRecordFromEARepository("t_object", "{54944273-F312-44b2-A78D-43488F915429}")
    assert countTagsOfObject(record["Object_ID"]) == 18

    # Testen van tags
    tag = getRecordFromEARepository("t_objectproperties", "{5BAA8E81-480F-405D-A818-A3F79725AFE3}")
    assert tag is not None
    assert tag["Value"] == "test_"


def test_insert_new_elements():
    """
    Test het toevoegen van nieuwe Packages, Classes, Attributen, Enumeraties,
    Literalen, Associaties en Generalisaties aan een EA Repository via --ea_allow_insert.

    Werkwijze:
      1. Importeer de insert test JSON (bevat alle bestaande elementen + nieuwe elementen).
      2. Exporteer naar de EA repo met --ea_allow_insert.
      3. Verifieer dat elk nieuw element correct is toegevoegd aan de qea database.
    """
    # GUIDs van de nieuwe testrecords (in EA repo {}-formaat)
    NEW_PACKAGE_GUID = "{AAAAAAAA-0000-0000-0000-000000000001}"
    NEW_CLASS_GUID = "{AAAAAAAA-0000-0000-0000-000000000002}"
    NEW_ATTR_GUID = "{AAAAAAAA-0000-0000-0000-000000000003}"
    NEW_ENUM_GUID = "{AAAAAAAA-0000-0000-0000-000000000004}"
    NEW_LITERAL_GUID = "{AAAAAAAA-0000-0000-0000-000000000005}"
    NEW_ASSOC_GUID = "{AAAAAAAA-0000-0000-0000-000000000006}"
    NEW_GEN_GUID = "{AAAAAAAA-0000-0000-0000-000000000007}"

    # Controleer basistoestand vóór import: nieuwe elementen mogen nog niet bestaan
    assert (
        getRecordFromEARepository("t_object", NEW_PACKAGE_GUID) is None
    ), "Nieuw package mag nog niet bestaan vóór de insert test"
    assert (
        getRecordFromEARepository("t_object", NEW_CLASS_GUID) is None
    ), "Nieuwe klasse mag nog niet bestaan vóór de insert test"
    assert (
        getRecordFromEARepository("t_object", NEW_ENUM_GUID) is None
    ), "Nieuwe enumeratie mag nog niet bestaan vóór de insert test"
    assert (
        getRecordFromEARepository("t_connector", NEW_ASSOC_GUID) is None
    ), "Nieuwe associatie mag nog niet bestaan vóór de insert test"
    assert (
        getRecordFromEARepository("t_connector", NEW_GEN_GUID) is None
    ), "Nieuwe generalisatie mag nog niet bestaan vóór de insert test"

    # Baseline: tel bestaande elementen
    classes_before = countObjectsByType("Class")
    enums_before = countObjectsByType("Enumeration")
    packages_before = countObjectsByType("Package")
    assocs_before = countConnectorsByType("Association")
    gens_before = countConnectorsByType("Generalization")

    # Stap 1: importeer de insert test JSON (bevat bestaande + nieuwe elementen)
    inputfile = "./test/data/Monumenten_test_15_insert.json"
    test_args = ["import", "-f", inputfile, "-t", "json", "-db_create"]
    cli.main(test_args)

    # Stap 2: exporteer naar EA repo met --ea_allow_insert
    test_args = ["export", "-f", EA_DB, "-t", "earepo", "--tag_strategy", "update", "--ea_allow_insert"]
    cli.main(test_args)

    # --- Verifieer nieuw Package ---
    # Elk package wordt zowel in t_object als in t_package opgeslagen
    pkg_obj = getRecordFromEARepository("t_object", NEW_PACKAGE_GUID)
    assert pkg_obj is not None, "Nieuw package niet gevonden in t_object na insert"
    assert pkg_obj[const.EA_REPO_MAPPER["name"]] == "Nieuw Testpackage"
    assert pkg_obj["Object_Type"] == "Package"

    pkg_row = getRecordFromEARepository("t_package", NEW_PACKAGE_GUID)
    assert pkg_row is not None, "Nieuw package niet gevonden in t_package na insert"
    assert pkg_row[const.EA_REPO_MAPPER["name"]] == "Nieuw Testpackage"

    # Totaal aantal packages moet met 1 gestegen zijn
    assert countObjectsByType("Package") == packages_before + 1, "Aantal packages in t_object moet met 1 gestegen zijn"

    # --- Verifieer nieuwe Class ---
    cls_obj = getRecordFromEARepository("t_object", NEW_CLASS_GUID)
    assert cls_obj is not None, "Nieuwe klasse niet gevonden in t_object na insert"
    assert cls_obj[const.EA_REPO_MAPPER["name"]] == "NieuweTestKlasse"
    assert cls_obj["Object_Type"] == "Class"
    assert countObjectsByType("Class") == classes_before + 1, "Aantal klassen in t_object moet met 1 gestegen zijn"

    # --- Verifieer nieuw Attribuut ---
    new_class_object_id = cls_obj["Object_ID"]
    attr_row = getRecordFromEARepository("t_attribute", NEW_ATTR_GUID)
    assert attr_row is not None, "Nieuw attribuut niet gevonden in t_attribute na insert"
    assert attr_row[const.EA_REPO_MAPPER_ATTRIBUTES["name"]] == "nieuwTestAttribuut"
    assert attr_row["Object_ID"] == new_class_object_id, "Attribuut moet gekoppeld zijn aan de juiste klasse"

    # --- Verifieer nieuwe Enumeratie ---
    enum_obj = getRecordFromEARepository("t_object", NEW_ENUM_GUID)
    assert enum_obj is not None, "Nieuwe enumeratie niet gevonden in t_object na insert"
    assert enum_obj[const.EA_REPO_MAPPER["name"]] == "NieuweTestEnumeratie"
    assert enum_obj["Object_Type"] == "Enumeration"
    assert (
        countObjectsByType("Enumeration") == enums_before + 1
    ), "Aantal enumeraties in t_object moet met 1 gestegen zijn"

    # --- Verifieer nieuw Literal ---
    new_enum_object_id = enum_obj["Object_ID"]
    literal_row = getRecordFromEARepository("t_attribute", NEW_LITERAL_GUID)
    assert literal_row is not None, "Nieuw literal niet gevonden in t_attribute na insert"
    assert literal_row[const.EA_REPO_MAPPER_LITERALS["name"]] == "nieuwTestLiteral"
    assert literal_row["Object_ID"] == new_enum_object_id, "Literal moet gekoppeld zijn aan de juiste enumeratie"

    # --- Verifieer nieuwe Associatie ---
    assoc_row = getRecordFromEARepository("t_connector", NEW_ASSOC_GUID)
    assert assoc_row is not None, "Nieuwe associatie niet gevonden in t_connector na insert"
    assert assoc_row[const.EA_REPO_MAPPER_ASSOCIATION["name"]] == "nieuw testassociatie"
    assert assoc_row["Connector_Type"] == "Association"
    # Controleer dat de juiste klassen zijn gekoppeld (NieuweTestKlasse -> test-Ambacht)
    ambacht_obj = getRecordFromEARepository("t_object", "{54944273-F312-44b2-A78D-43488F915429}")
    assert assoc_row["End_Object_ID"] == ambacht_obj["Object_ID"], "Associatie moet naar de juiste doelklasse verwijzen"
    assert assoc_row["Start_Object_ID"] == new_class_object_id, "Associatie moet van de juiste bronklasse komen"
    assert countConnectorsByType("Association") == assocs_before + 1, "Aantal associaties moet met 1 gestegen zijn"

    # --- Verifieer nieuwe Generalisatie ---
    gen_row = getRecordFromEARepository("t_connector", NEW_GEN_GUID)
    assert gen_row is not None, "Nieuwe generalisatie niet gevonden in t_connector na insert"
    assert gen_row["Connector_Type"] == "Generalization"
    # Subklasse = NieuweTestKlasse, superklasse = Bouwtype
    bouwtype_obj = getRecordFromEARepository("t_object", "{5E9DAFBB-C9B5-4706-A43D-07AD4979DED4}")
    assert gen_row["Start_Object_ID"] == new_class_object_id, "Generalisatie: subklasse moet NieuweTestKlasse zijn"
    assert gen_row["End_Object_ID"] == bouwtype_obj["Object_ID"], "Generalisatie: superklasse moet Bouwtype zijn"
    assert countConnectorsByType("Generalization") == gens_before + 1, "Aantal generalisaties moet met 1 gestegen zijn"


def test_delete_stale_elements():
    """
    Test het verwijderen van stale Classes, Attributen, Enumeratieliteralen
    en Associaties uit een EA Repository via --ea_allow_delete.

    Werkwijze:
      1. Verifieer dat de te verwijderen elementen bestaan in de baseline qea.
      2. Importeer de delete test JSON (zonder de te verwijderen elementen).
      3. Exporteer naar de EA repo met --ea_allow_delete.
      4. Verifieer dat de verwijderde elementen niet meer aanwezig zijn.
      5. Verifieer dat de overgebleven elementen nog steeds aanwezig zijn.
    """
    # GUIDs van elementen die verwijderd moeten worden
    BOUWACTIVITEIT_GUID = "{4AD539EC-A308-43da-B025-17A1647303F3}"
    AMBACHT_ATTR1_GUID = "{97B64E49-D913-4648-985D-C2692F1EDC51}"  # ambachtsoort
    AMBACHT_ATTR2_GUID = "{6FEBCD91-8B50-4942-A989-6C9B242CEBC2}"  # jaarAmbachtTot
    AMBACHT_ATTR3_GUID = "{6277018C-A2EC-4069-9625-487494821237}"  # jaarAmbachtVanaf
    GEMEENTELIJK_LITERAL_GUID = "{774B86B6-5B16-4f29-ABF0-40671AD9E0F9}"  # gemeentelijkmonument
    BOUWSTIJL_ASSOC_GUID = "{144ADF26-C2E9-4080-8F4F-32F9B255E4AE}"  # monument bouwstijl
    BOUWACTIVITEIT_ASSOC_GUID = "{55585CB9-E569-47ca-9EFE-B9D5CF46BCBD}"  # monument bouwactiviteit

    # GUIDs van elementen die NIET verwijderd mogen worden
    AMBACHT_GUID = "{54944273-F312-44b2-A78D-43488F915429}"  # Ambacht (blijft bestaan)
    MODEL_PKG_GUID = "{F7651B45-2B64-4197-A6E5-BFC56EC98466}"  # Model Monumenten (blijft)
    RIJKSMONUMENT_LITERAL_GUID = "{B2AE8AFC-C1D5-4d83-BFD3-EBF1663F3468}"  # rijksmonument (blijft)
    MONUMENT_AMBACHT_ASSOC_GUID = "{8E18F665-2A86-44fd-AD55-3E435A282BDF}"  # monument ambacht (blijft)
    TYPEMONUMENT_GUID = "{5C808AC9-CB09-4f4d-813E-821829856BA8}"  # TypeMonument enum (blijft)

    # Stap 1: Verifieer dat de te verwijderen elementen bestaan vóór de delete test
    assert (
        getRecordFromEARepository("t_object", BOUWACTIVITEIT_GUID) is not None
    ), "Bouwactiviteit moet bestaan vóór de delete test"
    assert (
        getRecordFromEARepository("t_attribute", AMBACHT_ATTR1_GUID) is not None
    ), "ambachtsoort attribuut moet bestaan vóór de delete test"
    assert (
        getRecordFromEARepository("t_attribute", AMBACHT_ATTR2_GUID) is not None
    ), "jaarAmbachtTot attribuut moet bestaan vóór de delete test"
    assert (
        getRecordFromEARepository("t_attribute", AMBACHT_ATTR3_GUID) is not None
    ), "jaarAmbachtVanaf attribuut moet bestaan vóór de delete test"
    assert (
        getRecordFromEARepository("t_attribute", GEMEENTELIJK_LITERAL_GUID) is not None
    ), "gemeentelijkmonument literal moet bestaan vóór de delete test"
    assert (
        getRecordFromEARepository("t_connector", BOUWSTIJL_ASSOC_GUID) is not None
    ), "monument bouwstijl associatie moet bestaan vóór de delete test"
    assert (
        getRecordFromEARepository("t_connector", BOUWACTIVITEIT_ASSOC_GUID) is not None
    ), "monument bouwactiviteit associatie moet bestaan vóór de delete test"

    # Baseline: tel elementen vóór de delete operatie
    classes_before = countObjectsByType("Class")
    assocs_before = countConnectorsByType("Association")

    # Haal Object_ID van Ambacht op om het aantal attributen te controleren
    ambacht_before = getRecordFromEARepository("t_object", AMBACHT_GUID)
    ambacht_attrs_before = countAttributesOfObject(ambacht_before["Object_ID"])

    # Stap 2: importeer de delete test JSON (zonder Bouwactiviteit, 3 Ambacht attributen,
    # gemeentelijkmonument literal en 2 associaties)
    inputfile = "./test/data/Monumenten_test_15_delete.json"
    test_args = ["import", "-f", inputfile, "-t", "json", "-db_create"]
    cli.main(test_args)

    # Stap 3: exporteer naar EA repo met --ea_allow_delete
    test_args = ["export", "-f", EA_DB, "-t", "earepo", "--tag_strategy", "update", "--ea_allow_delete"]
    cli.main(test_args)

    # --- Verifieer verwijdering van Class Bouwactiviteit ---
    assert (
        getRecordFromEARepository("t_object", BOUWACTIVITEIT_GUID) is None
    ), "Bouwactiviteit moet verwijderd zijn uit t_object"
    assert (
        countObjectsByType("Class") == classes_before - 1
    ), "Aantal klassen moet met 1 gedaald zijn na verwijdering Bouwactiviteit"

    # --- Verifieer verwijdering van 3 Ambacht attributen ---
    assert (
        getRecordFromEARepository("t_attribute", AMBACHT_ATTR1_GUID) is None
    ), "ambachtsoort attribuut moet verwijderd zijn uit t_attribute"
    assert (
        getRecordFromEARepository("t_attribute", AMBACHT_ATTR2_GUID) is None
    ), "jaarAmbachtTot attribuut moet verwijderd zijn uit t_attribute"
    assert (
        getRecordFromEARepository("t_attribute", AMBACHT_ATTR3_GUID) is None
    ), "jaarAmbachtVanaf attribuut moet verwijderd zijn uit t_attribute"
    ambacht_after = getRecordFromEARepository("t_object", AMBACHT_GUID)
    assert (
        countAttributesOfObject(ambacht_after["Object_ID"]) == ambacht_attrs_before - 3
    ), "Ambacht moet 3 attributen minder hebben na verwijdering"

    # --- Verifieer verwijdering van literal gemeentelijkmonument ---
    assert (
        getRecordFromEARepository("t_attribute", GEMEENTELIJK_LITERAL_GUID) is None
    ), "gemeentelijkmonument literal moet verwijderd zijn uit t_attribute"

    # --- Verifieer verwijdering van 2 associaties ---
    assert (
        getRecordFromEARepository("t_connector", BOUWSTIJL_ASSOC_GUID) is None
    ), "monument bouwstijl associatie moet verwijderd zijn uit t_connector"
    assert (
        getRecordFromEARepository("t_connector", BOUWACTIVITEIT_ASSOC_GUID) is None
    ), "monument bouwactiviteit associatie moet verwijderd zijn uit t_connector"
    assert countConnectorsByType("Association") == assocs_before - 2, "Aantal associaties moet met 2 gedaald zijn"

    # --- Verifieer dat ongewijzigde elementen nog steeds aanwezig zijn ---
    assert getRecordFromEARepository("t_object", AMBACHT_GUID) is not None, "Ambacht klasse mag niet verwijderd zijn"
    assert (
        getRecordFromEARepository("t_object", MODEL_PKG_GUID) is not None
    ), "Model Monumenten package mag niet verwijderd zijn"
    assert (
        getRecordFromEARepository("t_package", MODEL_PKG_GUID) is not None
    ), "Model Monumenten package mag niet verwijderd zijn uit t_package"
    assert (
        getRecordFromEARepository("t_attribute", RIJKSMONUMENT_LITERAL_GUID) is not None
    ), "rijksmonument literal mag niet verwijderd zijn"
    assert (
        getRecordFromEARepository("t_connector", MONUMENT_AMBACHT_ASSOC_GUID) is not None
    ), "monument ambacht associatie mag niet verwijderd zijn"

    # --- Verifieer dat enumeratie TypeMonument nog steeds aanwezig is ---
    typemonument = getRecordFromEARepository("t_object", TYPEMONUMENT_GUID)
    assert typemonument is not None, "TypeMonument enumeratie mag niet verwijderd zijn"
    assert typemonument["Object_Type"] == "Enumeration"
