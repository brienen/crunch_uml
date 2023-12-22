from __future__ import annotations
from typing import List, Optional
from enum import Enum
from sqlalchemy import Integer, String, Date, Boolean, Text, Enum as SAEnum, Column, Table, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship, mapped_column, Mapped


class Base(DeclarativeBase):
    id = mapped_column(Integer, primary_key=True)



# Enumeraries

class Onderwijstype(Enum):
  VMBO_T = 1
  VMBO_K = 2
  VMBO_B = 3
  HAVO = 4
  VWO = 5




# Koppeltabellen

koppel_kent_EAID_FA07FA3D_3EC3_450e_8FE0_766875D7CC5F = Table(
    "koppel_kent_EAID_FA07FA3D_3EC3_450e_8FE0_766875D7CC5F",
    Base.metadata,
    Column("left_id", ForeignKey("school.id"), primary_key=True),
    Column("right_id", ForeignKey("onderwijsloopbaan.id"), primary_key=True),
)
koppel_heeft_EAID_CED5C094_5222_4347_9FE1_7D5B2DECA3DD = Table(
    "koppel_heeft_EAID_CED5C094_5222_4347_9FE1_7D5B2DECA3DD",
    Base.metadata,
    Column("left_id", ForeignKey("school.id"), primary_key=True),
    Column("right_id", ForeignKey("onderwijssoort.id"), primary_key=True),
)



# Classes
class Inschrijving(Base):
    '''<Geen Definities>
    '''
    __tablename__ = "inschrijving"
    
    datum = mapped_column(String)
    school_id: Mapped[int] = mapped_column(ForeignKey("school.id"), index=True, nullable=False)
    school: Mapped[School] = relationship(back_populates="inschrijvingen")
    leerling_id: Mapped[int] = mapped_column(ForeignKey("leerling.id"), index=True, nullable=False)
    leerling: Mapped[Leerling] = relationship(back_populates="inschrijvingen") 

class Leerjaar(Base):
    '''<Geen Definities>
    '''
    __tablename__ = "leerjaar"
    
    eindjaar = mapped_column(Integer)
    startjaar = mapped_column(Integer) 

class Leerling(Base):
    '''<Geen Definities>
    '''
    __tablename__ = "leerling"
    
    kwetsbarejongere = mapped_column(Boolean)
    inschrijvingen: Mapped[List[Inschrijving]] = relationship(back_populates="leerling")
    startkwalificatie: Mapped[Startkwalificatie] = relationship(back_populates="leerling")
    onderwijsloopbaanen: Mapped[List[Onderwijsloopbaan]] = relationship(back_populates="leerling")
    uitschrijvingen: Mapped[List[Uitschrijving]] = relationship(back_populates="leerling") 

class Locatie(Base):
    '''<Geen Definities>
    '''
    __tablename__ = "locatie"
    
    adres = mapped_column(String)
    school_id: Mapped[Optional[int]] = mapped_column(ForeignKey("school.id"), index=True, nullable=True)
    school: Mapped[School] = relationship(back_populates="locaties") 

class Loopbaanstap(Base):
    '''<Geen Definities>
    '''
    __tablename__ = "loopbaanstap"
    
    klas = mapped_column(Integer)
    onderwijstype = mapped_column(SAEnum(Onderwijstype))
    schooljaar = mapped_column(String)
    onderwijsloopbaan_id: Mapped[int] = mapped_column(ForeignKey("onderwijsloopbaan.id"), index=True, nullable=False)
    onderwijsloopbaan: Mapped[Onderwijsloopbaan] = relationship(back_populates="loopbaanstapen") 

class Onderwijsloopbaan(Base):
    '''<Geen Definities>
    '''
    __tablename__ = "onderwijsloopbaan"
    
    loopbaanstapen: Mapped[List[Loopbaanstap]] = relationship(back_populates="onderwijsloopbaan")
    leerling_id: Mapped[int] = mapped_column(ForeignKey("leerling.id"), index=True, nullable=False)
    leerling: Mapped[Leerling] = relationship(back_populates="onderwijsloopbaanen")
    schoolen: Mapped[List[School]] = relationship(secondary=koppel_kent_EAID_FA07FA3D_3EC3_450e_8FE0_766875D7CC5F) 

class Onderwijsniveau(Base):
    '''<Geen Definities>
    '''
    __tablename__ = "onderwijsniveau"
     

class Onderwijssoort(Base):
    '''<Geen Definities>
    '''
    __tablename__ = "onderwijssoort"
    
    omschrijving = mapped_column(String(80))
    onderwijstype = mapped_column(SAEnum(Onderwijstype))
    schoolen: Mapped[List[School]] = relationship(secondary=koppel_heeft_EAID_CED5C094_5222_4347_9FE1_7D5B2DECA3DD) 

class OuderOfVerzorger(Base):
    '''<Geen Definities>
    '''
    __tablename__ = "ouder_of_verzorger"
     

class School(Base):
    '''<Geen Definities>
    '''
    __tablename__ = "school"
    
    naam = mapped_column(String(200))
    locaties: Mapped[List[Locatie]] = relationship(back_populates="school")
    onderwijsloopbaanen: Mapped[List[Onderwijsloopbaan]] = relationship(secondary=koppel_kent_EAID_FA07FA3D_3EC3_450e_8FE0_766875D7CC5F)
    onderwijssoorten: Mapped[List[Onderwijssoort]] = relationship(secondary=koppel_heeft_EAID_CED5C094_5222_4347_9FE1_7D5B2DECA3DD)
    uitschrijvingen: Mapped[List[Uitschrijving]] = relationship(back_populates="school")
    inschrijvingen: Mapped[List[Inschrijving]] = relationship(back_populates="school") 

class Startkwalificatie(Base):
    '''<Geen Definities>
    '''
    __tablename__ = "startkwalificatie"
    
    datumbehaald = mapped_column(String)
    leerling_id: Mapped[int] = mapped_column(ForeignKey("leerling.id"), index=True, nullable=False)
    leerling: Mapped[Leerling] = relationship(back_populates="startkwalificatie") 

class Uitschrijving(Base):
    '''<Geen Definities>
    '''
    __tablename__ = "uitschrijving"
    
    datum = mapped_column(String)
    diplomabehaald = mapped_column(Boolean)
    leerling_id: Mapped[int] = mapped_column(ForeignKey("leerling.id"), index=True, nullable=False)
    leerling: Mapped[Leerling] = relationship(back_populates="uitschrijvingen")
    school_id: Mapped[int] = mapped_column(ForeignKey("school.id"), index=True, nullable=False)
    school: Mapped[School] = relationship(back_populates="uitschrijvingen") 


