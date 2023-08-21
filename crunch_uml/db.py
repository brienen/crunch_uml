import sqlalchemy
from sqlalchemy import Column, ForeignKey, String, Text, create_engine
from sqlalchemy.orm import relationship, sessionmaker

import crunch_uml.const as const

Base = sqlalchemy.orm.declarative_base() # type: ignore


# Model definitions
class UML_Generic:
    id = Column(String, primary_key=True)  # Store the XMI id separately
    name = Column(String)
    descr = Column(Text)


class Package(Base, UML_Generic): # type: ignore
    __tablename__ = 'packages'

    parent_package_id = Column(String, ForeignKey('packages.id', deferrable=True), index=True)
    parent_package = relationship("Package")


class Class(Base, UML_Generic): # type: ignore
    __tablename__ = 'classes'

    package_id = Column(String, ForeignKey('packages.id', deferrable=True), index=True, nullable=False)
    package = relationship("Package")


class Attribute(Base, UML_Generic): # type: ignore
    __tablename__ = 'attributes'

    clazz_id = Column(String, ForeignKey('classes.id', deferrable=True), index=True, nullable=False)
    clazz = relationship("Class")


class Enumeratie(Base, UML_Generic): # type: ignore
    __tablename__ = 'enumeraties'

    package_id = Column(String, ForeignKey('packages.id', deferrable=True), index=True)
    package = relationship("Package")


class EnumerationLiteral(Base, UML_Generic): # type: ignore
    __tablename__ = 'enumeratieliterals'

    enumeratie_id = Column(String, ForeignKey('enumeraties.id', deferrable=True), index=True, nullable=False)
    enumeratie = relationship("Enumeratie")


class Database:
    _instance = None

    def __new__(cls, db_url=const.DATABASE_URL, db_create=True, dc_upsert=False):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            # Setting up the database
            cls._instance.engine = create_engine(db_url)
            if db_create:
                Base.metadata.drop_all(bind=cls._instance.engine)  # Drop all tables
            Base.metadata.create_all(bind=cls._instance.engine)
            Session = sessionmaker(bind=cls._instance.engine)
            cls._instance.session = Session()
        return cls._instance

    def add_package(self, package):
        self.session.add(package)

    def count_packages(self):
        return self.session.query(Package).count()

    def add_class(self, clazz):
        self.session.add(clazz)

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
