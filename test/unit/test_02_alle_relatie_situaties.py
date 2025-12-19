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
    assert schema.count_enumeratie() == 0
    assert schema.count_class() == 14
    assert schema.count_attribute() == 4
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
