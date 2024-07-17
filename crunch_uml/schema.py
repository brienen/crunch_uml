import logging

import crunch_uml.const as const
import crunch_uml.db as db
from crunch_uml.exceptions import CrunchException

logger = logging.getLogger()


def add_args(argumentparser, subparser_dict):
    # argumentparser.add_argument(
    #    '-db_noorph',
    #    '--database_no_orphans',
    #    action='store_true',
    #    help='Do not create orphan classes when relations point to classes that are not found in the imported file.',
    # )
    argumentparser.add_argument(
        '-sch',
        '--schema_name',
        type=str,
        help=f"Default schema name, default is {const.DEFAULT_SCHEMA}",
        default=const.DEFAULT_SCHEMA,
    )


class Schema:
    def __init__(self, database, schema_name=const.DEFAULT_SCHEMA):
        if not database:
            raise CrunchException(f'Cannot create schema {schema_name} with database with None value.')
        self.database = database
        self.schema_id = schema_name
        self.processed_objects = set()  # Houdt bij welke objecten al verwerkt zijn

    def add(self, obj, recursive=False, processed_objects=set()):
        self.save(obj, recursive=recursive, processed_objects=processed_objects, add=True)

    def save(self, obj, recursive=False, processed_objects=set(), add=False):
        if obj is None:
            return
        # Voeg het object toe aan de set van verwerkte objecten
        if obj in processed_objects:
            return  # Voorkom recursieve lus door het object niet opnieuw te verwerken
        processed_objects.add(obj)

        # Save object
        if hasattr(obj, 'schema_id'):
            obj.schema_id = self.schema_id
        if add:
            self.database.add(obj)
        else:
            self.database.save(obj)
        # self.database.session.flush()

        if recursive:
            cls = obj.__class__
            # Bewaar de relaties als die er zijn
            if cls.__mapper__ and cls.__mapper__.relationships:
                for attr, relation in cls.__mapper__.relationships.items():
                    related_objects = getattr(obj, attr)

                    # Controleer of de relatie een lijst is (uselist=True) of een enkel object
                    if relation.uselist:
                        for rel_obj in related_objects:
                            self.save(rel_obj, recursive=True, processed_objects=processed_objects, add=add)
                    else:
                        if related_objects is not None:
                            self.save(related_objects, recursive=True, processed_objects=processed_objects, add=add)

    def count_package(self):
        return self.database.session.query(db.Package).filter_by(schema_id=self.schema_id).count()

    def get_package(self, id):
        return self.database.session.query(db.Package).filter_by(id=id, schema_id=self.schema_id).first()

    def get_diagram(self, id):
        return self.database.session.query(db.Diagram).filter_by(id=id, schema_id=self.schema_id).first()

    def get_class(self, id):
        return self.database.session.query(db.Class).filter_by(id=id, schema_id=self.schema_id).first()

    def get_enumeration(self, id):
        return self.database.session.query(db.Enumeratie).filter_by(id=id, schema_id=self.schema_id).first()

    def get_enumeration_literal(self, id):
        return self.database.session.query(db.EnumerationLiteral).filter_by(id=id, schema_id=self.schema_id).first()

    def get_attribute(self, id):
        return self.database.session.query(db.Attribute).filter_by(id=id, schema_id=self.schema_id).first()

    def get_association(self, id):
        return self.database.session.query(db.Association).filter_by(id=id, schema_id=self.schema_id).first()

    def get_generalization(self, id):
        return self.database.session.query(db.Generalization).filter_by(id=id, schema_id=self.schema_id).first()

    def get_all_enumerations(self):
        return self.database.session.query(db.Enumeratie).filter_by(schema_id=self.schema_id).all()

    def count_class(self):
        return self.database.session.query(db.Class).filter_by(schema_id=self.schema_id).count()

    def count_attribute(self):
        return self.database.session.query(db.Attribute).filter_by(schema_id=self.schema_id).count()

    def count_enumeratie(self):
        return self.database.session.query(db.Enumeratie).filter_by(schema_id=self.schema_id).count()

    def count_enumeratieliteral(self):
        return self.database.session.query(db.EnumerationLiteral).filter_by(schema_id=self.schema_id).count()

    def count_association(self):
        return self.database.session.query(db.Association).filter_by(schema_id=self.schema_id).count()

    def count_generalizations(self):
        return self.database.session.query(db.Generalization).filter_by(schema_id=self.schema_id).count()

    def count_diagrams(self):
        return self.database.session.query(db.Diagram).filter_by(schema_id=self.schema_id).count()

    def get_session(self):
        return self.database.session

    def clean(self):
        self.database.session.query(db.Package).filter_by(schema_id=self.schema_id).delete()
        self.database.session.query(db.Class).filter_by(schema_id=self.schema_id).delete()
        self.database.session.query(db.Enumeratie).filter_by(schema_id=self.schema_id).delete()
        self.database.session.query(db.EnumerationLiteral).filter_by(schema_id=self.schema_id).delete()
        self.database.session.query(db.Attribute).filter_by(schema_id=self.schema_id).delete()
        self.database.session.query(db.Association).filter_by(schema_id=self.schema_id).delete()
        self.database.session.query(db.Generalization).filter_by(schema_id=self.schema_id).delete()
        self.database.session.query(db.Diagram).filter_by(schema_id=self.schema_id).delete()
        self.database.session.query(db.DiagramAssociation).filter_by(schema_id=self.schema_id).delete()
        self.database.session.query(db.DiagramClass).filter_by(schema_id=self.schema_id).delete()
        self.database.session.query(db.DiagramEnumeration).filter_by(schema_id=self.schema_id).delete()
        self.database.session.query(db.DiagramGeneralization).filter_by(schema_id=self.schema_id).delete()
