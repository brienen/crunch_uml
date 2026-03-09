# Export

The `export` command generates output from the database in the desired format.

## Basic Syntax

```bash
crunch_uml export -t <type> -f <file> [options]
```

Or from a specific schema:

```bash
crunch_uml -sch my_schema export -t <type> -f <file>
```

## Supported Output Formats

### Tabular formats

| Type | Option `-t` | Description |
|---|---|---|
| JSON | `json` | JSON document with all tables |
| CSV | `csv` | Multiple CSV files, one per table |
| Excel | `xlsx` | Excel file with tabs per table |
| i18n | `i18n` | Translation file with translatable fields |

### Documentation formats

| Type | Option `-t` | Description |
|---|---|---|
| Jinja2 | `jinja2` | Custom template-based output, one file per model |
| GGM Markdown | `ggm_md` | Markdown per model (GGM format) |
| Model Overview | `model_overview_md` | Markdown overview of all models |
| Model Statistics | `model_stats_md` | Statistics per model |
| Schema Diff | `diff_md` | Differences between two schemas |
| Plain HTML | `plain_html` | HTML output |
| ER Diagram | `er_diagram` | Entity-Relationship diagram |
| UML Mermaid | `uml_mmd` | Mermaid UML diagrams |

### Linked Data formats

| Type | Option `-t` | Description | Required |
|---|---|---|---|
| Turtle | `ttl` | RDF in Turtle syntax | `--linked_data_namespace` |
| RDF/XML | `rdf` | RDF in XML format | `--linked_data_namespace` |
| JSON-LD | `json-ld` | RDF in JSON-LD | `--linked_data_namespace` |
| ShEx | `shex` | Shape Expressions | |
| Profile | `profile` | Profile export | |

### Code generation

| Type | Option `-t` | Description |
|---|---|---|
| JSON Schema | `json_schema` | JSON Schema for data validation |
| OpenAPI | `openapi` | OpenAPI/Swagger specification |
| SQLAlchemy | `sqla` | Python SQLAlchemy model code |

### Repository updates

| Type | Option `-t` | Description |
|---|---|---|
| EA Repository | `earepo` | Update existing Enterprise Architect repository |
| EA MIM Repository | `eamimrepo` | Update EA repository with MIM tags |

## Options

| Option | Description |
|---|---|
| `-f, --outputfile` | Path to output file |
| `-t, --outputtype` | Output type (see tables above) |
| `-pi, --output_package_ids` | Comma-separated list of package IDs to export |
| `-xpi, --output_exclude_package_ids` | Package IDs to exclude |
| `-jt, --output_jinja2_template` | Jinja2 template file |
| `-jtd, --output_jinja2_templatedir` | Directory with Jinja2 templates |
| `-ldns, --linked_data_namespace` | Namespace for Linked Data renderers |
| `-js_url, --json_schema_url` | URL for JSON Schema references |
| `--mapper` | JSON string for renaming columns in output |
| `--entity_name` | Specific entity to export (with CSV) |
| `--compare_schema_name` | Schema for diff comparison |
| `--compare_title` | Title for the diff report |
| `-vt, --version_type` | Version update for EA Repo: `minor`, `major`, `none` |
| `-ts, --tag_strategy` | Tag strategy for EA Repo: `update`, `upsert`, `replace` |
| `--language` | Language for i18n export |
| `--translate` | Automatically translate to specified language |
| `--from_language` | Source language for translations (default: `nl`) |

## Examples

### Excel export

```bash
crunch_uml -sch my_model export -t xlsx -f specification.xlsx
```

### Generate Markdown documentation

```bash
crunch_uml -sch my_model export -t jinja2 \
    --output_jinja2_template ggm_markdown.j2 \
    -f docs/definition.md \
    --output_jinja2_templatedir ./templates/
```

### Export Linked Data (Turtle)

```bash
crunch_uml -sch my_model export -t ttl \
    -f ontology.ttl \
    --linked_data_namespace https://example.org/model/
```

### Schema comparison

```bash
crunch_uml -sch previous_version export -t diff_md \
    -f changes.md \
    --compare_schema_name current_version \
    --compare_title "Changes v1.0 → v2.0"
```

### Update EA Repository

```bash
crunch_uml -sch my_model export -f model.qea -t earepo \
    --tag_strategy upsert
```

!!! warning "Be careful with EA Repository updates"
    The `earepo` renderer works directly on an Enterprise Architect repository. Always make a backup before using `--tag_strategy replace`, as this replaces all existing tags.

### CSV export with column mapping

```bash
crunch_uml -sch my_model export -t csv \
    -f export/data \
    --mapper '{"name": "Name", "definition": "Description"}' \
    --entity_name classes
```
