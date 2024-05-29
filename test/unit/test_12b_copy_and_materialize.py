import pytest

import crunch_uml.schema as sch
from crunch_uml import cli, const, db


@pytest.mark.filterwarnings(":Object of type <.*> not in session")
def test_import_onderwijs():
    test_args = ["import", "-f", "./test/data/Materialize_Generalizations.xml", "-t", "eaxmi", "-db_create"]
    cli.main(test_args)

    test_args = [
        "transform",
        "-ttp",
        "copy",
        "-sch_to",
        "materialize",
        "-rt_pkg",
        "EAPK_D476DA83_2028_40aa_B96F_342F2C3BDFD2",
        "-m_gen",
        "True",
    ]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database, 'materialize')

    assert schema.count_package() == 1
    assert schema.count_class() == 1
    assert schema.count_attribute() == 7
    assert schema.count_association() == 0
    assert schema.count_generalizations() == 0
    assert schema.count_enumeratie() == 2
