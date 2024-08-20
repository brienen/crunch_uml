import argparse
import importlib.util
import logging
import re
import uuid
from datetime import datetime
from urllib.parse import urlparse

from crunch_uml import const

logger = logging.getLogger()


def valid_url(value):
    parsed = urlparse(value)
    if not all([parsed.scheme, parsed.netloc]):
        raise argparse.ArgumentTypeError(f"'{value}' is geen geldige URL.")
    return value


def remove_substring(s, substring):
    pattern = re.compile(re.escape(substring), re.IGNORECASE)
    return pattern.sub('', s).strip()


def getEAGuid():
    str_uuid = uuid.uuid4()
    str_uuid = str(str_uuid).replace("-", "_")
    return 'EAID_' + str_uuid


def get_repo_guid():
    str_uuid = str(uuid.uuid4())
    return '{' + str_uuid + '}'


def fromEAGuid(ea_guid):
    strea_guid = ea_guid.lstrip("EA").lstrip("ID_").lstrip("PK_").replace("_", "-")
    return '{' + strea_guid + '}'


def getMeervoud(naamwoord):
    # Woorden die eindigen op een onbeklemtoonde 'e' krijgen 'n'
    if not isinstance(naamwoord, str):
        return ''
    # Woorden die eindigen op een onbeklemtoonde 'e' krijgen 'n'
    elif naamwoord.endswith('ie'):
        return f"{naamwoord}s"
    # Woorden die eindigen op een onbeklemtoonde 'e' krijgen 'n'
    elif naamwoord.endswith('e'):
        return f"{naamwoord}n"
    # Woorden die eindigen op een klinker (behalve 'e') krijgen 's'
    elif naamwoord[-1] in 'aiou':
        return f"{naamwoord}s"
    # Woorden die eindigen op 's', 'f' of 'ch' krijgen 'en'
    elif naamwoord.endswith(('s', 'f', 'ch')):
        return f"{naamwoord}en"
    # Default regel
    else:
        return f"{naamwoord}en"


def find_module_path(module_name):
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        logger.warning(f"Module {module_name} not found")
        return None
    spec = str(spec.origin).removesuffix('__init__.py')

    return spec


def parse_date(date_string):
    # Lijst van mogelijke datumformaten
    formats = [
        const.DEFAULT_DATE_TIME_FORMAT,  # Default format
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%I:%M %p",  # Time only, for edge cases
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue

    raise ValueError(f"Date format of '{date_string}' is not recognized.")


def reverse_dict(d):
    return {v: k for k, v in d.items()}
