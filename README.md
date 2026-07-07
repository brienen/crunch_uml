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

## Local LLM translations via Ollama

The `i18n` exporter ships with three translation backends:

| Backend          | When to use                                       |
| ---------------- | ------------------------------------------------- |
| `translators` (default) | Quick exports, no extra setup. Uses public Google/Bing endpoints. |
| `ollama`         | Higher quality, offline, context-aware. Runs a local LLM (Mistral) via Ollama. |
| `pipeline`       | Best quality and reproducible. Layered deterministic pipeline: termbanks (IATE/EuroVoc/own LOD) + local LLMs with voting. See [the pipeline section](#deterministic-translation-pipeline) below. |

### Set up Ollama

```bash
# Install Ollama: https://ollama.com
ollama pull mistral-small3.1:24b   # ~14 GB Q4_K_M — recommended default
ollama serve                       # if not already running
```

### Activate

```bash
export CRUNCH_UML_TRANSLATE_BACKEND=ollama
export OLLAMA_NUM_PARALLEL=8       # server-side, match the worker count

crunch_uml export -t i18n -f out.json --language en --translate True --from_language nl
```

If Ollama is unreachable or returns an error the renderer transparently
falls back to the `translators` API, so adding the env-var never breaks
an existing pipeline.

### Tuning knobs

Every setting is configurable both as an environment variable **and** as a
CLI flag on `crunch_uml export`. The CLI flag wins when both are set; the
env-var wins over the baked-in default.

| Setting | CLI flag | Env-var | Default | Purpose |
| --- | --- | --- | --- | --- |
| Backend | `--translate_backend {translators,ollama}` | `CRUNCH_UML_TRANSLATE_BACKEND` | `translators` | Pick the translation engine |
| Model | `--ollama_model TAG` | `CRUNCH_UML_OLLAMA_MODEL` | `mistral-small3.1:24b` | Any Ollama tag |
| Server URL | `--ollama_url URL` | `CRUNCH_UML_OLLAMA_URL` | `http://localhost:11434` | Remote Ollama instance |
| Timeout | `--ollama_timeout SEC` | `CRUNCH_UML_OLLAMA_TIMEOUT` | `120` | Seconds per call |
| Workers | `--translate_workers N` | `CRUNCH_UML_TRANSLATE_WORKERS` | `8` | Parallel translation threads |
| Context prompt | `--translate_context` (flag) | `CRUNCH_UML_TRANSLATE_CONTEXT=1` | off | Include section/field hints in the prompt |

#### One-liner with CLI flags

```bash
crunch_uml export -t i18n -f out.json --language en --translate True \
    --from_language nl \
    --translate_backend ollama \
    --ollama_model mistral-small3.1:24b \
    --translate_workers 8 \
    --translate_context
```

### Identifier casing

Many model fields are `camelCase`, `PascalCase` or `snake_case` identifiers
rather than prose. The prompt instructs the LLM to translate the words and
rejoin them in the same style, and a deterministic post-processing step
(`reconcile_case`) repairs any leftover whitespace. So
`"aanvangAanwezigheid"` reliably comes back as `"startAttendance"` even
when the model briefly drops the camelCase shape.

### Opaque tokens are never translated

Some values have no meaningful translation and previously made the LLM
hallucinate. The Ollama backend short-circuits these patterns: the source
is returned verbatim without any model call.

* XML/HTML-like single tags: `<memo>`, `<typing>`, `</br>`, `<UML:Class>`
* EA-generated identifiers: `EAID_…`, `EAPK_…`, `EAID_attr_…`
* URLs (`http://`, `https://`, `www.…`)
* ISO dates and timestamps (`2024-05-13`, `2024-05-13T10:30:00Z`)
* Pure punctuation / numbers

### Model recommendation

| Tag                    | Size   | Speed on M4 | When                                  |
| ---------------------- | ------ | ----------- | ------------------------------------- |
| `mistral-small3.1:24b` | ~14 GB | 30-40 tok/s | **Default.** Best balance.            |
| `mistral-nemo:12b`     | ~7 GB  | 50-70 tok/s | Iteration / dev loop.                 |
| `mistral-large:123b`   | ~70 GB | 10-15 tok/s | Publication-quality batch runs.       |

## Deterministic translation pipeline

The `pipeline` backend is the recommended route for authoritative,
reproducible translations. Official EU/government terminology is the basis;
the context from the source model decides the meaning. Same input + same
sources + same (logged) model digests → same output. Full design:
[docs/technisch/vertaalpijplijn.md](docs/technisch/vertaalpijplijn.md).

The cascade, per model element (name, definition and other fields translated
together in one call, so they stay consistent):

1. **i18n file as translation memory** — existing translations per
   (section, GUID, field) are reused, never re-translated. Reviewed
   translations in the i18n file always win.
2. **Termbanks** — candidates from IATE (TBX), EuroVoc and any other Linked
   Open Data source (SKOS/RDFS/OWL, all rdflib serialisations, format
   auto-detected). An exact hit that is unambiguous after deterministic
   disambiguation (domain + source definition overlap) is taken without any
   model, concept URI logged.
3. **Local LLMs via Ollama** — two *workhorse* models translate
   independently with a binding glossary; agreement on the name accepts,
   disagreement escalates to the *heavy* model. Definitions are checked
   deterministically against the glossary instead. Hierarchical order
   (packages → classes → attributes) feeds each level's fixed name
   translations into the glossary of the level below.
4. **NMT safety net** (optional `transformers` dependency) below the LLM.
5. **Online services** (Google/Bing) only when explicitly allowed — they are
   not reproducible.

A **preflight** establishes what is available before anything is translated
and logs a compact overview (resolved model tags + digests + pull dates,
loaded termbanks with their version read from the data itself). Missing or
outdated resources produce a warning and a skipped layer — never a crash,
never silent wrong output. Model names are *prefixes*: `mistral-small`
resolves to the highest locally installed tag, so minor model upgrades need
no config change.

### Configure

```bash
export CRUNCH_UML_TRANSLATE_BACKEND=pipeline

# Termbanks: comma-separated files or directories; order = priority.
# Formats are auto-detected (.ttl/.rdf/.jsonld/... via rdflib, .tbx as IATE).
export CRUNCH_UML_TERMBANKS="resources/gemma_begrippen.ttl,resources/lod/,resources/IATE_export.tbx"

# LLM roles: first = primary workhorse (definitions), second = second vote on names.
export CRUNCH_UML_LLM_WORKHORSES="qwen2.5:14b,mistral-small3.1:24b"
export CRUNCH_UML_LLM_HEAVY="qwen2.5:32b"          # escalation model (largest you can run)

crunch_uml export -t i18n -f out.json --language en --translate True --from_language nl
```

All pipeline settings (env-var, with an equivalent CLI flag on `crunch_uml
export`):

| Env-var | Default | Purpose |
| --- | --- | --- |
| `CRUNCH_UML_TERMBANKS` | empty | Comma-separated termbank paths (files or directories); order = priority |
| `CRUNCH_UML_TERMBANK_MAX_AGE_DAYS` | off | Warn when a source's version/date is older |
| `CRUNCH_UML_LLM_WORKHORSES` | `mistral-small3.1:24b` | Comma-separated model prefixes; 1 model disables the voting layer (warning) |
| `CRUNCH_UML_LLM_HEAVY` | off | Escalation model prefix |
| `CRUNCH_UML_OLLAMA_MIN_VERSION` | off | Warn when the Ollama server is older |
| `CRUNCH_UML_NMT_MODEL` | off | Hugging Face NMT model, `{from}`/`{to}` placeholders (e.g. `Helsinki-NLP/opus-mt-{from}-{to}`) |
| `CRUNCH_UML_TRANSLATE_ALLOW_ONLINE` | `0` | `1` allows the online translators route as last resort |
| `CRUNCH_UML_TRANSLATE_SEED` | `42` | Seed for LLM calls (temperature is fixed at 0) |

### Getting the termbanks

* **IATE** — download the TBX export from
  [iate.europa.eu/download-iate](https://iate.europa.eu/download-iate) and
  point `CRUNCH_UML_TERMBANKS` at the `.tbx` file. The release date in the
  header is reported by the preflight.
* **EuroVoc** — download the SKOS distribution from
  [op.europa.eu](https://op.europa.eu/en/web/eu-vocabularies) (any RDF
  serialisation works) and add the file or its directory to the list.
* **Own vocabularies** — any SKOS/RDFS/OWL file (e.g. the
  GEMMA-begrippenkader as Turtle) drops in without code changes; labels,
  definitions and domains are queried generically.

### Degradation behaviour

| Situation | Behaviour |
| --- | --- |
| Ollama unreachable / no models | Warning; LLM layer off, termbank hits still translate, rest falls through to NMT/online/original |
| Workhorse model not installed | Warning with the exact `ollama pull` command; remaining models are used |
| Only one workhorse available | Warning; voting layer off, escalation relies on the deterministic glossary check |
| Heavy model missing | Warning; hard cases keep the primary workhorse's answer |
| Termbank missing/unreadable | Warning; source skipped, the others keep working |
| No termbank at all | Emphatic warning: terms are translated without authoritative grounding |
| Nothing available at all | Source values are kept; the count is reported in a warning |

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
