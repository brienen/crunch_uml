"""
Attribuut-multipliciteit (lower/upper bound) wordt ingelezen en bewaard.

Aanleiding (GGM v3.0.0): ``verplicht`` stond voor alle 4.925 attributen op 0
en de LOD-export gaf elk attribuut sh:minCount 0 / sh:maxCount 1, terwijl de
EA-bron voor 357 attributen 0..1 en voor enkele 0..* of 1..* vastlegt. De
multipliciteit staat nu in ``Attribute.mult_start``/``mult_end``:

* EA-XMI: ``lowerValue``/``upperValue`` in de modelboom, met de
  ``<bounds lower upper>`` uit de EA-extensie als terugval;
* QEA: ``t_attribute.LowerBound``/``UpperBound``;
* de XMI-renderer schrijft haar weer als lowerValue/upperValue, zodat een
  rondgang haar behoudt.

``verplicht`` blijft ongemoeid (JSON-schema en Excel bouwen daarop).
"""

import os

import pytest

import crunch_uml.schema as sch
from crunch_uml import cli, const, db

FIXTURE = "./test/data/MIM_LOD_Fixture.xml"
SCHEMA = "mim_mult"


def attribuut(schema, suffix):
    kandidaten = [a for a in schema.get_all_attributes() if a.id.endswith(suffix)]
    assert len(kandidaten) == 1, f"attribuut ...{suffix} niet (eenduidig) gevonden"
    return kandidaten[0]


@pytest.fixture(scope="module")
def fixture_schema():
    cli.main(["-sch", SCHEMA, "import", "-f", FIXTURE, "-t", "eaxmi", "-db_create"])
    database = db.Database(const.DATABASE_URL, db_create=False)
    return sch.Schema(database, SCHEMA)


def test_fixture_wordt_volledig_ingelezen(fixture_schema):
    s = fixture_schema
    assert s.count_package() == 5
    assert s.count_class() == 5
    assert s.count_datatype() == 1
    assert s.count_attribute() == 16  # 14 attributen + 2 associatie-einden
    assert s.count_enumeratie() == 1
    assert s.count_enumeratieliteral() == 2
    assert s.count_association() == 2
    assert s.count_generalizations() == 1


@pytest.mark.parametrize(
    "suffix,start,eind",
    [
        ("F001", "1", "1"),  # naam 1..1
        ("F002", "0", "1"),  # geboortedatum 0..1
        ("F003", "0", "-1"),  # telefoonnummers 0..* (EA schrijft -1 in de modelboom)
        ("F004", "1", "1"),  # gewicht
        ("F041", "1", "1"),  # data-element van een datatype
    ],
)
def test_multipliciteit_uit_de_modelboom(fixture_schema, suffix, start, eind):
    attr = attribuut(fixture_schema, suffix)
    assert (attr.mult_start, attr.mult_end) == (start, eind)


def test_bounds_uit_de_ea_extensie_als_terugval(fixture_schema):
    """Zorgverlener.naam heeft geen lowerValue/upperValue in de modelboom,
    alleen <bounds lower="0" upper="1"/> in de extensie."""
    attr = attribuut(fixture_schema, "F011")
    assert attr.name == "naam"
    assert (attr.mult_start, attr.mult_end) == ("0", "1")


def test_verplicht_blijft_ongemoeid(fixture_schema):
    assert all(not attr.verplicht for attr in fixture_schema.get_all_attributes())


def test_qea_leest_lower_en_upperbound():
    cli.main(["-sch", "mim_mult_qea", "import", "-f", "./test/data/Monumenten.qea", "-t", "qea"])
    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database, "mim_mult_qea")
    attributen = [a for a in schema.get_all_attributes() if a.name]
    assert attributen
    assert {(a.mult_start, a.mult_end) for a in attributen} == {("1", "1")}


def test_xmi_rondgang_behoudt_multipliciteit(fixture_schema):
    outputfile = "./test/output/mim_mult_rondgang.xml"
    cli.main(["-sch", SCHEMA, "export", "-f", outputfile, "-t", "xmi"])
    assert os.path.exists(outputfile)
    cli.main(["-sch", "mim_mult_terug", "import", "-f", outputfile, "-t", "eaxmi"])
    database = db.Database(const.DATABASE_URL, db_create=False)
    terug = sch.Schema(database, "mim_mult_terug")
    for suffix, verwacht in (("F001", ("1", "1")), ("F002", ("0", "1")), ("F003", ("0", "-1")), ("F011", ("0", "1"))):
        attr = attribuut(terug, suffix)
        assert (attr.mult_start, attr.mult_end) == verwacht, suffix
    os.remove(outputfile)
