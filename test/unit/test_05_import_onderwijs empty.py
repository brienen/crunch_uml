import crunch_uml.schema as sch
from crunch_uml import cli, const, db


def test_import_onderwijs_empty():
    test_args = ["import", "-t", "xmi", "-f", "./test/data/GGM_Onderwijs_XMI.2.1.xml", "-db_create"]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=True)
    schema = sch.Schema(database)

    assert schema.count_package() == 0
    assert schema.count_enumeratie() == 0
    assert schema.count_class() == 0
    assert schema.count_attribute() == 0
    assert schema.count_enumeratieliteral() == 0
