import json
import os

import crunch_uml.schema as sch
from crunch_uml import cli, const, db, util


def test_import_monumenten():
    outputfile = "./test/output/Monumenten.i18n"

    test_args = ["import", "-f", "./test/data/GGM_Monumenten_EA2.1.xml", "-t", "eaxmi", "-db_create"]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)
    assert schema.count_package() == 3
    assert schema.count_enumeratie() == 1
    assert schema.count_class() == 10
    assert schema.count_attribute() == 40
    assert schema.count_enumeratieliteral() == 2

    # export to json
    test_args = ["export", "-f", outputfile, "-t", "i18n", '--language', 'nl']
    cli.main(test_args)
    assert os.path.exists(outputfile)
    assert util.is_valid_i18n_file(outputfile)
    print("test_import_monumenten passed")

    # Open en laad het eerste JSON-bestand
    data = None
    with open(outputfile, 'r') as file1:
        data = json.load(file1)
        ambacht = data['nl']['classes'][0]['EAID_54944273_F312_44b2_A78D_43488F915429']
        ambacht['name'] = 'Ambacht_name'
        ambacht['alias'] = 'Ambacht_alias'
        ambacht['definitie'] = 'Ambacht_definitie'
        ambacht['toelichting'] = 'Ambacht_toelichting'
        ambacht['stereotype'] = 'Ambacht_stereotype'
        ambacht['synoniemen'] = 'Ambacht_synoniemen'
        data['nl']['classes'][0]['EAID_54944273_F312_44b2_A78D_43488F915429'] = ambacht

    with open(outputfile, "w") as json_file:
        json.dump(data, json_file, ensure_ascii=False, indent=4, default=str)

    test_args = ["import", "-f", outputfile, "-t", "i18n", '--language', 'nl']
    cli.main(test_args)
    print("data saved")

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)
    clazz = schema.get_class('EAID_54944273_F312_44b2_A78D_43488F915429')
    assert clazz.name == 'Ambacht_name'
    assert clazz.alias == 'Ambacht_alias'
    assert clazz.definitie == 'Ambacht_definitie'
    assert clazz.toelichting == 'Ambacht_toelichting'
    assert clazz.stereotype == 'Ambacht_stereotype'
    assert clazz.synoniemen == 'Ambacht_synoniemen'
    print("test_import_monumenten passed")
