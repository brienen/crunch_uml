<div align="center">

# Crunch-UML

Crunch_UML is a parser for XMI files originating from UML tools such as Enterprise Architect. The tool reads the XMI and stores entities and relationships in an SQLite database for further analysis or use.

**Crunch_UML is stillunder heavy development and does not have any releases.**

[![Build Status](https://github.com/brienen/crunch_uml/workflows/build/badge.svg)](https://github.com/brienen/crunch_uml/actions)
[![Coverage Status](https://coveralls.io/repos/github/brienen/crunch_uml/badge.svg?branch=main)](https://coveralls.io/github/brienen/crunch_uml?branch=main)
[![PyPi](https://img.shields.io/pypi/v/crunch_uml)](https://pypi.org/project/crunch_uml)
[![Licence](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

- Parses entities such as `Package`, `Class`, and `Relation` from an XMI file.
- Uses SQLAlchemy for database access and manipulation.
- Configurable logging support.
- Supports setting the logging level via command line parameters.
- Singleton Database Design for centralized database manipulation.

## Install

```bash
# Install tool
pip3 install crunch_uml

# Install locally
make install
```

## Usage

Usage instructions go here.

```bash
python main.py -f <path_to_xmi_file> [--verbose] [--debug]
```

Arguments:
- `-f, --file` : Specify the XMI file to be parsed.
- `--verbose` : Set the logging level to INFO.
- `--debug` : Set the logging level to DEBUG.

## Modules

- `main.py` : Main script for parsing and handling command line arguments.
- `db.py` : Contains the singleton database class and related functions for managing database operations.

## Logging

Logging is implemented with Python's built-in `logging` module. By default, logs are sent to `stderr`. Use `--verbose` for INFO logs and `--debug` for DEBUG logs.

## Development

```bash
# Get a comprehensive list of development tools
make help
```

## Future Improvements

- Expansion to other database backends such as PostgreSQL or MySQL.
- Provide more granular control over logging, for example specifying log files.

---

You can use this foundation and expand upon it as you continue to develop your program and add new features.