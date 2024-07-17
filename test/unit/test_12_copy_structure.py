import crunch_uml.schema as sch
from crunch_uml import cli, const, db


def test_import_monumenten():
    test_args = ["import", "-f", "./test/data/GGM_Monumenten_EA2.1.xml", "-t", "eaxmi", "-db_create"]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)
    assert schema.count_package() == 3
    assert schema.count_enumeratie() == 1
    assert schema.count_class() == 10
    assert schema.count_attribute() == 40
    assert schema.count_enumeratieliteral() == 2
    assert schema.count_association() == 9

    root = schema.get_package('EAPK_45B88627_6F44_4b6d_BE77_3EC51BBE679E')  # Main Package
    kopie_schema = sch.Schema(database, 'kopie')
    kopie = root.get_copy(None)
    kopie_schema.add(kopie, recursive=True)

    kopie2_schema = sch.Schema(database, 'kopie2')
    kopie2 = root.get_copy(None)
    kopie2_schema.add(kopie2, recursive=True)
    database.commit()

    model = schema.get_package('EAPK_F7651B45_2B64_4197_A6E5_BFC56EC98466')  # Model Package
    kopie3_schema = sch.Schema(database, 'kopie3')
    kopie3 = model.get_copy(None)
    kopie3_schema.add(kopie3, recursive=True)
    database.commit()

    assert kopie_schema.count_package() == 3
    assert kopie_schema.count_enumeratie() == 1
    assert kopie_schema.count_class() == 6
    assert kopie_schema.count_attribute() == 40
    assert kopie_schema.count_enumeratieliteral() == 2
    assert kopie_schema.count_association() == 5

    assert kopie2_schema.count_package() == 3
    assert kopie2_schema.count_enumeratie() == 1
    assert kopie2_schema.count_class() == 6
    assert kopie2_schema.count_attribute() == 40
    assert kopie2_schema.count_enumeratieliteral() == 2
    assert kopie2_schema.count_association() == 5

    assert kopie3_schema.count_package() == 1
    assert kopie3_schema.count_enumeratie() == 1
    assert kopie3_schema.count_class() == 6
    assert kopie3_schema.count_attribute() == 40
    assert kopie3_schema.count_enumeratieliteral() == 2
    assert kopie3_schema.count_association() == 5
    database.close()

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)
    root = schema.get_package('EAPK_45B88627_6F44_4b6d_BE77_3EC51BBE679E')  # Main Package
    kopie_schema = sch.Schema(database, 'kopie4')
    kopie = root.get_copy(None)
    kopie_schema.add(kopie, recursive=True)
    database.commit()
    assert kopie_schema.count_package() == 3
    assert kopie_schema.count_enumeratie() == 1
    assert kopie_schema.count_class() == 6
    assert kopie_schema.count_attribute() == 40
    assert kopie_schema.count_enumeratieliteral() == 2
    assert kopie_schema.count_association() == 5
    database.close()

    database = db.Database(const.DATABASE_URL, db_create=False)
    root = schema.get_package('EAPK_5B6708DC_CE09_4284_8DCE_DD1B744BB652')  # Diagram Package
    kopie_schema6 = sch.Schema(database, 'kopie6')
    kopie = root.get_copy(None)
    kopie_schema6.add(kopie, recursive=True)
    database.commit()
    assert kopie_schema6.count_package() == 1
    assert kopie_schema6.count_enumeratie() == 1
    assert kopie_schema6.count_class() == 6
    assert kopie_schema6.count_attribute() == 40
    assert kopie_schema6.count_enumeratieliteral() == 2
    assert kopie_schema6.count_diagrams() == 2

    database.close()
