import crunch_uml.schema as sch
from crunch_uml import cli, const, db


def test_import_onderwijs():
    test_args = ["import", "-f", "./test/data/GGM_Onderwijs_XMI.2.1.xml", "-t", "eaxmi", "-db_create"]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)
    assert schema.count_package() == 3
    assert schema.count_enumeratie() == 1
    assert schema.count_class() == 27
    assert schema.count_attribute() == 16
    assert schema.count_enumeratieliteral() == 5
    assert schema.count_association() == 24

    test_args = [
        "transform",
        "-ttp",
        "plugin",
        "-sch_to",
        "test",
        "-rt_pkg",
        "EAPK_CD9BF007_85C6_4af9_B3F4_2CAB5BF26B5E",
        "--plugin_class_name",
        "TestPlugin",
        "--plugin_file_name",
        "./test/data/testplugin.py",
    ]
    cli.main(test_args)
