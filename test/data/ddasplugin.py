import logging

import crunch_uml.util as util
from crunch_uml.db import Association, Attribute, Class
from crunch_uml.exceptions import CrunchException
from crunch_uml.transformers.plugin import Plugin

logger = logging.getLogger()

TRAJECT_ID = "EAID_839017B2_0F95_42d0_AB2B_E873636340DA"
ORGANISATIE_ID = "EAID_A947042E_7CA6_44f8_902A_1C1185A391F6"
SCHULDEISER_ID = "EAID_DCDAD212_479E_4fc3_B886_585AE57D8C21"
UITWISSELMODEL_ID = "EAID_6b4326e3_eb4e_41d2_902b_0bff06604f63"
CLIENT_ID = "EAID_DAF09055_A5A6_4ff4_A158_21B20567B296"
LEVERING_ID = "EAID_DAB09055_A5A6_4ff4_A158_21B20567B888"
SCHULDEN_ID = "EAID_93E12A3E_71E3_431e_9871_BF6075EAAEF1"
Trajecten_sort_order = [
    'client',
    'aanmelding',
    'intake',
    'planVanAanpak',
    'stabilisatie',
    'schuldregeling',
    'begeleiding',
    'oplossing',
    'nazorg',
    'uitstroom',
]


class DDASPlugin(Plugin):
    def transformLogic(self, args, root_package, schema_from, schema_to):
        logger.info("Starting DDAS-Plugin")
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

        # Fix Copy error where enums are not connected
        for enum in kopie.enumerations:
            if enum.name in [
                "Geslachtsaanduiding",
                "Burgerlijke staat",
                "adelijkeTitel",
                "soortRechtsvorm",
                "Boolean",
                "geslacht",
                "Gezinsrelatie",
                "soortRechtsvorm",
            ]:
                kopie.enumerations.remove(enum)

        # Now remove all associations with name 'resulteert in'
        for clazz in kopie.classes:
            lst_assoc = [assoc for assoc in clazz.uitgaande_associaties]
            for association in lst_assoc:
                if str(association.name).strip() in [
                    "resulteert in",
                    "dienstverlening",
                    "voert traject uit",
                    "soort",
                ]:
                    clazz.uitgaande_associaties.remove(association)

        # Now remove classes 'project', 'projectsoort' en 'notariele status'
        for clazz in kopie.classes:
            if str(clazz.name).strip() in [
                "Huishouden",
                "Partner",
                "Inkomen",
                "Woningbezit",
                "Ondernemer",
            ]:  # or str(clazz.name).strip() == "Projectsoort" or str(clazz.name).strip() == "Notariele status"
                kopie.classes.remove(clazz)

        # Zet de onderdelen van het traject in de juiste volgorde
        sort_order = [item.lower() for item in Trajecten_sort_order if isinstance(item, str)]
        for clazz in kopie.classes:
            if str(clazz.name).strip() == "Schuldhulptraject":
                for association in clazz.uitgaande_associaties:
                    dst_class = schema_from.get_class(association.dst_class_id)
                    if dst_class:
                        dst_name = str(dst_class.name).strip().lower()
                        if dst_name in sort_order:
                            association.order = sort_order.index(dst_name) + 1
                        else:
                            association.order = 100

        # Now add the Class Uitwisselmodel
        uitwisselmodel = Class(
            id=UITWISSELMODEL_ID,
            name="Uitwisselmodel",
            schema_id=schema_to.schema_id,
            package=kopie,
            definitie=(
                "Het uitwisselmodel is een model dat de gegevens bevat die uitgewisseld worden tussen de verschillende"
                " partijen."
            ),
        )
        startdatumLevering = Attribute(
            id=util.getEAGuid(),
            name="startdatumLevering",
            schema_id=schema_to.schema_id,
            primitive="Datum",
        )
        einddatumLevering = Attribute(
            id=util.getEAGuid(),
            name="einddatumLevering",
            schema_id=schema_to.schema_id,
            primitive="Datum",
        )
        aanleverdatumEnTijd = Attribute(
            id=util.getEAGuid(),
            name="aanleverdatumEnTijd",
            schema_id=schema_to.schema_id,
            primitive="datumtijd",
        )
        uitwisselmodel.attributes.append(startdatumLevering)
        uitwisselmodel.attributes.append(einddatumLevering)
        uitwisselmodel.attributes.append(aanleverdatumEnTijd)

        # Add the class Levering
        levering = Class(
            id=LEVERING_ID,
            name="Levering",
            schema_id=schema_to.schema_id,
            package=kopie,
            definitie=(
                "Een levering is steeds een schuldhulporganisatie met daarbij een verzameling van schuldhulptrajecten"
                " die op een bepaald moment worden aangeleverd."
            ),
        )
        teller = Attribute(
            id=util.getEAGuid(),
            name="teller",
            schema_id=schema_to.schema_id,
            primitive="int",
            verplicht=True,
            definitie="Teller van het aantal leveringen dat in het bestand is opgenomen.",
        )
        levering.attributes.append(teller)
        assoc_uitmod_to_levering = Association(
            id=util.getEAGuid(),
            name="is van",
            schema_id=schema_to.schema_id,
            src_class_id=uitwisselmodel.id,
            dst_class_id=levering.id,
            dst_mult_start="1",
            dst_mult_end="-1",
            src_role="leveringen",
            definitie="De leveringen die in het uitwisselmodel zijn opgenomen.",
            order=1,
        )
        uitwisselmodel.uitgaande_associaties.append(assoc_uitmod_to_levering)
        assoc_uitmod_to_levering.dst_class = levering

        assoc_levering_to_organisatie = Association(
            id=util.getEAGuid(),
            name="organisatie",
            schema_id=schema_to.schema_id,
            src_class_id=levering.id,
            dst_class_id=ORGANISATIE_ID,
            dst_mult_start="1",
            dst_mult_end="1",
            src_role="aanleverende_organisatie",
            definitie="De organisatie die het uitwisselmodel aanlevert.",
            order=1,
        )
        assoc_levering_to_trajecten = Association(
            id=util.getEAGuid(),
            name="trajecten",
            schema_id=schema_to.schema_id,
            src_class_id=levering.id,
            dst_class_id=TRAJECT_ID,
            dst_mult_start="0",
            dst_mult_end="-1",
            src_role="schuldhulptrajecten",
            definitie="De aan te leveren trajecten.",
            order=2,
        )
        levering.uitgaande_associaties.append(assoc_levering_to_organisatie)
        levering.uitgaande_associaties.append(assoc_levering_to_trajecten)

        kopie.classes.append(uitwisselmodel)
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

        # Zet de juiste attrributen bij client postcode, geboortedatum en geslacht (en huisnummer(toevoeging))
        lst_attr = [attr for attr in schema_to.get_class(CLIENT_ID).attributes]
        client = schema_to.get_class(CLIENT_ID)
        for attr in lst_attr:
            if not str(attr.name).strip().lower() in [
                "geslachtsaanduiding",
                "burgerservicenummer",
                "geboortedatum",
            ]:
                client.attributes.remove(attr)
                attr.clazz_id = None
        client.attributes.append(
            Attribute(
                id=util.getEAGuid(),
                name="Postcode",
                schema_id=schema_to.schema_id,
                primitive="AN6",
                verplicht=False,
            )
        )
        client.attributes.append(
            Attribute(
                id=util.getEAGuid(),
                name="Huisnummer",
                schema_id=schema_to.schema_id,
                primitive="AN5",
                verplicht=False,
            )
        )
        client.attributes.append(
            Attribute(
                id=util.getEAGuid(),
                name="Huisnummertoevoeging",
                schema_id=schema_to.schema_id,
                primitive="AN4",
                verplicht=False,
            )
        )

        # Laat alleen schulden in hetleefgebied va de client zien

        logger.info("DDAS Plugin finished.")
