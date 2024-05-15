import crunch_uml.schema as sch
from crunch_uml import cli, const, db


def test_import_monumenten():
    test_args = [
        "import",
        "-url",
        "https://raw.githubusercontent.com/brienen/crunch_uml/main/test/data/GGM_Monumenten_EA2.1.xml",
        "-t",
        "eaxmi",
        "-db_create",
    ]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)
    assert schema.count_package() == 3
    assert schema.count_enumeratie() == 1
    assert schema.count_class() == 10
    assert schema.count_attribute() == 40
    assert schema.count_enumeratieliteral() == 2

    clazz = schema.get_class('EAID_4AD539EC_A308_43da_B025_17A1647303F3')
    assert clazz.gemma_type == 'business-object'
    assert clazz.gemma_url == 'https://gemmaonline.nl/index.php/GEMMA2/0.9/id-2b2319c1-d5b9-43c6-87cb-43bb194c65c6'
    assert clazz.definitie == 'Het bouwen van een bouwwerk.'
