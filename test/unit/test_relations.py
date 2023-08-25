from crunch_uml import cli, const, db


def test_relations():
    test_args = ["-f", "./test/data/RelationTest.xml"]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    assert database.count_package() == 1
    assert database.count_enumeratie() == 1
    assert database.count_class() == 6
    assert database.count_attribute() == 5
    assert database.count_enumeratieliteral() == 1

    assoc = database.get_association('EAID_226EA15E_18E2_488d_8844_07DCFBA8A6E2')
    assert assoc.name == 'assoc to Orphan'

    assoc = database.get_association('EAID_8FC391C5_3370_4bd4_A64E_C08369C7E2A6')
    assert assoc.src_class.name == 'Class A'
    assert assoc.dst_class.name == 'Class B'
