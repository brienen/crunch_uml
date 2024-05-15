import json
import os

from crunch_uml import cli


def test_relations_export_json():
    outputfile = "./test/data/test.json"

    # Import Data
    test_args = ["import", "-f", "./test/data/RelationTest.xml", "-t", "eaxmi", "-db_create"]
    cli.main(test_args)

    # Export to out file
    test_args = ["export", "-f", outputfile, "-t", "json"]
    cli.main(test_args)
    assert os.path.exists(outputfile)

    # Load the data from the created JSON file
    with open(outputfile, 'r') as f:
        data = json.load(f)

    # Cleanup
    os.remove(outputfile)

    # Assert data
    expectedkeys = [
        'classes',
        'attributes',
        'packages',
        'enumeraties',
        'enumeratieliterals',
        'associaties',
        'generalizations',
    ]
    for expectedkey in expectedkeys:
        assert expectedkey in data.keys()

    assert len(data['packages']) == 1
    assert len(data['classes']) == 7
    assert len(data['attributes']) == 5
    assert len(data['enumeraties']) == 1
    assert len(data['enumeratieliterals']) == 1
    assert len(data['associaties']) == 3
    assert len(data['generalizations']) == 1
