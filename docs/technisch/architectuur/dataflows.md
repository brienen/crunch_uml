# Dataflows

## Overzicht

crunch_uml kent drie primaire dataflows die corresponderen met de drie CLI-commando's.

```mermaid
graph LR
    subgraph "Import Flow"
        I1["Invoerbestand<br/>XMI / JSON / XLSX"] --> I2["Parser.parse()"]
        I2 --> I3["Schema.save()"]
        I3 --> I4["Database.commit()"]
        I4 --> I5[("Database")]
    end

    style I1 fill:#dae8fc,stroke:#6c8ebf
    style I2 fill:#fff2cc,stroke:#d6b656
    style I3 fill:#FFF4E0,stroke:#d79b00
    style I4 fill:#f8cecc,stroke:#b85450
    style I5 fill:#f8cecc,stroke:#b85450
```

```mermaid
graph LR
    subgraph "Transform Flow"
        T1["Schema A<br/>(bron)"] --> T2["Transformer.transform()"]
        T2 --> T3["get_copy() +<br/>materialize"]
        T3 --> T4["Schema B<br/>(doel)"]
    end

    style T1 fill:#f8cecc,stroke:#b85450
    style T2 fill:#FFF4E0,stroke:#d79b00
    style T3 fill:#d5e8d4,stroke:#82b366
    style T4 fill:#f8cecc,stroke:#b85450
```

```mermaid
graph LR
    subgraph "Export Flow"
        E1[("Database")] --> E2["Schema.get_all_*()"]
        E2 --> E3["Renderer.render()"]
        E3 --> E4["Format + Filter"]
        E4 --> E5["Uitvoerbestand<br/>JSON / MD / RDF / XLSX"]
    end

    style E1 fill:#f8cecc,stroke:#b85450
    style E2 fill:#f8cecc,stroke:#b85450
    style E3 fill:#dae8fc,stroke:#6c8ebf
    style E4 fill:#d5e8d4,stroke:#82b366
    style E5 fill:#dae8fc,stroke:#6c8ebf
```

---

## Import Flow — Detail

```mermaid
sequenceDiagram
    participant User as Gebruiker
    participant CLI as cli.py
    participant Reg as ParserRegistry
    participant Parser as Parser
    participant Schema as Schema
    participant DB as Database

    User->>CLI: crunch_uml import -f model.xmi -t xmi
    CLI->>Reg: getinstance("xmi")
    Reg-->>CLI: XMIParser instance
    CLI->>DB: Database(db_url)
    CLI->>Schema: Schema(database, schema_name)
    CLI->>Parser: parse(args, schema)

    loop Voor elk element in het bronbestand
        Parser->>Parser: Parse XML structuur (fase 1)
        Parser->>Schema: save(package/class/attribute)
    end

    loop Voor elke relatie
        Parser->>Parser: Parse connectors (fase 2)
        Parser->>Schema: save(association/generalization)
    end

    CLI->>DB: commit()
    DB-->>User: Model opgeslagen
```

De XMI-parser werkt in twee fasen:

1. **Fase 1** — `phase1_process_packages_classes()`: extraheert packages, classes, attributes en enumerations uit de XML-boom
2. **Fase 2** — `phase2_process_connectors()`: verwerkt associaties, generalisaties en diagramrelaties die refereren aan de in fase 1 aangemaakte objecten

---

## Transform Flow — Detail

```mermaid
sequenceDiagram
    participant CLI as cli.py
    participant Reg as TransformerRegistry
    participant Trans as Transformer
    participant SchA as Schema (bron)
    participant SchB as Schema (doel)
    participant DB as Database

    CLI->>Reg: getinstance("copy")
    Reg-->>CLI: CopyTransformer
    CLI->>Trans: transform(args, database)
    Trans->>SchA: get_package(root_package_id)
    SchA-->>Trans: Package hiërarchie
    Trans->>Trans: package.get_copy(materialize=...)

    alt Materialisatie aan
        Trans->>Trans: Kopieer parent-attributen naar children
    end

    Trans->>SchB: add(kopie, recursive=True)
    CLI->>DB: commit()
```

---

## Export Flow — Detail

```mermaid
sequenceDiagram
    participant CLI as cli.py
    participant Reg as RendererRegistry
    participant Rend as Renderer
    participant Schema as Schema
    participant File as Uitvoerbestand

    CLI->>Reg: getinstance("json")
    Reg-->>CLI: JSONRenderer
    CLI->>Rend: render(args, schema)
    Rend->>Schema: get_all_packages() / get_all_classes()
    Schema-->>Rend: ORM objecten
    Rend->>Rend: object_as_dict() serialisatie
    Rend->>Rend: Column filtering + mapper
    Rend->>File: Schrijf output
```

---

## Volledige Pipeline

Een typische pipeline combineert meerdere commando's:

```mermaid
graph TB
    A["bronbestand.xmi"] -->|"import"| B[("Schema: v1")]
    B -->|"transform"| C[("Schema: v2")]
    C -->|"export json"| D["output.json"]
    C -->|"export markdown"| E["docs.md"]
    C -->|"export rdf"| F["ontologie.ttl"]
    C -->|"export sqla"| G["models.py"]

    style B fill:#f8cecc,stroke:#b85450
    style C fill:#f8cecc,stroke:#b85450
```
