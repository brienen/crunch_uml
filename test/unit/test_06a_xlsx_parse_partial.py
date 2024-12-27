import crunch_uml.schema as sch
from crunch_uml import cli, const, db


def test_xlsx_parser_renderer():  # sourcery skip: extract-duplicate-method
    # First import Onderwijs into clean database
    test_args = [
        "import",
        "-t",
        "eaxmi",
        "-f",
        "./test/data/GGM_Onderwijs_XMI.2.1.xml",
        "-db_create",
    ]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)

    assert schema.count_package() == 3
    assert schema.count_enumeratie() == 1
    assert schema.count_class() == 27
    assert schema.count_attribute() == 16
    assert schema.count_enumeratieliteral() == 5
    assert schema.count_association() == 24

    assert schema.get_class("EAID_CFFD5F20_5FA9_4d93_AD34_6867D64A58B9").name == "Inschrijving"
    assert (
        schema.get_class("EAID_CFFD5F20_5FA9_4d93_AD34_6867D64A58B9").definitie
        == "Deelname van iemand aan een opleiding bij een onderwijsinstelling."
    )
    assert schema.get_class("EAID_CFFD5F20_5FA9_4d93_AD34_6867D64A58B9").bron is None
    assert (
        schema.get_class("EAID_CFFD5F20_5FA9_4d93_AD34_6867D64A58B9").gemma_url
        == "https://gemmaonline.nl/index.php/GEMMA/id-5e8930d4-8f06-4075-bf2b-31f45ee86dbc"
    )
    assert schema.get_class("EAID_CFFD5F20_5FA9_4d93_AD34_6867D64A58B9").author == "crossover"

    assert schema.get_class("EAID_266057AF_58BD_42e1_B4D5_16EB266B9B7A").name == "Leerling"
    assert (
        schema.get_class("EAID_266057AF_58BD_42e1_B4D5_16EB266B9B7A").definitie
        == "Mens die een opleiding volgt, heeft gevolgd of gaat volgen of opgaat of is opgegaan voor een toets. (Bron: KOI)"
    )
    assert schema.get_class("EAID_266057AF_58BD_42e1_B4D5_16EB266B9B7A").bron is None
    assert (
        schema.get_class("EAID_266057AF_58BD_42e1_B4D5_16EB266B9B7A").gemma_url
        == "https://gemmaonline.nl/index.php/GEMMA/id-e2ea124f-56ce-4614-9e32-0f13371a5ede"
    )
    assert schema.get_class("EAID_266057AF_58BD_42e1_B4D5_16EB266B9B7A").author == "Arjen Brienen"

    # Now import partial XLSX file into database
    test_args = [
        "import",
        "-t",
        "xlsx",
        "-f",
        "./test/data/OntbrekendeDefinitiesGGM.xlsx",
        "--update_only",
    ]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema_updates = sch.Schema(database)

    assert schema_updates.get_class("EAID_CFFD5F20_5FA9_4d93_AD34_6867D64A58B9").name == "Inschrijving"
    assert schema_updates.get_class("EAID_CFFD5F20_5FA9_4d93_AD34_6867D64A58B9").definitie == "XXXX Test description"
    assert schema_updates.get_class("EAID_CFFD5F20_5FA9_4d93_AD34_6867D64A58B9").bron == "XXXX Test Bron"
    assert (
        schema_updates.get_class("EAID_CFFD5F20_5FA9_4d93_AD34_6867D64A58B9").gemma_url
        == "https://gemmaonline.nl/index.php/GEMMA/id-5e8930d4-8f06-4075-bf2b-31f45ee86dbc"
    )
    assert schema_updates.get_class("EAID_CFFD5F20_5FA9_4d93_AD34_6867D64A58B9").author == "crossover"

    assert schema_updates.get_class("EAID_266057AF_58BD_42e1_B4D5_16EB266B9B7A").name == "Leerling"
    assert schema_updates.get_class("EAID_266057AF_58BD_42e1_B4D5_16EB266B9B7A").definitie == "XXXX Test description"
    assert schema_updates.get_class("EAID_266057AF_58BD_42e1_B4D5_16EB266B9B7A").bron == "XXXX Test Bron"
    assert (
        schema_updates.get_class("EAID_266057AF_58BD_42e1_B4D5_16EB266B9B7A").gemma_url
        == "https://gemmaonline.nl/index.php/GEMMA/id-e2ea124f-56ce-4614-9e32-0f13371a5ede"
    )
    assert schema_updates.get_class("EAID_266057AF_58BD_42e1_B4D5_16EB266B9B7A").author == "Arjen Brienen"

    assert schema_updates.count_class() == 27
