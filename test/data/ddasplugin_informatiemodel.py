import logging

import crunch_uml.util as util
from crunch_uml.db import Attribute
from crunch_uml.exceptions import CrunchException
from crunch_uml.transformers.plugin import Plugin

logger = logging.getLogger()

TRAJECT_ID = "EAID_839017B2_0F95_42d0_AB2B_E873636340DA"
ORGANISATIE_ID = "EAID_A947042E_7CA6_44f8_902A_1C1185A391F6"
SCHULDEISER_ID = "EAID_DCDAD212_479E_4fc3_B886_585AE57D8C21"
UITWISSELMODEL_ID = "EAID_6b4326e3_eb4e_41d2_902b_0bff06604f63"
CLIENT_ID = "EAID_DAF09055_A5A6_4ff4_A158_21B20567B296"
PARTNER_ID = "EAID_093B2482_D72E_4f88_931C_75C9DABED007"
LEVERING_ID = "EAID_DAB09055_A5A6_4ff4_A158_21B20567B888"
SCHULDEN_ID = "EAID_93E12A3E_71E3_431e_9871_BF6075EAAEF1"


class DDASPluginInformatiemodel(Plugin):
    def transformLogic(self, args, root_package, schema_from, schema_to):
        logger.info("Starting DDAS-Plugin to create the datamodel.")
        # Clean up
        schema_to.clean()

        if not root_package.id == "EAPK_06C51790_1F81_4ac4_8E16_5177352EF2E1":
            msg = (
                f"Cannot transform using {self.__class__.__name__}: Root package is needs to be model"
                " schuldhulpverlening with id EAPK_06C51790_1F81_4ac4_8E16_5177352EF2E1."
            )
            logger.error(msg)
            raise CrunchException(msg)

        # Kopie schuldhulpverlening model
        kopie = root_package.get_copy(None, materialize_generalizations=True)

        # Remove unneccary enumerations from inherited attributes
        lst_enum = [enum for enum in kopie.enumerations]
        gsl_teller = 0
        for enum in lst_enum:
            if enum.name == "geslacht" and gsl_teller < 1:  # Geslacht needs to stay exacly once
                gsl_teller += 1
                kopie.enumerations.remove(enum)
            if enum.name in [
                "Geslachtsaanduiding",
                "Burgerlijke staat",
                "adelijkeTitel",
                "soortRechtsvorm",
                "Boolean",
                "Gezinsrelatie",
                "soortRechtsvorm",
            ]:
                kopie.enumerations.remove(enum)

        schema_to.add(kopie, recursive=True)

        # Zet de juiste attrributen bij aanlevereende organisatie
        def set_org(org_id, lst_incl):
            org = schema_to.get_class(org_id)
            lst_attr = [attr for attr in schema_to.get_class(org_id).attributes]
            for attr in lst_attr:
                if not str(attr.name).strip().lower() in lst_incl:
                    org.attributes.remove(attr)
                    attr.clazz_id = None
            org.attributes.append(
                Attribute(
                    id=util.getEAGuid(),
                    name="postcode",
                    schema_id=schema_to.schema_id,
                    primitive="AN6",
                    verplicht=False,
                )
            )

        set_org(ORGANISATIE_ID, ["(statutaire) naam", "kvk-nummer"])
        org = schema_to.get_class(ORGANISATIE_ID)
        org.attributes.append(
            Attribute(
                id=util.getEAGuid(),
                name="gemeentecode",
                schema_id=schema_to.schema_id,
                primitive="AN2",
                verplicht=False,
                definitie="De gemeentecode als de aanleverende organisatie een gemeente is.",
            )
        )

        set_org(SCHULDEISER_ID, ["naam", "kvknummer"])
        org = schema_to.get_class(SCHULDEISER_ID)
        org.attributes.append(
            Attribute(
                id=util.getEAGuid(),
                name="privepersoon",
                schema_id=schema_to.schema_id,
                primitive="boolean",
                verplicht=False,
            )
        )

        traject = schema_to.get_class(TRAJECT_ID)
        traject.attributes.append(
            Attribute(
                id=util.getEAGuid(),
                name="gemeentecode",
                schema_id=schema_to.schema_id,
                primitive="AN2",
                verplicht=True,
                definitie=(
                    "De gemeentecode van de gemeente onder wiens verantwoordelijkheid het schuldhulptraject wordt"
                    " uitgevoerd."
                ),
            )
        )

        # Zet de juiste attrributen bij client postcode, geboortedatum en geslacht (en huisnummer(toevoeging))
        def set_person(person_id):
            lst_attr = [attr for attr in schema_to.get_class(person_id).attributes]
            person = schema_to.get_class(person_id)
            for attr in lst_attr:
                if not str(attr.name).strip().lower() in [
                    "geslachtsaanduiding",
                    "burgerservicenummer",
                    "geboortedatum",
                ]:
                    person.attributes.remove(attr)
                    attr.clazz_id = None
            person.attributes.append(
                Attribute(
                    id=util.getEAGuid(),
                    name="Postcode",
                    schema_id=schema_to.schema_id,
                    primitive="AN6",
                    verplicht=False,
                )
            )
            person.attributes.append(
                Attribute(
                    id=util.getEAGuid(),
                    name="Huisnummer",
                    schema_id=schema_to.schema_id,
                    primitive="AN5",
                    verplicht=False,
                )
            )
            person.attributes.append(
                Attribute(
                    id=util.getEAGuid(),
                    name="Huisnummertoevoeging",
                    schema_id=schema_to.schema_id,
                    primitive="AN4",
                    verplicht=False,
                )
            )

        set_person(CLIENT_ID)
        set_person(PARTNER_ID)
        # Laat alleen schulden in hetleefgebied va de client zien

        logger.info("DDAS Datamodel Plugin finished.")
