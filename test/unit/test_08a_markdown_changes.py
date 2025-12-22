import os

import crunch_uml.schema as sch
from crunch_uml import cli, const, db


def test_markdown_monumenten_onderwijs():
    dir = "./test/output/"

    test_args = [
        "import",
        "-f",
        "./test/data/GGM_Monumenten_EA2.1.xml",
        "-t",
        "eaxmi",
        "-db_create",
    ]
    cli.main(test_args)

    test_args = [
        "transform",
        "-ttp",
        "copy",
        "-sch_to",
        "new",
        "-rt_pkg",
        "EAPK_F7651B45_2B64_4197_A6E5_BFC56EC98466",
    ]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database, schema_name="new")
    assert schema.count_package() == 1
    assert schema.count_enumeratie() == 1
    assert schema.count_class() == 6
    assert schema.count_attribute() == 41
    assert schema.count_enumeratieliteral() == 2

    test_args = ["-sch", "old_raw", "import", "-f", "./test/data/GGM_Monumenten_Changed_EA2.1.xml", "-t", "eaxmi"]
    cli.main(test_args)

    test_args = [
        "transform",
        "-ttp",
        "copy",
        "-sch_from",
        "old_raw",
        "-sch_to",
        "old",
        "-rt_pkg",
        "EAPK_F7651B45_2B64_4197_A6E5_BFC56EC98466",
    ]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database, schema_name="old")
    assert schema.count_package() == 1
    assert schema.count_enumeratie() == 1
    assert schema.count_class() == 6
    assert schema.count_attribute() == 32
    assert schema.count_enumeratieliteral() == 3

    test_args = [
        "-sch",
        "new",
        "export",
        "-t",
        "diff_md",
        "-f",
        f"{dir}GGM_Changes.md",
        "--compare_schema_name",
        "old",
        "--compare_title",
        "Oud_tegen_nieuw",
    ]
    cli.main(test_args)

    monfilename = f"{dir}GGM_Changes.md"
    assert os.path.exists(monfilename)
    assert open(monfilename, "r").read().find("Bouwstijl — **Removed**")
    assert open(monfilename, "r").read().find("omschrijving — **Added**")
    assert open(monfilename, "r").read().find("toelichting — **Removed**")
    assert open(monfilename, "r").read().find("`test` — **Added**")
