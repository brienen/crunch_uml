# Installatie

## Via pip (aanbevolen)

```bash
pip install crunch-uml
```

Na installatie is het commando `crunch_uml` beschikbaar:

```bash
crunch_uml --help
```

## Vanuit broncode

```bash
git clone https://github.com/brienen/crunch_uml.git
cd crunch_uml
pip install -e .
```

Of start direct vanuit de broncode:

```bash
python ./crunch_uml/cli.py --help
```

## Vereisten

- Python 3.9, 3.10, 3.11 of 3.12
- Afhankelijkheden worden automatisch geïnstalleerd (SQLAlchemy, lxml, pandas, etc.)

## Database

Standaard gebruikt crunch_uml een SQLite-database in de huidige directory (`crunch_uml.db`). Je kunt elke SQLAlchemy-compatible database gebruiken:

```bash
# SQLite (default)
crunch_uml -db_url sqlite:///mijn_model.db import -f model.xmi -t eaxmi

# PostgreSQL
crunch_uml -db_url postgresql://user:pass@localhost/crunch import -f model.xmi -t eaxmi
```

## Eerste test

Controleer of de installatie werkt:

```bash
# Importeer een XMI-bestand en maak een nieuwe database aan
crunch_uml import -f jouw_model.xmi -t eaxmi -db_create

# Bekijk het resultaat als Excel
crunch_uml export -t xlsx -f output.xlsx
```
