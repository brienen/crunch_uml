import sqlalchemy
from sqlalchemy import Column, ForeignKey, String, Text, create_engine, Float
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
    parent_package = relationship("Package", back_populates="subpackages")
    subpackages = relationship("Class", back_populates="parent_package")
    classes = relationship("Class", back_populates="package")
    enumerations = relationship("Enumeratie", back_populates="package")


class Class(Base, UMLBase, UMLTags):  # type: ignore
    __tablename__ = 'classes'

    package_id = Column(String, ForeignKey('packages.id', deferrable=True), index=True, nullable=False)
    package = relationship("Package", back_populates="classes")
    attributes = relationship("Attribute", back_populates="clazz")


class Attribute(Base, UML_Generic):  # type: ignore
    __tablename__ = 'attributes'

    clazz_id = Column(String, ForeignKey('classes.id', deferrable=True), index=True, nullable=False)
    clazz = relationship("Class", back_populates="attributes")


class Enumeratie(Base, UMLBase, UMLTags):  # type: ignore
    __tablename__ = 'enumeraties'

    package_id = Column(String, ForeignKey('packages.id', deferrable=True), index=True)
    package = relationship("Package", back_populates="enumerations")
    literals = relationship("EnumerationLiteral", back_populates="enumeratie")


class EnumerationLiteral(Base, UML_Generic):  # type: ignore
    __tablename__ = 'enumeratieliterals'

    enumeratie_id = Column(String, ForeignKey('enumeraties.id', deferrable=True), index=True, nullable=False)
    enumeratie = relationship("Enumeratie", back_populates='literals')


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

    def save_package(self, package):
        self.session.merge(package)

    def count_packages(self):
        return self.session.query(Package).count()

    def get_package(self, id):
        return self.session.get(Package, id)

    def save_class(self, clazz):
        self.session.add(clazz)

    def get_class(self, id):
        return self.session.get(Class, id)

    def count_class(self):
        return self.session.query(Class).count()

    def add_attribute(self, attr):
        self.session.add(attr)

    def count_attribute(self):
        return self.session.query(Attribute).count()

    def add_enumeratie(self, enum):
        self.session.add(enum)

    def count_enumeratie(self):
        return self.session.query(Enumeratie).count()

    def add_enumeratieliteral(self, enumlit):
        self.session.add(enumlit)

    def count_enumeratieliteral(self):
        return self.session.query(EnumerationLiteral).count()

    def commit(self):
        self.session.commit()

    def close(self):
        self.session.close()
