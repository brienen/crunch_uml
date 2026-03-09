# Technische Stack

## Afhankelijkheden

### Runtime

| Categorie | Bibliotheek | Versie | Toepassing |
|---|---|---|---|
| ORM / Database | SQLAlchemy | 2.0.20+ | Object-Relational Mapping, multi-DB support |
| XML Parsing | lxml | 4.9.3+ | XMI/XML parsing (in-huis bibliotheken) |
| Data Processing | pandas | 2.2.2+ | CSV, Excel verwerking |
| Excel | openpyxl | 3.0.10+ | Excel lezen en schrijven |
| Templating | Jinja2 | 3.1.2+ | Template-gebaseerde rendering |
| Linked Data | rdflib | 7.0.0+ | RDF/OWL/TTL/JSON-LD |
| HTTP | requests | 2.32.3+ | Remote URL parsing |
| Validatie | jsonschema | 4.22+ | JSON Schema validatie |
| Vertaling | translators | 5.9.2+ | Machine translation i18n |
| HTML | beautifulsoup4 | 4.12.2+ | HTML parsing |
| HTML→MD | markdownify | 1.2.2+ | HTML-to-Markdown conversie |
| Strings | inflection | 0.5.1+ | String inflection |
| URL Validatie | validators | 0.28.0+ | URL validatie |
| Encoding | chardet, charset-normalizer | — | Encoding detectie |

### Development

| Categorie | Bibliotheek | Versie | Toepassing |
|---|---|---|---|
| Testing | pytest | 8.x | Unit testing |
| Coverage | pytest-cov | 5.x | Code coverage |
| Formatting | black | 24.x | Code formatting (line length: 120) |
| Imports | isort | 5.x | Import sorting (profiel: black) |
| Type Checking | mypy | 1.11.x | Static type checking |
| Linting | flake8 | 7.x | Code linting |
| Security | bandit | 1.7.x | Security scanning |
| Build | build | 1.1.x | Package building |
| Publish | twine | 5.x | PyPI publishing |

### Beoogde toevoegingen

| Bibliotheek | Toepassing |
|---|---|
| Alembic | Database migraties |
| FastAPI | REST API interface |
| Snowflake connector | Cloud database |
| Azure SQL connector | Cloud database |
| ijson | Streaming JSON parsing |
| uvicorn | ASGI server |

## Python Compatibiliteit

crunch_uml ondersteunt Python 3.9 t/m 3.12.

## Configuratie

### Code Quality

```toml
# pyproject.toml

[tool.black]
line-length = 120

[tool.isort]
profile = "black"
skip = ["cli.py"]

[tool.mypy]
# Type checking enabled
```

### Logging

```python
# Configuratie in cli.py
FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
# Levels: DEBUG (-d), INFO (-v), WARNING (default)
# Output: stderr
```

### Database

```python
# Default in const.py
DATABASE_URL = "sqlite:///crunch_uml.db"
# Ondersteunt elke SQLAlchemy-compatible connection string
```

## Entry Points

```toml
[project.scripts]
crunch_uml = "crunch_uml.cli:main"
```

## Distributie

- **PyPI**: [pypi.org/project/crunch_uml](https://pypi.org/project/crunch_uml)
- **GitHub**: [github.com/brienen/crunch_uml](https://github.com/brienen/crunch_uml)
- **Licentie**: MIT
