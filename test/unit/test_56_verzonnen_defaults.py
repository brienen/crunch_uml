"""
Wat de bron niet levert wordt niet verzonnen (0.8.7).

Aanleiding: een EA-model zonder MIM-tags (XMI 2.1) kreeg in de LOD-export wel
``sh:maxCount`` maar nergens ``sh:minCount``. De kolom ``mogelijk_geen_waarde``
had de default "Ja", zodat elk attribuut en elke relatie zonder die tag als
'mogelijk geen waarde' gold en ``sh:minCount`` verviel (MIM 6.4.9.18). De
kolom heeft geen default meer; de export kiest de MIM-default (Nee).

Bijvangst in dezelfde hoek:

* de xmi-parser bewaarde een ontbrekende multipliciteit van een relatie als
  de tekst 'None';
* ``Association.isGelimiteerdMeervoudig(dst=False)`` keek naar de ondergrens;
* de SQLAlchemy-export bepaalde ``nullable`` van een vreemde sleutel uit de
  verkeerde zijde van de relatie.
"""

import glob
import os

import pytest
from rdflib import Graph, Literal
from rdflib.namespace import SH

import crunch_uml.schema as sch
from crunch_uml import cli, const, db
from crunch_uml.renderers.lod_mim import MIM

# Een GGM-uitsnede in EA XMI 2.1 zonder de tag 'mogelijk geen waarde'.
BRON = "./test/data/GGM_Monumenten_EA2.1.xml"
SCHEMA = "geen_default"
BASE = "https://voorbeeld.nl/monumenten/"
OUTPUT = "./test/output/geen_default.ttl"
SQLA_DIR = "./test/output/sqla56"


@pytest.fixture(scope="module", params=["xmi", "eaxmi"])
def ingelezen(request):
    cli.main(["-sch", SCHEMA, "import", "-f", BRON, "-t", request.param, "-db_create"])
    database = db.Database(const.DATABASE_URL, db_create=False)
    return sch.Schema(database, SCHEMA)


def test_bron_zonder_tag_geeft_geen_mogelijk_geen_waarde(ingelezen):
    attributen = ingelezen.get_all_attributes()
    associaties = ingelezen.get_all_associations()
    assert attributen and associaties
    assert {a.mogelijk_geen_waarde for a in attributen} == {None}
    assert {a.mogelijk_geen_waarde for a in associaties} == {None}


def test_ontbrekende_multipliciteit_van_relatie_is_null(ingelezen):
    waarden = set()
    for assoc in ingelezen.get_all_associations():
        waarden |= {assoc.src_mult_start, assoc.src_mult_end, assoc.dst_mult_start, assoc.dst_mult_end}
    assert None in waarden  # de bron heeft een relatie zonder multipliciteit
    assert "None" not in waarden


def test_mincount_blijft_staan_zonder_tag(ingelezen):
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    cli.main(["-sch", SCHEMA, "export", "-f", OUTPUT, "-t", "ttl", "--linked_data_namespace", BASE])
    graaf = Graph()
    graaf.parse(OUTPUT, format="turtle")
    os.remove(OUTPUT)

    verplicht = set(graaf.subjects(MIM.kardinaliteit, Literal("1..1")))
    assert len(verplicht) > 10
    for prop in verplicht:
        shapes = list(graaf.subjects(SH.path, prop))
        assert len(shapes) == 1
        assert (shapes[0], SH.minCount, Literal(1)) in graaf, f"sh:minCount ontbreekt voor {prop}"
        assert (shapes[0], SH.maxCount, Literal(1)) in graaf
    assert (None, MIM.mogelijkGeenWaarde, Literal(True)) not in graaf
    assert (None, MIM.mogelijkGeenWaarde, Literal(False)) in graaf


