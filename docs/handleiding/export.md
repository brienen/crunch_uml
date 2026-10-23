---
title: Export — UML model naar JSON, XLSX, Markdown, JSON-Schema, EA repo, …
description: >-
  Genereer output uit de crunch_uml database in vrijwel elk gangbaar formaat:
  JSON, CSV, Excel, Markdown-documentatie, JSON-Schema, OpenAPI, Linked Data
  (RDF/Turtle/JSON-LD), SQLAlchemy, en updates naar Enterprise Architect.
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
  - UML naar JSON
  - UML naar JSON-Schema
  - UML naar Markdown
  - Linked Data export
  - Enterprise Architect repository update
---

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

### Model-uitwisseling

| Type | Optie `-t` | Beschrijving |
|---|---|---|
| EA XMI | `xmi` | XMI 2.1 met Enterprise Architect-extensiesectie, inclusief diagrammen met layout. Opnieuw importeerbaar via `eaxmi` en in Sparx EA |

### Tabulaire formaten

| Type | Optie `-t` | Beschrijving |
|---|---|---|
| JSON | `json` | JSON document met alle tabellen (inclusief diagram-koppeltabellen met geometrie) |
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
| EA Repository | `earepo` | Update bestaand Enterprise Architect repository, inclusief diagram-membership en layout (`t_diagramobjects`/`t_diagramlinks`) |
| EA MIM Repository | `eamimrepo` | Update EA repository met MIM-tags |

## Opties

| Optie | Beschrijving |
|---|---|
| `-f, --outputfile` | Pad naar uitvoerbestand |
| `-t, --outputtype` | Uitvoertype (zie tabellen hierboven) |
| `-pi, --output_package_ids` | Kommagescheiden lijst van package ID's om te exporteren |
| `-xpi, --output_exclude_package_ids` | Package ID's om uit te sluiten |
| `-xpn, --output_exclude_package_names` | Kommagescheiden packagenaam-patronen (hoofdletterongevoelig, `*` en `?`) die met hun subpackages worden weggelaten; de Linked Data-renderers gebruiken standaard `Diagram,Diagrammen intern gebruik,Tekenwijze,View*`, een lege string (`""`) schakelt dit uit |
| `-jt, --output_jinja2_template` | Jinja2 template-bestand |
| `-jtd, --output_jinja2_templatedir` | Directory met Jinja2 templates |
| `-ldns, --linked_data_namespace` | Namespace voor Linked Data renderers |
| `-ldlang, --lod_language` | Taaltag voor labels, definities en toelichtingen in de Linked Data-export (standaard `nl`; `""` geeft literals zonder taaltag) |
| `-ldver, --lod_version` | Versie van het informatiemodel (`owl:versionInfo`, `owl:versionIRI`) |
| `--lod_title`, `--lod_publisher`, `--lod_license` | Titel, uitgever en licentie van het informatiemodel (`dcterms:title`, `dcterms:publisher`, `dcterms:license`) |
| `--lod_informatiedomein` | Functioneel domein van het informatiemodel (`mim:informatiedomein`) |
| `--lod_informatiemodeltype` | `conceptueel`, `logisch` (standaard) of `technisch` (`mim:informatiemodeltype`) |
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
| `--translate_backend` | Backend: `translators` (default, Google/Bing) of `ollama` (lokaal LLM). Zie [Vertalingen](vertalingen.md). |
| `--ollama_model` | Ollama model-tag (default `mistral-small3.1:24b`) |
| `--ollama_url` | URL van de Ollama-server (default `http://localhost:11434`) |
| `--ollama_timeout` | Timeout per Ollama-call in seconden (default `120`) |
| `--translate_workers` | Aantal parallelle vertaal-threads (default `8`) |
| `--translate_context` | Stuur section/field-hints in de prompt voor consistentere domeintermen |

## Voorbeelden

### EA XMI-export (round-trip)

```bash
# Compleet model inclusief diagrammen met layout als EA-compatibele XMI
crunch_uml -sch mijn_model export -t xmi -f model.xml
```

Het resultaat is opnieuw importeerbaar met `import -t eaxmi` (verliesvrij, inclusief geometrie) en importeerbaar in Sparx Enterprise Architect. De EA-specifieke keuzes zijn gedocumenteerd in `crunch_uml/renderers/EA_QUIRKS.md`.

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

Elk modelpakket (een package met minstens één klasse) wordt een `owl:Ontology` met een eigen namespace
`{namespace}{model}/`, waarin `{model}` de slug van de pakketnaam is zonder het losse woord *Model*
(`Model Kern RGBZ` → `kern-rgbz/`). Klassen krijgen `{model}/{klasse}`, attributen en associaties
`{model}/{klasse}/{naam}`. Gelijknamige associaties vanuit één klasse krijgen de doelklasse als
achtervoegsel (`project/heeft-projectlocatie`), naamloze associaties heten `{rol of relatie}-{doelklasse}`
en gelijknamige attributen krijgen hun datatype of doelklasse als achtervoegsel, zodat elke property
precies één `rdfs:range` en haar eigen `dcterms:identifier` houdt. Gelijknamige modelpakketten krijgen de
naam van het bovenliggende pakket als voorvoegsel, met een waarschuwing.

Klassen zonder stereotype (in EA-modellen technische elementen zoals `ProxyConnector`) worden
overgeslagen; datatype-klassen blijven. Packages met de namen `Diagram`, `Diagrammen intern gebruik`,
`Tekenwijze` en `View*` worden met hun subpackages standaard weggelaten; pas dit aan met
`--output_exclude_package_names` of schakel het uit met `--output_exclude_package_names ""`.

