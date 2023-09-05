import argparse
from urllib.parse import urlparse

def valid_url(value):
    parsed = urlparse(value)
    if not all([parsed.scheme, parsed.netloc]):
        raise argparse.ArgumentTypeError(f"'{value}' is geen geldige URL.")
    return value