@pytest.mark.parametrize(
    "eind,dst,verwacht",
    [
        ("1", True, False),
        ("5", True, True),
        ("-1", True, False),
        ("1", False, False),
        ("5", False, True),
        (None, False, False),
    ],
)
def test_gelimiteerd_meervoudig_kijkt_naar_de_bovengrens(eind, dst, verwacht):
    # De ondergrens is aan beide zijden 2: alleen de bovengrens telt.
    assoc = db.Association(src_mult_start="2", dst_mult_start="2")
    if dst:
        assoc.dst_mult_end = eind
    else:
        assoc.src_mult_end = eind
    assert assoc.isGelimiteerdMeervoudig(dst=dst) is verwacht


def bouw_zaakmodel():
    database = db.Database(const.DATABASE_URL, db_create=True)
    schema = sch.Schema(database)
    schema.save(db.Package(id="EAPK_ROOT", name="Test"))
    schema.save(db.Package(id="EAPK_ZAKEN", name="Model Zaken", parent_package_id="EAPK_ROOT", modelnaam_kort="zkn"))
    for naam in ("Zaak", "Zaaktype", "Behandelaar", "Besluit", "Dossier", "Notitie"):
        schema.save(db.Class(id=f"EAID_{naam.upper()}", name=naam, package_id="EAPK_ZAKEN", stereotype="Objecttype"))

    def relatie(id, bron, bron_mult, doel, doel_mult):
        schema.save(
            db.Association(
                id=id,
                name=f"{bron} {doel}",
                src_class_id=f"EAID_{bron.upper()}",
                src_mult_start=bron_mult[0],
                src_mult_end=bron_mult[1],
                dst_class_id=f"EAID_{doel.upper()}",
                dst_mult_start=doel_mult[0],
                dst_mult_end=doel_mult[1],
            )
        )

    # Sleutel bij de bron (n-1): verplicht als de doelzijde minimaal 1 is.
    relatie("EAID_R1", "Zaak", ("0", "-1"), "Zaaktype", ("1", "1"))
    relatie("EAID_R2", "Zaak", ("1", "-1"), "Behandelaar", ("0", "1"))
    # Sleutel bij het doel (1-n): verplicht als de bronzijde minimaal 1 is.
    relatie("EAID_R3", "Zaak", ("1", "1"), "Besluit", ("1", "-1"))
    relatie("EAID_R4", "Dossier", ("0", "1"), "Notitie", ("0", "-1"))
    database.commit()


def test_sqla_nullable_volgt_de_zijde_waar_de_sleutel_naar_wijst():
    bouw_zaakmodel()
    os.makedirs(SQLA_DIR, exist_ok=True)
    for f in glob.glob(f"{SQLA_DIR}/*.py"):
        os.remove(f)
    cli.main(["export", "-t", "sqla", "-f", f"{SQLA_DIR}/model.py"])
    bestanden = glob.glob(f"{SQLA_DIR}/*.py")
    assert len(bestanden) == 1
    with open(bestanden[0], encoding="utf-8") as fh:
        regels = [regel.strip() for regel in fh if "_id: Mapped[" in regel]
    os.remove(bestanden[0])

    def sleutel(naam):
        gevonden = [regel for regel in regels if regel.startswith(f"{naam}: ")]
        assert len(gevonden) == 1, f"{naam}: {gevonden}"
        return gevonden[0]

    assert len(regels) == 4
    # Zaak 0..* -> Zaaktype 1..1: elke zaak heeft een zaaktype.
    assert "Mapped[int]" in sleutel("zaaktype_id") and "nullable=False" in sleutel("zaaktype_id")
    # Zaak 1..* -> Behandelaar 0..1: een zaak kan zonder behandelaar.
    assert "Mapped[Optional[int]]" in sleutel("behandelaar_id") and "nullable=True" in sleutel("behandelaar_id")
    # Zaak 1..1 -> Besluit 1..*: elk besluit hoort bij een zaak.
    assert "Mapped[int]" in sleutel("zaak_id") and "nullable=False" in sleutel("zaak_id")
    # Dossier 0..1 -> Notitie 0..*: een notitie kan zonder dossier.
    assert "Mapped[Optional[int]]" in sleutel("dossier_id") and "nullable=True" in sleutel("dossier_id")
