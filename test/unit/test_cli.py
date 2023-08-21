from crunch_uml import cli
from crunch_uml import db
from crunch_uml import const
import pytest

def test_main():
    test_args = ["-f", "./test/data/GGM_Onderwijs_XMI.2.1.xml", "-v"]
    cli.main(test_args)

    database = db.Database(const.DATABASE_URL, db_create=True)
    assert database.count_packages == 3
    assert database.count_enumeratie == 1
