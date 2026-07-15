# Import

The `import` command reads UML model data from a source file and stores it in the crunch_uml database.

## Basic Syntax

```bash
crunch_uml import -f <file> -t <type> [options]
```

## Supported Input Formats

| Type | Option `-t` | Description |
|---|---|---|
| XMI | `xmi` | Standard XMI 2.1 — without tool-specific extensions and without diagrams |
| Enterprise Architect XMI | `eaxmi` | XMI with EA-specific extensions (diagrams including layout, tags, metadata) |
| QEA | `qea` | Enterprise Architect native repository file (.qea/.qeax), including diagrams with layout |
| JSON | `json` | JSON with table names as keys and arrays of records |
| Excel | `xlsx` | Excel file with one worksheet per table |
| CSV | `csv` | Single CSV file, mapped to one table |
| i18n | `i18n` | Translation file for multilingual models |

!!! tip "Which type to choose?"
    Working with Enterprise Architect? Use `eaxmi` — this also processes diagrams and EA-specific metadata. Use `xmi` only for XMI files from other tools.

!!! info "Diagrams with geometry"
    The `eaxmi` and `qea` parsers read diagrams in full: which elements appear on a diagram **and** their layout (positions, sizes, stacking order and the routing of relationship lines). The geometry is stored in a canonical coordinate system; see the [data model](../technisch/datamodel.md) for the details and the coverage matrix.

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

The Excel file must contain worksheets with names that match the tables in the data model: `packages`, `classes`, `attributes`, `enumerations`, `enumerationliterals`, `associations`, `generalizations`, `diagrams` and the diagram junction tables (`diagram_class`, `diagram_enumeration`, `diagram_association`, `diagram_generalization`) with membership and layout.

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

### Shared database as import staging (run markers and version policy)

When crunch_uml writes to a shared database (say, a PostgreSQL staging database another application reads from), v0.5.1 adds two safeguards:

**Run markers.** Every `import` invocation writes a row to the `crunch_uml_runs` table (outside the data model, so it never leaks into exports): at the start with an empty `completed_at`, and only after the successful commit is `completed_at` stamped as the very last step. External readers should only consume schemas whose latest run has a `completed_at` — a row without one means "in progress or aborted" (crunch_uml writes table-by-table, non-transactionally, so reading halfway yields a torn model).

**Version policy.** When a database carries a different datamodel version, `-on_version_mismatch` decides what happens: `recreate` (historical behaviour: discard everything and rebuild), `fail` (stop without touching anything), or the default `auto` — which only recreates the local default database and fails on any explicitly provided `-db_url`. A mismatched crunch_uml version can therefore no longer accidentally wipe a shared staging database:

```bash
# Staging workflow: GGM into a PostgreSQL staging database, one schema per release
pip install 'crunch_uml[postgres]'
crunch_uml -db_url postgresql://crunch_writer:***@staging-host/crunch_staging \
  -sch ggm_2_5_1 import -f "Gemeentelijk Gegevensmodel XMI2.1.xml" -t eaxmi

# Deliberately recreate after a crunch_uml upgrade with a datamodel change:
crunch_uml -db_url postgresql://... -on_version_mismatch recreate -sch ggm_2_5_1 import -f model.xml -t eaxmi
```
