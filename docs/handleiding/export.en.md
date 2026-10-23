---
title: Export — UML model to JSON, XLSX, Markdown, JSON-Schema, EA repo, …
description: >-
  Generate output from the crunch_uml database in nearly every common
  format: JSON, CSV, Excel, Markdown documentation, JSON-Schema, OpenAPI,
  Linked Data (RDF/Turtle/JSON-LD), SQLAlchemy, and Enterprise Architect
  repository updates.
tags:
  - export
  - renderer
  - cli
  - json
  - excel
  - markdown
  - i18n
keywords:
  - crunch_uml export
  - UML to JSON
  - UML to JSON Schema
  - UML to Markdown
  - Linked Data export
  - Enterprise Architect repository update
---

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

### Model exchange

| Type | Option `-t` | Description |
|---|---|---|
| EA XMI | `xmi` | XMI 2.1 with Enterprise Architect extension section, including diagrams with layout. Re-importable via `eaxmi` and into Sparx EA |

### Tabular formats

| Type | Option `-t` | Description |
|---|---|---|
| JSON | `json` | JSON document with all tables (including diagram junction tables with geometry) |
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
| EA Repository | `earepo` | Update existing Enterprise Architect repository, including diagram membership and layout (`t_diagramobjects`/`t_diagramlinks`) |
| EA MIM Repository | `eamimrepo` | Update EA repository with MIM tags |

## Options

| Option | Description |
|---|---|
| `-f, --outputfile` | Path to output file |
| `-t, --outputtype` | Output type (see tables above) |
| `-pi, --output_package_ids` | Comma-separated list of package IDs to export |
| `-xpi, --output_exclude_package_ids` | Package IDs to exclude |
| `-xpn, --output_exclude_package_names` | Comma-separated package-name patterns (case-insensitive, `*` and `?`) excluded together with their subpackages; the Linked Data renderers default to `Diagram,Diagrammen intern gebruik,Tekenwijze,View*`, an empty string (`""`) disables this |
| `-jt, --output_jinja2_template` | Jinja2 template file |
| `-jtd, --output_jinja2_templatedir` | Directory with Jinja2 templates |
| `-ldns, --linked_data_namespace` | Namespace for Linked Data renderers |
| `-ldlang, --lod_language` | Language tag for labels, definitions and explanations in the Linked Data export (default `nl`; `""` gives literals without a tag) |
| `-ldver, --lod_version` | Version of the information model (`owl:versionInfo`, `owl:versionIRI`) |
| `--lod_title`, `--lod_publisher`, `--lod_license` | Title, publisher and licence of the information model (`dcterms:title`, `dcterms:publisher`, `dcterms:license`) |
| `--lod_informatiedomein` | Functional domain of the information model (`mim:informatiedomein`) |
| `--lod_informatiemodeltype` | `conceptueel`, `logisch` (default) or `technisch` (`mim:informatiemodeltype`) |
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
| `--translate_backend` | Backend: `translators` (default, Google/Bing) or `ollama` (local LLM). See [Translations](vertalingen.md). |
| `--ollama_model` | Ollama model tag (default `mistral-small3.1:24b`) |
| `--ollama_url` | URL of the Ollama server (default `http://localhost:11434`) |
| `--ollama_timeout` | Timeout per Ollama call in seconds (default `120`) |
| `--translate_workers` | Number of parallel translation threads (default `8`) |
| `--translate_context` | Send section/field hints in the prompt for more consistent domain terms |

## Examples

### EA XMI export (round-trip)

```bash
# Complete model including diagrams with layout as EA-compatible XMI
crunch_uml -sch my_model export -t xmi -f model.xml
```

The result can be re-imported with `import -t eaxmi` (lossless, including geometry) and imported into Sparx Enterprise Architect. The EA-specific choices are documented in `crunch_uml/renderers/EA_QUIRKS.md`.

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

Every model package (a package with at least one class) becomes an `owl:Ontology` with its own namespace
`{namespace}{model}/`, where `{model}` is the slug of the package name without the standalone word *Model*
(`Model Kern RGBZ` → `kern-rgbz/`). Classes get `{model}/{class}`, attributes and associations
`{model}/{class}/{name}`. Same-named associations from one class get the target class as suffix
(`project/heeft-projectlocatie`), nameless associations are named `{role or relatie}-{target}` and
same-named attributes get their datatype or target class as suffix, so every property keeps exactly one
`rdfs:range` and its own `dcterms:identifier`. Model packages sharing a name are prefixed with the parent
package name, with a warning.

Classes without a stereotype (technical EA elements such as `ProxyConnector`) are skipped; datatype
classes stay. Packages named `Diagram`, `Diagrammen intern gebruik`, `Tekenwijze` and `View*` are left
out with their subpackages by default; adjust this with `--output_exclude_package_names` or disable it
with `--output_exclude_package_names ""`.

