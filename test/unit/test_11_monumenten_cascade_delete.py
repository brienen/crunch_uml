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

    enum = schema.get_enumeration('EAID_5C808AC9_CB09_4f4d_813E_821829856BA8')
    session = schema.get_session()
    session.delete(enum)  # Verwijder het object
    session.commit()  # Commit de transactie om de wijzigingen op te slaan
    assert schema.count_package() == 3
    assert schema.count_enumeratie() == 0
    assert schema.count_class() == 10
    assert schema.count_attribute() == 40
    assert schema.count_enumeratieliteral() == 0

    clazz = schema.get_class('EAID_54944273_F312_44b2_A78D_43488F915429')
    session = schema.get_session()
    session.delete(clazz)  # Verwijder het object
    session.commit()  # Commit de transactie om de wijzigingen op te slaan
    assert schema.count_package() == 3
    assert schema.count_enumeratie() == 0
    assert schema.count_class() == 9
    assert schema.count_attribute() == 37
    assert schema.count_enumeratieliteral() == 0

    root = schema.get_package('EAPK_45B88627_6F44_4b6d_BE77_3EC51BBE679E')
    session = schema.get_session()
    session.delete(root)  # Verwijder het object
    session.commit()  # Commit de transactie om de wijzigingen op te slaan
    assert schema.count_package() == 0
    assert schema.count_enumeratie() == 0
    assert schema.count_class() == 4
    assert schema.count_attribute() == 0
    assert schema.count_enumeratieliteral() == 0
    session.close()  # Commit de transactie om de wijzigingen op te slaan
