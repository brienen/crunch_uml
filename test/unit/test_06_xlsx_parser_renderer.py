import os

import pandas as pd

from crunch_uml import cli, const, db


def are_excel_files_equal(file1_path, file2_path):
    # Laad de Excel-bestanden
    xls1 = pd.ExcelFile(file1_path)
    xls2 = pd.ExcelFile(file2_path)

    # Krijg de namen van alle tabbladen in elk bestand
    file1_sheets = xls1.sheet_names
    file2_sheets = xls2.sheet_names

    # Check of de twee bestanden hetzelfde aantal tabbladen hebben
    if set(file1_sheets) != set(file2_sheets):
        return False

    # Loop door elk tabblad en vergelijk de gegevens
    for sheet in file1_sheets:
        df1 = xls1.parse(sheet)
        df2 = xls2.parse(sheet)

        # Pandas heeft een handige methode 'equals' om dataframes te vergelijken
        if not df1.equals(df2):
            return False

    # Als alle tabbladen hetzelfde zijn
    return True


def test_xlsx_parser_renderer():  # sourcery skip: extract-duplicate-method
    inputfile = "./test/output/Onderwijs_input.xlsx"
    outputfile = "./test/output/Onderwijs_output.xlsx"

    # import monumenten into clean database
    test_args = ["import", "-t", "xmi", "-f", "./test/data/GGM_Onderwijs_XMI.2.1.xml", "-db_create"]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    assert database.count_package() == 3
    assert database.count_enumeratie() == 1
    assert database.count_class() == 27
    assert database.count_attribute() == 16
    assert database.count_enumeratieliteral() == 5
    assert database.count_association() == 24

    # export to xlsx
    test_args = ["export", "-f", inputfile, "-t", "xlsx"]
    cli.main(test_args)
    assert os.path.exists(inputfile)

    # import xlsx to clean database
    test_args = ["import", "-f", inputfile, "-t", "xlsx", "-db_create"]
    cli.main(test_args)

    # Check if data is correctly read
    database = db.Database(const.DATABASE_URL, db_create=False)
    assert database.count_package() == 3
    assert database.count_enumeratie() == 1
    assert database.count_class() == 27
    assert database.count_attribute() == 16
    assert database.count_enumeratieliteral() == 5
    assert database.count_association() == 24

    # export to output xlsx
    test_args = ["export", "-f", outputfile, "-t", "xlsx"]
    cli.main(test_args)
    assert os.path.exists(outputfile)

    # Check if the contents of the files are equal
    assert are_excel_files_equal(inputfile, outputfile)

    # Cleanup
    os.remove(outputfile)


def test_xlsx_parser_and_changes():  # sourcery skip: extract-duplicate-method
    inputfile = "./test/data/Onderwijs.xlsx"
    inputfile = "./test/output/Onderwijs_input.xlsx"
    changefile = "./test/data/Onderwijs_changes.xlsx"

    # import inputfile into clean database
    # import xlsx to clean database
    test_args = ["import", "-f", inputfile, "-t", "xlsx", "-db_create"]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    assert database.count_package() == 3
    assert database.count_enumeratie() == 1
    assert database.count_class() == 27
    assert database.count_attribute() == 16
    assert database.count_enumeratieliteral() == 5
    assert database.count_association() == 24

    # import changes into database
    test_args = ["import", "-t", "xlsx", "-f", changefile]
    cli.main(test_args)

    # Check if content is correctly loaded
    database = db.Database(const.DATABASE_URL, db_create=False)
    assert database.count_package() == 3
    assert database.count_enumeratie() == 1
    assert database.count_class() == 27
    assert database.count_attribute() == 16
    assert database.count_enumeratieliteral() == 5
    assert database.count_association() == 24

    # Zoek alle voorkomens van het type Package waar definitie de waarde "Test" heeft
    assert database.get_session().query(db.Attribute).filter(db.Attribute.definitie == "Test Descr").count() == 15

    # Zoek alle voorkomens van het type Generalization waar definitie de waarde "Test" heeft
    assert (
        database.get_session().query(db.Generalization).filter(db.Generalization.definitie == "Test Descr").count() == 4
    )
