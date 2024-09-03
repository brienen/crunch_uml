import os

import crunch_uml.schema as sch
from crunch_uml import cli, const, db, util


def test_import_monumenten():
    outputfile = "./test/output/Monumenten.i18n"

    test_args = ["import", "-f", "./test/data/GGM_Monumenten_EA2.1.xml", "-t", "eaxmi", "-db_create"]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)
    assert schema.count_package() == 3
    assert schema.count_enumeratie() == 1
    assert schema.count_class() == 10
    assert schema.count_attribute() == 40
    assert schema.count_enumeratieliteral() == 2

    # export to json
    test_args = ["export", "-f", outputfile, "-t", "i18n", '--language', 'nl']
    cli.main(test_args)
    assert os.path.exists(outputfile)
    assert util.is_valid_i18n_file(outputfile)
    print("test_import_monumenten passed")
