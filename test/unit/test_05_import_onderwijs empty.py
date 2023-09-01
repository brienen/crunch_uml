from crunch_uml import cli, const, db


def test_import_onderwijs_empty():
    test_args = ["import", "-t", "xmi", "-f", "./test/data/GGM_Onderwijs_XMI.2.1.xml", "-db_create"]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=True)
    assert database.count_package() == 0
    assert database.count_enumeratie() == 0
    assert database.count_class() == 0
    assert database.count_attribute() == 0
    assert database.count_enumeratieliteral() == 0
