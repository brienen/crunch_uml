# Architecture Overview

## Layer Model

crunch_uml is built from six layers, from user interaction to external storage. Each layer has a clear responsibility and communicates only with directly adjacent layers.

```mermaid
graph TB
    subgraph L1["<b>Presentation Layer</b>"]
        CLI["cli.py<br/>ArgumentParser + main()"]
        CONST["const.py<br/>Constants & Namespaces"]
        LOG["Logging<br/>DEBUG / INFO / WARN"]
        API["REST API<br/><i>Planned</i>"]
        CONFIG["Configuration Module<br/><i>Planned</i>"]
        MONITOR["Monitoring & Metrics<br/><i>Planned</i>"]
    end

    subgraph L2["<b>Orchestration Layer</b>"]
        REG["Registry<br/>registry.py"]
        PREG["ParserRegistry<br/>7 parsers"]
        RREG["RendererRegistry<br/>11 renderers"]
        TREG["TransformerRegistry<br/>2 + plugins"]
        PLUG["Plugin Framework<br/>Dynamic loading"]
    end

    subgraph L3I["<b>Import Layer</b>"]
        XMI["XMI Parser"]
        EAXMI["EA XMI Parser"]
        QEA["QEA Parser"]
        JSON_P["JSON Parser"]
        XLSX_P["XLSX Parser"]
        CSV_P["CSV Parser"]
        I18N_P["i18n Parser"]
        API_P["API Parser<br/><i>Planned</i>"]
        STREAM["Streaming Parser<br/><i>Planned</i>"]
    end

    subgraph L3T["<b>Transformation Layer</b>"]
        COPY["CopyTransformer<br/>Deep copy + materialization"]
        PLUGT["PluginTransformer<br/>Dynamic plugins"]
        MAP["Universal Mapping Layer<br/><i>Planned</i>"]
        DIFF["Schema Diff & Merge<br/><i>Planned</i>"]
        GEN2["Generalization v2<br/><i>Planned</i>"]
        LANG["lang.py — Translation Module"]
    end

    subgraph L3E["<b>Export Layer</b>"]
        JSON_R["JSON Renderer"]
        CSV_R["CSV Renderer"]
        XLSX_R["XLSX Renderer"]
        JINJA["Jinja2 Renderer"]
        GGM["GGM Markdown"]
        JSCHEMA["JSON Schema"]
        LOD["TTL / RDF / JSON-LD"]
        SQLA["SQLAlchemy Gen."]
        EAREP["EA Repo Updater"]
        SDIFF["Schema Diff MD"]
        GQL["GraphQL / OpenAPI<br/><i>Planned</i>"]
    end

    subgraph L4["<b>Persistence Layer</b>"]
        DB["Database (db.py)<br/>Singleton + SQLAlchemy 2.0"]
        SCH["Schema (schema.py)<br/>Multi-version isolation"]
        ORM["ORM Models<br/>Package | Class | Attribute<br/>Association | Generalization | Diagram"]
        MIX["Mixins & Tags<br/>UML_Generic | UMLBase | UMLTags*"]
        CACHE["Caching & Validation<br/><i>Planned</i>"]
        IDX["Indexing Techniques<br/><i>Planned</i>"]
        REPO["Centralized Repo<br/><i>Planned</i>"]
    end

    subgraph L5["<b>External Systems</b>"]
        SQLITE[("SQLite")]
        PG[("PostgreSQL")]
        MYSQL[("MySQL")]
        EA_DB[("Enterprise Architect")]
        FS["File System"]
        SNOW[("Snowflake<br/><i>Planned</i>")]
        AZURE[("AzureDB<br/><i>Planned</i>")]
    end

    CLI --> REG
    REG --> PREG & RREG & TREG
    PREG --> L3I
    TREG --> L3T
    RREG --> L3E
    L3I -->|"write"| L4
    L3T -->|"read/write"| L4
    L4 -->|"read"| L3E
    L4 --> L5

    style L1 fill:#dae8fc,stroke:#6c8ebf
    style L2 fill:#d5e8d4,stroke:#82b366
    style L3I fill:#fff2cc,stroke:#d6b656
    style L3T fill:#FFF4E0,stroke:#d79b00
    style L3E fill:#dae8fc,stroke:#6c8ebf
    style L4 fill:#f8cecc,stroke:#b85450
    style L5 fill:#e1d5e7,stroke:#9673a6
    style API fill:#e1d5e7,stroke:#9673a6,stroke-dasharray: 5 5
    style CONFIG fill:#e1d5e7,stroke:#9673a6,stroke-dasharray: 5 5
    style MONITOR fill:#e1d5e7,stroke:#9673a6,stroke-dasharray: 5 5
    style API_P fill:#e1d5e7,stroke:#9673a6,stroke-dasharray: 5 5
    style STREAM fill:#e1d5e7,stroke:#9673a6,stroke-dasharray: 5 5
    style MAP fill:#e1d5e7,stroke:#9673a6,stroke-dasharray: 5 5
    style DIFF fill:#e1d5e7,stroke:#9673a6,stroke-dasharray: 5 5
    style GEN2 fill:#e1d5e7,stroke:#9673a6,stroke-dasharray: 5 5
    style GQL fill:#e1d5e7,stroke:#9673a6,stroke-dasharray: 5 5
    style CACHE fill:#e1d5e7,stroke:#9673a6,stroke-dasharray: 5 5
    style IDX fill:#e1d5e7,stroke:#9673a6,stroke-dasharray: 5 5
    style REPO fill:#e1d5e7,stroke:#9673a6,stroke-dasharray: 5 5
    style SNOW fill:#e1d5e7,stroke:#9673a6,stroke-dasharray: 5 5
    style AZURE fill:#e1d5e7,stroke:#9673a6,stroke-dasharray: 5 5
```

