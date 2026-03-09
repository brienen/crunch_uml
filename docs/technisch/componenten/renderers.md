# Renderers (Exportlaag)

Renderers genereren output in diverse formaten op basis van de opgeslagen modellen. Ze registreren zich via `@RendererRegistry.register()`.

## Klasse-hiërarchie

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

## Overzicht

| Renderer | Type | Bestand | Outputformaat |
|---|---|---|---|
| JSONRenderer | `json` | `pandasrenderer.py` | JSON (array of records / indexed) |
| CSVRenderer | `csv` | `pandasrenderer.py` | CSV per tabel |
| I18nRenderer | `i18n` | `pandasrenderer.py` | Vertaal-JSON |
| XLSXRenderer | `xlsx` | `xlsxrenderer.py` | Excel (.xlsx) |
| Jinja2Renderer | `jinja2` | `jinja2renderer.py` | Custom template output |
| GGM_MDRenderer | `ggm_md` | `jinja2renderer.py` | Markdown (GGM-formaat) |
| JSON_SchemaRenderer | `json_schema` | `jinja2renderer.py` | JSON Schema |
| TTLRenderer | `ttl` | `lodrenderer.py` | Turtle (RDF) |
| RDFRenderer | `rdf` | `lodrenderer.py` | RDF/XML |
| JSONLDRenderer | `jsonld` | `lodrenderer.py` | JSON-LD |
| SQLARenderer | `sqla` | `sqlarenderer.py` | Python SQLAlchemy code |
| EARepoUpdater | `ea_repo` | `earepoupdater.py` | Direct EA database update |
| SchemaDiffMD | `schema_diff_md` | `jinja2renderer.py` | Schema-vergelijking markdown |

---

## Tabulaire Renderers

**JSON, CSV, XLSX** — Pandas-gebaseerde export met ondersteuning voor:

- Column filtering via `--output_columns`
- Key renaming via `--mapper`
- Meerdere record-types: `RECORD_TYPE_RECORD` (array) of `RECORD_TYPE_INDEXED` (object met ID als key)

---

## Template Renderers

**Jinja2, GGM Markdown, JSON Schema** — Gebaseerd op Jinja2 templates in `crunch_uml/templates/`:

| Template | Toepassing |
|---|---|
| `ggm_markdown.j2` | Nederlandse overheids-documentatie |
| `json_schema.j2` | JSON Schema voor validatie |
| `ddas_markdown.j2` | DDAS-specifieke documentatie |
| `ggm_sqlalchemy.j2` | SQLAlchemy modelcode |

HTML-to-Markdown conversie via BeautifulSoup + markdownify.

---

## Linked Data Renderers

**TTL, RDF, JSON-LD** — Via rdflib met namespace-ondersteuning (`--linked_data_namespace`). Genereert RDF/OWL ontologieën op basis van het opgeslagen model.

---

## EA Repo Updater

!!! warning "Destructieve operaties"
    De EA Repo Updater heeft directe ODBC-toegang tot Enterprise Architect databases. Bevat flags voor gevaarlijke operaties:

    - `--ea_allow_insert` — Toestaan van nieuwe records
    - `--ea_allow_delete` — Toestaan van verwijderingen

    Tag-strategieën: `update` | `upsert` | `replace`

---

## Schema Diff Renderer

Vergelijkt twee schema's via `--compare_schema_name` en genereert een markdown diff-rapport.

---

## CLI-argumenten (Export)

| Argument | Beschrijving |
|---|---|
| `-f / --outputfile` | Pad naar uitvoerbestand |
| `-t / --outputtype` | Type renderer |
| `-pi / --output_package_ids` | Filter op specifieke packages |
| `-jt / --output_jinja2_template` | Custom Jinja2 template |
| `-jtd` | Template directory |
| `--linked_data_namespace` | Namespace voor LOD renderers |
| `--compare_schema_name` | Schema voor diff-vergelijking |

## Beoogde uitbreidingen

!!! note "GraphQL Schema Renderer"
    Genereer GraphQL schema's op basis van het opgeslagen model.

!!! note "OpenAPI Renderer"
    Genereer OpenAPI/Swagger specificaties voor REST API's.

## Een nieuwe renderer toevoegen

```python
from crunch_uml.renderers.renderer import Renderer, RendererRegistry

@RendererRegistry.register("mijn_formaat", descr="Custom output")
class MijnRenderer(Renderer):
    def render(self, args, schema):
        models = schema.get_all_classes()
        # Genereer output
        ...
```
