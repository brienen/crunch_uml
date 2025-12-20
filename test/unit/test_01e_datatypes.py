import crunch_uml.schema as sch
from crunch_uml import cli, const, db


def test_modelafhandeling():
    test_args = [
        "import",
        "-t",
        "eaxmi",
        "-f",
        "./test/data/TestMetDatatypes.xml",
        "-db_create",
    ]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)
    assert schema.count_package() == 1
    assert schema.count_enumeratie() == 0
    assert schema.count_class() == 2
    assert schema.count_datatype() == 1
    assert schema.count_attribute() == 5
    assert schema.count_enumeratieliteral() == 0
    assert schema.count_association() == 1
    assert schema.count_generalizations() == 0
    assert schema.count_diagrams() == 1

    root = schema.get_package("EAPK_8A3A597B_DB0A_80ED_9741_C8F725E6B448")
    assert root.name == "Test met Datatypes"

    dt = schema.get_datatype("EAID_25E904A8_6978_420e_ABA4_0EF9D5E2EB5A")
    assert dt.name == "DataType1"
    assert dt.is_datatype is True

    klass = schema.get_class("EAID_8402693C_E188_D047_97BD_8814FC8A637A")
    assert klass.name == "Class B"
    assert klass.is_datatype is False

    dt = schema.get_datatype("EAID_8402693C_E188_D047_97BD_8814FC8A637A")
    assert dt is None
