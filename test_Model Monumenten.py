from __future__ import annotations
from typing import List
from enum import Enum
from sqlalchemy import Integer, String, Date, Boolean, Text, Enum as SAEnum, Column, Table, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship, mapped_column, Mapped


class Base(DeclarativeBase):
    id = mapped_column(Integer, primary_key=True)



# Enumeraries

class TypeMonument(Enum):
  rijksmonument = 1
  gemeentelijkmonument = 2




# Koppeltabellen

koppel_monumentambacht_EAID_8E18F665_2A86_44fd_AD55_3E435A282BDF = Table(
    "koppel_monumentambacht_EAID_8E18F665_2A86_44fd_AD55_3E435A282BDF",
    Base.metadata,
    Column("left_id", ForeignKey("beschermde_status.id"), primary_key=True),
    Column("right_id", ForeignKey("ambacht.id"), primary_key=True),
)
koppel_monumentbouwstijl_EAID_144ADF26_C2E9_4080_8F4F_32F9B255E4AE = Table(
    "koppel_monumentbouwstijl_EAID_144ADF26_C2E9_4080_8F4F_32F9B255E4AE",
    Base.metadata,
    Column("left_id", ForeignKey("beschermde_status.id"), primary_key=True),
    Column("right_id", ForeignKey("bouwstijl.id"), primary_key=True),
)
koppel_monumentbouwactiviteit_EAID_55585CB9_E569_47ca_9EFE_B9D5CF46BCBD = Table(
    "koppel_monumentbouwactiviteit_EAID_55585CB9_E569_47ca_9EFE_B9D5CF46BCBD",
    Base.metadata,
    Column("left_id", ForeignKey("beschermde_status.id"), primary_key=True),
    Column("right_id", ForeignKey("bouwactiviteit.id"), primary_key=True),
)
koppel_monumentbouwtype_EAID_D9634EAD_2869_40a1_B243_805897E4B1B3 = Table(
    "koppel_monumentbouwtype_EAID_D9634EAD_2869_40a1_B243_805897E4B1B3",
    Base.metadata,
    Column("left_id", ForeignKey("beschermde_status.id"), primary_key=True),
    Column("right_id", ForeignKey("bouwtype.id"), primary_key=True),
)
koppel_monumentfunctie_EAID_FD27EB67_1CFA_4f40_AE79_329DE9DE6754 = Table(
    "koppel_monumentfunctie_EAID_FD27EB67_1CFA_4f40_AE79_329DE9DE6754",
    Base.metadata,
    Column("left_id", ForeignKey("beschermde_status.id"), primary_key=True),
    Column("right_id", ForeignKey("oorspronkelijke_functie.id"), primary_key=True),
)



# Classes
class Ambacht(Base):
    '''Beroep waarbij een handwerker met gereedschap eindproducten maakt.
    '''
    __tablename__ = "ambacht"
    
    ambachtjaartot = mapped_column(Integer)
    ambachtjaarvanaf = mapped_column(Integer)
    ambachtsoort = mapped_column(String(300))
    beschermde_statusen: Mapped[List[BeschermdeStatus]] = relationship(secondary=koppel_monumentambacht_EAID_8E18F665_2A86_44fd_AD55_3E435A282BDF) 

