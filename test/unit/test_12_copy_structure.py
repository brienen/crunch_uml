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

    root = schema.get_package('EAPK_45B88627_6F44_4b6d_BE77_3EC51BBE679E')
    kopie_schema = sch.Schema(database, 'kopie')
    kopie = root.get_copy(None)
    kopie_schema.save(kopie, recursive=True)

    kopie2_schema = sch.Schema(database, 'kopie2')
    kopie2 = root.get_copy(None)
    kopie2_schema.save(kopie2, recursive=True)
    database.commit()

    model = schema.get_package('EAPK_F7651B45_2B64_4197_A6E5_BFC56EC98466')
    kopie3_schema = sch.Schema(database, 'kopie3')
    kopie3 = model.get_copy(None)
    kopie3_schema.save(kopie3, recursive=True)
    database.commit()

    assert kopie_schema.count_package() == 3
    assert kopie_schema.count_enumeratie() == 1
    assert kopie_schema.count_class() == 6
    assert kopie_schema.count_attribute() == 40
    assert kopie_schema.count_enumeratieliteral() == 2

    assert kopie2_schema.count_package() == 3
    assert kopie2_schema.count_enumeratie() == 1
    assert kopie2_schema.count_class() == 6
    assert kopie2_schema.count_attribute() == 40
    assert kopie2_schema.count_enumeratieliteral() == 2

    assert kopie3_schema.count_package() == 1
    assert kopie3_schema.count_enumeratie() == 1
    assert kopie3_schema.count_class() == 6
    assert kopie3_schema.count_attribute() == 40
    assert kopie3_schema.count_enumeratieliteral() == 2
    database.close()

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)
    root = schema.get_package('EAPK_45B88627_6F44_4b6d_BE77_3EC51BBE679E')
    kopie_schema = sch.Schema(database, 'kopie4')
    kopie = root.get_copy(None)
    kopie_schema.save(kopie, recursive=True)
    database.commit()
    assert kopie_schema.count_package() == 3
    assert kopie_schema.count_enumeratie() == 1
    assert kopie_schema.count_class() == 6
    assert kopie_schema.count_attribute() == 40
    assert kopie_schema.count_enumeratieliteral() == 2

    root = schema.get_package('EAPK_5B6708DC_CE09_4284_8DCE_DD1B744BB652') # Empty Package
    kopie_schema = sch.Schema(database, 'kopie5')
    kopie = root.get_copy(None)
    class_ambacht = schema.get_class('EAID_54944273_F312_44b2_A78D_43488F915429') # Class Ambacht
    kopie_class_ambacht = class_ambacht.get_copy(kopie)
    kopie_schema.save(kopie, recursive=True)
    database.commit()
    assert kopie_schema.count_package() == 1
    assert kopie_schema.count_enumeratie() == 0
    assert kopie_schema.count_class() == 1
    assert kopie_schema.count_attribute() == 3
    assert kopie_schema.count_enumeratieliteral() == 0

    database.close()


    