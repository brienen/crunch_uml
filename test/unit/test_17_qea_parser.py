import crunch_uml.schema as sch
from crunch_uml import cli, const, db


def test_import_monumenten_qea():
    """Test importing from an Enterprise Architect .qea repository file."""
    test_args = [
        "import",
        "-f",
        "./test/data/Monumenten.qea",
        "-t",
        "qea",
        "-db_create",
    ]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)

    # Monumenten.qea has 4 packages (Model, Monumenten, Diagram, and one sub-package)
    assert schema.count_package() == 4

    # 6 classes
    assert schema.count_class() == 6

    # 1 enumeration (TypeMonument)
    assert schema.count_enumeratie() == 1

    # 2 enumeration literals (rijksmonument, gemeentelijkmonument)
    assert schema.count_enumeratieliteral() == 2

    # 32 attributes across all classes
    assert schema.count_attribute() == 32

    # 5 associations (monument -> various related classes)
    assert schema.count_association() == 5

    # 0 generalizations in this model
    assert schema.count_generalizations() == 0

    # Verify a specific class exists and has correct GUID-based ID
    bouwactiviteit = schema.get_class("EAID_4AD539EC_A308_43da_B025_17A1647303F3")
    assert bouwactiviteit is not None
    assert bouwactiviteit.name == "Bouwactiviteit"
    assert bouwactiviteit.definitie == "Het bouwen van een bouwwerk."

    # Verify tagged values are applied
    assert bouwactiviteit.gemma_type == "business-object"

    # Verify enumeration
    type_monument = schema.get_enumeration("EAID_5C808AC9_CB09_4f4d_813E_821829856BA8")
    assert type_monument is not None
    assert type_monument.name == "TypeMonument"
