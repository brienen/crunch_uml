import crunch_uml.schema as sch
from crunch_uml import cli, const, db


def test_modelafhandeling():
    test_args = [
        "import",
        "-t",
        "eaxmi",
        "-f",
        "./test/data/Test_models.xml",
        "-db_create",
    ]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)
    assert schema.count_package() == 10
    assert schema.count_enumeratie() == 1
    assert schema.count_class() == 4
    assert schema.count_attribute() == 0
    assert schema.count_enumeratieliteral() == 0
    assert schema.count_association() == 1
    assert schema.count_generalizations() == 0
    assert schema.count_diagrams() == 3

    root = schema.get_package("EAPK_3F4BE1F0_796D_489b_9C61_042E7C4E2410")
    assert root.name == "Nested Package Hierarchy"
    assert root.is_model() is True
    # assert len(root.get_submodels()) == 3
    # assert len(root.get_submodels(recursive=True)) == 5
    # assert len(root.get_packages_in_model()) == 1
    # assert len(root.get_classes_in_model()) == 0
    # assert len(root.get_diagrams_in_model()) == 1

    # classdiagram = schema.get_class("EAID_A711D333_4D4A_495b_954F_F39DBC82B935")
    # model = classdiagram.package.get_model()
    # assert model.name == "Package A.1"
    # assert len(model.get_packages_in_model()) == 5
    # assert len(model.get_classes_in_model()) == 1
    # assert len(model.get_diagrams_in_model()) == 2

    # enum = schema.get_enumeration("EAID_AC91B803_296F_441e_9D3B_16542829B697")
    # model = enum.package.get_model()
    # assert model.modelnaam_kort == "A111"
    # assert len(model.get_enumerations_in_model()) == 1
    # assert len(model.get_classes_in_model()) == 2
    # assert len(model.get_diagrams_in_model()) == 0
