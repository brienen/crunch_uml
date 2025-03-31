import json
import os

import crunch_uml.schema as sch
from crunch_uml import cli, const, db


def are_json_files_equal(file1_path, file2_path, exclude_keys=None):
    """
    Vergelijk twee JSON-bestanden en negeer specifieke velden tijdens de vergelijking.

    :param file1_path: Pad naar het eerste JSON-bestand.
    :param file2_path: Pad naar het tweede JSON-bestand.
    :param exclude_keys: Lijst van velden die moeten worden uitgesloten van de vergelijking.
    :return: True als de JSON-bestanden gelijk zijn (met uitgesloten velden), anders False.
    """
    try:
        # Open en laad het eerste JSON-bestand
        with open(file1_path, "r") as file1:
            data1 = json.load(file1)

        # Open en laad het tweede JSON-bestand
        with open(file2_path, "r") as file2:
            data2 = json.load(file2)

        # Als geen exclusielijst is opgegeven, stel deze in als lege lijst
        if exclude_keys is None:
            exclude_keys = []

        def remove_keys(data, keys):
            """Verwijder opgegeven sleutels uit een JSON-structuur."""
            if isinstance(data, dict):
                return {k: remove_keys(v, keys) for k, v in data.items() if k not in keys}
            elif isinstance(data, list):
                return [remove_keys(item, keys) for item in data]
            else:
                return data

        # Verwijder uitgesloten velden uit beide JSON-structuren
        filtered_data1 = remove_keys(data1, exclude_keys)
        filtered_data2 = remove_keys(data2, exclude_keys)

        # Vergelijk de twee gefilterde JSON-structuren
        return filtered_data1 == filtered_data2

    except Exception as e:
        print(f"Er is een fout opgetreden tijdens het vergelijken van de bestanden: {str(e)}")
        return False


def test_json_parser_renderer():
    # sourcery skip: extract-duplicate-method, move-assign-in-block
    inputfile = "./test/output/Monumenten_import.json"
    outputfile = "./test/output/Monumenten_export.json"
    mapper = {
        "id": "GGM-guid",
        "gemma_url": "GEMMA-URL",
        "gemma_type": "GEMMA-type",
        "gemma_naam": "GEMMA-naam",
        "definitie": "definitie_aangepast",
        "name": "name_aangepast",
    }
    mapper_reverse = {v: k for k, v in mapper.items()}

    # import monumenten into clean database
    test_args = [
        "import",
        "-f",
        "./test/data/GGM_Monumenten_EA2.1.xml",
        "-t",
        "eaxmi",
        "-db_create",
    ]
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
    test_args = ["export", "-f", inputfile, "-t", "json", "--mapper", str(json.dumps(mapper))]
    cli.main(test_args)
    assert os.path.exists(inputfile)

    # Test of de mappings goed zijn weggeschreeven
    with open(inputfile, "r") as file:
        data = json.load(file)
        ambacht = [
            item for item in data['classes'] if item.get("GGM-guid") == "EAID_54944273_F312_44b2_A78D_43488F915429"
        ]
        assert ambacht is not None
        assert (
            ambacht[0].get("definitie_aangepast")
            == "Beroep waarbij een handwerker met gereedschap eindproducten maakt."
        )
        assert ambacht[0].get("name_aangepast") == "Ambacht"

    # import json to clean database
    test_args = ["import", "-f", inputfile, "-t", "json", "-db_create", "--mapper", str(json.dumps(mapper_reverse))]
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
    test_args = ["export", "-f", outputfile, "-t", "json", "--mapper", str(json.dumps(mapper))]
    cli.main(test_args)
    assert os.path.exists(outputfile)

    # Check if the contents of the files are equal
    assert are_json_files_equal(
        inputfile,
        outputfile,
        exclude_keys=[const.COLUMN_DOMEIN_DATUM_TIJD_EXPORT, const.COLUMN_DOMEIN_IV3, const.COLUMN_DOMEIN_GGM_UML_TYPE],
    )
