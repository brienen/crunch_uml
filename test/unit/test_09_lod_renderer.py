import os

from rdflib import Graph, exceptions

import crunch_uml.schema as sch
from crunch_uml import cli, const, db


def count_occurences(word, file):
    count = 0
    with open(file, 'r') as f:
        for line in f:
            words = line.split()
            for i in words:
                if i == word:
                    count = count + 1

    return count


def is_valid_ttl_file(filename):
    """
    Test of een bestand een geldig Turtle-bestand is.

    Args:
    - filename (str): Pad naar het Turtle-bestand.

    Returns:
    - bool: True als het bestand correct Turtle-formaat heeft, anders False.
    """
    g = Graph()
    try:
        g.parse(filename, format="turtle")
        return True
    except exceptions.ParserError:
        return False


def test_lod_renderer():
    # sourcery skip: extract-duplicate-method, move-assign-in-block
    outputfile = "./test/output/Monumenten.ttl"

    # import monumenten into clean database
    test_args = ["import", "-f", "./test/data/GGM_Monumenten_EA2.1.xml", "-t", "eaxmi", "-db_create"]
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
    test_args = ["export", "-f", outputfile, "-t", "ttl"]
    cli.main(test_args)
    assert os.path.exists(outputfile)
    assert is_valid_ttl_file(outputfile)

    # Test if all classes are there
    assert count_occurences('owl:Class', outputfile) == 6  # Only classes in the model
    assert count_occurences('owl:DatatypeProperty', outputfile) == 31

    # Cleanup
    os.remove(outputfile)
