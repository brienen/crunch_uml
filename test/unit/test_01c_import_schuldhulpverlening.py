import crunch_uml.schema as sch
from crunch_uml import cli, const, db


def test_import_schuldhulpverlening():
    test_args = ["import", "-t", "eaxmi", "-f", "./test/data/Model Schuldhulpverlening.xml", "-db_create"]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)
    assert schema.count_package() == 3
    assert schema.count_enumeratie() == 5
    assert schema.count_class() == 61
    assert schema.count_attribute() == 127
    assert schema.count_enumeratieliteral() == 20
    assert schema.count_association() == 64
    assert schema.count_generalizations() == 4
    assert schema.count_diagrams() == 5

    budgetcoaching = schema.get_enumeration_literal('EAID_8DAEAE4A_D0E0_46b8_8642_8D29EA4C39EE')
    assert budgetcoaching.name == 'Budgetcoaching'
    assert budgetcoaching.type == 'BC'

    organisatiediagram = schema.get_diagram('EAID_752DF3AE_43AC_4165_8FCD_FDDE73075872')
    assert len(organisatiediagram.classes) == 7
    assert len(organisatiediagram.enumerations) == 2
    assert len(organisatiediagram.associations) == 8
    assert len(organisatiediagram.generalizations) == 1
