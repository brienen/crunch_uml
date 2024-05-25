import pytest

import crunch_uml.schema as sch
from crunch_uml import cli, const, db


@pytest.mark.filterwarnings(":Object of type <.*> not in session")
def test_import_onderwijs():
    test_args = ["import", "-f", "./test/data/GGM_Onderwijs_XMI.2.1.xml", "-t", "xmi", "-db_create"]
    cli.main(test_args)

    test_args = [
        "transform",
        "-ttp",
        "copy",
        "-sch_to",
        "onderwijs",
        "-rt_pkg",
        "EAPK_CD9BF007_85C6_4af9_B3F4_2CAB5BF26B5E",
    ]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database, 'onderwijs')

    assert schema.count_package() == 1
    assert schema.count_enumeratie() == 1
    assert schema.count_class() == 12
    assert schema.count_attribute() == 16
    assert schema.count_enumeratieliteral() == 5
    assert schema.count_association() == 10
    assert schema.count_generalizations() == 0
