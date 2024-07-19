import argparse
import importlib.util
import logging
import re
import uuid
from urllib.parse import urlparse

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
