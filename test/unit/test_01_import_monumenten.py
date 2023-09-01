from crunch_uml import cli, const, db


def test_import_monumenten():
    test_args = ["import", "-f", "./test/data/GGM_Monumenten_EA2.1.xml", "-t", "eaxmi", "-db_create"]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    assert database.count_package() == 3
    assert database.count_enumeratie() == 1
    assert database.count_class() == 10
    assert database.count_attribute() == 40
    assert database.count_enumeratieliteral() == 2

    clazz = database.get_class('EAID_4AD539EC_A308_43da_B025_17A1647303F3')
    assert clazz.archimate_type == 'Business object'
    assert clazz.gemma_guid == 'id-4ad539ec-a308-43da-b025-17a1647303f3'
    assert clazz.definitie == 'Het bouwen van een bouwwerk.'
