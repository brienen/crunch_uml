import argparse
import importlib.util
import json
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
    return pattern.sub("", s).strip()


def lremove_substring(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix) :]
    return text


def getEAGuid():
    str_uuid = uuid.uuid4()
    str_uuid = str(str_uuid).replace("-", "_")
    return "EAID_" + str_uuid


def get_repo_guid():
    str_uuid = str(uuid.uuid4())
    return "{" + str_uuid + "}"


def fromEAGuid(ea_guid):
    strea_guid = lremove_substring(ea_guid, "EAID_")
    strea_guid = lremove_substring(strea_guid, "EAPK_")
    strea_guid = strea_guid.replace("_", "-")
    return "{" + strea_guid + "}"


def getMeervoud(naamwoord):
    # Woorden die eindigen op een onbeklemtoonde 'e' krijgen 'n'
    if not isinstance(naamwoord, str):
        return ""
    # Woorden die eindigen op een onbeklemtoonde 'e' krijgen 'n'
    elif naamwoord.endswith("ie"):
        return f"{naamwoord}s"
    # Woorden die eindigen op een onbeklemtoonde 'e' krijgen 'n'
    elif naamwoord.endswith("e"):
        return f"{naamwoord}n"
    # Woorden die eindigen op een klinker (behalve 'e') krijgen 's'
    elif naamwoord[-1] in "aiou":
        return f"{naamwoord}s"
    # Woorden die eindigen op 's', 'f' of 'ch' krijgen 'en'
    elif naamwoord.endswith(("s", "f", "ch")):
        return f"{naamwoord}en"
    # Default regel
    else:
        return f"{naamwoord}en"


def find_module_path(module_name):
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        logger.warning(f"Module {module_name} not found")
        return None
    spec = str(spec.origin).removesuffix("__init__.py")

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


def is_valid_i18n_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Controleer of de root een dictionary is
        if not isinstance(data, dict):
            print("Root element is not a dictionary.")
            return False

        # Controleer of er minstens één taalcode aanwezig is
        if not all(isinstance(key, str) for key in data.keys()):
            print("One or more keys in the root element are not strings.")
            return False

        # Controleer elke taalcode
        for language, content in data.items():
            # Content moet een dictionary zijn
            if not isinstance(content, dict):
                print(f"Content for language '{language}' is not a dictionary.")
                return False

            # Controleer verwachte secties (bijvoorbeeld "packages", "classes", etc.)
            for section, entries in content.items():
                if not isinstance(entries, list):
                    print(f"Section '{section}' under language '{language}' is not a list.")
                    return False

                for entry in entries:
                    if not isinstance(entry, dict):
                        print(f"An entry in section '{section}' under language '{language}' is not a dictionary.")
                        return False

                    for key, value in entry.items():
                        if not isinstance(value, dict):
                            print(
                                f"Entry '{key}' in section '{section}' under language '{language}' is not a dictionary."
                            )
                            return False
                        if "name" not in value:
                            print(
                                f"Entry '{key}' in section '{section}' under language '{language}' does not have a 'name' key."
                            )
                            return False

        # Als alle controles slagen
        return True

    except json.JSONDecodeError:
        print("The file is not a valid JSON file.")
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False


def count_dict_elements(d):
    count = 0

    if isinstance(d, dict):
        for key, value in d.items():
            count += 1  # Tel de huidige key-value pair
            count += count_dict_elements(value)  # Recursief tellen van geneste elementen
    elif isinstance(d, list):
        for item in d:
            count += count_dict_elements(item)  # Recursief tellen van elementen in de lijst
    else:
        count += 1  # Als het een enkel element is (geen dict of lijst), tel het als 1

    return count


def nested_get(d, keys, default=None):
    """
    Safely get a value from a nested dictionary.

    Args:
        d (dict): The dictionary to search in.
        keys (list): A list of keys defining the path to the value.
        default: A default value if the key path does not exist.

    Returns:
        The value at the nested key path, or the default value.
    """
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key, default)
        else:
            return default
    return d


def is_empty_or_none(value: str) -> bool:
    """
    Check if a string is None or empty.

    Args:
        value (str): The string to check.

    Returns:
        bool: True if the string is None or empty, False otherwise.
    """
    return value is None or value.strip() == ""
