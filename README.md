<div align="center">

# Crunch-UML

Crunch_UML is a parser for XMI files originating from UML tools such as Enterprise Architect. The tool reads the XMI and stores entities and relationships in an SQLite database for further analysis or use.

**Crunch_UML is stillunder heavy development and does not have any releases.**

[![Build Status](https://github.com/brienen/crunch_uml/workflows/build/badge.svg)](https://github.com/brienen/crunch_uml/actions)
[![Coverage Status](https://coveralls.io/repos/github/brienen/crunch_uml/badge.svg?branch=main)](https://coveralls.io/github/brienen/crunch_uml?branch=main)
[![PyPi](https://img.shields.io/pypi/v/crunch_uml)](https://pypi.org/project/crunch_uml)
[![Licence](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

- Parses entities such as `Package`, `Class`, and `Relation` from an XMI file.
- Uses SQLAlchemy for database access and manipulation.
- Imports different input formats
- Saves all imported data to SQLAlchemy database
- Supports Upserts to be able to import different datasets, changes to datasets etc.  
- Exports to different output formats: Excel, JSON, CSV, Jinja2 templating, Markdown

## Install

1. Download the repository and goto root directory
2. Install packages from requirements.txt

## Usage

You can use the utility with different parameters:

```bash
python ./crunch_uml/cli.py [--opties]
```

- `-h, --help`: Toont dit hulpmenu en stopt de uitvoering.
- `-v, --verbose`: Zet logniveau op INFO.
- `-d, --debug`: Zet logniveau op DEBUG.
- `-db_create, --database_create_new`: Maak een nieuwe database en verwijder de bestaande.
- `-db_url DATABASE_URL, --database_url DATABASE_URL`: URL van de crunch_uml-database. Kan elke door [SQLAlchemy](https://docs.sqlalchemy.org/en/20/dialects/) ondersteunde database zijn. Standaard is `sqlite:///crunch_uml.db`.
- `-if INPUTFILE, --inputfile INPUTFILE`: Pad naar het XMI-bestand.
- `-it INPUTTYPE, --inputtype INPUTTYPE`: Geeft inputtype aan. Mogelijke waarden: `['xmi', 'eaxmi', 'json', 'xlsx', 'csv']`.
- `--skip_xmi_relations`: Sla het parsen van relaties over (alleen voor XMI-bestanden).
- `-of OUTPUTFILE, --outputfile OUTPUTFILE`: Output-bestand.
- `-ot OUTPUTTYPE, --outputtype OUTPUTTYPE`: Geeft outputtype aan. Mogelijke waarden: `['json', 'csv', 'xlsx', 'jinja2', 'ggm_md']`.
- `-opi OUTPUT_PACKAGE_IDS, --output_package_ids OUTPUT_PACKAGE_IDS`: Lijst van package ID's gescheiden door komma's.
- `-oxpi OUTPUT_EXCLUDE_PACKAGE_IDS, --output_exclude_package_ids OUTPUT_EXCLUDE_PACKAGE_IDS`: Lijst van package ID's die uit de uitvoer moeten worden uitgesloten, gescheiden door komma's.
- `-ojtd OUTPUT_JINJA2_TEMPLATEDIR, --output_jinja2_templatedir OUTPUT_JINJA2_TEMPLATEDIR`: Jinja2 template directory.
- `-ojt OUTPUT_JINJA2_TEMPLATE, --output_jinja2_template OUTPUT_JINJA2_TEMPLATE`: Jinja2 template.


## Development

```bash
# Get a comprehensive list of development tools
make help
```

## Future Improvements

- Expansion to other database backends such as PostgreSQL or MySQL.
- Export XMI, Turtle (Linked Data)
- Develop more Jinja2 templates
- Perform checking
- Direct access to repositories (import and export)

---

You can use this foundation and expand upon it as you continue to develop your program and add new features.