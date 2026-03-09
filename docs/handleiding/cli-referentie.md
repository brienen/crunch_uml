# CLI-referentie

Compleet overzicht van alle commando's en opties in crunch_uml.

## Globale opties

```bash
crunch_uml [-h] [-v] [-d] [-w] [-db_url URL] [-sch SCHEMA] {import,transform,export} ...
```

| Optie | Lang | Beschrijving |
|---|---|---|
| `-h` | `--help` | Toon helptekst |
| `-v` | `--verbose` | Zet log-niveau op INFO |
| `-d` | `--debug` | Zet log-niveau op DEBUG |
| `-w` | `--do_not_suppress_warnings` | Onderdruk waarschuwingen niet |
| `-db_url` | `--database_url` | Database URL (standaard: `sqlite:///crunch_uml.db`) |
| `-sch` | `--schema_name` | Schema naam (standaard: `default`) |

## Import

```bash
crunch_uml import [-h] [-db_create] -f FILE [-url URL] -t TYPE [--skip_xmi_relations]
                   [--mapper JSON] [--update_only] [--language LANG]
```

| Optie | Lang | Beschrijving |
|---|---|---|
| `-db_create` | `--database_create_new` | Maak nieuwe database (verwijdert bestaande) |
| `-f` | `--inputfile` | Invoerbestand |
| `-url` | | URL voor remote import |
| `-t` | `--inputtype` | Invoertype: `xmi`, `eaxmi`, `qea`, `json`, `xlsx`, `csv`, `i18n` |
| | `--skip_xmi_relations` | Sla relatie-parsing over (XMI) |
| | `--mapper` | JSON kolom-mapping: `'{"oud": "nieuw"}'` |
| | `--update_only` | Alleen bestaande records bijwerken |
| | `--language` | Taal voor i18n (standaard: `nl`) |

## Transform

```bash
crunch_uml transform [-h] [-sch_from SCHEMA] -sch_to SCHEMA -ttp TYPE
                      [-sch_to_cln] [-rt_pkg ID] [-m_gen BOOL]
                      [-plug_mod FILE] [-plug_cl CLASS]
```

| Optie | Lang | Beschrijving |
|---|---|---|
| `-sch_from` | `--schema_from` | Bronschema (standaard: `default`) |
| `-sch_to` | `--schema_to` | Doelschema |
| `-sch_to_cln` | `--schema_to_clean` | Maak doelschema eerst leeg |
| `-ttp` | `--transformationtype` | Type: `copy` of `plugin` |
| `-rt_pkg` | `--root_package` | Root package ID |
| `-m_gen` | `--materialize_generalizations` | Vlak inheritance af (`True`/`False`) |
| `-plug_mod` | `--plugin_file_name` | Pad naar plugin-bestand |
| `-plug_cl` | `--plugin_class_name` | Plugin klassenaam |

## Export

```bash
crunch_uml export [-h] -f FILE -t TYPE [-pi IDS] [-xpi IDS]
                   [-jt TEMPLATE] [-jtd DIR] [-ldns NS] [-js_url URL]
                   [-vt TYPE] [-ts STRATEGY] [--mapper JSON]
                   [--entity_name NAME] [--compare_schema_name SCHEMA]
                   [--compare_title TITLE] [--language LANG]
                   [--translate BOOL] [--from_language LANG]
```

| Optie | Lang | Beschrijving |
|---|---|---|
| `-f` | `--outputfile` | Uitvoerbestand |
| `-t` | `--outputtype` | Uitvoertype (zie [Export](export.md)) |
| `-pi` | `--output_package_ids` | Kommagescheiden package ID's |
| `-xpi` | `--output_exclude_package_ids` | Uit te sluiten package ID's |
| `-jt` | `--output_jinja2_template` | Jinja2 template-bestand |
| `-jtd` | `--output_jinja2_templatedir` | Template directory |
| `-ldns` | `--linked_data_namespace` | Namespace voor LOD |
| `-js_url` | `--json_schema_url` | URL voor JSON Schema |
| `-vt` | `--version_type` | EA versie-update: `minor`, `major`, `none` |
| `-ts` | `--tag_strategy` | EA tag-strategie: `update`, `upsert`, `replace` |
| | `--mapper` | JSON kolom-mapping |
| | `--entity_name` | Specifieke entiteit (bij CSV) |
| | `--compare_schema_name` | Schema voor diff |
| | `--compare_title` | Titel diff-rapport |
| | `--language` | Taal voor i18n |
| | `--translate` | Automatisch vertalen |
| | `--from_language` | Brontaal (standaard: `nl`) |

## Ondersteunde tabellen

De volgende tabellen worden herkend bij import en export:

`packages`, `classes`, `attributes`, `enumerations`, `enumerationliterals`, `associations`, `generalizations`

## Database backends

crunch_uml ondersteunt elke SQLAlchemy-compatible database:

| Backend | Connection string |
|---|---|
| SQLite (standaard) | `sqlite:///crunch_uml.db` |
| PostgreSQL | `postgresql://user:pass@host/db` |
| MySQL | `mysql://user:pass@host/db` |
| MariaDB | `mariadb://user:pass@host/db` |

!!! note "Afwijkingen README"
    De volgende items zijn aanwezig in de code maar ontbraken in de oorspronkelijke README: de `-w` flag, het `qea` parser-type, de `--schema_to_clean` optie, en 11 extra renderer-types (waaronder `diff_md`, `eamimrepo`, `sqla`, `openapi`, `plain_html`, `model_overview_md`, `er_diagram`, `shex`, `profile`, `uml_mmd`, `model_stats_md`). De README vermeldde ook een transformer-type `transform` dat niet bestaat — de juiste types zijn `copy` en `plugin`.
