import logging
import warnings

import inflection
from sqlalchemy import (
    Boolean,
    Column,
    ForeignKeyConstraint,
    PrimaryKeyConstraint,
    String,
    Text,
    create_engine,
)
from sqlalchemy import exc as sa_exc
from sqlalchemy import inspect
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.orm.relationships import RelationshipProperty

import crunch_uml.const as const
import crunch_uml.util as util
from crunch_uml.exceptions import CrunchException

logger = logging.getLogger()
suppress_warnings = True


def add_args(argumentparser, subparser_dict):
    global suppress_warnings
    # Rest of the code...
    #    '--database_no_orphans',
    #    action='store_true',
    #    help='Do not create orphan classes when relations point to classes that are not found in the imported file.',
    # )
    import_subparser = subparser_dict.get(const.CMD_IMPORT)
    import_subparser.add_argument(
        '-db_create',
        '--database_create_new',
        action='store_true',
        help='Create a new database and discard existing one.',
        default=False,
    )
    argumentparser.add_argument(
        '-db_url',
        '--database_url',
        type=str,
        help=(
            "URL of the crunch_uml database. Can be any SQLAlchemy (https://docs.sqlalchemy.org/en/20/dialects/)"
            f" supported database. Default is {const.DATABASE_URL}"
        ),
        default=const.DATABASE_URL,
    )


class BaseModel:
    @classmethod
    def model_lookup_by_table_name(cls, table_name):
        registry_instance = getattr(cls, "registry")
        for mapper_ in registry_instance.mappers:
            model = mapper_.class_
            model_class_name = model.__tablename__
            if model_class_name == table_name:
                return model
        return None


Base = declarative_base(cls=BaseModel)


# Get list of tables defined in schema
def getTables():
    return list(Base.metadata.tables.keys())


# Get list of column names
def getColumnNames(tablename):
    """
    Geeft een lijst met kolomnamen terug voor een gegeven tabelnaam.
    """
    # Controleer of de tabelnaam bestaat in de Base's metadata
    if tablename not in Base.metadata.tables:
        raise ValueError(f"Tabelnaam '{tablename}' niet gevonden in de metadata.")

    # Verkrijg de tabel-object
    table = Base.metadata.tables[tablename]

    # Haal de kolomnamen op en retourneer ze
    return [column.name for column in table.columns]


# Model definitions
# class Schema(Base):
#    __tablename__ = 'schemas'

#    id = Column(String, primary_key=True)  # Use the schema name as ID
#    definitie = Column(Text)


# Koppeltabellen
class DiagramClass(Base):  # type: ignore
    __tablename__ = 'diagram_class'
    diagram_id = Column(String, nullable=False)
    schema_id = Column(String, nullable=False)
    class_id = Column(String, nullable=False)
    __table_args__ = (
        PrimaryKeyConstraint('diagram_id', 'schema_id', 'class_id'),
        ForeignKeyConstraint(['diagram_id', 'schema_id'], ['diagrams.id', 'diagrams.schema_id']),
        ForeignKeyConstraint(['class_id', 'schema_id'], ['classes.id', 'classes.schema_id']),
    )
    __mapper_args__ = {'confirm_deleted_rows': False}


class DiagramEnumeration(Base):  # type: ignore
    __tablename__ = 'diagram_enumeration'
    diagram_id = Column(String, nullable=False)
    schema_id = Column(String, nullable=False)
    enumeration_id = Column(String, nullable=False)
    __table_args__ = (
        PrimaryKeyConstraint('diagram_id', 'schema_id', 'enumeration_id'),
        ForeignKeyConstraint(['diagram_id', 'schema_id'], ['diagrams.id', 'diagrams.schema_id']),
        ForeignKeyConstraint(['enumeration_id', 'schema_id'], ['enumerations.id', 'enumerations.schema_id']),
    )
    __mapper_args__ = {'confirm_deleted_rows': False}