#### MIM 1.2 layer

The export follows the normative transformation of MIM 1.2 (annex 6.4, *Transformatie MIM – RDFS/OWL/SHACL*):
every resource carries the MIM metaclass and the MIM metadata from the model next to its OWL/SHACL typing.

| Model element | OWL/SHACL | MIM |
|---|---|---|
| root package | `owl:Ontology` on the base URI | `mim:Informatiemodel` with `mim:mimversie "1.2"`, `mim:informatiemodeltype`, `mim:relatiemodelleringstype`, `mim:informatiedomein`, `owl:versionInfo`/`owl:versionIRI` and `dcterms:title/modified/publisher/license` from the `--lod_*` options |
| other packages | `owl:Ontology`, `dcterms:isPartOf` to the parent, `owl:imports` from parent to child | `mim:Domein` |
| class | `owl:Class` + `sh:NodeShape` | `mim:Objecttype`; `mim:Gegevensgroeptype` (package *Groepattribuutsoort*), `mim:Relatieklasse` (`rdfs:subClassOf rdf:Statement`), `mim:Referentielijst`/`mim:Codelijst` |
| datatype class (*Complex datatype*, *Union*, `is_datatype`) | `sh:NodeShape` only, no `owl:Class` | `mim:GestructureerdDatatype`; its attributes `mim:DataElement`, referring attributes `sh:node` |
| attribute | `owl:DatatypeProperty`/`owl:ObjectProperty` + `sh:PropertyShape` | `mim:Attribuutsoort` (`mim:Gegevensgroep` when typed by a gegevensgroeptype, `mim:Relatiesoort` when typed by an object type) with `mim:type` and `mim:kardinaliteit` |
| association | `owl:ObjectProperty`, also `sh:property` of the source class NodeShape | `mim:Relatiesoort` with `mim:bron`, `mim:doel`, `mim:kardinaliteit` and `mim:kardinaliteitRelatieBron` |
| enumeration | `owl:Class` `rdfs:subClassOf skos:Concept`, `skos:ConceptScheme`, `sh:NodeShape` | `mim:Enumeratie`; values `mim:Enumeratiewaarde` with the code as `skos:notation` |

The metadata from the EA tags travels as `mim:herkomst`, `mim:herkomstDefinitie`, `mim:datumOpname`
(`xsd:date`), `mim:toelichting`, `mim:alias`, `mim:begrip` (also `dct:subject`), `mim:populatie`,
`mim:kwaliteit`, `mim:authentiek` (a concept from `mim:Authenticiteit`), `mim:lengte` (with
`sh:minLength`/`sh:maxLength`), `mim:patroon`, `mim:formeelPatroon` (`sh:pattern`), the history indications,
`mim:indicatieClassificerend`, `mim:mogelijkGeenWaarde`, `mim:eenheid` and the value range
(`sh:minInclusive` etc.). Tag values are stripped of the `#NOTES#` tag-definition notes and `<memo>`
placeholders. Cardinality comes from the multiplicity in the model: `sh:minCount`/`sh:maxCount` per
MIM 6.4.9.15, where `sh:minCount` is dropped when *mogelijk geen waarde* is Ja (6.4.9.18). Nothing is
invented: only the MIM defaults (indications `false`, cardinality `1..1`, `mim:unidirectioneel true`,
`mim:aggregatietype mim:Geen`) are written, and at the end of the export crunch_uml logs which mandatory
metadata the source lacks.

Validate against the MIM shapes (pyshacl, from `dev_requirements.txt`):

```bash
python tools/validate_mim_lod.py ontology.ttl
```

The tool checks the export against `test/data/mim/mim-shapes.ttl` (with `mim.ttl` as vocabulary) and
summarises the findings per shape, path and constraint with example resources; `--json` writes the report.

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

!!! info "Diagram layout is written back"
    The `earepo` renderer also updates the diagram layout: existing rows in `t_diagramobjects`/`t_diagramlinks` receive the positions and line routings from the model, elements that are newly placed on a diagram are added, and membership that disappeared from the model is removed. Rows of element types that crunch_uml does not manage (such as Notes) and of elements unknown to the schema are left untouched.

### CSV export with column mapping

```bash
crunch_uml -sch my_model export -t csv \
    -f export/data \
    --mapper '{"name": "Name", "definition": "Description"}' \
    --entity_name classes
```

### i18n export with a local LLM (Ollama / Mistral)

```bash
crunch_uml -sch my_model export -t i18n \
    -f my_model.i18n.json \
    --language en --translate True --from_language nl \
    --translate_backend ollama \
    --ollama_model mistral-small3.1:24b \
    --translate_context
```

See the dedicated [Translations page](vertalingen.md) for the full story
(model choice, casing preservation, opaque tokens, performance numbers).