class BeschermdeStatus(Base):
    '''Status van de bescherming van een monument. Een monument / erfgoed is een overblijfsel van kunst, cultuur, architectuur of nijverheid dat van algemeen belang wordt geacht vanwege de historische, volkskundige, artistieke, wetenschappelijke, industrieel-archeologische of andere sociaal-culturele waarde. Vormen van monument / erfgoed met de status rijks- provinciaal- of gemeentelijke monument / erfgoed zijn beschermd op grond van een besluit van respectievelijk het Ministerie OCW, de provincie of de gemeente,
    '''
    __tablename__ = "beschermde_status"
    
    bronnen = mapped_column(String(400))
    complex = mapped_column(String(200))
    datuminschrijvingregister = mapped_column(Date)
    gemeentelijkmonumentcode = mapped_column(String(80))
    gezichtscode = mapped_column(String(20))
    naam = mapped_column(String(200))
    omschrijving = mapped_column(Text)
    opmerking = mapped_column(Text)
    rijksmonumentcode = mapped_column(String(80))
    type = mapped_column(SAEnum(TypeMonument))
    ambachten: Mapped[List[Ambacht]] = relationship(secondary=koppel_monumentambacht_EAID_8E18F665_2A86_44fd_AD55_3E435A282BDF)
    bouwstijlen: Mapped[List[Bouwstijl]] = relationship(secondary=koppel_monumentbouwstijl_EAID_144ADF26_C2E9_4080_8F4F_32F9B255E4AE)
    bouwactiviteiten: Mapped[List[Bouwactiviteit]] = relationship(secondary=koppel_monumentbouwactiviteit_EAID_55585CB9_E569_47ca_9EFE_B9D5CF46BCBD)
    bouwtypen: Mapped[List[Bouwtype]] = relationship(secondary=koppel_monumentbouwtype_EAID_D9634EAD_2869_40a1_B243_805897E4B1B3)
    oorspronkelijke_functies: Mapped[List[OorspronkelijkeFunctie]] = relationship(secondary=koppel_monumentfunctie_EAID_FD27EB67_1CFA_4f40_AE79_329DE9DE6754) 

class Bouwactiviteit(Base):
    '''Het bouwen van een bouwwerk.
    '''
    __tablename__ = "bouwactiviteit"
    
    bouwjaarklasse = mapped_column(String(80))
    bouwjaartot = mapped_column(Integer)
    bouwjaarvan = mapped_column(Integer)
    indicatie = mapped_column(String(8))
    omschrijving = mapped_column(String(300))
    beschermde_statusen: Mapped[List[BeschermdeStatus]] = relationship(secondary=koppel_monumentbouwactiviteit_EAID_55585CB9_E569_47ca_9EFE_B9D5CF46BCBD) 

class Bouwstijl(Base):
    '''Trant van bouwen met bepaalde kenmerken in een bepaalde periode. In de betrokken tijdperken waren het geen levende voorstellingen; het zijn later geformuleerde (generaliserende) geschiedkundige constructies. Doelbewust komt deze tendens op sedert c. 1830. (Haslinghuis)
    '''
    __tablename__ = "bouwstijl"
    
    hoofdstijl = mapped_column(String(200))
    substijl = mapped_column(String(200))
    toelichting = mapped_column(Text)
    zuiverheid = mapped_column(String(200))
    beschermde_statusen: Mapped[List[BeschermdeStatus]] = relationship(secondary=koppel_monumentbouwstijl_EAID_144ADF26_C2E9_4080_8F4F_32F9B255E4AE) 

class Bouwtype(Base):
    '''Typering van een bouwstijl
    '''
    __tablename__ = "bouwtype"
    
    hoofdcategorie = mapped_column(String(200))
    subcategorie = mapped_column(String(200))
    toelichting = mapped_column(Text)
    beschermde_statusen: Mapped[List[BeschermdeStatus]] = relationship(secondary=koppel_monumentbouwtype_EAID_D9634EAD_2869_40a1_B243_805897E4B1B3) 

class OorspronkelijkeFunctie(Base):
    '''De functie van een object na bouw of oplevering
    '''
    __tablename__ = "oorspronkelijke_functie"
    
    functie = mapped_column(String(200))
    functiesoort = mapped_column(String(200))
    hoofdcategorie = mapped_column(String(200))
    hoofdfunctie = mapped_column(Boolean)
    subcategorie = mapped_column(String(200))
    toelichting = mapped_column(Text)
    verbijzondering = mapped_column(String(200))
    beschermde_statusen: Mapped[List[BeschermdeStatus]] = relationship(secondary=koppel_monumentfunctie_EAID_FD27EB67_1CFA_4f40_AE79_329DE9DE6754) 


