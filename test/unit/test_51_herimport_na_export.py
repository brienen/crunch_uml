"""
Een herimport met -db_create in hetzelfde proces als een eerdere import en
export (zoals de testsuite en scripts doen) mag niet struikelen over de
objecten die de SQLAlchemy-sessie nog kent.

Aanleiding: na een LOD-export bleven de modelobjecten als referentiecycli in
de sessie hangen tot de garbage collector langskwam; ``-db_create`` dropte de
tabellen maar liet de identity map staan, en de herimport probeerde die
'persistente' objecten te UPDATEn ("expected to update 1 row(s); 0 were
matched"). ``_reset_database`` maakt nu eerst de sessie leeg.
"""

import os

import crunch_uml.schema as sch
from crunch_uml import cli, const, db

FIXTURE = "./test/data/GGM_Monumenten_EA2.1.xml"


def test_herimport_met_db_create_na_export():
    cli.main(["import", "-f", FIXTURE, "-t", "eaxmi", "-db_create"])
    outputfile = "./test/output/herimport.ttl"
    cli.main(["export", "-f", outputfile, "-t", "ttl"])

    # Houd de objecten expliciet vast: zo zitten ze zeker nog in de identity
    # map op het moment van de herimport.
    database = db.Database(const.DATABASE_URL, db_create=False)
    vastgehouden = sch.Schema(database).get_all_classes()
    assert vastgehouden
    assert len(database.session.identity_map) > 0

    cli.main(["import", "-f", FIXTURE, "-t", "eaxmi", "-db_create"])
    schema = sch.Schema(db.Database(const.DATABASE_URL, db_create=False))
    assert schema.count_class() == 11
    assert schema.count_attribute() == 41
    assert len(vastgehouden) == 11  # alleen om de referentie in leven te houden
    os.remove(outputfile)
