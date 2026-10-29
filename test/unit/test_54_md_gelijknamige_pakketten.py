"""
Tests voor de documentatie van gelijknamige pakketten en van pakketten met alleen
enumeraties (0.8.4).

Een model is een pakket met klassen of enumeraties: 'Datatypes' naast een model, met
alleen enumeraties, krijgt nu een eigen pagina. Het GGM heeft zes pakketten 'Datatypes'
en drie 'Enumeratiesoort'; die schreven tot 0.8.3 hetzelfde bestand en overschreven
elkaar. Een naam die vaker voorkomt krijgt het bovenliggende pakket erachter, en zo
nodig nog een niveau hoger; een unieke naam blijft ongewijzigd.
"""

import glob
import os

import crunch_uml.schema as sch
from crunch_uml import cli, const, db

DIR = "./test/output/md54"


def bouw_model():
    database = db.Database(const.DATABASE_URL, db_create=True)
    schema = sch.Schema(database)

    def pkg(id, name, parent=None):
        schema.save(db.Package(id=id, name=name, parent_package_id=parent))

    def enum(id, name, package, literal):
        schema.save(db.Enumeratie(id=id, name=name, package_id=package, definitie=f"Definitie van {name}"))
        schema.save(db.EnumerationLiteral(id=id + "_L", name=literal, enumeratie_id=id))

    pkg("EAPK_ROOT", "Test")
    pkg("EAPK_INKOMEN", "Inkomen", "EAPK_ROOT")
    # Twee pakketten 'Datatypes' met alleen enumeraties, onder verschillende ouders.
    pkg("EAPK_REDEN", "Reden aanvraag", "EAPK_INKOMEN")
    pkg("EAPK_REDEN_DT", "Datatypes", "EAPK_REDEN")
    enum("EAID_E_REDEN", "RedenSoort", "EAPK_REDEN_DT", "verhuizing")
    pkg("EAPK_DIENSTEN", "Diensten", "EAPK_INKOMEN")
    pkg("EAPK_DIENSTEN_DT", "Datatypes", "EAPK_DIENSTEN")
    enum("EAID_E_DIENST", "DienstSoort", "EAPK_DIENSTEN_DT", "advies")
    # Een derde 'Datatypes' mét een klasse, en een model met een unieke naam.
    pkg("EAPK_NORM", "Normafwijking", "EAPK_INKOMEN")
    pkg("EAPK_NORM_DT", "Datatypes", "EAPK_NORM")
    schema.save(db.Class(id="EAID_BEDRAG", name="Bedrag", package_id="EAPK_NORM_DT", stereotype="Objecttype"))
    pkg("EAPK_MODEL_DIENSTEN", "Model Diensten", "EAPK_DIENSTEN")
    schema.save(db.Class(id="EAID_DIENST", name="Dienst", package_id="EAPK_MODEL_DIENSTEN", stereotype="Objecttype"))
    schema.save(
        db.Attribute(id="EAID_DIENST_SOORT", name="soort", clazz_id="EAID_DIENST", enumeration_id="EAID_E_DIENST")
    )
    # Een pakket zonder klassen en zonder enumeraties is geen model.
    pkg("EAPK_LEEG", "Leeg", "EAPK_INKOMEN")
    database.commit()


def test_gelijknamige_pakketten_en_enumeratiepakketten():
    bouw_model()
    os.makedirs(DIR, exist_ok=True)
    for f in glob.glob(f"{DIR}/*.md"):
        os.remove(f)
    cli.main(["export", "-t", "ggm_md", "-f", f"{DIR}/defs.md"])

    bestanden = sorted(os.path.basename(f) for f in glob.glob(f"{DIR}/*.md"))
    assert bestanden == [
        "defs_Datatypes (Diensten).md",
        "defs_Datatypes (Normafwijking).md",
        "defs_Datatypes (Reden aanvraag).md",
        "defs_Model Diensten.md",
    ]
    with open(f"{DIR}/defs_Datatypes (Reden aanvraag).md", encoding="utf-8") as fh:
        reden = fh.read()
    assert "RedenSoort" in reden and "verhuizing" in reden
    with open(f"{DIR}/defs_Datatypes (Diensten).md", encoding="utf-8") as fh:
        assert "DienstSoort" in fh.read()
    with open(f"{DIR}/defs_Model Diensten.md", encoding="utf-8") as fh:
        assert "Dienst" in fh.read()

    for f in glob.glob(f"{DIR}/*.md"):
        os.remove(f)
    os.rmdir(DIR)
