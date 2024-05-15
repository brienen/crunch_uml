import crunch_uml.schema as sch
from crunch_uml import cli, const, db


def test_relations():
    test_args = ["import", "-f", "./test/data/AlleRelatieSitiuaties.xml", "-t", "xmi", "-db_create"]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)

    assert schema.count_package() == 1
    assert schema.count_enumeratie() == 0
    assert schema.count_class() == 14
    assert schema.count_attribute() == 4
    assert schema.count_enumeratieliteral() == 0
    assert schema.count_association() == 5
    assert schema.count_generalizations() == 0
