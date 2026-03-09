# CLI Reference

Complete overview of all commands and options in crunch_uml.

## Global Options

```bash
crunch_uml [-h] [-v] [-d] [-w] [-db_url URL] [-sch SCHEMA] {import,transform,export} ...
```

| Option | Long | Description |
|---|---|---|
| `-h` | `--help` | Show help text |
| `-v` | `--verbose` | Set log level to INFO |
| `-d` | `--debug` | Set log level to DEBUG |
| `-w` | `--do_not_suppress_warnings` | Don't suppress warnings |
| `-db_url` | `--database_url` | Database URL (default: `sqlite:///crunch_uml.db`) |
| `-sch` | `--schema_name` | Schema name (default: `default`) |

## Import

```bash
crunch_uml import [-h] [-db_create] -f FILE [-url URL] -t TYPE [--skip_xmi_relations]
                   [--mapper JSON] [--update_only] [--language LANG]
```

| Option | Long | Description |
|---|---|---|
| `-db_create` | `--database_create_new` | Create new database (deletes existing) |
| `-f` | `--inputfile` | Input file |
| `-url` | | URL for remote import |
| `-t` | `--inputtype` | Input type: `xmi`, `eaxmi`, `qea`, `json`, `xlsx`, `csv`, `i18n` |
| | `--skip_xmi_relations` | Skip relation parsing (XMI) |
| | `--mapper` | JSON column mapping: `'{"old": "new"}'` |
| | `--update_only` | Only update existing records |
| | `--language` | Language for i18n (default: `nl`) |

## Transform

```bash
crunch_uml transform [-h] [-sch_from SCHEMA] -sch_to SCHEMA -ttp TYPE
                      [-sch_to_cln] [-rt_pkg ID] [-m_gen BOOL]
                      [-plug_mod FILE] [-plug_cl CLASS]
```

| Option | Long | Description |
|---|---|---|
| `-sch_from` | `--schema_from` | Source schema (default: `default`) |
| `-sch_to` | `--schema_to` | Target schema |
| `-sch_to_cln` | `--schema_to_clean` | Clean target schema first |
| `-ttp` | `--transformationtype` | Type: `copy` or `plugin` |
| `-rt_pkg` | `--root_package` | Root package ID |
| `-m_gen` | `--materialize_generalizations` | Flatten inheritance (`True`/`False`) |
| `-plug_mod` | `--plugin_file_name` | Path to plugin file |
| `-plug_cl` | `--plugin_class_name` | Plugin class name |

## Export

```bash
crunch_uml export [-h] -f FILE -t TYPE [-pi IDS] [-xpi IDS]
                   [-jt TEMPLATE] [-jtd DIR] [-ldns NS] [-js_url URL]
                   [-vt TYPE] [-ts STRATEGY] [--mapper JSON]
                   [--entity_name NAME] [--compare_schema_name SCHEMA]
                   [--compare_title TITLE] [--language LANG]
                   [--translate BOOL] [--from_language LANG]
```

| Option | Long | Description |
|---|---|---|
| `-f` | `--outputfile` | Output file |
| `-t` | `--outputtype` | Output type (see [Export](export.md)) |
| `-pi` | `--output_package_ids` | Comma-separated package IDs |
| `-xpi` | `--output_exclude_package_ids` | Package IDs to exclude |
| `-jt` | `--output_jinja2_template` | Jinja2 template file |
| `-jtd` | `--output_jinja2_templatedir` | Template directory |
| `-ldns` | `--linked_data_namespace` | Namespace for LOD |
| `-js_url` | `--json_schema_url` | URL for JSON Schema |
| `-vt` | `--version_type` | EA version update: `minor`, `major`, `none` |
| `-ts` | `--tag_strategy` | EA tag strategy: `update`, `upsert`, `replace` |
| | `--mapper` | JSON column mapping |
| | `--entity_name` | Specific entity (with CSV) |
| | `--compare_schema_name` | Schema for diff |
| | `--compare_title` | Title diff report |
| | `--language` | Language for i18n |
| | `--translate` | Automatically translate |
| | `--from_language` | Source language (default: `nl`) |

## Supported Tables

The following tables are recognized on import and export:

`packages`, `classes`, `attributes`, `enumerations`, `enumerationliterals`, `associations`, `generalizations`

## Database Backends

crunch_uml supports any SQLAlchemy-compatible database:

| Backend | Connection string |
|---|---|
| SQLite (default) | `sqlite:///crunch_uml.db` |
| PostgreSQL | `postgresql://user:pass@host/db` |
| MySQL | `mysql://user:pass@host/db` |
| MariaDB | `mariadb://user:pass@host/db` |

!!! note "Deviations from README"
    The following items are present in the code but were missing from the original README: the `-w` flag, the `qea` parser type, the `--schema_to_clean` option, and 11 additional renderer types (including `diff_md`, `eamimrepo`, `sqla`, `openapi`, `plain_html`, `model_overview_md`, `er_diagram`, `shex`, `profile`, `uml_mmd`, `model_stats_md`). The README also mentioned a transformer type `transform` that does not exist — the correct types are `copy` and `plugin`.
