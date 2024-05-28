import argparse
import re
from urllib.parse import urlparse, urlunparse
import uuid


def valid_url(value):
    parsed = urlparse(value)
    if not all([parsed.scheme, parsed.netloc]):
        raise argparse.ArgumentTypeError(f"'{value}' is geen geldige URL.")
    return urlunparse(value)


def remove_substring(s, substring):
    pattern = re.compile(re.escape(substring), re.IGNORECASE)
    return pattern.sub('', s).strip()

def getEAGuid():
    uuid = uuid.uuid4()
    uuid = uuid.replace("-", "_")
    return 'EAID_' + uuid