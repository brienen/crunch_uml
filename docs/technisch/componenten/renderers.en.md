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

## I18n renderer and translation backends

The `I18nRenderer` exports translatable fields to a JSON i18n file and can
optionally translate them in-flight. Two backends are available:

| Backend | Source | Speed | Quality |
| --- | --- | --- | --- |
| `translators` (default) | Google/Bing via the `translators` library | ~0.1 s per call (network) | OK for prose, weak on identifiers |
| `ollama` | Local LLM (Mistral) via Ollama | ~0.3-1 s per call (local) | Strong on domain jargon, casing preserved |

### Pipeline of `translate_data`

```mermaid
flowchart LR
    A[All entries] --> B{Existing translation?<br/>update_i18n=True}
    B -->|yes| C[Reuse from original_i18n]
    B -->|no| D[Add to to_translate set]
    D --> E[Dedup unique strings]
    E --> F[ThreadPool, 8 workers]
    F --> G[lang.translate per worker]
    G --> H{Backend?}
    H -->|translators| I[ts.translate_text]
    H -->|ollama| J[ollama_translator.translate]
    J -->|fail| I
    I --> K[Splat translations<br/>back into structure]
    J --> K
    C --> K
```

### Three passes in `I18nRenderer.translate_data`

1. **Collect** — walk through every entry, gather unique strings in a set;
   skip any string already translated in `original_i18n`.
2. **Translate in parallel** — `ThreadPoolExecutor(max_workers=8)`,
   configurable via `--translate_workers` or `CRUNCH_UML_TRANSLATE_WORKERS`.
   The GIL is released during HTTP calls, so scaling is near-linear.
3. **Rebuild** — reconstruct the output structure, filling in the
   translations from the dedup cache.

Effect: a GGM model with ~500 unique strings translates in 1-2 minutes
instead of 10+ minutes (old per-call pipeline).

### Ollama backend specifics

`crunch_uml/ollama_translator.py` wraps three deterministic safety layers
around the LLM call:

| Layer | Purpose |
| --- | --- |
| **Opaque-token preserve filter** | XML tags (`<memo>`), EAID identifiers, URLs, ISO dates and pure punctuation are returned verbatim without an LLM call. Prevents hallucination around `<memo>` and GUIDs. |
| **`num_predict` cap** | Cap on output tokens (4× input + 128, max 2048). Prevents runaway generation. |
| **`reconcile_case` safety net** | If the source is a `camelCase` / `PascalCase` / `snake_case` / `kebab-case` / `ALL_CAPS` identifier and the LLM output contains whitespace, the helper splits the output and deterministically re-cases it. |

### Fallback chain

```mermaid
flowchart TD
    A[lang.translate value] --> B{CRUNCH_UML_TRANSLATE_BACKEND=ollama?}
    B -->|no| F[translators library]
    B -->|yes| C[ollama_translator.translate]
    C -->|success| D[reconcile_case]
    D --> Z[result]
    C -->|RequestException| E[log warning]
    E --> F
    F -->|success| Z
    F -->|fail x3| G[keep source text]
    G --> Z
```

A missing Ollama server never breaks the pipeline; the external API
catches every failure.

End-user guide: see [Translations](../../handleiding/vertalingen.md).

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
