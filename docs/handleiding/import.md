# Import

Het `import`-commando leest UML-modeldata uit een bronbestand en slaat het op in de crunch_uml database.

## Basissyntax

```bash
crunch_uml import -f <bestand> -t <type> [opties]
```

## Ondersteunde invoerformaten

| Type | Optie `-t` | Beschrijving |
|---|---|---|
| XMI | `xmi` | Standaard XMI 2.1 — zonder tool-specifieke extensies |
| Enterprise Architect XMI | `eaxmi` | XMI met EA-specifieke extensies (diagrammen, tags, metadata) |
| QEA | `qea` | Enterprise Architect native repository-bestand (.qea/.qeax) |
| JSON | `json` | JSON met tabelnamen als keys en arrays van records |
| Excel | `xlsx` | Excel-bestand met één worksheet per tabel |
| CSV | `csv` | Enkel CSV-bestand, gekoppeld aan één tabel |
| i18n | `i18n` | Vertaalbestand voor meertalige modellen |

!!! tip "Welk type kiezen?"
    Werk je met Enterprise Architect? Gebruik dan `eaxmi` — dit verwerkt ook diagrammen en EA-specifieke metadata. Gebruik `xmi` alleen voor XMI-bestanden uit andere tools.

## Opties

| Optie | Beschrijving |
|---|---|
| `-f, --inputfile` | Pad naar het invoerbestand |
| `-url` | URL voor remote import (bij JSON) |
| `-t, --inputtype` | Invoertype: `xmi`, `eaxmi`, `qea`, `json`, `xlsx`, `csv`, `i18n` |
| `-db_create` | Maak een nieuwe database aan (verwijdert bestaande) |
| `--skip_xmi_relations` | Sla het parsen van relaties over (alleen structuur) |
| `--mapper` | JSON-string voor het hernoemen van kolommen |
| `--update_only` | Alleen bestaande records bijwerken, geen nieuwe aanmaken |
| `--language` | Taal voor i18n-import (standaard: `nl`) |

## Voorbeelden

### Enterprise Architect XMI importeren

```bash
# Nieuwe database aanmaken en EA XMI importeren
crunch_uml import -f model.xmi -t eaxmi -db_create
```

### QEA-bestand importeren

```bash
crunch_uml import -f model.qea -t qea -db_create
```

### JSON importeren met kolom-mapping

```bash
crunch_uml import -f data.json -t json --mapper '{"old_name": "name", "old_def": "definitie"}'
```

### Excel importeren

```bash
crunch_uml import -f specificatie.xlsx -t xlsx -db_create
```

Het Excel-bestand moet worksheets bevatten met namen die overeenkomen met de tabellen in het datamodel: `packages`, `classes`, `attributes`, `enumerations`, `enumerationliterals`, `associations`, `generalizations`.

### Import in een specifiek schema

Standaard worden alle data in het `default`-schema geladen. Met `-sch` kun je een ander schema kiezen:

```bash
# Versie 1.0 importeren in schema "v1"
crunch_uml -sch v1 import -f model_v1.xmi -t eaxmi

# Versie 2.0 importeren in schema "v2" (zelfde database)
crunch_uml -sch v2 import -f model_v2.xmi -t eaxmi
```

Nu staan beide versies naast elkaar in dezelfde database en kun je ze vergelijken.

### Vertaalbestand importeren

```bash
crunch_uml -sch vertaling_en import -f translations.json -t i18n --language en
```
