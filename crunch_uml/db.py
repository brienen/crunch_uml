import logging
import re
import warnings

import inflection
from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    create_engine,
)
from sqlalchemy import exc as sa_exc
from sqlalchemy import insert, inspect, select
from sqlalchemy import text as sqlalchemy_text
from sqlalchemy import update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.orm.relationships import RelationshipProperty

import crunch_uml.const as const
import crunch_uml.util as util
from crunch_uml.exceptions import CrunchException

logger = logging.getLogger()
suppress_warnings = True

# Version of the crunch_uml datamodel, stored inside every database in the
# crunch_uml_meta table. Bump this ONLY when the schema changes in a way the
# additive migration (Database._add_missing_tables_and_columns) cannot
# handle: renamed or retyped columns, changed primary keys, changed
# semantics. On connect the stored version is compared with this value; a
# mismatch means the database is incompatible and it is recreated from
# scratch (all data discarded — models must be re-imported). Databases
# without a version marker predate this mechanism and are treated as
# additively migratable.
DATAMODEL_VERSION = 1
DATAMODEL_VERSION_KEY = "datamodel_version"

# The meta table deliberately lives in its own MetaData, NOT in Base.metadata:
# the generic renderers/parsers iterate Base.metadata.tables and must never
# see it (it has no schema_id and carries no model data).
_meta_metadata = MetaData()
crunch_meta_table = Table(
    "crunch_uml_meta",
    _meta_metadata,
    Column("key", String, primary_key=True),
    Column("value", String),
)


