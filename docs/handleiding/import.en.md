# Import

The `import` command reads UML model data from a source file and stores it in the crunch_uml database.

## Basic Syntax

```bash
crunch_uml import -f <file> -t <type> [options]
```

## Supported Input Formats

| Type | Option `-t` | Description |
|---|---|---|
| XMI | `xmi` | Standard XMI 2.1 — without tool-specific extensions |
| Enterprise Architect XMI | `eaxmi` | XMI with EA-specific extensions (diagrams, tags, metadata) |
| QEA | `qea` | Enterprise Architect native repository file (.qea/.qeax) |
| JSON | `json` | JSON with table names as keys and arrays of records |
| Excel | `xlsx` | Excel file with one worksheet per table |
| CSV | `csv` | Single CSV file, mapped to one table |
| i18n | `i18n` | Translation file for multilingual models |

!!! tip "Which type to choose?"
    Working with Enterprise Architect? Use `eaxmi` — this also processes diagrams and EA-specific metadata. Use `xmi` only for XMI files from other tools.

## Options

| Option | Description |
|---|---|
| `-f, --inputfile` | Path to the input file |
| `-url` | URL for remote import (with JSON) |
| `-t, --inputtype` | Input type: `xmi`, `eaxmi`, `qea`, `json`, `xlsx`, `csv`, `i18n` |
| `-db_create` | Create a new database (deletes existing) |
| `--skip_xmi_relations` | Skip parsing relations (structure only) |
| `--mapper` | JSON string for renaming columns |
| `--update_only` | Only update existing records, don't create new ones |
| `--language` | Language for i18n import (default: `nl`) |

## Examples

### Import Enterprise Architect XMI

```bash
# Create new database and import EA XMI
crunch_uml import -f model.xmi -t eaxmi -db_create
```

### Import QEA file

```bash
crunch_uml import -f model.qea -t qea -db_create
```

### Import JSON with column mapping

```bash
crunch_uml import -f data.json -t json --mapper '{"old_name": "name", "old_def": "definition"}'
```

### Import Excel

```bash
crunch_uml import -f specification.xlsx -t xlsx -db_create
```

The Excel file must contain worksheets with names that match the tables in the data model: `packages`, `classes`, `attributes`, `enumerations`, `enumerationliterals`, `associations`, `generalizations`.

### Import into a specific schema

By default all data is loaded into the `default` schema. With `-sch` you can choose a different schema:

```bash
# Import version 1.0 into schema "v1"
crunch_uml -sch v1 import -f model_v1.xmi -t eaxmi

# Import version 2.0 into schema "v2" (same database)
crunch_uml -sch v2 import -f model_v2.xmi -t eaxmi
```

Now both versions are side by side in the same database and you can compare them.

### Import translation file

```bash
crunch_uml -sch translation_en import -f translations.json -t i18n --language en
```
