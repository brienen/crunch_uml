from crunch_uml import cli, const, db


def test_relations():
    test_args = ["import", "-f", "./test/data/AlleRelatieSitiuaties.xml", "-t", "xmi", "-db_create"]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    assert database.count_package() == 1
    assert database.count_enumeratie() == 0
    assert database.count_class() == 14
    assert database.count_attribute() == 4
    assert database.count_enumeratieliteral() == 0
    assert database.count_association() == 5
    assert database.count_generalizations() == 0
