import sqlalchemy
from sqlalchemy import Column, ForeignKey, String, Text, create_engine
from sqlalchemy.orm import relationship, sessionmaker

import crunch_uml.const as const

Base = sqlalchemy.orm.declarative_base()  # type: ignore


# Model definitions
class UML_Generic:
    id = Column(String, primary_key=True)  # Store the XMI id separately
    name = Column(String)
    descr = Column(Text)


class UMLBase(UML_Generic):
    author = Column(String)
    version = Column(String)
    phase = Column(String)
    status = Column(String)
    created = Column(String)
    modified = Column(String)
    stereotype = Column(String)
    uri = Column(String)
    visibility = Column(String)
    alias = Column(String)


class UMLTags:
    archimate_type = Column(String)
    bron = Column(String)
    datum_tijd_export = Column(String)
    domein_dcat = Column(String)
    domein_gemma = Column(String)
    gemma_guid = Column(String)
    synoniemen = Column(String)
    toelichting = Column(String)


class Package(Base, UMLBase):  # type: ignore
    __tablename__ = 'packages'

    parent_package_id = Column(String, ForeignKey('packages.id', deferrable=True), index=True)
    parent_package = relationship("Package", back_populates="subpackages", remote_side="Package.id")
    subpackages = relationship("Package", back_populates="parent_package")
    classes = relationship("Class", back_populates="package")
    enumerations = relationship("Enumeratie", back_populates="package")


class Class(Base, UMLBase, UMLTags):  # type: ignore
    __tablename__ = 'classes'

    package_id = Column(String, ForeignKey('packages.id', deferrable=True), index=True)
    package = relationship("Package", back_populates="classes")
    attributes = relationship("Attribute", back_populates="clazz", lazy='joined', foreign_keys='Attribute.clazz_id')
    inkomende_associaties = relationship(
        "Association", back_populates="dst_class", foreign_keys='Association.dst_class_id'
    )
    uitgaande_associaties = relationship(
        "Association", back_populates="src_class", foreign_keys='Association.src_class_id'
    )
    superclasses = relationship(
        "Generalization", back_populates="superclass", foreign_keys='Generalization.superclass_id'
    )
    subclasses = relationship(
        "Generalization", back_populates="subclass", foreign_keys='Generalization.subclass_id'
    )


class Attribute(Base, UML_Generic):  # type: ignore
    __tablename__ = 'attributes'

    clazz_id = Column(String, ForeignKey('classes.id', deferrable=True), index=True, nullable=False)
    clazz = relationship("Class", back_populates="attributes", foreign_keys='Attribute.clazz_id')
    primitive = Column(String)
    enumeration_id = Column(String, ForeignKey('enumeraties.id', deferrable=True), index=True)
    enumeration = relationship("Enumeratie", lazy='joined')
    type_class_id = Column(String, ForeignKey('classes.id', deferrable=True), index=True)
    type_class = relationship("Class", foreign_keys='Attribute.type_class_id')


class Enumeratie(Base, UMLBase, UMLTags):  # type: ignore
    __tablename__ = 'enumeraties'

    package_id = Column(String, ForeignKey('packages.id', deferrable=True), index=True, nullable=False)
    package = relationship("Package", back_populates="enumerations")
    literals = relationship("EnumerationLiteral", back_populates="enumeratie", lazy='joined')


class EnumerationLiteral(Base, UML_Generic):  # type: ignore
    __tablename__ = 'enumeratieliterals'

    enumeratie_id = Column(String, ForeignKey('enumeraties.id', deferrable=True), index=True, nullable=False)
    enumeratie = relationship("Enumeratie", back_populates='literals')


class Association(Base, UML_Generic):  # type: ignore
    __tablename__ = 'associaties'

    src_class_id = Column(
        String, ForeignKey('classes.id', deferrable=True, name='fk_src_class'), index=True, nullable=False
    )
    src_class = relationship("Class", back_populates="uitgaande_associaties", foreign_keys='Association.src_class_id')
    src_mult_start = Column(String)
    src_mult_end = Column(String)
    src_multiplicity = Column(String)
    src_documentation = Column(Text)
    dst_class_id = Column(
        String, ForeignKey('classes.id', deferrable=True, name='fk_dst_class'), index=True, nullable=False
    )
    dst_class = relationship("Class", back_populates="inkomende_associaties", foreign_keys='Association.dst_class_id')
    dst_mult_start = Column(String)
    dst_mult_end = Column(String)
    dst_multiplicity = Column(String)
    dst_documentation = Column(Text)

class Generalization(Base, UML_Generic):  # type: ignore
    __tablename__ = 'generalizations'

    superclass_id = Column(
        String, ForeignKey('classes.id', deferrable=True, name='fk_super_class'), index=True, nullable=False
    )
    superclass = relationship("Class", back_populates="superclasses", foreign_keys='Generalization.superclass_id')
    subclass_id = Column(
        String, ForeignKey('classes.id', deferrable=True, name='fk_sub_class'), index=True, nullable=False
    )
    subclass = relationship("Class", back_populates="subclasses", foreign_keys='Generalization.subclass_id')




class Database:
    _instance = None

    def __new__(cls, db_url=const.DATABASE_URL, db_create=True, db_upsert=False):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            # Setting up the database
            cls._instance.engine = create_engine(db_url)
            if db_create:
                Base.metadata.drop_all(bind=cls._instance.engine)  # Drop all tables
                Base.metadata.create_all(bind=cls._instance.engine)
            Session = sessionmaker(bind=cls._instance.engine)
            cls._instance.session = Session()
        elif db_create:
            Base.metadata.drop_all(bind=cls._instance.engine)  # Drop all tables
            Base.metadata.create_all(bind=cls._instance.engine)
        return cls._instance

    def save(self, obj):
        self.session.merge(obj)

    def count_package(self):
        return self.session.query(Package).count()

    def get_package(self, id):
        return self.session.get(Package, id)

    def get_class(self, id):
        return self.session.get(Class, id)

    def get_attribute(self, id):
        return self.session.get(Attribute, id)

    def get_association(self, id):
        return self.session.get(Association, id)

    def get_generalization(self, id):
        return self.session.get(Generalization, id)

    def get_all_enumerations(self):
        return self.session.query(Enumeratie).all()

    def count_class(self):
        return self.session.query(Class).count()

    def count_attribute(self):
        return self.session.query(Attribute).count()

    def count_enumeratie(self):
        return self.session.query(Enumeratie).count()

    def count_enumeratieliteral(self):
        return self.session.query(EnumerationLiteral).count()

    def count_association(self):
        return self.session.query(Association).count()

    def count_generalizations(self):
        return self.session.query(Generalization).count()

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()

    def close(self):
        self.session.close()

    def get_session(self):
        return self.session
