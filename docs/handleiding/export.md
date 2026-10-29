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
| `--lod_shapes_file` | Schrijf de SHACL-shapes naar dit bestand; het uitvoerbestand bevat dan alleen de RDFS/OWL-ontologie |
| `--lod_views_dir` | Map voor de views: per diagram een deelgraaf van de ontologie (`{map}/{pad}.{ext}`) |
| `--lod_views_exclude` | Naampatronen van diagrammen en van pakketten erboven die geen view worden (standaard `Diagrammen intern gebruik,Tekenwijze,View*`; `""` sluit niets uit) |
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

Een model is een pakket met minstens één klasse of enumeratie; een pakket met alleen enumeraties (in het GGM
`Enumeratiesoort` naast een model, of `Datatypes`) krijgt dus ook een eigen bestand. Het bestand heet
`{uitvoernaam}_{pakketnaam}.md`. Komt een pakketnaam vaker voor, dan krijgen die pakketten het bovenliggende
pakket erachter, `{uitvoernaam}_Datatypes (Reden aanvraag).md`, en zo nodig nog een niveau hoger
(`Datatypes (Inkomen > Reden aanvraag)`); een unieke naam blijft zoals hij was. Het template krijgt die naam
mee als `model_name`.

### Linked Data (Turtle) exporteren

```bash
crunch_uml -sch mijn_model export -t ttl \
    -f ontologie.ttl \
    --linked_data_namespace https://example.org/model/
```

