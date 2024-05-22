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
    kopie2_schema = sch.Schema(database, 'kopie2')
    kopie = root.get_copy(None)
    kopie_schema.save(kopie, recursive=True)
    database.commit()
    #kopie = root.get_copy(None)
    #kopie2_schema.save(kopie, recursive=True)
    #database.commit()
    assert kopie_schema.count_package() == 3
    assert kopie_schema.count_enumeratie() == 1
    assert kopie_schema.count_class() == 6
    assert kopie_schema.count_attribute() == 40
    assert kopie_schema.count_enumeratieliteral() == 2
    database.close()

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)
    root = schema.get_package('EAPK_45B88627_6F44_4b6d_BE77_3EC51BBE679E')
    kopie_schema = sch.Schema(database, 'kopie2')
    kopie = root.get_copy(None)
    #kopie_schema.save(kopie, recursive=True)
    database.commit()
    #assert kopie_schema.count_package() == 3
    #assert kopie_schema.count_enumeratie() == 1
    #assert kopie_schema.count_class() == 6
    #assert kopie_schema.count_attribute() == 40
    #assert kopie_schema.count_enumeratieliteral() == 2
    database.close()

    #database = db.Database(const.DATABASE_URL, db_create=False)
    #schema = sch.Schema(database)
    #clazz = schema.get_class('EAID_4AD539EC_A308_43da_B025_17A1647303F3')
    #clazz_schema = sch.Schema(database, 'clazz')
    #clazz_kopie = clazz.get_copy()
    #clazz_schema.save(clazz_kopie, recursive=True)
    #database.commit()


    