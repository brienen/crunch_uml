# Installation

## Via pip (recommended)

```bash
pip install crunch-uml
```

To write to a PostgreSQL database (for instance a shared import staging, see the import manual), install the postgres extra as well:

```bash
pip install 'crunch_uml[postgres]'
```

After installation, the `crunch_uml` command is available:

```bash
crunch_uml --help
```

## From source code

```bash
git clone https://github.com/brienen/crunch_uml.git
cd crunch_uml
pip install -e .
```

Or run directly from source:

```bash
python ./crunch_uml/cli.py --help
```

## Requirements

- Python 3.10, 3.11, 3.12 or 3.13
- Dependencies are installed automatically (SQLAlchemy, lxml, pandas, etc.)

## Database

By default crunch_uml uses a SQLite database in the current directory (`crunch_uml.db`). You can use any SQLAlchemy-compatible database:

```bash
# SQLite (default)
crunch_uml -db_url sqlite:///my_model.db import -f model.xmi -t eaxmi

# PostgreSQL
crunch_uml -db_url postgresql://user:pass@localhost/crunch import -f model.xmi -t eaxmi
```

## First test

Check if the installation works:

```bash
# Import an XMI file and create a new database
crunch_uml import -f your_model.xmi -t eaxmi -db_create

# View the result as Excel
crunch_uml export -t xlsx -f output.xlsx
```