def add_args(argumentparser, subparser_dict):
    global suppress_warnings
    suppress_warnings = True
    # Rest of the code...
    #    '--database_no_orphans',
    #    action='store_true',
    #    help='Do not create orphan classes when relations point to classes that are not found in the imported file.',
    # )
    import_subparser = subparser_dict.get(const.CMD_IMPORT)
    import_subparser.add_argument(
        "-db_create",
        "--database_create_new",
        action="store_true",
        help="Create a new database and discard existing one.",
        default=False,
    )
    argumentparser.add_argument(
        "-db_url",
        "--database_url",
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
#
# Canonical diagram geometry
# --------------------------
# The diagram junction tables carry the layout of elements on a diagram in a
# *canonical* coordinate system: origin in the top-left corner of the diagram,
# x grows to the right, y grows downwards, and all stored values are positive.
# Parsers and renderers convert between this canonical system and the various
# Enterprise Architect conventions at the edge; the database itself only ever
# contains canonical values. The EA conventions (verified against real files):
#
# * XMI extension node geometry ("Left=..;Top=..;Right=..;Bottom=..;") uses
#   positive Top/Bottom values: x=Left, y=Top, width=Right-Left,
#   height=Bottom-Top.
# * QEA t_diagramobjects stores *negative* RectTop/RectBottom: x=RectLeft,
#   y=-RectTop, width=RectRight-RectLeft, height=RectTop-RectBottom.
# * Edge waypoints ("Path=") have negative y in both sources; canonical
#   waypoints flip the sign. XMI separates x:y pairs with '$', QEA with ';'.
#
# All geometry columns are nullable: membership without a known layout stays
# valid, and files/databases written before these columns existed remain
# importable. The raw EA style/geometry strings are kept losslessly in
# ea_style/ea_geometry so a round-trip can reproduce them exactly.


class DiagramNodeGeometry:
    """Canonical geometry for node-like diagram members (classes, enums)."""

    x = Column(Float, nullable=True)  # left edge, canonical coordinates
    y = Column(Float, nullable=True)  # top edge, canonical coordinates
    width = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    z_order = Column(Integer, nullable=True)  # stacking order (EA seqno/Sequence)
    ea_style = Column(Text, nullable=True)  # raw EA style string, lossless


class DiagramEdgeGeometry:
    """Canonical geometry for edge-like diagram members (associations, generalizations)."""

    waypoints = Column(Text, nullable=True)  # JSON list of {"x": .., "y": ..}, canonical
    hidden = Column(Boolean, nullable=True)  # EA Hidden flag
    ea_geometry = Column(Text, nullable=True)  # raw EA geometry string, lossless
    ea_style = Column(Text, nullable=True)  # raw EA style string, lossless


class DiagramClass(Base, DiagramNodeGeometry):  # type: ignore
    __tablename__ = "diagram_class"
    diagram_id = Column(String, nullable=False)
    schema_id = Column(String, nullable=False)
    class_id = Column(String, nullable=False)
    __table_args__ = (
        PrimaryKeyConstraint("diagram_id", "schema_id", "class_id"),
        ForeignKeyConstraint(["diagram_id", "schema_id"], ["diagrams.id", "diagrams.schema_id"]),
        ForeignKeyConstraint(["class_id", "schema_id"], ["classes.id", "classes.schema_id"]),
    )
    __mapper_args__ = {"confirm_deleted_rows": False}


class DiagramEnumeration(Base, DiagramNodeGeometry):  # type: ignore
    __tablename__ = "diagram_enumeration"
    diagram_id = Column(String, nullable=False)
    schema_id = Column(String, nullable=False)
    enumeration_id = Column(String, nullable=False)
    __table_args__ = (
        PrimaryKeyConstraint("diagram_id", "schema_id", "enumeration_id"),
        ForeignKeyConstraint(["diagram_id", "schema_id"], ["diagrams.id", "diagrams.schema_id"]),
        ForeignKeyConstraint(
            ["enumeration_id", "schema_id"],
            ["enumerations.id", "enumerations.schema_id"],
        ),
    )
    __mapper_args__ = {"confirm_deleted_rows": False}


class DiagramAssociation(Base, DiagramEdgeGeometry):  # type: ignore
    __tablename__ = "diagram_association"
    diagram_id = Column(String, nullable=False)
    schema_id = Column(String, nullable=False)
    association_id = Column(String, nullable=False)
    __table_args__ = (
        PrimaryKeyConstraint("diagram_id", "schema_id", "association_id"),
        ForeignKeyConstraint(["diagram_id", "schema_id"], ["diagrams.id", "diagrams.schema_id"]),
        ForeignKeyConstraint(
            ["association_id", "schema_id"],
            ["associations.id", "associations.schema_id"],
        ),
    )
    __mapper_args__ = {"confirm_deleted_rows": False}


class DiagramGeneralization(Base, DiagramEdgeGeometry):  # type: ignore
    __tablename__ = "diagram_generalization"
    diagram_id = Column(String, nullable=False)
    schema_id = Column(String, nullable=False)
    generalization_id = Column(String, nullable=False)
    __table_args__ = (
        PrimaryKeyConstraint("diagram_id", "schema_id", "generalization_id"),
        ForeignKeyConstraint(["diagram_id", "schema_id"], ["diagrams.id", "diagrams.schema_id"]),
        ForeignKeyConstraint(
            ["generalization_id", "schema_id"],
            ["generalizations.id", "generalizations.schema_id"],
        ),
    )
    __mapper_args__ = {"confirm_deleted_rows": False}


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
        clsname = type(self).__name__.split(".")[-1]
        return f'{clsname}: "{self.name}"'

    def get_copy(self, parent, materialize_generalizations=False):
        cls = self.__class__
        # Maak een nieuwe instantie van de klasse
        copy_instance = cls()
        for attr, column in self.__table__.columns.items():
            setattr(copy_instance, attr, getattr(self, attr))

        setattr(copy_instance, "kopie", True)
        return copy_instance

    def make_copy_to_schema(self, sch, parent=None, recursive=True, materialize_generalizations=False):
        cls = self.__class__
        # Maak een nieuwe instantie van de klasse
        rel_keys = self.to_dict_rel().keys()
        copy_instance = cls()
        for attr, column in self.__table__.columns.items():
            if attr not in rel_keys:
                setattr(copy_instance, attr, getattr(self, attr))

        setattr(copy_instance, "kopie", True)
        sch.save(copy_instance)
        return copy_instance


# define the base class for UML elements
class UMLBase(UML_Generic):
    author = Column(String)
    version = Column(String)
    phase = Column(String)
    status = Column(String)
    uri = Column(String)
    visibility = Column(String)
    alias = Column(String)


# Define the base class for UML tags conformant to MIM
class UMLTagsCommon:
    herkomst = Column(String)
    herkomst_definitie = Column(String)
    toelichting = Column(String)
    begrip = Column(String)
    datum_opname = Column(String)


class UMLTagsGEMMA:
    gemma_naam = Column(String)
    gemma_type = Column(String)
    gemma_url = Column(String)
    gemma_definitie = Column(String)
    gemma_toelichting = Column(String)
    domein_dcat = Column(String)
    domein_iv3 = Column(String)
    datum_tijd_export = Column(String)


class UMLTagsHistory:
    heeft_tijdlijn_geldigheid = Column(String, default="Nee")
    heeft_tijdlijn_registratie = Column(String, default="Nee")
    indicatie_formele_historie = Column(String, default="Nee")
    indicatie_materiele_historie = Column(String, default="Nee")
    indicatie_in_onderzoek = Column(String, default="Nee")


class UMLTagsNumeriek:
    minimumwaarde_inclusief = Column(String)
    minimumwaarde_exclusief = Column(String)
    maximumwaarde_inclusief = Column(String)
    maximumwaarde_exclusief = Column(String)
    eenheid = Column(String)


class UMLTagsMetadata:
    populatie = Column(String)
    kwaliteit = Column(String)
    synoniemen = Column(String)
    authentiek = Column(String)


# Define the UML tags classes for different UML elements
class UMLTags(UMLTagsCommon, UMLTagsGEMMA, UMLTagsMetadata):
    archimate_type = Column(String)


class UMLTagsAttribute(UMLTagsCommon, UMLTagsHistory, UMLTagsNumeriek, UMLTagsMetadata):
    lengte = Column(String)
    patroon = Column(String)
    formeel_patroon = Column(String)
    indicatie_classificerend = Column(String)
    mogelijk_geen_waarde = Column(String, default="Ja")


class UMLTagsRelation(UMLTagsCommon, UMLTagsHistory, UMLTagsMetadata):
    mogelijk_geen_waarde = Column(String, default="Ja")


class UMLTagsGeneralization(UMLTagsCommon):
    pass


class UMLTagsLiteral(UMLTagsCommon):
    pass


class UMLTagsDomain(UMLTagsCommon):
    afkorting = Column(String)
    release = Column(String)


class Package(Base, UMLBase, UMLTagsDomain):  # type: ignore
    __tablename__ = "packages"

    parent_package_id = Column(String, index=True)
    parent_package = relationship(
        "Package", back_populates="subpackages", remote_side="[Package.id, Package.schema_id]", lazy="joined"
    )
    subpackages = relationship("Package", back_populates="parent_package", cascade="all, delete-orphan")

    classes = relationship("Class", back_populates="package", cascade="all, delete-orphan")
    enumerations = relationship("Enumeratie", back_populates="package", cascade="all, delete-orphan")
    diagrams = relationship("Diagram", back_populates="package", cascade="all, delete-orphan")
    modelnaam_kort = Column(String)

    @hybrid_property
    def is_domain(self):
        return self.stereotype == "Domein"

    @hybrid_property
    def domain(self):
        if self.is_domain:
            return self
        else:
            if self.parent_package:
                return self.parent_package.domain
            else:
                return None

    @hybrid_property
    def domain_name(self):
        """
        Verwijder getallen aan het begin van een string en trim
        leidende en afsluitende spaties.

        :param input_string: De originele string
        :return: De opgeschoonde string
        """
        if self.domain is None:
            return None

        name = str(self.domain.name)
        name = re.sub(r'^\d+', '', name)
        name = name.strip()
        return name

    __table_args__ = (
        ForeignKeyConstraint(
            ["parent_package_id", "schema_id"],
            ["packages.id", "packages.schema_id"],
            deferrable=True,
        ),
    )

    # Logic for models
    def get_classes(self):
        return [c for c in self.classes if not c.is_datatype]

    def get_datatypes(self):
        return [c for c in self.classes if c.is_datatype]

    def is_model(self):
        return self.modelnaam_kort is not None or self.parent_package is None

    def get_model(self):
        if self.is_model() or self.parent_package is None:
            return self
        else:
            return self.parent_package.get_model()

    def get_parent_model(self):
        if self.parent_package is None:
            return None
        elif self.parent_package.get_model() == self.get_model():
            return self.parent_package.get_parent_model()
        else:
            return self.parent_package.get_model()

    def get_submodels(self, recursive=False):
        submodels = []
        for subpackage in self.subpackages:
            if subpackage.is_model():
                submodels.append(subpackage)
            if recursive or not subpackage.is_model():
                submodels.extend(subpackage.get_submodels())
        return submodels

    def get_packages_in_model(self):
        model = self.get_model()

        subpackages = []
        if self == model:
            subpackages.append(self)

        for subpackage in self.subpackages:
            if not subpackage.is_model():
                subpackages.append(subpackage)
                subpackages.extend(subpackage.get_packages_in_model())
        return subpackages

    def get_classes_in_model(self):
        packages = self.get_packages_in_model()
        return {clazz for package in packages for clazz in package.classes}

    def get_enumerations_in_model(self):
        packages = self.get_packages_in_model()
        return {enum for package in packages for enum in package.enumerations}

    def get_diagrams_in_model(self):
        packages = self.get_packages_in_model()
        return {diagram for package in packages for diagram in package.diagrams}

    def get_class_by_name(self, name):
        """
        Get class by name from the model
        """
        if name is None:
            return None
        with warnings.catch_warnings():
            warnings.simplefilter("ignore" if suppress_warnings else "default", category=sa_exc.SAWarning)
            for clazz in self.get_classes_in_model():
                if clazz.name.lower() == name.lower():
                    return clazz
            return None

    def get_enumeration_by_name(self, name):
        """
        Get enumeration by name from the model
        """
        if name is None:
            return None
        with warnings.catch_warnings():
            warnings.simplefilter("ignore" if suppress_warnings else "default", category=sa_exc.SAWarning)
            for enum in self.get_enumerations_in_model():
                if enum.name.lower() == name.lower():
                    return enum
            return None

    def get_diagram_by_name(self, name):
        """
        Get diagram by name from the model
        """
        if name is None:
            return None
        with warnings.catch_warnings():
            warnings.simplefilter("ignore" if suppress_warnings else "default", category=sa_exc.SAWarning)
            for diagram in self.get_diagrams_in_model():
                if diagram.name.lower() == name.lower():
                    return diagram
            return None

    # End of logic for models

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

    def get_associations_inscope(self):
        """Associations whose both endpoint classes are in scope of this package."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore" if suppress_warnings else "default", category=sa_exc.SAWarning)
            clazzes = self.get_classes_inscope()
            return {assoc for clazz in clazzes for assoc in clazz.uitgaande_associaties if assoc.dst_class in clazzes}

    def get_generalizations_inscope(self):
        """Generalizations whose both endpoint classes are in scope of this package."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore" if suppress_warnings else "default", category=sa_exc.SAWarning)
            clazzes = self.get_classes_inscope()
            return {gener for clazz in clazzes for gener in clazz.superclasses if gener.superclass in clazzes}

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
                clazz_copy = clazz.get_copy(
                    copy_instance,
                    materialize_generalizations=materialize_generalizations,
                )
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

    def make_copy_to_schema(self, sch, parent=None, recursive=True, materialize_generalizations=False):
        if parent and not isinstance(parent, Package):
            raise CrunchException(
                f"Error: wrong parent type for package while copying. Parent cannot be of type {type(parent)}"
            )

        # Roep de get_copy methode van de superklasse aan
        copy_instance = super().make_copy_to_schema(
            sch, parent=parent, materialize_generalizations=materialize_generalizations
        )
        if parent is not None:
            copy_instance.parent_package_id = parent.id

        # Voer eventuele extra stappen uit voor de literals
        if recursive:
            for subpackage in self.subpackages:
                subpackage.make_copy_to_schema(
                    sch,
                    parent=copy_instance,
                    recursive=recursive,
                    materialize_generalizations=materialize_generalizations,
                )
            for clazz in self.classes:
                if clazz.name != const.ORPHAN_CLASS:
                    clazz.make_copy_to_schema(
                        sch,
                        parent=copy_instance,
                        recursive=recursive,
                        materialize_generalizations=materialize_generalizations,
                    )
            for enum in self.enumerations:
                enum_copy = enum.make_copy_to_schema(sch, parent=copy_instance)
                copy_instance.enumerations.append(enum_copy)
            for diagram in self.diagrams:
                diagram_copy = diagram.make_copy_to_schema(sch, parent=copy_instance)
                copy_instance.diagrams.append(diagram_copy)
        return sch.save(copy_instance)


