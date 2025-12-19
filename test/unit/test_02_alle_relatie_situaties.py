import crunch_uml.schema as sch
from crunch_uml import cli, const, db


def test_relations():
    test_args = [
        "import",
        "-f",
        "./test/data/AlleRelatieSitiuaties.xml",
        "-t",
        "xmi",
        "-db_create",
    ]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)

    assert schema.count_package() == 1
    assert schema.count_enumeratie() == 1
    assert schema.count_class() == 14
    assert schema.count_attribute() == 6
    assert schema.count_enumeratieliteral() == 0
    assert schema.count_association() == 5
    assert schema.count_generalizations() == 0

    clazz = schema.get_class("EAID_8FCE6497_45FB_4d1c_9030_B59E37093162")
    assert clazz.name == "Class 3A"

    attr = schema.get_attribute("EAID_1BD4A048_3ABF_4b1f_B913_B6E8AED1AC5A")
    assert attr.name == "attribuut 1"
    type_class = attr.type_class
    assert type_class.id == "EAID_4C9BD12B_F8C0_41d9_BCC6_CE466553F46D"
    assert type_class.name == "Class 3B"
    assert attr.enumeration is None
    assert attr.primitive == "Class 3B"

    attr2 = schema.get_attribute("EAID_FC69D850_0CA6_49dc_9619_30C5AAE07FC1")
    assert attr2.name == "attribuut 2"
    assert attr2.type_class is None
    enum = attr2.enumeration
    assert enum.id == "EAID_0733126E_4331_4c0c_BF49_40787D94F1DA"
    assert enum.name == 'Enumeration 1'
    assert attr2.primitive == "Enumeration 1"

    attr3 = schema.get_attribute("EAID_63E8FB02_F606_4b93_8E62_41E5A5568B06")
    assert attr3.name == "attribuut 3"
    assert attr3.type_class is None
    assert attr3.enumeration is None
    assert attr3.primitive == "String"