!!! info "Legend"
    - **Solid lines** = Implemented components
    - **Dashed lines (purple)** = Planned components
    - Colors per layer: blue (presentation/export), green (orchestration), yellow (import), orange (transformation), red (persistence), purple (external)

## Directory Structure

```
crunch_uml/
├── __init__.py                 # Package entry point
├── cli.py                      # CLI argument parser & main()
├── const.py                    # Constants, mappings, configuration
├── db.py                       # Database models & Database class (1200+ lines)
├── schema.py                   # Schema wrapper for database operations
├── registry.py                 # Plugin registry pattern base class
├── lang.py                     # Translation module
├── util.py                     # Helper utilities
├── exceptions.py               # Custom exceptions
├── parsers/
│   ├── parser.py               # Parser base class & registry
│   ├── xmiparser.py            # Standard XMI parser
│   ├── eaxmiparser.py          # Enterprise Architect XMI parser
│   ├── qeaparser.py            # QEA format parser
│   └── multiple_parsers.py     # JSON, CSV, XLSX, i18n parsers
├── renderers/
│   ├── renderer.py             # Renderer base class & registry
│   ├── pandasrenderer.py       # JSON, CSV, i18n renderers
│   ├── xlsxrenderer.py         # Excel renderer
│   ├── jinja2renderer.py       # Jinja2, GGM_MD, JSON-Schema renderers
│   ├── lodrenderer.py          # TTL, RDF, JSON-LD renderers
│   ├── sqlarenderer.py         # SQLAlchemy model generator
│   └── earepoupdater.py        # EA repo updater
├── transformers/
│   ├── transformer.py          # Transformer base class & registry
│   ├── copytransformer.py      # Copy/clone transformer
│   ├── plugintransformer.py    # Plugin-based custom transformers
│   └── plugin.py               # Plugin base class
└── templates/                  # Jinja2 templates
    ├── ggm_markdown.j2
    ├── json_schema.j2
    ├── ddas_markdown.j2
    ├── ggm_sqlalchemy.j2
    └── json_datatypes.json
```

## Core Principles

1. **Registry-driven extensibility** — New parsers, renderers and transformers are registered via `@register` decorators, without modification of existing code
2. **Multi-schema isolation** — Multiple versions of the same model in one database, isolated via `schema_id`
3. **Pipeline architecture** — Import → Transform → Export as separate, composable steps
4. **Plugin framework** — Custom transformations via dynamically loaded plugins
