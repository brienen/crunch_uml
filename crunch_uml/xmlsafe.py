"""One hardened lxml configuration for XML read from files crunch_uml does not control.

Model files (EA XMI) can come from anyone, so parsing must never:

* expand entities (no "billion laughs", no external entity file reads);
* touch the network (no DTD or schema fetches);
* grow unbounded trees (``huge_tree=False`` keeps libxml2's size and depth limits);
* accept a document type declaration at all: an EA export never has one.

Use :func:`make_parser` for DOM parsing and :func:`reject_doctype` before and
after the parse. ``SAFE_PARSER_OPTIONS`` also serves ``iterparse`` callers.
"""

import re

from lxml import etree

from crunch_uml.exceptions import CrunchException

#: Upper bound for how much of a file sniffers (encoding, DOCTYPE, detection) read.
SNIFF_BYTES = 64 * 1024

SAFE_PARSER_OPTIONS = dict(
    resolve_entities=False,
    no_network=True,
    huge_tree=False,
    load_dtd=False,
    dtd_validation=False,
    attribute_defaults=False,
)

# Everything allowed before the root element except a DOCTYPE: whitespace,
# processing instructions (the XML declaration) and comments.
_PROLOG_MISC_RE = re.compile(r"(?:\s+|<\?.*?\?>|<!--.*?-->)*", re.S)


class XMLForbiddenError(CrunchException):
    """The XML document contains constructs that are refused for safety."""


def make_parser(**overrides):
    """An ``etree.XMLParser`` with the hardened options (plus overrides such as ``encoding``)."""
    options = dict(SAFE_PARSER_OPTIONS)
    options["recover"] = False
    options.update(overrides)
    return etree.XMLParser(**options)


def reject_doctype(text=None, root=None):
    """Raise :class:`XMLForbiddenError` when a document type declaration is present.

    ``text`` is checked on its prolog (at most :data:`SNIFF_BYTES` characters,
    before parsing); ``root`` is checked on the parsed tree, which also catches a
    DOCTYPE that hides behind a very long leading comment.
    """
    if text is not None:
        head = text[:SNIFF_BYTES]
        match = _PROLOG_MISC_RE.match(head)
        if head.startswith("<!DOCTYPE", match.end() if match else 0):
            raise XMLForbiddenError("XML document type declarations (DOCTYPE) are not accepted.")
    if root is not None:
        docinfo = root.getroottree().docinfo
        if docinfo.doctype or docinfo.internalDTD is not None or docinfo.externalDTD is not None:
            raise XMLForbiddenError("XML document type declarations (DOCTYPE) are not accepted.")


def parse_bytes(data, encoding=None):
    """Parse XML bytes with the hardened parser and refuse DOCTYPEs."""
    parser = make_parser(encoding=encoding) if encoding else make_parser()
    root = etree.fromstring(data, parser)
    reject_doctype(root=root)
    return root
