# Architectuuroverzicht

## Lagenmodel

crunch_uml is opgebouwd uit zes lagen, van gebruikersinteractie tot externe opslag. Elke laag heeft een duidelijke verantwoordelijkheid en communiceert alleen met direct aangrenzende lagen.

```mermaid
graph TB
    subgraph L1["<b>Presentatielaag</b>"]
        CLI["cli.py<br/>ArgumentParser + main()"]
        CONST["const.py<br/>Constanten & Namespaces"]
        LOG["Logging<br/>DEBUG / INFO / WARN"]
        API["REST API<br/><i>beoogd</i>"]
        CONFIG["Configuratiemodule<br/><i>beoogd</i>"]
        MONITOR["Monitoring & Metrics<br/><i>beoogd</i>"]
    end

    subgraph L2["<b>Orchestratielaag</b>"]
        REG["Registry<br/>registry.py"]
        PREG["ParserRegistry<br/>7 parsers"]
        RREG["RendererRegistry<br/>11 renderers"]
        TREG["TransformerRegistry<br/>2 + plugins"]
        PLUG["Plugin Framework<br/>Dynamisch laden"]
    end

    subgraph L3I["<b>Importlaag</b>"]
        XMI["XMI Parser"]
        EAXMI["EA XMI Parser"]
        QEA["QEA Parser"]
        JSON_P["JSON Parser"]
        XLSX_P["XLSX Parser"]
        CSV_P["CSV Parser"]
        I18N_P["i18n Parser"]
        API_P["API Parser<br/><i>beoogd</i>"]
        STREAM["Streaming Parser<br/><i>beoogd</i>"]
    end

    subgraph L3T["<b>Transformatielaag</b>"]
        COPY["CopyTransformer<br/>Deep copy + materialization"]
        PLUGT["PluginTransformer<br/>Dynamische plugins"]
        MAP["Universele Mapping Layer<br/><i>beoogd</i>"]
        DIFF["Schema Diff & Merge<br/><i>beoogd</i>"]
        GEN2["Generalization v2<br/><i>beoogd</i>"]
        LANG["lang.py — Vertaalmodule"]
    end

    subgraph L3E["<b>Exportlaag</b>"]
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
        GQL["GraphQL / OpenAPI<br/><i>beoogd</i>"]
    end

    subgraph L4["<b>Persistentielaag</b>"]
        DB["Database (db.py)<br/>Singleton + SQLAlchemy 2.0"]
        SCH["Schema (schema.py)<br/>Multi-versie isolatie"]
        ORM["ORM Modellen<br/>Package | Class | Attribute<br/>Association | Generalization | Diagram"]
        MIX["Mixins & Tags<br/>UML_Generic | UMLBase | UMLTags*"]
        CACHE["Caching & Validatie<br/><i>beoogd</i>"]
        IDX["Indexeringstechnieken<br/><i>beoogd</i>"]
        REPO["Gecentraliseerde Repo<br/><i>beoogd</i>"]
    end

    subgraph L5["<b>Externe Systemen</b>"]
        SQLITE[("SQLite")]
        PG[("PostgreSQL")]
        MYSQL[("MySQL")]
        EA_DB[("Enterprise Architect")]
        FS["Bestandssysteem"]
        SNOW[("Snowflake<br/><i>beoogd</i>")]
        AZURE[("AzureDB<br/><i>beoogd</i>")]
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

!!! info "Legenda"
    - **Doorgetrokken lijnen** = gerealiseerde componenten
    - **Gestreepte lijnen (paars)** = beoogde componenten
    - Kleuren per laag: blauw (presentatie/export), groen (orchestratie), geel (import), oranje (transformatie), rood (persistentie), paars (extern)

## Directorystructuur

```
crunch_uml/
├── __init__.py                 # Package entry point
├── cli.py                      # CLI argument parser & main()
├── const.py                    # Constanten, mappings, configuratie
├── db.py                       # Database modellen & Database klasse (1200+ regels)
├── schema.py                   # Schema wrapper voor database-operaties
├── registry.py                 # Plugin registry pattern base class
├── lang.py                     # Vertaalmodule
├── util.py                     # Helper utilities
├── exceptions.py               # Custom exceptions
├── parsers/
│   ├── parser.py               # Parser base class & registry
│   ├── xmiparser.py            # Standaard XMI parser
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

## Kernprincipes

1. **Registry-driven uitbreidbaarheid** — Nieuwe parsers, renderers en transformers worden geregistreerd via `@register` decorators, zonder aanpassing van bestaande code
2. **Multi-schema isolatie** — Meerdere versies van hetzelfde model in één database, geïsoleerd via `schema_id`
3. **Pipeline-architectuur** — Import → Transform → Export als losse, composable stappen
4. **Plugin framework** — Custom transformaties via dynamisch geladen plugins
