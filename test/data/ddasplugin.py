import logging

from crunch_uml.transformers.plugin import Plugin
from crunch_uml.exceptions import CrunchException
from crunch_uml.db import Class, Attribute, Association
import crunch_uml.util as util

logger = logging.getLogger()

TRAJECT_ID="EAID_839017B2_0F95_42d0_AB2B_E873636340DA"
ORGANISATIE_ID="EAID_A947042E_7CA6_44f8_902A_1C1185A391F6"
UITWISSELMODEL_ID="EAID_6b4326e3_eb4e_41d2_902b_0bff06604f63"
CLIENT_ID="EAID_DAF09055_A5A6_4ff4_A158_21B20567B296"

class DDASPlugin(Plugin):
    def transformLogic(self, args, root_package, schema_from, schema_to):
        logger.info("Starting DDAS-Plugin")
        if not root_package.id == "EAPK_06C51790_1F81_4ac4_8E16_5177352EF2E1":
            msg = f"Cannot transform using {self.__class__.__name__}: Root package is needs to be model schuldhulpverlening with id EAPK_06C51790_1F81_4ac4_8E16_5177352EF2E1."
            logger.error(msg)
            raise CrunchException(msg)

        # Kopie schuldhulpverlening model
        kopie = root_package.get_copy(None, materialize_generalizations=False)

        # Now remove all associations with name 'resulteert in'
        for clazz in kopie.classes:
            for association in clazz.uitgaande_associaties:
                if str(association.name).strip() in ["resulteert in", "dienstverlening", "voert traject uit"]:
                    clazz.uitgaande_associaties.remove(association)

        # Now remove classes 'project', 'projectsoort' en 'notariele status'
        #for clazz in kopie.classes:
        #    if str(clazz.name).strip() == "Project": #or str(clazz.name).strip() == "Projectsoort" or str(clazz.name).strip() == "Notariele status"
        #        kopie.classes.remove(clazz)


        # Now add the Class Uitwisselmodel
        uitwisselmodel = Class(id=UITWISSELMODEL_ID, name="Uitwisselmodel", schema_id=schema_to.schema_id, definitie="Het uitwisselmodel is een model dat de gegevens bevat die uitgewisseld worden tussen de verschillende partijen.")
        aanleverperiodeStartdatum = Attribute(id=util.getEAGuid(), name="aanleverperiodeStartdatum", schema_id=schema_to.schema_id, primitive="Datum")
        aanleverperiodeEinddatum = Attribute(id=util.getEAGuid(), name="aanleverperiodeEinddatum", schema_id=schema_to.schema_id, primitive="Datum")
        uitwisselmodel.attributes.append(aanleverperiodeStartdatum)
        uitwisselmodel.attributes.append(aanleverperiodeEinddatum)
        
        assoc_uitmod_to_organisatie = Association(id=util.getEAGuid(), name="is van", schema_id=schema_to.schema_id, src_class_id=uitwisselmodel.id, dst_class_id=ORGANISATIE_ID, dst_mult_start="1", dst_mult_end="1", src_role="aanleverende_organisatie", definitie="De organisatie die het uitwisselmodel aanlevert.")
        assoc_uitmod_to_trajecten = Association(id=util.getEAGuid(), name="levert", schema_id=schema_to.schema_id, src_class_id=uitwisselmodel.id, dst_class_id=TRAJECT_ID, dst_mult_start="0", dst_mult_end="-1", src_role="schuldhulptrajecten", definitie="De aan te leveren trajecten.")
        uitwisselmodel.uitgaande_associaties.append(assoc_uitmod_to_organisatie)
        uitwisselmodel.uitgaande_associaties.append(assoc_uitmod_to_trajecten)

        kopie.classes.append(uitwisselmodel)
        schema_to.add(kopie, recursive=True)

        #Zet de juiste attrributen bij client
        client = schema_to.get_class(CLIENT_ID)
        for attr in client.attributes:
            client.attributes.remove(attr)
        client.attributes.append(Attribute(id=util.getEAGuid(), name="bsn", schema_id=schema_to.schema_id, primitive="AN200", verplicht=False))
        client.attributes.append(Attribute(id=util.getEAGuid(), name="postcode", schema_id=schema_to.schema_id, primitive="AN6", verplicht=False))
        client.attributes.append(Attribute(id=util.getEAGuid(), name="geboortedatum", schema_id=schema_to.schema_id, primitive="Datum", verplicht=False))
        client.attributes.append(Attribute(id=util.getEAGuid(), name="geslacht", schema_id=schema_to.schema_id, primitive="AN6", verplicht=False))


        logger.info("DDAS Plugin finished.")
