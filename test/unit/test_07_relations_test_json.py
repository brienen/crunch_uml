import json
import os

from crunch_uml import cli


def test_relations_export_json():
    outputfile = "./test/output/test.json"

    # Import Data
    test_args = [
        "import",
        "-f",
        "./test/data/RelationTest.xml",
        "-t",
        "eaxmi",
        "-db_create",
    ]
    cli.main(test_args)

    # Export to out file
    test_args = ["export", "-f", outputfile, "-t", "json"]
    cli.main(test_args)
    assert os.path.exists(outputfile)

    # Load the data from the created JSON file
    with open(outputfile, "r") as f:
        data = json.load(f)

    # Cleanup
    os.remove(outputfile)

    # Assert data
    expectedkeys = [
        "classes",
        "attributes",
        "packages",
        "enumerations",
        "enumerationliterals",
        "associations",
        "generalizations",
    ]
    for expectedkey in expectedkeys:
        assert expectedkey in data.keys()

    assert len(data["packages"]) == 1
    assert len(data["classes"]) == 7
    assert len(data["attributes"]) == 5
    assert len(data["enumerations"]) == 1
    assert len(data["enumerationliterals"]) == 1
    assert len(data["associations"]) == 3
    assert len(data["generalizations"]) == 1