Elk modelpakket (een package met minstens één klasse of enumeratie) wordt een `owl:Ontology` met een eigen namespace
`{namespace}{pad}/`, waarin `{pad}` de pakketboom van het model volgt: de slugs van alle pakketten van de
wortel tot en met het modelpakket, zonder volgnummer en zonder het losse woord *Model*
(`99 Kern › Model BAG` → `kern/bag/`, `1 Veiligheid en Vergunningen › Model VTH` → `veiligheid-en-vergunningen/vth/`,
`99 Kern › RGBZPlus › Model RGBZ › Model Kern RGBZ` → `kern/rgbzplus/rgbz/kern-rgbz/`).
Het wortelpakket is de basis-URI zelf; een pakket met dezelfde naam als de wortel (EA's modelknoop)
en een package *Diagram* leveren geen segment, en een pakket met dezelfde naam als zijn ouder zonder
klassen (`BAG › Model BAG`, ook geschakeld: `Omgevingswet › Model Omgevingswet › Model Omgevingswet`) gaat
in die ouder op: één segment `bag/`, waarbij het diepste pakket de ouder in de hiërarchie vertegenwoordigt. Elk tussenliggend pakket is een `mim:Domein` op
`{namespace}{pad}/` (`kern/`). Klassen krijgen `{pad}/{klasse}`, attributen en associaties
`{pad}/{klasse}/{naam}`; de views gebruiken dezelfde segmenten. Gelijknamige associaties vanuit één klasse krijgen de doelklasse als
achtervoegsel (`project/heeft-projectlocatie`), naamloze associaties heten `{rol of relatie}-{doelklasse}`
en gelijknamige attributen krijgen hun datatype of doelklasse als achtervoegsel, zodat elke property
precies één `rdfs:range` en haar eigen `dcterms:identifier` houdt. Gelijknamige modelpakketten krijgen de
naam van het bovenliggende pakket als voorvoegsel, met een waarschuwing. Volgnummers waarmee pakketten in
EA op volgorde staan vallen uit het segment (`99 Kern` → `domein/kern`, `3 Economie` → `economie/`); de
`owl:versionIRI` is `{namespace}{versie}/` met de versie zoals opgegeven (`v3.0.0/`).

Technische EA-elementen (`Boundary`, `ProxyConnector`, `Text`) worden overgeslagen op hun EA-objecttype
(`object_type`, dat de `qea`- en `eaxmi`-parsers meegeven); een klasse zonder stereotype blijft dan een
klasse. Kent de bron geen objecttype, dan geldt de oude regel: klassen zonder stereotype zijn technisch,
datatype-klassen blijven. Attributen getypeerd via de classifier naar een DataType-element met de naam
van een primitief datatype (de MIM11-primitieven `CharacterString`, `Date`, `Integer`, `Boolean`, ...,
datatypen als `Bedrag` en `GUID`, GML-geometrieën als `GM_Point`) worden `owl:DatatypeProperty` met het
XSD- of GeoSPARQL-type; enumeratiewaarden met dezelfde slug (`A`, `A+`, `A++`) krijgen een volgnummer
(`a`, `a-2`, `a-3`) en witruimte aan het begin en eind van namen en definities valt uit de literals.
Packages met de namen `Diagram`, `Diagrammen intern gebruik`,
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

#### SHACL-shapes apart

Met `--lod_shapes_file shapes.ttl` schrijft de renderer de SHACL-laag naar een eigen bestand: de NodeShapes
onder `{namespace}shapes/` met alles wat erover gezegd wordt, de PropertyShapes (blank nodes) met hun
`sh:in`-lijsten, elke triple met een `sh:`-predicaat en de typering `a sh:NodeShape` (ook van
gestructureerde en eigen primitieve datatypen, die in MIM 6.4.6 zelf de NodeShape zijn). Het uitvoerbestand
bevat dan alleen de RDFS/OWL-ontologie met de MIM-metagegevens. Het shapes-bestand is een `owl:Ontology` op
`{namespace}shapes/` die de ontologie importeert (`owl:imports`); de ontologie verwijst ernaar met
`rdfs:seeAlso`. Samen zijn beide bestanden triple voor triple gelijk aan de ongesplitste export. De
extensie van het shapes-bestand volgt het uitvoertype. De validator neemt meerdere bestanden:

```bash
python tools/validate_mim_lod.py ontologie.ttl shapes.ttl
```

#### Views: deelmodellen per diagram

Met `--lod_views_dir map` schrijft de renderer per diagram in het model een *view*: een deelgraaf van de
ontologie met dezelfde IRI's en zonder SHACL. Een view bevat:

* de klassen en enumeraties op het diagram, met alles wat de ontologie erover zegt (typering, labels,
  MIM-metagegevens);
* al hun attributen en enumeratiewaarden, en de enumeraties die het type van zo'n attribuut zijn, ook als
  die niet getekend zijn; andere typen buiten het diagram blijven een verwijzing (`rdfs:range`,
  `mim:type`);
* de associaties waarvan bron én doel op het diagram staan en de generalisaties tussen klassen op het
  diagram. De view volgt de elementen op het diagram, niet de tekenwijze: een connector die in EA op het
  diagram verborgen is (*Hidden*) telt mee. Een `rdfs:subClassOf` naar een klasse buiten het diagram
  blijft weg.

Elk bestand komt op `{map}/{pad}.{ext}`, waarbij `{pad}` de pakketboom van het model volgt: de slugs van de
pakketten boven het diagram (zonder volgnummer; modelpakketten zonder het woord *Model*) en de slug van de
diagramnaam, bijvoorbeeld `kern/bag/onderzoek` voor het diagram *Onderzoek* in *99 Kern › Model BAG ›
Diagram*. Het wortelpakket, een pakket met dezelfde naam als het wortelpakket (EA's modelknoop) en het
package *Diagram* leveren geen segment. De graph-IRI van de view is `{namespace}[{versie}/]{pad}`: met
`--lod_version v3.0.0` dus `{namespace}v3.0.0/kern/bag/onderzoek`, onder de `owl:versionIRI` van het
informatiemodel en zonder botsing met term-IRI's. In Turtle staat die IRI ook als kopregel
`# graph: <...>` bovenaan het bestand, zodat een loader de named graph kan afleiden. De view beschrijft
zichzelf als `owl:Ontology` met `rdfs:label`, `dcterms:identifier` (de EA-GUID van het diagram),
`dcterms:isPartOf` het informatiemodel en `owl:versionInfo`. Zonder `--lod_version` krijgt een diagram
met dezelfde naam als een klasse in hetzelfde pakket geen eigen beschrijving, met een waarschuwing.

Diagrammen zonder klassen of enumeraties uit de ontologie (pakketdiagrammen, diagrammen met alleen
uitgesloten klassen) leveren geen view; van gelijknamige diagrammen in hetzelfde pakket wordt alleen het
eerste geschreven, met een waarschuwing. Met `--lod_views_exclude` (naampatronen van diagrammen én van
de pakketten erboven; standaard `Diagrammen intern gebruik,Tekenwijze,View*`, `""` schakelt het uit)
laat je diagrammen weg. Bestaande bestanden in de map worden overschreven; verdwenen diagrammen worden
niet opgeruimd.

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
