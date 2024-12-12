<div align="center">

# Crunch_UML

Crunch_UML is a tool for parsing, trasforming and exporting UML information models. It can parse XMI files originating from UML tools such as Enterprise Architect. Crunch_uml reads the XMI (and other formats) with its import routines and stores entities and relationships in a SQLAlchemy compatible database (default SQLite) for further use. After it supports transformations to different model schema's in the database, and it supports different kind of exports using its export routines.

Crunch_uml is work in progress, I use it for different projects that involve datamodels 

[![Build Status](https://github.com/brienen/crunch_uml/workflows/build/badge.svg)](https://github.com/brienen/crunch_uml/actions)
[![Coverage Status](https://coveralls.io/repos/github/brienen/crunch_uml/badge.svg?branch=main)](https://coveralls.io/github/brienen/crunch_uml?branch=main)
[![PyPi](https://img.shields.io/pypi/v/crunch_uml)](https://pypi.org/project/crunch_uml)
[![Licence](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

- Parses entities such as `Package`, `Class`, `Generalization` and `Relation` from an XMI file.
- Uses SQLAlchemy for database access and manipulation.
- Imports different input formats into the databases
- Saves all imported data to SQLAlchemy database
- Can use different schema's within the same database to hold different datamodels
- Supports Upserts to be able to import different datasets, changes to datasets etc.  
- Supports `Model Schemas` that enable storing different versions of the same model in the samen database. This way it can be used for manipulating sub-models or multi lingual daat models.
- Exports to different output formats: Excel, JSON, CSV, Jinja2 templating, Markdown

## Install and Usage

Install using pip:

```bash
pip install crunch-uml
```

and start the program like so:

```bash
crunch_uml [-h] [-v] [-d] [-db_url DATABASE_URL] [-sch] {import,transform,export} ...
```

or download repository, install packages as they are described in setup.py, got to the root of the downloaded files and start the program like so:  

```bash
python ./crunch_uml/cli.py [-h] [-v] [-d] [-db_url DATABASE_URL] [-sch] {import,transform,export} ...
```

## General Options:

- `-h, --help`: Show this help message and exit.
- `-v, --verbose`: Set log level to INFO.
- `-d, --debug`: Set log level to DEBUG.
- `-db_url DATABASE_URL, --database_url DATABASE_URL`: URL of the crunch_uml database. Supports any SQLAlchemy (https://docs.sqlalchemy.org/en/20/dialects/) compatible database. The default is `sqlite:///crunch_uml.db`.
- `-sch SCHEMA, --schema_name SCHEMA`: Name of the schema that will be used. Different models can be loaded into different schema's in the samen database. For export one schema should used.

## Commands:

- `import`: Import data to the Crunch UML database.
  - `-h, --help`: Show this help message and exit.
  - `-db_create, --database_create_new`: Create a new database and discard the existing one.
  - `-f INPUTFILE, --inputfile INPUTFILE`: Path to import file.
  - `-url URL`: URL for import
  - `-t INPUTTYPE, --inputtype INPUTTYPE`: Specifies input type from the following: ['xmi', 'eaxmi', 'json', 'xlsx', 'csv', 'i18n'].
  - `--skip_xmi_relations`: Skip parsing relations for XMI files only.
  
  **Supported Input Types**:
    - `xmi`: XMI Parser for strict XMI files. No extensions, like EA extensions, are parsed. Tested on XMI v2.1 spec.
    - `eaxmi`: XMI Parser that processes EA (Enterprise Architect) specific extensions. Tested on XMI v2.1 spec.
    - `json`: Generic parser that reads JSON files and looks for table and column definitions.
    - `xlsx`: Generic parser that reads Excel files, expecting one or more worksheets that correspond with the names of one or more tables.
    - `csv`: Generic parser that reads a single CSV file, expecting its name to be in the list of tables.
    - `i18n`: Parser that reads i18n file and stores the values in the database. Use --language to specify language. default language: 'nl'
  
  The following tables are supported: ['packages', 'classes', 'attributes', 'enumerations', 'enumerationliterals', 'associations', 'generalizations'].

- `export`: Export data from the Crunch UML database.
  - `-h, --help`: Show this help message and exit.
  - `-f OUTPUTFILE, --outputfile OUTPUTFILE`: Specify the output file.
  - `-t OUTPUTTYPE, --outputtype OUTPUTTYPE`: Specifies output type from the following: ['jinja2', 'ggm_md', 'json', 'csv', 'xlsx', 'ttl', 'rdf', 'json-ld, 'json-schema', 'earepo', 'i18n'].
  - `-pi OUTPUT_PACKAGE_IDS, --output_package_ids OUTPUT_PACKAGE_IDS`: List of package IDs separated by commas.
  - `-xpi OUTPUT_EXCLUDE_PACKAGE_IDS, --output_exclude_package_ids OUTPUT_EXCLUDE_PACKAGE_IDS`: List of package IDs to be excluded from the output, separated by commas.
  - `-jtd OUTPUT_JINJA2_TEMPLATEDIR, --output_jinja2_templatedir OUTPUT_JINJA2_TEMPLATEDIR`: Directory for Jinja2 templates.
  - `-jt OUTPUT_JINJA2_TEMPLATE, --output_jinja2_template OUTPUT_JINJA2_TEMPLATE`: Specific Jinja2 template file.
  - `-ldns LINKED_DATA_NAMESPACE, --linked_data_namespace LINKED_DATA_NAMESPACE`: Namespace for linked data renderers.
  - `-js_url JSON_SCHEMA_URL, --json_schema_url JSON_SCHEMA_URL`: URL for JSON schema that should be used for references to the schema.
  - `-vt {minor,major,none}, --version_type {minor,major,none}`: Used only for Enterprise Architect Repository Updater! After update should the version be updated? minor for minnor increments or major for major increments, None for no version update.
  - ` -ts {update,upsert,replace}, --tag_strategy {update,upsert,replace}`: Used only for Enterprise Architect Repository Updater! Defines how changing tags of Classes, Enumerations, Attributes, Literals and Packages should be updated.update for updating only existing tags, upsert for updating existing tags and adding new tags, replace for replacing all tags.
 
  **Supported Export Types**:
    - `jinja2`: Renderer using Jinja2 to render one file per model in the database, where a model refers to a package with at least one Class. Requires "output_jinja2_template" and "output_jinja2_templatedir".
    - `ggm_md`: Renderer that produces a basic markdown file per model in the database, where a model refers to a package containing at least one Class.
    - `json`: Produces a JSON document where each element relates to a table in the data model.
    - `csv`: Produces multiple CSV files, each corresponding to a table in the data model.
    - `xlsx`: Produces an Excel sheet with tabs corresponding to tables in the data model.
    - `ttl`: Renderer that renders Linked Data ontology in turtle from the supplied models, where a model is a package that includes at least one Class. Needs parameter "output_lod_url".
    - `rdf`: Renderer that renders Linked Data ontology in RDF from the supplied models, where a model is a package that includes at least one Class.  Needs parameter "output_lod_url".
    - `json-ld`: Renderer that renders Linked Data ontology in JSON-LD from the supplied models, where a model is a package that includes at least one Class. Needs parameter "output_lod_url".',
    - `json_schema`: Render JSON-Schema from a model using a base class as starting point and use outgoing associations only. Needs parameter "json_schema_url".  
    - `earepo`: Updates as Enterprise Architect v16 repository. Only updates existing Classes and attributes, Enumerations and literals, Packages and Associations. Does not add new things, updates only.provide the EA Repo through the --file parameter.
    - `i18n`: Renders a i18n file containing all tables with keys to the translatable fields: 'name', 'definitie', 'toelichting', 'alias', 'type','synoniemen','src_documentation', 'dst_documentation', Also translates to a specified language when using the --translate parameter.

- `transform`: Transfrom the datamodel from one schema to a datamodel in another schema.
  - `-sch_from`, `--schema_from`: Schema in database om het datamodel uit te lezen, standaard waarde is 'default'.
  - `-sch_to`, `--schema_to`: Schema in database om het getransformeerde datamodel naar te schrijven.
  - `-ttp`, `--transformationtype`: Geeft transformationtype aan. Beschikbare types zijn: 'copy', 'transform'.
  - `-rt_pkg`, `--root_package`: Geeft het root package dat getransformeerd moet worden.
  - `-m_gen`, `--materialize_generalizations`: Kopieert alle attributen van bovenliggende klassen naar de onderliggende klassen. Alle strings anders dan "True" worden geïnterpreteerd als False.
  - `-plug_mod`, `--plugin_file_name`: Naam (inclusief pad) van het Python-bestand dat de transformation plugin bevat die dynamisch geladen moet worden.
  - `-plug_cl`, `--plugin_class_name`: Naam van de klasse binnen de module die de transformation plugin implementeert. De klasse moet een subklasse zijn van 'crunch_uml.transformers.plugin.Plugin'.

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
- Direct access to repositories export
