from crunch_uml import cli, const, db


def test_relations():
    test_args = ["import", "-f", "./test/data/RelationTest.xml", "-t", "xmi", "-db_create"]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    assert database.count_package() == 1
    assert database.count_enumeratie() == 1
    assert database.count_class() == 7
    assert database.count_attribute() == 5
    assert database.count_enumeratieliteral() == 1
    assert database.count_association() == 3
    assert database.count_generalizations() == 1

    assoc = database.get_association('EAID_226EA15E_18E2_488d_8844_07DCFBA8A6E2')
    assert assoc.name == 'assoc to Orphan'

    assoc = database.get_association('EAID_8FC391C5_3370_4bd4_A64E_C08369C7E2A6')
    assert assoc.src_class.name == 'Class A'
    assert assoc.dst_class.name == 'Class B'

    attr = database.get_attribute('EAID_18BD2EDE_1337_4817_9DE6_8191EF0B0763')
    assert attr.enumeration_id == 'EAID_ED3BE54D_FD1B_46d3_AECA_621A7FD7D667'
    attr = database.get_attribute('EAID_dstC391C5_3370_4bd4_A64E_C08369C7E2A6')
    assert attr.type_class_id == 'EAID_48A02EC8_683B_414f_B8A7_7518B789C8F5'

    gener = database.get_generalization('EAID_7C4B53BC_DCF3_47a5_8D44_E0F23E9FA511')
    assert gener.superclass.name == 'Class F'
    assert gener.subclass.name == 'Class E'
