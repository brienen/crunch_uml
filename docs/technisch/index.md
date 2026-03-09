# Technisch Ontwerp

Dit deel van de documentatie beschrijft de interne architectuur, componenten en het technisch ontwerp van crunch_uml. Het is bedoeld voor ontwikkelaars die aan crunch_uml werken of het willen uitbreiden.

## Architectuurdiagram

![Architectuuroverzicht](../image/01_architectuur.drawio.svg)

## Overzicht

crunch_uml is opgebouwd als een **plugin-gebaseerde, registry-driven architectuur** met zes lagen:

1. **Presentatielaag** — CLI interface, logging, constanten
2. **Orchestratielaag** — Registry pattern en plugin framework
3. **Importlaag** — 8 parsers voor diverse invoerformaten
4. **Transformatielaag** — Copy transformer en plugin framework
5. **Exportlaag** — 22 renderers voor diverse uitvoerformaten
6. **Persistentielaag** — SQLAlchemy ORM met multi-schema ondersteuning

## Secties

| Sectie | Inhoud |
|---|---|
| [Architectuur](architectuur/index.md) | Lagenmodel, dataflows, design patterns |
| [Componenten](componenten/index.md) | Parsers, transformers, renderers, persistentie |
| [Datamodel](datamodel.md) | ORM-entiteiten, relaties en multi-schema werking |
| [Kwetsbaarheden](kwetsbaarheden.md) | Technische risico's en mitigatie |
| [Roadmap](roadmap.md) | Beoogde componenten en doorontwikkeling |
| [Technische Stack](stack.md) | Afhankelijkheden en tooling |