class DiagramAssociation(Base):  # type: ignore
    __tablename__ = 'diagram_association'
    diagram_id = Column(String, nullable=False)
    schema_id = Column(String, nullable=False)
    association_id = Column(String, nullable=False)
    __table_args__ = (
        PrimaryKeyConstraint('diagram_id', 'schema_id', 'association_id'),
        ForeignKeyConstraint(['diagram_id', 'schema_id'], ['diagrams.id', 'diagrams.schema_id']),
        ForeignKeyConstraint(['association_id', 'schema_id'], ['associations.id', 'associations.schema_id']),
    )
    __mapper_args__ = {'confirm_deleted_rows': False}


class DiagramGeneralization(Base):  # type: ignore
    __tablename__ = 'diagram_generalization'
    diagram_id = Column(String, nullable=False)
    schema_id = Column(String, nullable=False)
    generalization_id = Column(String, nullable=False)
    __table_args__ = (
        PrimaryKeyConstraint('diagram_id', 'schema_id', 'generalization_id'),
        ForeignKeyConstraint(['diagram_id', 'schema_id'], ['diagrams.id', 'diagrams.schema_id']),
        ForeignKeyConstraint(['generalization_id', 'schema_id'], ['generalizations.id', 'generalizations.schema_id']),
    )
    __mapper_args__ = {'confirm_deleted_rows': False}


# Mixins
class UML_Generic:
    id = Column(String, primary_key=True)  # Store the XMI id separately
    schema_id = Column(String, primary_key=True)
    name = Column(String)
    definitie = Column(Text)
    bron = Column(String)
    toelichting = Column(String)
    created = Column(String)
    modified = Column(String)
    stereotype = Column(String)

    # @declared_attr
    # def schema(cls):
    #    return relationship("Schema")

    # Return all attributes, but without relations
    def to_dict(self):
        return {
            column.key: getattr(self, column.key)
            for column in inspect(self.__class__).attrs
            if not isinstance(column, RelationshipProperty)
        }

    # Return all attributes, relations only
    def to_dict_rel(self):
        return {
            column.key: getattr(self, column.key)
            for column in inspect(self.__class__).attrs
            if isinstance(column, RelationshipProperty)
        }

    def __repr__(self):
        clsname = type(self).__name__.split('.')[-1]
        return f'{clsname}: "{self.name}"'

    def get_copy(self, parent, materialize_generalizations=False):
        cls = self.__class__
        # Maak een nieuwe instantie van de klasse
        copy_instance = cls()
        for attr, column in self.__table__.columns.items():
            setattr(copy_instance, attr, getattr(self, attr))

        setattr(copy_instance, "kopie", True)
        return copy_instance


class UMLBase(UML_Generic):
    author = Column(String)
    version = Column(String)
    phase = Column(String)
    status = Column(String)
    uri = Column(String)
    visibility = Column(String)
    alias = Column(String)


class UMLTags:
    archimate_type = Column(String)
    datum_tijd_export = Column(String)
    synoniemen = Column(String)
    domein_dcat = Column(String)
    domein_iv3 = Column(String)
    gemma_naam = Column(String)
    gemma_type = Column(String)
    gemma_url = Column(String)
    gemma_definitie = Column(String)
    gemma_toelichting = Column(String)


