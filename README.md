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

```bash
cli.py [-h] [-v] [-d] [-db_url DATABASE_URL] {import,export} ...
```

### General Options:

- `-h, --help`: Show this help message and exit.
- `-v, --verbose`: Set log level to INFO.
- `-d, --debug`: Set log level to DEBUG.
- `-db_url DATABASE_URL, --database_url DATABASE_URL`: URL of the crunch_uml database. Supports any SQLAlchemy (https://docs.sqlalchemy.org/en/20/dialects/) compatible database. The default is `sqlite:///crunch_uml.db`.

### Commands:

- `import`: Import data to the Crunch UML database.
  - `-h, --help`: Show this help message and exit.
  - `-db_create, --database_create_new`: Create a new database and discard the existing one.
  - `-f INPUTFILE, --inputfile INPUTFILE`: Path to the XMI file.
  - `-t INPUTTYPE, --inputtype INPUTTYPE`: Specifies input type from the following: ['xmi', 'eaxmi', 'json', 'xlsx', 'csv'].
  - `--skip_xmi_relations`: Skip parsing relations for XMI files only.
  
  **Supported Input Types**:
    - `xmi"`: XMI Parser for strict XMI files. No extensions, like EA extensions, are parsed. Tested on XMI v2.1 spec.
    - `eaxmi"`: XMI Parser that processes EA (Enterprise Architect) specific extensions. Tested on XMI v2.1 spec.
    - `json"`: Generic parser that reads JSON files and looks for table and column definitions.
    - `xlsx"`: Generic parser that reads Excel files, expecting one or more worksheets that correspond with the names of one or more tables.
    - `csv"`: Generic parser that reads a single CSV file, expecting its name to be in the list of tables.
  
  The following tables are supported: ['packages', 'classes', 'attributes', 'enumerations', 'enumerationliterals', 'associations', 'generalizations'].

- `export`: Export data from the Crunch UML database.
  - `-h, --help`: Show this help message and exit.
  - `-f OUTPUTFILE, --outputfile OUTPUTFILE`: Specify the output file.
  - `-t OUTPUTTYPE, --outputtype OUTPUTTYPE`: Specifies output type from the following: ['jinja2', 'ggm_md', 'json', 'csv', 'xlsx'].
  - `-pi OUTPUT_PACKAGE_IDS, --output_package_ids OUTPUT_PACKAGE_IDS`: List of package IDs separated by commas.
  - `-xpi OUTPUT_EXCLUDE_PACKAGE_IDS, --output_exclude_package_ids OUTPUT_EXCLUDE_PACKAGE_IDS`: List of package IDs to be excluded from the output, separated by commas.
  - `-jtd OUTPUT_JINJA2_TEMPLATEDIR, --output_jinja2_templatedir OUTPUT_JINJA2_TEMPLATEDIR`: Directory for Jinja2 templates.
  - `-jt OUTPUT_JINJA2_TEMPLATE, --output_jinja2_template OUTPUT_JINJA2_TEMPLATE`: Specific Jinja2 template file.
  
  **Supported Export Types**:
    - `jinja2"`: Renderer using Jinja2 to render one file per model in the database, where a model refers to a package with at least one Class. Requires "output_jinja2_template" and "output_jinja2_templatedir".
    - `ggm_md"`: Renderer that produces a basic markdown file per model in the database, where a model refers to a package containing at least one Class.
    - `json"`: Produces a JSON document where each element relates to a table in the data model.
    - `csv"`: Produces multiple CSV files, each corresponding to a table in the data model.
    - `xlsx"`: Produces an Excel sheet with tabs corresponding to tables in the data model.


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