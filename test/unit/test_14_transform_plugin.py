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


def test_ddas_plugin():
    test_args = ["import", "-t", "eaxmi", "-f", "./test/data/Model Schuldhulpverlening.xml", "-db_create"]
    cli.main(test_args)

    # database = db.Database(const.DATABASE_URL, db_create=False)
    # schema = sch.Schema(database)
    # root = schema.get_package('EAPK_06C51790_1F81_4ac4_8E16_5177352EF2E1')
    # kopie = root.get_copy(None)
    # kopie_schema = sch.Schema(database, 'schuldhulp')
    # kopie_schema.add(kopie, recursive=True)

    # database = db.Database(const.DATABASE_URL, db_create=False)
    # schema = sch.Schema(database, 'schuldhulp')
    # assert schema.count_package() == 1
    # assert schema.count_enumeratie() == 6
    # assert schema.count_class() == 31
    # assert schema.count_attribute() == 114
    # assert schema.count_enumeratieliteral() == 20

    test_args = [
        "transform",
        "-ttp",
        "plugin",
        "-sch_from",
        "default",
        "-sch_to",
        "uitwisselmodel",
        "-rt_pkg",
        "EAPK_06C51790_1F81_4ac4_8E16_5177352EF2E1",
        "--plugin_class_name",
        "DDASPlugin",
        "--plugin_file_name",
        "./test/data/ddasplugin.py",
    ]
    cli.main(test_args)

    test_args = [
        "-sch",
        "uitwisselmodel",
        "export",
        "-t",
        "json_schema",
        "--output_class_id",
        "EAID_6b4326e3_eb4e_41d2_902b_0bff06604f63",
        "-f",
        "./test/output/json_schema.json",
    ]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database, 'uitwisselmodel')
    assert schema.count_package() == 1
