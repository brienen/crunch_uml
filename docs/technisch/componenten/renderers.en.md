# Renderers (Export Layer)

Renderers generate output in diverse formats based on the stored models. They register themselves via `@RendererRegistry.register()`.

## Class Hierarchy

```mermaid
classDiagram
    class Renderer {
        <<abstract>>
        +render(args, schema)*
        +get_included_columns(args)
    }

    class ModelRenderer {
        +getModels(args, schema)
    }

    class ClassRenderer {
        +getClass(args, schema)
    }

    class JSONRenderer
    class CSVRenderer
    class I18nRenderer
    class XLSXRenderer
    class Jinja2Renderer
    class GGM_MDRenderer
    class JSON_SchemaRenderer
    class TTLRenderer
    class RDFRenderer
    class JSONLDRenderer
    class SQLARenderer
    class EARepoUpdater
    class SchemaDiffMarkdownRenderer

    Renderer <|-- ModelRenderer
    Renderer <|-- JSONRenderer
    Renderer <|-- CSVRenderer
    Renderer <|-- I18nRenderer
    Renderer <|-- XLSXRenderer
    ModelRenderer <|-- Jinja2Renderer
    ModelRenderer <|-- GGM_MDRenderer
    ModelRenderer <|-- JSON_SchemaRenderer
    Renderer <|-- TTLRenderer
    Renderer <|-- RDFRenderer
    Renderer <|-- JSONLDRenderer
    ModelRenderer <|-- SQLARenderer
    Renderer <|-- EARepoUpdater
    Renderer <|-- SchemaDiffMarkdownRenderer
```

## Overview

| Renderer | Type | File | Output Format |
|---|---|---|---|
| JSONRenderer | `json` | `pandasrenderer.py` | JSON (array of records / indexed) |
| CSVRenderer | `csv` | `pandasrenderer.py` | CSV per table |
| I18nRenderer | `i18n` | `pandasrenderer.py` | Translation JSON |
| XLSXRenderer | `xlsx` | `xlsxrenderer.py` | Excel (.xlsx) |
| Jinja2Renderer | `jinja2` | `jinja2renderer.py` | Custom template output |
| GGM_MDRenderer | `ggm_md` | `jinja2renderer.py` | Markdown (GGM format) |
| JSON_SchemaRenderer | `json_schema` | `jinja2renderer.py` | JSON Schema |
| TTLRenderer | `ttl` | `lodrenderer.py` | Turtle (RDF) |
| RDFRenderer | `rdf` | `lodrenderer.py` | RDF/XML |
| JSONLDRenderer | `jsonld` | `lodrenderer.py` | JSON-LD |
| SQLARenderer | `sqla` | `sqlarenderer.py` | Python SQLAlchemy code |
| EARepoUpdater | `ea_repo` | `earepoupdater.py` | Direct EA database update |
| SchemaDiffMD | `schema_diff_md` | `jinja2renderer.py` | Schema comparison markdown |

---

## Tabular Renderers

**JSON, CSV, XLSX** — Pandas-based export with support for:

- Column filtering via `--output_columns`
- Key renaming via `--mapper`
- Multiple record types: `RECORD_TYPE_RECORD` (array) or `RECORD_TYPE_INDEXED` (object with ID as key)

---

## Template Renderers

**Jinja2, GGM Markdown, JSON Schema** — Based on Jinja2 templates in `crunch_uml/templates/`:

| Template | Application |
|---|---|
| `ggm_markdown.j2` | Dutch government documentation |
| `json_schema.j2` | JSON Schema for validation |
| `ddas_markdown.j2` | DDAS-specific documentation |
| `ggm_sqlalchemy.j2` | SQLAlchemy model code |

HTML-to-Markdown conversion via BeautifulSoup + markdownify.

---

## Linked Data Renderers

**TTL, RDF, JSON-LD** — Via rdflib with namespace support (`--linked_data_namespace`). Generates RDF/OWL ontologies based on the stored model.

---

## EA Repo Updater

!!! warning "Destructive Operations"
    The EA Repo Updater has direct ODBC access to Enterprise Architect databases. Contains flags for dangerous operations:

    - `--ea_allow_insert` — Allow new records
    - `--ea_allow_delete` — Allow deletions

    Tag strategies: `update` | `upsert` | `replace`

---

## Schema Diff Renderer

Compares two schemas via `--compare_schema_name` and generates a markdown diff report.

---

## CLI Arguments (Export)

| Argument | Description |
|---|---|
| `-f / --outputfile` | Path to output file |
| `-t / --outputtype` | Renderer type |
| `-pi / --output_package_ids` | Filter on specific packages |
| `-jt / --output_jinja2_template` | Custom Jinja2 template |
| `-jtd` | Template directory |
| `--linked_data_namespace` | Namespace for LOD renderers |
| `--compare_schema_name` | Schema for diff comparison |

## Planned Extensions

!!! note "GraphQL Schema Renderer"
    Generate GraphQL schemas based on the stored model.

!!! note "OpenAPI Renderer"
    Generate OpenAPI/Swagger specifications for REST APIs.

## Adding a New Renderer

```python
from crunch_uml.renderers.renderer import Renderer, RendererRegistry

@RendererRegistry.register("my_format", descr="Custom output")
class MyRenderer(Renderer):
    def render(self, args, schema):
        models = schema.get_all_classes()
        # Generate output
        ...
```
