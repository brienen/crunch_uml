# Componenten

crunch_uml is opgebouwd uit vier componentgroepen die elk een specifieke rol vervullen in de verwerkingspipeline.

```mermaid
graph TB
    subgraph Parsers["Parsers (Import)"]
        direction LR
        P1["XMI"] ~~~ P2["EA XMI"] ~~~ P3["QEA"]
        P4["JSON"] ~~~ P5["XLSX"] ~~~ P6["CSV"] ~~~ P7["i18n"]
    end

    subgraph Transformers["Transformers"]
        direction LR
        T1["CopyTransformer"] ~~~ T2["PluginTransformer"]
    end

    subgraph Renderers["Renderers (Export)"]
        direction LR
        R1["JSON"] ~~~ R2["CSV"] ~~~ R3["XLSX"]
        R4["Jinja2"] ~~~ R5["GGM MD"] ~~~ R6["JSON Schema"]
        R7["TTL/RDF/JSON-LD"] ~~~ R8["SQLAlchemy"] ~~~ R9["EA Repo"]
        R10["Schema Diff MD"] ~~~ R11["i18n"]
    end

    subgraph Persistentie["Persistentie"]
        direction LR
        D1["Database"] ~~~ D2["Schema"] ~~~ D3["ORM Models"]
    end

    Parsers -->|write| Persistentie
    Persistentie -->|read/write| Transformers
    Persistentie -->|read| Renderers

    style Parsers fill:#fff2cc,stroke:#d6b656
    style Transformers fill:#FFF4E0,stroke:#d79b00
    style Renderers fill:#dae8fc,stroke:#6c8ebf
    style Persistentie fill:#f8cecc,stroke:#b85450
```

## Pagina's

- [Parsers](parsers.md) — 7 geregistreerde input-parsers
- [Transformers](transformers.md) — Copy, Plugin en beoogde transformers
- [Renderers](renderers.md) — 11 geregistreerde output-renderers
- [Persistentie](persistentie.md) — Database, Schema en ORM-modellen