class Class(Base, UMLBase, UMLTags):  # type: ignore
    __tablename__ = "classes"

    package_id = Column(String, index=True)
    package = relationship("Package", back_populates="classes", lazy="joined")
    attributes = relationship(
        "Attribute",
        back_populates="clazz",
        lazy="joined",
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
        foreign_keys="[Generalization.subclass_id, Generalization.schema_id]",
        cascade="all, delete-orphan",
        overlaps="subclasses",
    )
    subclasses = relationship(
        "Generalization",
        back_populates="superclass",
        foreign_keys="[Generalization.superclass_id, Generalization.schema_id]",
        cascade="all, delete-orphan",
        overlaps="superclasses",
    )
    diagrams = relationship("Diagram", secondary="diagram_class", back_populates="classes")
    indicatie_formele_historie = Column(String)
    authentiek = Column(String)
    nullable = Column(String)
    is_datatype = Column(Boolean, default=False)

    # @hybrid_property
    # def domain(self):
    #    if self.package:
    #        package = self.package
    #        while package.stereotype != "Domein":
    #            package = package.parent_package
    #            if not package:
    #                return None
    #        return package

    __table_args__ = (
        ForeignKeyConstraint(
            ["package_id", "schema_id"],
            ["packages.id", "packages.schema_id"],
            deferrable=True,
        ),
    )

    def get_attribute_by_name(self, name):
        """
        Get attribute by name from the class
        """
        if name is None:
            return None
        with warnings.catch_warnings():
            warnings.simplefilter("ignore" if suppress_warnings else "default", category=sa_exc.SAWarning)
            for attr in self.attributes:
                if attr.name.lower() == name.lower():
                    return attr
            return None

    def copy_attributes(self, copy_instance, materialize_generalizations=False):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore" if suppress_warnings else "default", category=sa_exc.SAWarning)

            # Maak lijst van namen van al aanwezige attributen
            copy_attr_lst = [
                attribute.name for attribute in copy_instance.attributes if attribute.name and attribute.name != "None"
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

    def make_copy_to_schema(self, sch, parent=None, recursive=True, materialize_generalizations=False):
        if parent is not None or isinstance(parent, Package):
            raise CrunchException(
                f"Error: wrong parent type for package while copying. Parent cannot be of type {type(parent)}"
            )

        # Roep de get_copy methode van de superklasse aan
        copy_instance = super().make_copy_to_schema(sch)
        copy_instance.package = parent

        # Voer eventuele extra stappen uit voor de literals
        if recursive:
            for attr in self.attributes:
                attr_copy = attr.make_copy_to_schema(sch, parent=copy_instance)
                copy_instance.attributes.append(attr_copy)

        sch.save(copy_instance)
        return copy_instance


class Attribute(Base, UML_Generic, UMLTagsAttribute):  # type: ignore
    __tablename__ = "attributes"

    clazz_id = Column(String, index=True, nullable=False)
    clazz = relationship(
        "Class",
        back_populates="attributes",
        foreign_keys="[Attribute.clazz_id, Attribute.schema_id]",
    )
    primitive = Column(String)
    enumeration_id = Column(String, index=True)
    enumeration = relationship("Enumeratie", lazy="joined", overlaps="attributes,clazz")
    type_class_id = Column(String, index=True)
    type_class = relationship(
        "Class",
        foreign_keys="[Attribute.type_class_id, Attribute.schema_id]",
        overlaps="attributes,clazz,enumeration",
    )
    verplicht = Column(Boolean, default=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["clazz_id", "schema_id"],
            ["classes.id", "classes.schema_id"],
            deferrable=True,
            name="FK_clazz_id",
        ),
        ForeignKeyConstraint(
            ["enumeration_id", "schema_id"],
            ["enumerations.id", "enumerations.schema_id"],
            deferrable=True,
            name="FK_enumeration_id",
        ),
        ForeignKeyConstraint(
            ["type_class_id", "schema_id"],
            ["classes.id", "classes.schema_id"],
            deferrable=True,
            name="FK_type_class",
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

    def make_copy_to_schema(self, sch, parent=None, recursive=True, materialize_generalizations=False):
        if not isinstance(parent, Class):
            raise CrunchException(
                f"Error: wrong parent type for package while copying. Parent cannot be of type {type(parent)}"
            )

        # Roep de get_copy methode van de superklasse aan
        copy_instance = super().make_copy_to_schema(sch)
        copy_instance.clazz = parent

        # Voer eventuele extra stappen uit voor de literals
        if recursive:
            if self.enumeration:
                copy_instance.enumeration = self.enumeration.make_copy_to_schema(sch, parent=None)
            if self.type_class:
                copy_instance.type_class = self.type_class.make_copy_to_schema(sch, parent=None)

        sch.save(copy_instance)
        return copy_instance


class Enumeratie(Base, UMLBase, UMLTags):  # type: ignore
    __tablename__ = "enumerations"

    package_id = Column(String, index=True, nullable=False)
    package = relationship("Package", back_populates="enumerations")
    literals = relationship(
        "EnumerationLiteral",
        back_populates="enumeratie",
        lazy="joined",
        cascade="all, delete-orphan",
    )
    diagrams = relationship("Diagram", secondary="diagram_enumeration", back_populates="enumerations")

    # @hybrid_property
    # def domain(self):
    #    return self.package.domain

    __table_args__ = (
        ForeignKeyConstraint(
            ["package_id", "schema_id"],
            ["packages.id", "packages.schema_id"],
            deferrable=True,
        ),
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

    def make_copy_to_schema(self, sch, parent=None, recursive=True, materialize_generalizations=False):
        if parent is not None or isinstance(parent, Package):
            raise CrunchException(
                f"Error: wrong parent type for package while copying. Parent cannot be of type {type(parent)}"
            )

        # Roep de get_copy methode van de superklasse aan
        copy_instance = super().make_copy_to_schema(sch)
        copy_instance.package = parent

        # Voer eventuele extra stappen uit voor de literals
        if recursive:
            for literal in self.literals:
                literal_copy = literal.make_copy_to_schema(sch, parent=copy_instance)
                copy_instance.literals.append(literal_copy)

        sch.save(copy_instance)
        return copy_instance


class EnumerationLiteral(Base, UML_Generic):  # type: ignore
    __tablename__ = "enumerationliterals"

    enumeratie_id = Column(String, index=True, nullable=False)
    enumeratie = relationship("Enumeratie", back_populates="literals")
    type = Column(String)
    alias = Column(String)

    __table_args__ = (
        ForeignKeyConstraint(
            ["enumeratie_id", "schema_id"],
            ["enumerations.id", "enumerations.schema_id"],
            deferrable=True,
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


class Association(Base, UML_Generic, UMLTagsRelation):  # type: ignore
    __tablename__ = "associations"

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
        foreign_keys="[Association.dst_class_id, Association.schema_id]",
        overlaps="src_class,uitgaande_associaties",
    )
    dst_mult_start = Column(String)
    dst_mult_end = Column(String)
    dst_multiplicity = Column(String)
    dst_documentation = Column(Text)
    dst_role = Column(String)
    order = Column(Integer)
    diagrams = relationship("Diagram", secondary="diagram_association", back_populates="associations")

    __table_args__ = (
        ForeignKeyConstraint(
            ["src_class_id", "schema_id"],
            ["classes.id", "classes.schema_id"],
            deferrable=True,
            name="fk_src_class",
        ),
        ForeignKeyConstraint(
            ["dst_class_id", "schema_id"],
            ["classes.id", "classes.schema_id"],
            deferrable=True,
            name="fk_dst_class",
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
        if self.src_mult_end == "1":
            return "1-1" if self.dst_mult_end == "1" else "1-n"
        else:
            return "n-1" if self.dst_mult_end == "1" else "n-m"

    def isEnkelvoudig(self, dst: True):  # type: ignore
        if dst:
            return True if self.dst_mult_end in ["0", "1"] else False
        else:
            return True if self.src_mult_end in ["0", "1"] else False

    def isGelimiteerdMeervoudig(self, dst: True):  # type: ignore
        if dst:
            try:
                return int(self.dst_mult_end) > 1
            except (ValueError, TypeError):
                return False
        else:
            try:
                return int(self.src_mult_start) > 1
            except (ValueError, TypeError):
                return False

    def isVerplicht(self, dst: True):  # type: ignore
        if dst:
            try:
                return int(self.dst_mult_start) > 0
            except (ValueError, TypeError):
                return False
        else:
            try:
                return int(self.src_mult_start) > 0
            except (ValueError, TypeError):
                return False

    def getRole(self, view="src"):
        if view == "src":
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


class Generalization(Base, UML_Generic, UMLTagsRelation):  # type: ignore
    __tablename__ = "generalizations"

    superclass_id = Column(String, index=True, nullable=False)
    superclass = relationship(
        "Class",
        back_populates="subclasses",
        foreign_keys="[Generalization.superclass_id, Generalization.schema_id]",
        overlaps="superclasses, subclass",
    )
    subclass_id = Column(String, index=True, nullable=False)
    subclass = relationship(
        "Class",
        back_populates="superclasses",
        foreign_keys="[Generalization.subclass_id, Generalization.schema_id]",
        overlaps="subclasses, superclass",
    )
    diagrams = relationship("Diagram", secondary="diagram_generalization", back_populates="generalizations")

    __table_args__ = (
        ForeignKeyConstraint(
            ["superclass_id", "schema_id"],
            ["classes.id", "classes.schema_id"],
            deferrable=True,
            name="fk_super_class",
        ),
        ForeignKeyConstraint(
            ["subclass_id", "schema_id"],
            ["classes.id", "classes.schema_id"],
            deferrable=True,
            name="fk_sub_class",
        ),
    )

    def __repr__(self):
        clsname = type(self).__name__.split(".")[-1]
        return f"{clsname}: {self.subclass} isSubClassOf {self.superclass}"


class Diagram(Base, UMLBase):  # type: ignore
    __tablename__ = "diagrams"

    package_id = Column(String, index=True, nullable=False)
    package = relationship("Package", back_populates="diagrams")
    classes = relationship("Class", secondary="diagram_class", back_populates="diagrams")
    diagram_classes = relationship("DiagramClass", cascade="all, delete-orphan", overlaps="classes,diagrams")
    enumerations = relationship("Enumeratie", secondary="diagram_enumeration", back_populates="diagrams")
    diagram_enumerations = relationship(
        "DiagramEnumeration",
        cascade="all, delete-orphan",
        overlaps="enumerations,diagrams",
    )
    associations = relationship("Association", secondary="diagram_association", back_populates="diagrams")
    diagram_associations = relationship(
        "DiagramAssociation",
        cascade="all, delete-orphan",
        overlaps="associations,diagrams",
    )
    generalizations = relationship("Generalization", secondary="diagram_generalization", back_populates="diagrams")
    diagram_generalizations = relationship(
        "DiagramGeneralization",
        cascade="all, delete-orphan",
        overlaps="generalizations,diagrams",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["package_id", "schema_id"],
            ["packages.id", "packages.schema_id"],
            deferrable=True,
        ),
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

        node_geometry_fields = ("x", "y", "width", "height", "z_order", "ea_style")
        edge_geometry_fields = ("waypoints", "hidden", "ea_geometry", "ea_style")

        def copy_geometry(source_row, target_row, fields):
            if source_row is not None:
                for field in fields:
                    setattr(target_row, field, getattr(source_row, field))

        # Append classes
        original_diagram_classes = {dc.class_id: dc for dc in self.diagram_classes}
        clazzIDs_in_scope = [clazz.id for clazz in self.get_instances(Class, parent.get_root_package().id)]
        clazzIDs_already_copied = [clazz.id for clazz in copy_instance.package.get_root_package().get_classes_inscope()]
        for clazz in self.classes:
            if clazz.name != const.ORPHAN_CLASS:
                if clazz.id not in clazzIDs_in_scope and clazz.id not in clazzIDs_already_copied:
                    copy_clazz = clazz.get_copy(
                        copy_instance.package,
                        materialize_generalizations=materialize_generalizations,
                    )
                    # copy_instance.package.classes.append(copy_clazz)
                    logger.debug(f"Class {clazz.name} outside of scope copied to package {copy_instance.package.name}")
                    diagram_class = DiagramClass(
                        diagram_id=copy_instance.id,
                        schema_id=copy_instance.schema_id,
                        class_id=copy_clazz.id,
                    )
                else:
                    diagram_class = DiagramClass(
                        diagram_id=copy_instance.id,
                        schema_id=copy_instance.schema_id,
                        class_id=clazz.id,
                    )
                copy_geometry(original_diagram_classes.get(clazz.id), diagram_class, node_geometry_fields)
                copy_instance.diagram_classes.append(diagram_class)

        # Append enumerations
        original_diagram_enums = {de.enumeration_id: de for de in self.diagram_enumerations}
        enumerationIDs_in_scope = [
            enum.id for enum in self.get_instances(Enumeratie, parent.get_root_package().id)
        ]  # parent.get_enumerations_inscope()
        enumerationIDs_already_copied = [
            enum.id for enum in copy_instance.package.get_root_package().get_enumerations_inscope()
        ]
        for enum in self.enumerations:
            if enum.id not in enumerationIDs_in_scope and enum.id not in enumerationIDs_already_copied:
                copy_enum = enum.get_copy(
                    copy_instance.package,
                    materialize_generalizations=materialize_generalizations,
                )
                logger.debug(f"Enumeration {enum.name} outside of scope copied to package {copy_instance.package.name}")
                diagram_enum = DiagramEnumeration(
                    diagram_id=copy_instance.id,
                    schema_id=copy_instance.schema_id,
                    enumeration_id=copy_enum.id,
                )
            else:
                diagram_enum = DiagramEnumeration(
                    diagram_id=copy_instance.id,
                    schema_id=copy_instance.schema_id,
                    enumeration_id=enum.id,
                )
            copy_geometry(original_diagram_enums.get(enum.id), diagram_enum, node_geometry_fields)
            copy_instance.diagram_enumerations.append(diagram_enum)

        # Append associations and generalizations. Copies keep the original
        # ids, so a membership row stays valid exactly when the relation
        # itself ends up in the copy. Class.get_copy is what copies
        # relations: an association is copied along with its (copied) source
        # class when that class has a package and the far endpoint is a
        # non-orphan class in scope of the *owning class's own* root
        # package; a generalization is copied along with its superclass
        # under the same conditions. Mirror those conditions here —
        # anything else would create dangling membership rows.
        copied_class_ids = (
            set(clazzIDs_in_scope)
            | set(clazzIDs_already_copied)
            | {clazz.id for clazz in self.classes if clazz.name != const.ORPHAN_CLASS}
        )
        # Scope is determined per owning class: a diagram may show classes
        # from another root package, whose scope differs from the diagram's.
        owner_root_scope_cache: dict = {}

        def owner_scope_ids(owning_class):
            root = owning_class.package.get_root_package()
            if root.id not in owner_root_scope_cache:
                owner_root_scope_cache[root.id] = {clazz.id for clazz in root.get_classes_inscope()}
            return owner_root_scope_cache[root.id]

        def relation_is_copied(owning_class, far_class):
            # Same conditions as Class.get_copy uses when copying relations.
            return (
                owning_class is not None
                and owning_class.id in copied_class_ids
                and owning_class.name != const.ORPHAN_CLASS
                and owning_class.package is not None
                and far_class is not None
                and far_class.name != const.ORPHAN_CLASS
                and far_class.id in owner_scope_ids(owning_class)
            )

        original_diagram_assocs = {da.association_id: da for da in self.diagram_associations}
        for assoc in self.associations:
            if relation_is_copied(assoc.src_class, assoc.dst_class):
                diagram_assoc = DiagramAssociation(
                    diagram_id=copy_instance.id,
                    schema_id=copy_instance.schema_id,
                    association_id=assoc.id,
                )
                copy_geometry(original_diagram_assocs.get(assoc.id), diagram_assoc, edge_geometry_fields)
                copy_instance.diagram_associations.append(diagram_assoc)
            else:
                logger.debug(
                    f"Association {assoc.name} on diagram {self.name} is not part of the copy:"
                    " membership not copied."
                )

        original_diagram_geners = {dg.generalization_id: dg for dg in self.diagram_generalizations}
        for gener in self.generalizations:
            if relation_is_copied(gener.superclass, gener.subclass):
                diagram_gener = DiagramGeneralization(
                    diagram_id=copy_instance.id,
                    schema_id=copy_instance.schema_id,
                    generalization_id=gener.id,
                )
                copy_geometry(original_diagram_geners.get(gener.id), diagram_gener, edge_geometry_fields)
                copy_instance.diagram_generalizations.append(diagram_gener)
            else:
                logger.debug(
                    f"Generalization on diagram {self.name} is not part of the copy:" " membership not copied."
                )

        return copy_instance


class Database:
    _instance = None

    def __new__(cls, db_url=const.DATABASE_URL, db_create=False):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            # Setting up the database
            cls._instance.engine = create_engine(db_url)
            Session = sessionmaker(bind=cls._instance.engine)
            cls._instance.session = Session()
        if db_create:
            cls._instance._reset_database()

        cls._instance._check_and_create_database()  # Check if the database exists, if not create it
        return cls._instance

    def _reset_database(self):
        Base.metadata.drop_all(bind=self.engine)  # Drop all tables
        Base.metadata.create_all(bind=self.engine)  # Create all tables
        self._write_datamodel_version()

    def _check_and_create_database(self):
        try:
            inspector = inspect(self.engine)
            if Package.__tablename__ not in inspector.get_table_names():
                # If the 'packages' table does not exist, create all tables
                Base.metadata.create_all(bind=self.engine)
            else:
                stored_version = self._read_datamodel_version()
                if stored_version is not None and stored_version != DATAMODEL_VERSION:
                    # Incompatible datamodel: recreate the database. A None
                    # version means the database predates the version marker
                    # and is still additively migratable.
                    logger.warning(
                        f"Database has datamodel version {stored_version}, this version of crunch_uml"
                        f" requires {DATAMODEL_VERSION}: recreating the database. All data is discarded;"
                        " re-import your models."
                    )
                    self._reset_database()
                else:
                    self._add_missing_tables_and_columns(inspector)
        except OperationalError:
            # If the database does not exist or is not reachable, create it
            Base.metadata.create_all(bind=self.engine)
        self._write_datamodel_version()

    def _read_datamodel_version(self):
        """Version marker stored in the database, or None when the database
        predates the marker (or the value is unreadable)."""
        try:
            inspector = inspect(self.engine)
            if crunch_meta_table.name not in inspector.get_table_names():
                return None
            with self.engine.connect() as connection:
                row = connection.execute(
                    select(crunch_meta_table.c.value).where(crunch_meta_table.c.key == DATAMODEL_VERSION_KEY)
                ).first()
            if row is None or row[0] is None:
                return None
            return int(row[0])
        except (OperationalError, ValueError):
            return None

    def _write_datamodel_version(self):
        try:
            _meta_metadata.create_all(bind=self.engine, checkfirst=True)
            with self.engine.begin() as connection:
                updated = connection.execute(
                    update(crunch_meta_table)
                    .where(crunch_meta_table.c.key == DATAMODEL_VERSION_KEY)
                    .values(value=str(DATAMODEL_VERSION))
                ).rowcount
                if not updated:
                    connection.execute(
                        insert(crunch_meta_table).values(key=DATAMODEL_VERSION_KEY, value=str(DATAMODEL_VERSION))
                    )
        except OperationalError as e:
            logger.warning(f"Could not write datamodel version to database: {e}")

    def _add_missing_tables_and_columns(self, inspector):
        """Lightweight additive migration for existing database files.

        Database files written by an older version of crunch_uml miss columns
        that were added to the model later (e.g. the diagram geometry
        columns); ``create_all`` never alters existing tables, so querying
        such a file would fail with "no such column". Only additions are
        performed: missing tables are created and missing *nullable* columns
        are added — nothing is ever dropped or changed.
        """
        existing_tables = set(inspector.get_table_names())
        missing_tables = [table for table in Base.metadata.tables.values() if table.name not in existing_tables]
        if missing_tables:
            Base.metadata.create_all(bind=self.engine, tables=missing_tables)

        preparer = self.engine.dialect.identifier_preparer
        with self.engine.begin() as connection:
            for table in Base.metadata.tables.values():
                if table.name not in existing_tables:
                    continue
                existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
                for column in table.columns:
                    if column.name in existing_columns:
                        continue
                    if not column.nullable and column.default is None and column.server_default is None:
                        logger.warning(
                            f"Table '{table.name}' in existing database misses non-nullable column"
                            f" '{column.name}'; cannot add it automatically. Recreate the database"
                            " with --database_create_new."
                        )
                        continue
                    ddl = (
                        f"ALTER TABLE {preparer.quote(table.name)} ADD COLUMN"
                        f" {preparer.quote(column.name)} {column.type.compile(self.engine.dialect)}"
                    )
                    logger.info(f"Adding missing column '{column.name}' to table '{table.name}'")
                    connection.execute(sqlalchemy_text(ddl))

    def save(self, obj):
        # NB: no per-call flush. autoflush=True ensures any subsequent ORM
        # query in the same unit-of-work sees pending changes; parsers that
        # touch many rows in a tight loop call session.flush() explicitly at
        # phase boundaries instead. Flushing per save() turns each row into a
        # SQL round-trip — that was the dominant cost on large imports.
        return self.session.merge(obj)

    def add(self, obj):
        return self.session.add(obj)

    def count_package(self):
        return self.session.query(Package).count()

    def get_package(self, id):
        return self.session.get(Package, id)

    def get_class(self, id):
        return self.session.query(Class).filter_by(id=id, is_datatype=False).first()

    def get_datatype(self, id):
        return self.session.query(Class).filter_by(id=id, is_datatype=True).first()

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
        return self.session.query(Class).filter_by(is_datatype=False).count()

    def count_datatype(self):
        return self.session.query(Class).filter_by(is_datatype=True).count()

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
