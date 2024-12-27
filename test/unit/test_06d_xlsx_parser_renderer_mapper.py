import json
import os

import pandas as pd

import crunch_uml.schema as sch
from crunch_uml import cli, const, db


def are_xlsx_files_equal(file1: str, file2: str, ignore_whitespace: bool = True) -> bool:
    """
    Vergelijk twee Excel-bestanden efficiënt met Pandas.
    :param file1: Pad naar het eerste CSV-bestand.
    :param file2: Pad naar het tweede CSV-bestand.
    :param ignore_whitespace: Negeer extra witruimte bij vergelijking (standaard: True).
    :return: True als de bestanden gelijk zijn, anders False.
    """
    # Laad de CSV-bestanden als DataFrames
    df1 = pd.read_excel(file1)
    df2 = pd.read_excel(file2)

    # Optioneel: Verwijder witruimte van alle cellen
    if ignore_whitespace:
        df1 = df1.apply(lambda col: col.map(lambda x: x.strip() if isinstance(x, str) else x))
        df2 = df2.apply(lambda col: col.map(lambda x: x.strip() if isinstance(x, str) else x))

    # Controleer of de kolommen overeenkomen
    if not df1.columns.equals(df2.columns):
        print(f"Columns do not match:\nFile1: {list(df1.columns)}\nFile2: {list(df2.columns)}")
        return False

    # Sorteer de DataFrames en reset de index
    df1_sorted = df1.sort_values(list(df1.columns)).reset_index(drop=True)
    df2_sorted = df2.sort_values(list(df2.columns)).reset_index(drop=True)

    # Controleer of de DataFrames gelijk zijn
    if not df1_sorted.equals(df2_sorted):
        print("Rows do not match between the two files.")
        return False

    return True


def check_value_in_xlsx(file_path, guid_value, column, column_value):
    """
    Controleer of een rij in een CSV-bestand waar 'GGM_guid' gelijk is aan een bepaalde waarde
    ook een bepaalde waarde heeft in de kolom 'definitie_aangepast'.
    :param file_path: Pad naar het CSV-bestand.
    :param guid_value: Waarde om te zoeken in de kolom 'GGM_guid'.
    :param column_value: Verwachte waarde in de kolom 'definitie_aangepast'.
    :return: True als de waarde overeenkomt, anders False.
    """
    # Lees het CSV-bestand in
    df = pd.read_excel(file_path, sheet_name="classes")

    # Filter de DataFrame op de gewenste rij
    filtered_row = df[df["GGM-guid"] == guid_value]

    # Controleer of de kolom 'definitie_aangepast' de gewenste waarde heeft
    if not filtered_row.empty and (filtered_row[column] == column_value).any():
        return True
    return False


def test_csv_parser_renderer():
    # sourcery skip: extract-duplicate-method, move-assign-in-block
    inputfile = "./test/output/Monumenten_import.xlsx"
    outputfile = "./test/output/Monumenten_export.xlsx"
    mapper = {
        "id": "GGM-guid",
        "gemma_url": "GEMMA-URL",
        "gemma_type": "GEMMA-type",
        "gemma_naam": "GEMMA-naam",
        "definitie": "definitie_aangepast",
        "name": "name_aangepast",
    }
    mapper_reverse = {v: k for k, v in mapper.items()}

    # import monumenten into clean database
    test_args = [
        "import",
        "-f",
        "./test/data/GGM_Monumenten_EA2.1.xml",
        "-t",
        "eaxmi",
        "-db_create",
    ]
    cli.main(test_args)

    # Check if content is correctly loaded
    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)

    assert schema.count_package() == 3
    assert schema.count_enumeratie() == 1
    assert schema.count_class() == 10
    assert schema.count_attribute() == 40
    assert schema.count_enumeratieliteral() == 2

    # export to csv
    test_args = ["export", "-f", inputfile, "-t", "xlsx", "--mapper", str(json.dumps(mapper))]
    cli.main(test_args)
    assert os.path.exists(inputfile)

    # Test of de mappings goed zijn weggeschreeven
    assert check_value_in_xlsx(
        inputfile,
        "EAID_54944273_F312_44b2_A78D_43488F915429",
        "definitie_aangepast",
        "Beroep waarbij een handwerker met gereedschap eindproducten maakt.",
    )
    assert check_value_in_xlsx(inputfile, "EAID_54944273_F312_44b2_A78D_43488F915429", "name_aangepast", "Ambacht")

    # import csv to clean database
    test_args = ["import", "-f", inputfile, "-t", "xlsx", "-db_create", "--mapper", str(json.dumps(mapper_reverse))]
    cli.main(test_args)

    # Check if content is correctly loaded
    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)
    assert schema.count_class() == 10

    # export to csv
    test_args = ["export", "-f", outputfile, "-t", "xlsx", "--mapper", str(json.dumps(mapper))]
    cli.main(test_args)
    assert os.path.exists(outputfile)

    # Check if the contents of the files are equal
    assert are_xlsx_files_equal(outputfile, inputfile)
