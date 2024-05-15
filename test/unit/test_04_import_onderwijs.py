import crunch_uml.schema as sch
from crunch_uml import cli, const, db


def test_import_onderwijs():
    test_args = ["import", "-f", "./test/data/GGM_Onderwijs_XMI.2.1.xml", "-t", "xmi", "-db_create"]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)

    assert schema.count_package() == 3
    assert schema.count_enumeratie() == 1
    assert schema.count_class() == 27
    assert schema.count_attribute() == 16
    assert schema.count_enumeratieliteral() == 5
    assert schema.count_association() == 24

    assert schema.get_attribute('EAID_ADBA3E5C_CAAC_44f1_AE93_396D86091B42').primitive == 'Datum'
    assert schema.get_attribute('EAID_9BCB2AB1_71BF_45e8_A456_E3C4641E0ECC').primitive == 'int'
    assert schema.get_attribute('EAID_dstA8C8B3_BE1A_40bd_A4FF_980213D42E5C').primitive is None
    assert (
        schema.get_attribute('EAID_dstA8C8B3_BE1A_40bd_A4FF_980213D42E5C').type_class_id
        == 'EAID_0E3DE26B_C535_4a03_98A4_8D36DC3D5297'
    )
    assert schema.get_attribute('EAID_D730A5E4_33C0_46e8_B3D5_8A5ADF0255B6').primitive is None
    assert (
        schema.get_attribute('EAID_D730A5E4_33C0_46e8_B3D5_8A5ADF0255B6').enumeration_id
        == 'EAID_354AA899_00C3_4c36_93F7_0B364D331C93'
    )