#### MIM 1.2-laag

De export volgt de normatieve transformatie van MIM 1.2 (bijlage 6.4, *Transformatie MIM – RDFS/OWL/SHACL*):
elke resource draagt naast de OWL/SHACL-typering de MIM-metaklasse en de MIM-metagegevens uit het model.

| Modelelement | OWL/SHACL | MIM |
|---|---|---|
| wortelpakket | `owl:Ontology` op de basis-URI | `mim:Informatiemodel` met `mim:mimversie "1.2"`, `mim:informatiemodeltype`, `mim:relatiemodelleringstype`, `mim:informatiedomein`, `owl:versionInfo`/`owl:versionIRI` en `dcterms:title/modified/publisher/license` uit de `--lod_*`-opties |
| overige pakketten | `owl:Ontology`, `dcterms:isPartOf` naar de ouder, `owl:imports` van ouder naar kind | `mim:Domein` |
| klasse | `owl:Class` + `sh:NodeShape` | `mim:Objecttype`; `mim:Gegevensgroeptype` (package *Groepattribuutsoort*), `mim:Relatieklasse` (`rdfs:subClassOf rdf:Statement`), `mim:Referentielijst`/`mim:Codelijst` |
| datatype-klasse (*Complex datatype*, *Union*, `is_datatype`) | alleen `sh:NodeShape`, geen `owl:Class` | `mim:GestructureerdDatatype`; de attributen `mim:DataElement`, verwijzende attributen `sh:node` |
| attribuut | `owl:DatatypeProperty`/`owl:ObjectProperty` + `sh:PropertyShape` | `mim:Attribuutsoort` (`mim:Gegevensgroep` bij een gegevensgroeptype als type, `mim:Relatiesoort` bij een objecttype als type) met `mim:type` en `mim:kardinaliteit` |
| associatie | `owl:ObjectProperty`, ook `sh:property` van de NodeShape van de bronklasse | `mim:Relatiesoort` met `mim:bron`, `mim:doel`, `mim:kardinaliteit` en `mim:kardinaliteitRelatieBron` |
| enumeratie | `owl:Class` `rdfs:subClassOf skos:Concept`, `skos:ConceptScheme`, `sh:NodeShape` | `mim:Enumeratie`; waarden `mim:Enumeratiewaarde` met de code als `skos:notation` |

De metagegevens uit de EA-tags gaan mee als `mim:herkomst`, `mim:herkomstDefinitie`, `mim:datumOpname`
(`xsd:date`), `mim:toelichting`, `mim:alias`, `mim:begrip` (ook `dct:subject`), `mim:populatie`,
`mim:kwaliteit`, `mim:authentiek` (concept uit `mim:Authenticiteit`), `mim:lengte` (met `sh:minLength`/
`sh:maxLength`), `mim:patroon`, `mim:formeelPatroon` (`sh:pattern`), de historie-indicaties,
`mim:indicatieClassificerend`, `mim:mogelijkGeenWaarde`, `mim:eenheid` en het waardebereik
(`sh:minInclusive` e.d.). Tagwaarden worden ontdaan van de `#NOTES#`-notities van de tagdefinitie en van
`<memo>`-placeholders. De kardinaliteit komt uit de multipliciteit in het model: `sh:minCount`/`sh:maxCount`
volgens MIM 6.4.9.15, waarbij `sh:minCount` vervalt als *mogelijk geen waarde* Ja is (6.4.9.18). Wat de bron
niet levert wordt niet verzonnen; alleen de MIM-defaults (indicaties `false`, kardinaliteit `1..1`,
`mim:unidirectioneel true`, `mim:aggregatietype mim:Geen`) worden uitgeschreven, en aan het eind van de
export logt crunch_uml welke verplichte metagegevens de bron niet bevat.

Valideren tegen de MIM-shapes (pyshacl, uit `dev_requirements.txt`):

```bash
python tools/validate_mim_lod.py ontologie.ttl
```

De tool toetst de export aan `test/data/mim/mim-shapes.ttl` (met `mim.ttl` als vocabulaire) en vat de
meldingen samen per shape, pad en constraint, met voorbeeld-resources; `--json` schrijft het rapport weg.

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

!!! info "Diagramlayout wordt meegeschreven"
    De `earepo`-renderer werkt ook de diagramlayout bij: bestaande rijen in `t_diagramobjects`/`t_diagramlinks` krijgen de posities en lijnverlopen uit het model, elementen die nieuw op een diagram staan worden toegevoegd, en membership die uit het model verdween wordt verwijderd. Rijen van elementtypen die crunch_uml niet beheert (zoals Notes) en van elementen die het schema niet kent blijven onaangeroerd.

### CSV-export met kolom-mapping

```bash
crunch_uml -sch mijn_model export -t csv \
    -f export/data \
    --mapper '{"name": "Naam", "definitie": "Omschrijving"}' \
    --entity_name classes
```

### i18n-export met lokale LLM (Ollama / Mistral)

```bash
crunch_uml -sch mijn_model export -t i18n \
    -f mijn_model.i18n.json \
    --language en --translate True --from_language nl \
    --translate_backend ollama \
    --ollama_model mistral-small3.1:24b \
    --translate_context
```

Voor uitgebreide uitleg (model-keuze, casing-behoud, opake tokens) zie
de aparte [Vertalingen-pagina](vertalingen.md).
