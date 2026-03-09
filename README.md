<div align="center">

# Crunch_UML

**Bridge the gap between incompatible UML exchange formats**

Crunch_UML is a tool for parsing, transforming and exporting UML information models. UML tools like Enterprise Architect, Visual Paradigm and MagicDraw each produce their own flavour of XMI, making model exchange between tools and organisations unreliable. Crunch_UML solves this by reading models from multiple formats, storing them in a normalised database, and exporting to any target format.

[![Build Status](https://github.com/brienen/crunch_uml/workflows/build/badge.svg)](https://github.com/brienen/crunch_uml/actions)
[![Coverage Status](https://coveralls.io/repos/github/brienen/crunch_uml/badge.svg?branch=main)](https://coveralls.io/github/brienen/crunch_uml?branch=main)
[![PyPi](https://img.shields.io/pypi/v/crunch_uml)](https://pypi.org/project/crunch_uml)
[![Licence](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

```
  ┌─────────────────┐                                        ┌──────────────────┐
  │     Input       │                                        │     Output       │
  │                 │                                        │                  │
  │  XMI 2.1        │         ┌──────────────────┐           │  JSON            │
  │  EA XMI         │────────▶│   crunch_uml     │──────────▶│  Markdown        │
  │  QEA (EA native)│         │                  │           │  Excel           │
  │  JSON           │         │  Normaliseer     │           │  RDF / TTL       │
  │  Excel          │         │  Transformeer    │           │  JSON-LD         │
  │  CSV            │         │  Valideer        │           │  JSON Schema     │
  │  i18n           │         └────────┬─────────┘           │  OpenAPI         │
  │                 │                  │                     │  SQLAlchemy code │
  └─────────────────┘                  │                     │  EA Repository   │
                              ┌────────┴─────────┐           │  Schema Diff     │
                              │  crunch_uml.db   │           │  CSV             │
                              │  SQLite / PG     │           │  i18n            │
                              └──────────────────┘           └──────────────────┘
```

## Key Features

- **Multi-format import** — Reads XMI 2.1, Enterprise Architect XMI, QEA, JSON, Excel, CSV and i18n files
- **Normalised storage** — Stores all UML entities (Package, Class, Attribute, Association, Generalization, Enumeration, Diagram) in a SQLAlchemy database
- **Multi-schema support** — Load different versions or translations of the same model into separate schemas within one database, then compare or merge them
- **22 export formats** — JSON, CSV, Excel, Markdown, Jinja2 templates, RDF/TTL/JSON-LD, JSON Schema, OpenAPI, SQLAlchemy code, EA Repository update, schema diff, and more
- **Plugin architecture** — Add custom parsers, renderers or transformers without changing core code
- **Pipeline approach** — Import, transform and export are independent steps that can be combined into automated workflows
- **Upsert support** — Import different datasets or incremental changes into the same database

## Documentation

Documentation is avalailable on [GitHub Pages](https://brienen.github.io/crunch_uml)

## Install and Usage

Install using pip:

```bash
pip install crunch-uml
```

Quick start:

```bash
# Import an Enterprise Architect XMI file into a new database
crunch_uml import -f model.xmi -t eaxmi -db_create

# Copy a sub-model to a named schema
crunch_uml transform -ttp copy -sch_to my_model -rt_pkg EAPK_12345

# Export to Excel
crunch_uml -sch my_model export -t xlsx -f model.xlsx
```

Or clone the repository:

```bash
git clone https://github.com/brienen/crunch_uml.git
cd crunch_uml
pip install -e .
```

## General Options

```bash
crunch_uml [-h] [-v] [-d] [-w] [-db_url DATABASE_URL] [-sch SCHEMA] {import,transform,export} ...
```

| Option | Description |
|---|---|
| `-h, --help` | Show help message and exit |
| `-v, --verbose` | Set log level to INFO |
| `-d, --debug` | Set log level to DEBUG |
| `-w, --do_not_suppress_warnings` | Do not suppress warnings |
| `-db_url DATABASE_URL` | Database URL. Supports any [SQLAlchemy dialect](https://docs.sqlalchemy.org/en/20/dialects/). Default: `sqlite:///crunch_uml.db` |
| `-sch SCHEMA` | Schema name. Different models can be loaded into different schemas in the same database |

## Commands

### import

Import data into the Crunch UML database.

```bash
crunch_uml import -f <file> -t <type> [options]
```

| Option | Description |
|---|---|
| `-db_create` | Create a new database, discarding the existing one |
| `-f, --inputfile` | Path to import file |
| `-url` | URL for remote import (JSON) |
| `-t, --inputtype` | Input type (see table below) |
| `--skip_xmi_relations` | Skip parsing relations (XMI only) |
| `--mapper` | JSON string for column renaming: `'{"old": "new"}'` |
| `--update_only` | Only update existing records, do not create new ones |
| `--language` | Language for i18n import (default: `nl`) |

**Supported Input Types:**

| Type | Description |
|---|---|
| `xmi` | Standard XMI 2.1 parser (no tool-specific extensions) |
| `eaxmi` | Enterprise Architect XMI parser with EA-specific extensions |
| `qea` | Enterprise Architect native repository file (.qea/.qeax) |
| `json` | JSON with table names as keys and arrays of records |
| `xlsx` | Excel with worksheets corresponding to table names |
| `csv` | Single CSV file mapped to one table |
| `i18n` | Translation file for multilingual models |

Supported tables: `packages`, `classes`, `attributes`, `enumerations`, `enumerationliterals`, `associations`, `generalizations`.

### transform

Transform a model from one schema to another within the database.

```bash
crunch_uml transform -ttp <type> -sch_to <target_schema> [options]
```

| Option | Description |
|---|---|
| `-sch_from` | Source schema (default: `default`) |
| `-sch_to` | Target schema |
| `-sch_to_cln` | Clean target schema before writing |
| `-ttp` | Transformation type: `copy` or `plugin` |
| `-rt_pkg` | Root package ID to transform |
| `-m_gen` | Materialise generalisations: copy parent attributes to children (`True`/`False`) |
| `-plug_mod` | Path to plugin Python file |
| `-plug_cl` | Plugin class name (must extend `crunch_uml.transformers.plugin.Plugin`) |

### export

Export data from the Crunch UML database.

```bash
crunch_uml [-sch SCHEMA] export -t <type> -f <file> [options]
```

| Option | Description |
|---|---|
| `-f, --outputfile` | Output file path |
| `-t, --outputtype` | Output type (see table below) |
| `-pi` | Comma-separated list of package IDs to include |
| `-xpi` | Comma-separated list of package IDs to exclude |
| `-jt` | Jinja2 template file |
| `-jtd` | Jinja2 template directory |
| `-ldns` | Namespace for Linked Data renderers |
| `-js_url` | URL for JSON Schema references |
| `-vt` | EA Repo version update: `minor`, `major`, `none` |
| `-ts` | EA Repo tag strategy: `update`, `upsert`, `replace` |
| `--mapper` | JSON string for column renaming |
| `--entity_name` | Specific entity to export (for CSV) |
| `--compare_schema_name` | Schema for diff comparison |
| `--compare_title` | Title for diff report |
| `--language` | Language for i18n export |
| `--translate` | Auto-translate to specified language |
| `--from_language` | Source language (default: `nl`) |

**Supported Export Types:**

| Type | Description |
|---|---|
| `json` | JSON document with all tables |
| `csv` | Multiple CSV files, one per table |
| `xlsx` | Excel with tabs per table |
| `i18n` | Translation file with translatable fields |
| `jinja2` | Custom Jinja2 template output (one file per model). Requires `-jt` and `-jtd` |
| `ggm_md` | Markdown per model (GGM format) |
| `model_overview_md` | Markdown overview of all models |
| `model_stats_md` | Model statistics in markdown |
| `diff_md` | Schema diff report in markdown. Requires `--compare_schema_name` |
| `plain_html` | HTML output |
| `er_diagram` | Entity-Relationship diagram |
| `uml_mmd` | Mermaid UML diagrams |
| `ttl` | RDF in Turtle syntax. Requires `-ldns` |
| `rdf` | RDF/XML. Requires `-ldns` |
| `json-ld` | JSON-LD. Requires `-ldns` |
| `shex` | Shape Expressions |
| `profile` | Profile export |
| `json_schema` | JSON Schema for data validation. Requires `-js_url` |
| `openapi` | OpenAPI / Swagger specification |
| `sqla` | Python SQLAlchemy model code |
| `earepo` | Update existing EA v16 repository |
| `eamimrepo` | Update EA repository with MIM tags |

## Multi-Schema: Version Comparison & Translations

One of the most powerful features is multi-schema support. Import the same model multiple times into different schemas to compare versions or create translations:

```bash
# Import version 2.0
crunch_uml import -f model_v2.xmi -t eaxmi -db_create
crunch_uml transform -ttp copy -sch_to v2 -rt_pkg ROOT_ID

# Import version 1.0 into a separate schema
crunch_uml -sch v1_raw import -f model_v1.xmi -t eaxmi
crunch_uml transform -ttp copy -sch_from v1_raw -sch_to v1 -rt_pkg ROOT_ID

# Generate a diff report
crunch_uml -sch v1 export -t diff_md -f changes.md \
    --compare_schema_name v2 --compare_title "Changes v1 → v2"
```

## Development

```bash
# Get a comprehensive list of development tools
make help
```

## Documentation

Full documentation (including architecture, examples and technical design) is available via MkDocs:

```bash
pip install mkdocs-material mkdocs-glightbox
mkdocs serve
```

## Future Improvements

- Caching & validation engine for large models
- Streaming/chunked parsing for large files
- REST API interface (FastAPI)
- AI-based semantic indexing
- Snowflake and Azure database connectors

## License

[MIT](LICENSE)
