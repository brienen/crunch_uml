import crunch_uml.schema as sch
from crunch_uml import cli, const, db


def test_import_schuldhulp():
    test_args = ["import", "-f", "./test/data/Model Schuldhulpverlening.xml", "-t", "eaxmi", "-db_create"]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)
    assert schema.count_package() == 3
    assert schema.count_enumeratie() == 6
    assert schema.count_class() == 36
    assert schema.count_attribute() == 112
    assert schema.count_enumeratieliteral() == 20


    test_args = [
        "transform",
        "-ttp",
        "copy",
        "-sch_to",
        "schuldhulp",
        "-rt_pkg",
        "EAPK_06C51790_1F81_4ac4_8E16_5177352EF2E1",
    ]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database, 'schuldhulp')
    assert schema.count_package() == 1
    assert schema.count_enumeratie() == 6
    assert schema.count_class() == 31
    assert schema.count_attribute() == 112
    assert schema.count_enumeratieliteral() == 20

    test_args = [
        "export",
        "-t", "json_schema",
        "-f", "./test/output/schema.json",
        "--output_class_id", "EAID_839017B2_0F95_42d0_AB2B_E873636340DA",
        #"-sch", "schuldhulp"
    ]
    cli.main(test_args)
    assert schema.count_package() == 1
