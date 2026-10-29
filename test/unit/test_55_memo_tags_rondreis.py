"""
Tests voor memo-tags tussen EA-repository en database (0.8.6).

EA bewaart een memo-tag als '<memo>' in Value met de tekst in Notes; de XMI-export
plakt ze aan elkaar als '<memo>#NOTES#tekst'. De qea-parser geeft die XMI-vorm door
(tag_value), en de terugschrijver (export -t earepo) splitst hem weer: de waarde in
Value, de memotekst in Notes, en nooit '#NOTES#' in de repository. Het GGM v3.0.0 had
1.960 tagwaarden met de scheider in Value door eerder terugschrijven.
"""

import os
import shutil
import sqlite3

import pytest

import crunch_uml.schema as sch
from crunch_uml import cli, const, db
from crunch_uml.parsers.qeaparser import tag_value

EA_DB = "./test/output/MonumentenMIM_memo.qea"
AMBACHT = "EAID_54944273_F312_44b2_A78D_43488F915429"
AMBACHT_GUID = "{54944273-F312-44b2-A78D-43488F915429}"


@pytest.mark.parametrize(
    "value,notes,verwacht",
    [
        ("<memo>", "Zie verder de toelichting in de BRP.", "<memo>#NOTES#Zie verder de toelichting in de BRP."),
        ("<memo>", "", "<memo>"),
        ("<memo>", None, "<memo>"),
        ("BRP", "Description: De registratie ...", "BRP"),
        ("", "Description: ...", ""),
        (None, "tekst", None),
    ],
)
def test_tag_value(value, notes, verwacht):
    assert tag_value(value, notes) == verwacht


def tags_van(object_guid):
    con = sqlite3.connect(EA_DB)
    try:
        rows = con.execute(
            "SELECT p.Property, p.Value, p.Notes FROM t_objectproperties p "
            "JOIN t_object o ON o.Object_ID = p.Object_ID WHERE o.ea_guid = ?",
            (object_guid,),
        ).fetchall()
    finally:
        con.close()
    return {prop: (value, notes) for prop, value, notes in rows}


def test_terugschrijven_zet_waarde_en_memotekst_apart():
    os.makedirs("./test/output", exist_ok=True)
    shutil.copyfile("./test/data/MonumentenMIM.qea", EA_DB)
    cli.main(["import", "-f", "./test/data/GGM_Monumenten_EA2.1.xml", "-t", "eaxmi", "-db_create"])

    database = db.Database(const.DATABASE_URL, db_create=False)
    schema = sch.Schema(database)
    ambacht = schema.get_class(AMBACHT)
    assert ambacht is not None
    ambacht.toelichting = "<memo>#NOTES#Nieuwe toelichting.#NOTES#Nieuwe toelichting."
    ambacht.herkomst = "BRP#NOTES#Description: De registratie of het informatiemodel ..."
    ambacht.populatie = "<memo>#NOTES#Description: Alleen een tagdefinitie"
    database.commit()
    database.close()

    cli.main(["export", "-f", EA_DB, "-t", "earepo", "--tag_strategy", "upsert"])

    tags = tags_van(AMBACHT_GUID)
    assert tags["Toelichting"] == ("<memo>", "Nieuwe toelichting.")
    assert tags["Herkomst"][0] == "BRP"
    assert tags["Populatie"][0] == "<memo>" and not tags["Populatie"][1]  # lege memo: geen tekst
    for prop, (value, notes) in tags.items():
        assert "#NOTES#" not in (value or ""), prop
        assert "#NOTES#" not in (notes or ""), prop

    # Nog een keer terugschrijven verandert niets meer: de memotekst wordt met Notes vergeleken.
    cli.main(["export", "-f", EA_DB, "-t", "earepo", "--tag_strategy", "upsert"])
    assert tags_van(AMBACHT_GUID)["Toelichting"] == ("<memo>", "Nieuwe toelichting.")
    os.remove(EA_DB)
