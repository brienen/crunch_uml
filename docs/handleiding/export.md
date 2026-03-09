# Export

Het `export`-commando genereert output vanuit de database in het gewenste formaat.

## Basissyntax

```bash
crunch_uml export -t <type> -f <bestand> [opties]
```

Of vanuit een specifiek schema:

```bash
crunch_uml -sch mijn_schema export -t <type> -f <bestand>
```

## Ondersteunde uitvoerformaten

### Tabulaire formaten

| Type | Optie `-t` | Beschrijving |
|---|---|---|
| JSON | `json` | JSON document met alle tabellen |
| CSV | `csv` | Meerdere CSV-bestanden, één per tabel |
| Excel | `xlsx` | Excel-bestand met tabs per tabel |
| i18n | `i18n` | Vertaalbestand met vertaalbare velden |

### Documentatie-formaten

| Type | Optie `-t` | Beschrijving |
|---|---|---|
| Jinja2 | `jinja2` | Custom template-gebaseerde output, één bestand per model |
| GGM Markdown | `ggm_md` | Markdown per model (GGM-formaat) |
| Model Overview | `model_overview_md` | Markdown overzicht van alle modellen |
| Model Statistics | `model_stats_md` | Statistieken per model |
| Schema Diff | `diff_md` | Verschillen tussen twee schema's |
| Plain HTML | `plain_html` | HTML output |
| ER Diagram | `er_diagram` | Entity-Relationship diagram |
| UML Mermaid | `uml_mmd` | Mermaid UML-diagrammen |

### Linked Data formaten

| Type | Optie `-t` | Beschrijving | Vereist |
|---|---|---|---|
| Turtle | `ttl` | RDF in Turtle-syntax | `--linked_data_namespace` |
| RDF/XML | `rdf` | RDF in XML-formaat | `--linked_data_namespace` |
| JSON-LD | `json-ld` | RDF in JSON-LD | `--linked_data_namespace` |
| ShEx | `shex` | Shape Expressions | |
| Profile | `profile` | Profiel-export | |

### Code-generatie

| Type | Optie `-t` | Beschrijving |
|---|---|---|
| JSON Schema | `json_schema` | JSON Schema voor datavalidatie |
| OpenAPI | `openapi` | OpenAPI/Swagger specificatie |
| SQLAlchemy | `sqla` | Python SQLAlchemy modelcode |

### Repository-updates

| Type | Optie `-t` | Beschrijving |
|---|---|---|
| EA Repository | `earepo` | Update bestaand Enterprise Architect repository |
| EA MIM Repository | `eamimrepo` | Update EA repository met MIM-tags |

## Opties

| Optie | Beschrijving |
|---|---|
| `-f, --outputfile` | Pad naar uitvoerbestand |
| `-t, --outputtype` | Uitvoertype (zie tabellen hierboven) |
| `-pi, --output_package_ids` | Kommagescheiden lijst van package ID's om te exporteren |
| `-xpi, --output_exclude_package_ids` | Package ID's om uit te sluiten |
| `-jt, --output_jinja2_template` | Jinja2 template-bestand |
| `-jtd, --output_jinja2_templatedir` | Directory met Jinja2 templates |
| `-ldns, --linked_data_namespace` | Namespace voor Linked Data renderers |
| `-js_url, --json_schema_url` | URL voor JSON Schema referenties |
| `--mapper` | JSON-string voor het hernoemen van kolommen in output |
| `--entity_name` | Specifieke entiteit om te exporteren (bij CSV) |
| `--compare_schema_name` | Schema voor diff-vergelijking |
| `--compare_title` | Titel voor het diff-rapport |
| `-vt, --version_type` | Versie-update voor EA Repo: `minor`, `major`, `none` |
| `-ts, --tag_strategy` | Tag-strategie voor EA Repo: `update`, `upsert`, `replace` |
| `--language` | Taal voor i18n export |
| `--translate` | Vertaal automatisch naar opgegeven taal |
| `--from_language` | Brontaal voor vertalingen (standaard: `nl`) |

## Voorbeelden

### Excel-export

```bash
crunch_uml -sch mijn_model export -t xlsx -f specificatie.xlsx
```

### Markdown-documentatie genereren

```bash
crunch_uml -sch mijn_model export -t jinja2 \
    --output_jinja2_template ggm_markdown.j2 \
    -f docs/definitie.md \
    --output_jinja2_templatedir ./templates/
```

### Linked Data (Turtle) exporteren

```bash
crunch_uml -sch mijn_model export -t ttl \
    -f ontologie.ttl \
    --linked_data_namespace https://example.org/model/
```

### Schema-vergelijking

```bash
crunch_uml -sch vorige_versie export -t diff_md \
    -f wijzigingen.md \
    --compare_schema_name huidige_versie \
    --compare_title "Wijzigingen v1.0 → v2.0"
```

### EA Repository bijwerken

```bash
crunch_uml -sch mijn_model export -f model.qea -t earepo \
    --tag_strategy upsert
```

!!! warning "Let op bij EA Repository updates"
    De `earepo`-renderer werkt direct op een Enterprise Architect repository. Maak altijd een backup voordat je `--tag_strategy replace` gebruikt, want dit vervangt alle bestaande tags.

### CSV-export met kolom-mapping

```bash
crunch_uml -sch mijn_model export -t csv \
    -f export/data \
    --mapper '{"name": "Naam", "definitie": "Omschrijving"}' \
    --entity_name classes
```
