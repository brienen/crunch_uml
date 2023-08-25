from crunch_uml import cli, const, db


def test_import_onderwijs():
    test_args = ["-f", "./test/data/GGM_Onderwijs_XMI.2.1.xml"]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    assert database.count_package() == 3
    assert database.count_enumeratie() == 1
    assert database.count_class() == 27
    assert database.count_attribute() == 16
    assert database.count_enumeratieliteral() == 5
    assert database.count_association() == 24