class Package(Base, UMLBase):  # type: ignore
    __tablename__ = 'packages'

    parent_package_id = Column(String, index=True)
    parent_package = relationship("Package", back_populates="subpackages", remote_side="Package.id")
    subpackages = relationship("Package", back_populates="parent_package", cascade="all, delete-orphan")
    classes = relationship("Class", back_populates="package", cascade="all, delete-orphan")
    enumerations = relationship("Enumeratie", back_populates="package", cascade="all, delete-orphan")
    diagrams = relationship("Diagram", back_populates="package", cascade="all, delete-orphan")
    modelnaam_kort = Column(String)

    __table_args__ = (
        ForeignKeyConstraint(
            ['parent_package_id', 'schema_id'], ['packages.id', 'packages.schema_id'], deferrable=True
        ),
    )

    def get_root_package(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore" if suppress_warnings else "default", category=sa_exc.SAWarning)
            if not self.parent_package:
                return self
            else:
                return self.parent_package.get_root_package()

    def get_classes_inscope(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore" if suppress_warnings else "default", category=sa_exc.SAWarning)
            clazzes = {clazz for clazz in self.classes}
            # for diagram in self.diagrams:
            #    clazzes = clazzes.union({clazz for clazz in diagram.classes})
            for subpackage in self.subpackages:
                clazzes = clazzes.union(subpackage.get_classes_inscope())
            return clazzes

    def get_enumerations_inscope(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore" if suppress_warnings else "default", category=sa_exc.SAWarning)
            enums = {enum for enum in self.enumerations}
            # for diagram in self.diagrams:
            #    enums = enums.union({enum for enum in diagram.enumerations})
            for subpackage in self.subpackages:
                enums = enums.union(subpackage.get_enumerations_inscope())
            return enums

    def get_copy(self, parent, materialize_generalizations=False):
        if parent and not isinstance(parent, Package):
            raise CrunchException(
                f"Error: wrong parent type for package while copying. Parent cannot be of type {type(parent)}"
            )

        # Roep de get_copy methode van de superklasse aan
        copy_instance = super().get_copy(parent)
        if parent:
            copy_instance.parent_package_id = parent.id
            parent.subpackages.append(copy_instance)
        else:
            copy_instance.parent_package_id = None

        # Voer eventuele extra stappen uit voor de literals
        for subpackage in self.subpackages:
            subpackage_copy = subpackage.get_copy(
                copy_instance, materialize_generalizations=materialize_generalizations
            )
            subpackage_copy.parent_package_id = copy_instance.id  # Verwijzen naar de nieuwe Enumeratie
            copy_instance.subpackages.append(subpackage_copy)
        for clazz in self.classes:
            if clazz.name != const.ORPHAN_CLASS:
                clazz_copy = clazz.get_copy(copy_instance, materialize_generalizations=materialize_generalizations)
                clazz_copy.package_id = copy_instance.id  # Verwijzen naar de nieuwe Enumeratie
                # copy_instance.classes.append(clazz_copy)
        for enum in self.enumerations:
            enum_copy = enum.get_copy(copy_instance)
            enum_copy.package_id = copy_instance.id  # Verwijzen naar de nieuwe Enumeratie
            # copy_instance.enumerations.append(enum_copy)
        for diagram in self.diagrams:
            diagram_copy = diagram.get_copy(copy_instance)
            diagram_copy.package_id = copy_instance.id
            # copy_instance.diagrams.append(diagram_copy)

        return copy_instance


class Class(Base, UMLBase, UMLTags):  # type: ignore
    __tablename__ = 'classes'

    package_id = Column(String, index=True)
    package = relationship("Package", back_populates="classes")
    attributes = relationship(
        "Attribute",
        back_populates="clazz",
        lazy='joined',
        foreign_keys="[Attribute.clazz_id, Attribute.schema_id]",
        cascade="all, delete-orphan",
    )
    inkomende_associaties = relationship(
        "Association",
        back_populates="dst_class",
        foreign_keys="[Association.dst_class_id, Association.schema_id]",
        cascade="all, delete-orphan",
        overlaps="uitgaande_associaties",
    )
    uitgaande_associaties = relationship(
        "Association",
        back_populates="src_class",
        foreign_keys="[Association.src_class_id, Association.schema_id]",
        cascade="all, delete-orphan",
        overlaps="inkomende_associaties",
    )
    superclasses = relationship(
        "Generalization",
        back_populates="subclass",
        foreign_keys='[Generalization.subclass_id, Generalization.schema_id]',
        cascade="all, delete-orphan",
        overlaps="subclasses",
    )
    subclasses = relationship(
        "Generalization",
        back_populates="superclass",
        foreign_keys='[Generalization.superclass_id, Generalization.schema_id]',
        cascade="all, delete-orphan",
        overlaps="superclasses",
    )
    diagrams = relationship('Diagram', secondary='diagram_class', back_populates='classes')
    indicatie_formele_historie = Column(String)
    authentiek = Column(String)
    nullable = Column(String)

    __table_args__ = (
        ForeignKeyConstraint(['package_id', 'schema_id'], ['packages.id', 'packages.schema_id'], deferrable=True),
    )

    def copy_attributes(self, copy_instance, materialize_generalizations=False):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore" if suppress_warnings else "default", category=sa_exc.SAWarning)

            # Maak lijst van namen van al aanwezige attributen
            copy_attr_lst = [
                attribute.name for attribute in copy_instance.attributes if attribute.name and attribute.name != 'None'
            ]

            # Voer eventuele extra stappen uit voor de literals
            for attribute in self.attributes:
                if attribute.name not in copy_attr_lst:  # only add attributes whos name not already present
                    attribute_copy = attribute.get_copy(self)
                    if self.name != copy_instance.name:  # When copy from superclass the attribute should get new ID
                        attribute_copy.id = util.getEAGuid()

                    # copy enumeration if necesary
                    if attribute.enumeration and (
                        attribute.enumeration not in self.package.get_enumerations_inscope()
                        or self.name != copy_instance.name
                    ):
                        copy_enum = attribute.enumeration.get_copy(copy_instance.package)
                        copy_enum.id = util.getEAGuid()  # to avoid doubles give new ID
                        for literal in copy_enum.literals:
                            literal.id = util.getEAGuid()
                        attribute_copy.enumeration_id = copy_enum.id

                    # set class
                    attribute_copy.clazz_id = copy_instance.id  # Verwijzen naar de nieuwe Enumeratie
                    copy_instance.attributes.append(attribute_copy)

            if materialize_generalizations:
                for gener in self.superclasses:
                    if gener.superclass:
                        gener.superclass.copy_attributes(copy_instance, materialize_generalizations)
            return copy_instance

    def get_copy(self, parent, materialize_generalizations=False):
        if not parent or not isinstance(parent, Package):
            raise CrunchException(
                "Error: wrong parent type for class while copying. Parent must be of type Package and cannot be of type"
                f" {type(parent)}"
            )

        # Roep de get_copy methode van de superklasse aan
        copy_instance = super().get_copy(parent)
        copy_instance.package = parent

        # set attributes
        copy_instance = self.copy_attributes(copy_instance, materialize_generalizations)

        if self.package:
            classes_in_scope = self.package.get_root_package().get_classes_inscope()
            for assoc in self.uitgaande_associaties:
                if assoc.dst_class in classes_in_scope and assoc.dst_class.name != const.ORPHAN_CLASS:
                    assoc_kopie = assoc.get_copy(self)
                    assoc_kopie.src_class_id = copy_instance.id
                    copy_instance.uitgaande_associaties.append(assoc_kopie)
            for gener in self.subclasses:
                if gener.subclass in classes_in_scope and gener.subclass.name != const.ORPHAN_CLASS:
                    gener_kopie = gener.get_copy(self)
                    gener_kopie.superclass_id = copy_instance.id
                    copy_instance.subclasses.append(gener_kopie)

        return copy_instance


class Attribute(Base, UML_Generic):  # type: ignore
    __tablename__ = 'attributes'

    clazz_id = Column(String, index=True, nullable=False)
    clazz = relationship(
        "Class",
        back_populates="attributes",
        foreign_keys="[Attribute.clazz_id, Attribute.schema_id]",
    )
    primitive = Column(String)
    enumeration_id = Column(String, index=True)
    enumeration = relationship("Enumeratie", lazy='joined', overlaps="attributes,clazz")
    type_class_id = Column(String, index=True)
    type_class = relationship(
        "Class", foreign_keys="[Attribute.type_class_id, Attribute.schema_id]", overlaps="attributes,clazz,enumeration"
    )
    verplicht = Column(Boolean, default=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ['clazz_id', 'schema_id'], ['classes.id', 'classes.schema_id'], deferrable=True, name="FK_clazz_id"
        ),
        ForeignKeyConstraint(
            ['enumeration_id', 'schema_id'],
            ['enumerations.id', 'enumerations.schema_id'],
            deferrable=True,
            name="FK_enumeration_id",
        ),
        ForeignKeyConstraint(
            ['type_class_id', 'schema_id'], ['classes.id', 'classes.schema_id'], deferrable=True, name="FK_type_class"
        ),
    )

    def get_copy(self, parent, materialize_generalizations=False):
        if not parent or not isinstance(parent, Class):
            raise CrunchException(
                "Error: wrong parent type for attribute while copying. Parent must be of type Class and cannot be of"
                f" type {type(parent)}"
            )

        # Roep de get_copy methode van de superklasse aan
        copy_instance = super().get_copy(parent)
        copy_instance.clazz = parent
        # copy_instance.enumeration_id = None
        # copy_instance.type_class_id = None
        return copy_instance

    def getDatatype(self):
        if self.primitive is not None:
            return self.primitive
        elif self.enumeration is not None:
            return self.enumeration
        elif self.type_class is not None:
            return self.type_class
        else:
            return None


class Enumeratie(Base, UMLBase, UMLTags):  # type: ignore
    __tablename__ = 'enumerations'

    package_id = Column(String, index=True, nullable=False)
    package = relationship("Package", back_populates="enumerations")
    literals = relationship(
        "EnumerationLiteral", back_populates="enumeratie", lazy='joined', cascade="all, delete-orphan"
    )
    diagrams = relationship('Diagram', secondary='diagram_enumeration', back_populates='enumerations')

    __table_args__ = (
        ForeignKeyConstraint(['package_id', 'schema_id'], ['packages.id', 'packages.schema_id'], deferrable=True),
    )

    def get_copy(self, parent, materialize_generalizations=False):
        if not parent or not isinstance(parent, Package):
            raise CrunchException(
                "Error: wrong parent type for enumeratie while copying. Parent must be of type Parent and cannot be of"
                f" type {type(parent)}"
            )

        # Roep de get_copy methode van de superklasse aan
        copy_instance = super().get_copy(parent)
        copy_instance.package = parent

        # Voer eventuele extra stappen uit voor de literals
        for literal in self.literals:
            literal_copy = literal.get_copy(self)
            literal_copy.enumeratie_id = copy_instance.id  # Verwijzen naar de nieuwe Enumeratie
            copy_instance.literals.append(literal_copy)
        return copy_instance


class EnumerationLiteral(Base, UML_Generic):  # type: ignore
    __tablename__ = 'enumerationliterals'

    enumeratie_id = Column(String, index=True, nullable=False)
    enumeratie = relationship("Enumeratie", back_populates='literals')
    type = Column(String)

    __table_args__ = (
        ForeignKeyConstraint(
            ['enumeratie_id', 'schema_id'], ['enumerations.id', 'enumerations.schema_id'], deferrable=True
        ),
    )

    def get_copy(self, parent, materialize_generalizations=False):
        if not parent or not isinstance(parent, Enumeratie):
            raise CrunchException(
                "Error: wrong parent type for EnumerationLiteral while copying. Parent must be of type Enumeratie and"
                f" cannot be of type {type(parent)}"
            )

        # Roep de get_copy methode van de superklasse aan
        copy_instance = super().get_copy(parent)
        copy_instance.enumeratie = parent
        return copy_instance


class Association(Base, UML_Generic):  # type: ignore
    __tablename__ = 'associations'

    src_class_id = Column(String, index=True, nullable=False)
    src_class = relationship(
        "Class",
        back_populates="uitgaande_associaties",
        foreign_keys="[Association.src_class_id, Association.schema_id]",
        overlaps="inkomende_associaties",
    )
    src_mult_start = Column(String)
    src_mult_end = Column(String)
    src_multiplicity = Column(String)
    src_documentation = Column(Text)
    src_role = Column(String)
    dst_class_id = Column(String, index=True, nullable=False)
    dst_class = relationship(
        "Class",
        back_populates="inkomende_associaties",
        foreign_keys='[Association.dst_class_id, Association.schema_id]',
        overlaps="src_class,uitgaande_associaties",
    )
    dst_mult_start = Column(String)
    dst_mult_end = Column(String)
    dst_multiplicity = Column(String)
    dst_documentation = Column(Text)
    dst_role = Column(String)
    diagrams = relationship('Diagram', secondary='diagram_association', back_populates='associations')

    __table_args__ = (
        ForeignKeyConstraint(
            ['src_class_id', 'schema_id'], ['classes.id', 'classes.schema_id'], deferrable=True, name='fk_src_class'
        ),
        ForeignKeyConstraint(
            ['dst_class_id', 'schema_id'], ['classes.id', 'classes.schema_id'], deferrable=True, name='fk_dst_class'
        ),
    )

    def hasOrphan(self):
        return (
            self.dst_class is None
            or self.dst_class.package_id is None
            or self.src_class is None
            or self.src_class.package_id is None
        )

    def getType(self, clazz):
        if self.src_mult_end == '1':
            return '1-1' if self.dst_mult_end == '1' else '1-n'
        else:
            return 'n-1' if self.dst_mult_end == '1' else 'n-m'

    def isEnkelvoudig(self, dst: True):  # type: ignore
        if dst:
            return True if self.dst_mult_end in ["0", "1"] else False
        else:
            return True if self.src_mult_end in ["0", "1"] else False

    def isVerplicht(self, dst: True):  # type: ignore
        if dst:
            return True if isinstance(self.dst_mult_start, int) and int(self.dst_mult_start) > 0 else False
        else:
            return True if isinstance(self.src_mult_start, int) and int(self.src_mult_start) > 0 else False

    def getRole(self, view='src'):
        if view == 'src':
            if self.src_role:
                return self.src_role
            elif self.isEnkelvoudig(dst=True):
                return inflection.camelize(self.dst_class.name.replace(" ", ""), False)
            else:
                return inflection.camelize(util.getMeervoud(self.dst_class.name.replace(" ", "")), False)
        else:
            if self.dst_role:
                return self.dst_role
            elif self.isEnkelvoudig(dst=False):
                return inflection.camelize(self.src_class.name.replace(" ", ""), False)
            else:
                return inflection.camelize(util.getMeervoud(self.src_class.name.replace(" ", "")), False)


class Generalization(Base, UML_Generic):  # type: ignore
    __tablename__ = 'generalizations'

    superclass_id = Column(String, index=True, nullable=False)
    superclass = relationship(
        "Class",
        back_populates="subclasses",
        foreign_keys='[Generalization.superclass_id, Generalization.schema_id]',
        overlaps="superclasses, subclass",
    )
    subclass_id = Column(String, index=True, nullable=False)
    subclass = relationship(
        "Class",
        back_populates="superclasses",
        foreign_keys='[Generalization.subclass_id, Generalization.schema_id]',
        overlaps="subclasses, superclass",
    )
    diagrams = relationship('Diagram', secondary='diagram_generalization', back_populates='generalizations')

    __table_args__ = (
        ForeignKeyConstraint(
            ['superclass_id', 'schema_id'], ['classes.id', 'classes.schema_id'], deferrable=True, name='fk_super_class'
        ),
        ForeignKeyConstraint(
            ['subclass_id', 'schema_id'], ['classes.id', 'classes.schema_id'], deferrable=True, name='fk_sub_class'
        ),
    )

    def __repr__(self):
        clsname = type(self).__name__.split('.')[-1]
        return f'{clsname}: {self.subclass} isSubClassOf {self.superclass}'


class Diagram(Base, UMLBase):  # type: ignore
    __tablename__ = 'diagrams'

    package_id = Column(String, index=True, nullable=False)
    package = relationship("Package", back_populates="diagrams")
    classes = relationship('Class', secondary='diagram_class', back_populates='diagrams')
    diagram_classes = relationship('DiagramClass', cascade="all, delete-orphan", overlaps="classes,diagrams")
    enumerations = relationship('Enumeratie', secondary='diagram_enumeration', back_populates='diagrams')
    diagram_enumerations = relationship(
        'DiagramEnumeration', cascade="all, delete-orphan", overlaps="enumerations,diagrams"
    )
    associations = relationship('Association', secondary='diagram_association', back_populates='diagrams')
    diagram_associations = relationship(
        'DiagramAssociation', cascade="all, delete-orphan", overlaps="associations,diagrams"
    )
    generalizations = relationship('Generalization', secondary='diagram_generalization', back_populates='diagrams')
    diagram_generalizations = relationship(
        'DiagramGeneralization', cascade="all, delete-orphan", overlaps="generalizations,diagrams"
    )

    __table_args__ = (
        ForeignKeyConstraint(['package_id', 'schema_id'], ['packages.id', 'packages.schema_id'], deferrable=True),
    )

    def get_instances(self, type, root_package_id):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore" if suppress_warnings else "default", category=sa_exc.SAWarning)

            # Find root_package of self that is equal to root_package_id
            root_package = self.package
            while not root_package.id == root_package_id or root_package is None:
                root_package = root_package.parent_package
            if type == Class:
                return root_package.get_classes_inscope()
            elif type == Association:
                return root_package.get_associations_inscope()
            elif type == Generalization:
                return root_package.get_generalizations_inscope()
            elif type == Enumeratie:
                return root_package.get_enumerations_inscope()
            else:
                raise CrunchException(
                    "Error: while getting instances of type {type} from Diagram. Type must be of type Class,"
                    f" Association, Generalization or Enumeratie and cannot be of type {type}"
                )

    def get_copy(self, parent, materialize_generalizations=False):
        if not parent or not isinstance(parent, Package):
            raise CrunchException(
                "Error: wrong parent type for Diagram while copying. Parent must be of type Package and"
                f" cannot be of type {type(parent)}"
            )

        # Roep de get_copy methode van de superklasse aan
        copy_instance = super().get_copy(parent)
        copy_instance.package = parent

        # Append classes
        clazzIDs_in_scope = [clazz.id for clazz in self.get_instances(Class, parent.get_root_package().id)]
        clazzIDs_already_copied = [clazz.id for clazz in copy_instance.package.get_root_package().get_classes_inscope()]
        for clazz in self.classes:
            if clazz.name != const.ORPHAN_CLASS:
                if clazz.id not in clazzIDs_in_scope and clazz.id not in clazzIDs_already_copied:
                    copy_clazz = clazz.get_copy(
                        copy_instance.package, materialize_generalizations=materialize_generalizations
                    )
                    # copy_instance.package.classes.append(copy_clazz)
                    logger.debug(f"Class {clazz.name} outside of scope copied to package {copy_instance.package.name}")
                    diagram_class = DiagramClass(
                        diagram_id=copy_instance.id, schema_id=copy_instance.schema_id, class_id=copy_clazz.id
                    )
                else:
                    diagram_class = DiagramClass(
                        diagram_id=copy_instance.id, schema_id=copy_instance.schema_id, class_id=clazz.id
                    )
                copy_instance.diagram_classes.append(diagram_class)

        # Append enumerations
        enumerationIDs_in_scope = [
            enum.id for enum in self.get_instances(Enumeratie, parent.get_root_package().id)
        ]  # parent.get_enumerations_inscope()
        enumerationIDs_already_copied = [
            enum.id for enum in copy_instance.package.get_root_package().get_enumerations_inscope()
        ]
        for enum in self.enumerations:
            if enum.id not in enumerationIDs_in_scope and enum.id not in enumerationIDs_already_copied:
                copy_enum = enum.get_copy(
                    copy_instance.package, materialize_generalizations=materialize_generalizations
                )
                logger.debug(f"Enumeration {enum.name} outside of scope copied to package {copy_instance.package.name}")
                diagram_enum = DiagramEnumeration(
                    diagram_id=copy_instance.id, schema_id=copy_instance.schema_id, enumeration_id=copy_enum.id
                )
            else:
                diagram_enum = DiagramEnumeration(
                    diagram_id=copy_instance.id, schema_id=copy_instance.schema_id, enumeration_id=enum.id
                )
            copy_instance.diagram_enumerations.append(diagram_enum)

        return copy_instance


class Database:
    _instance = None

    def __new__(cls, db_url=const.DATABASE_URL, db_create=False, db_upsert=False):
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
        self.session.flush()

    def add(self, obj):
        self.session.add(obj)
        self.session.flush()

    def count_package(self):
        return self.session.query(Package).count()

    def get_package(self, id):
        return self.session.get(Package, id)

    def get_class(self, id):
        return self.session.get(Class, id)

    def get_enumeration(self, id):
        return self.session.get(Enumeratie, id)

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

    def count_diagrams(self):
        return self.session.query(Diagram).count()

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()

    def close(self):
        self.session.close()
        self._instance = None

    def get_session(self):
        return self.session
