import logging

import crunch_uml.const as const
import crunch_uml.db as db

logger = logging.getLogger()



def add_args(argumentparser, subparser_dict):
    # argumentparser.add_argument(
    #    '-db_noorph',
    #    '--database_no_orphans',
    #    action='store_true',
    #    help='Do not create orphan classes when relations point to classes that are not found in the imported file.',
    # )
    import_subparser = subparser_dict.get(const.CMD_IMPORT)
    import_subparser.add_argument(
        '-schema_create',
        '--schema_create_new',
        action='store_true',
        help='Create a new schema and discard existing one.',
        default=False,
    )
    argumentparser.add_argument(
        '-schema_name',
        '--schema_name',
        type=str,
        help=(
            f"Default schema name, default is {const.DEFAULT_SCHEMA}"
        ),
        default=const.DEFAULT_SCHEMA,
    )





class Schema:

    def __init__(self, database, schema_create=False, schema_name=const.DEFAULT_SCHEMA):
        self.database = database
        self.schema = database.get_schema(schema_name=schema_name)

    def save(self, obj):
        if hasattr(obj, 'schema_id'):
            obj.schema_id = self.schema.id
        self.database.session.merge(obj)

    def count_package(self):
        return self.database.session.query(db.Package).filter_by(schema_id=self.schema.id).count()

    def get_package(self, id):
        return self.database.session.query(db.Package).filter_by(id=id, schema_id=self.schema.id).first()

    def get_class(self, id):
        return self.database.session.query(db.Class).filter_by(id=id, schema_id=self.schema.id).first()

    def get_attribute(self, id):
        return self.database.session.query(db.Attribute).filter_by(id=id, schema_id=self.schema.id).first()

    def get_association(self, id):
        return self.database.session.query(db.Association).filter_by(id=id, schema_id=self.schema.id).first()

    def get_generalization(self, id):
        return self.database.session.query(db.Generalization).filter_by(id=id, schema_id=self.schema.id).first()

    def get_all_enumerations(self):
        return self.database.session.query(db.Enumeratie).filter_by(schema_id=self.schema.id).all()

    def count_class(self):
        return self.database.session.query(db.Class).filter_by(schema_id=self.schema.id).count()

    def count_attribute(self):
        return self.database.session.query(db.Attribute).filter_by(schema_id=self.schema.id).count()

    def count_enumeratie(self):
        return self.database.session.query(db.Enumeratie).filter_by(schema_id=self.schema.id).count()

    def count_enumeratieliteral(self):
        return self.database.session.query(db.EnumerationLiteral).filter_by(schema_id=self.schema.id).count()

    def count_association(self):
        return self.database.session.query(db.Association).filter_by(schema_id=self.schema.id).count()

    def count_generalizations(self):
        return self.database.session.query(db.Generalization).filter_by(schema_id=self.schema.id).count()

    def get_session(self):
        return self.database.session 
