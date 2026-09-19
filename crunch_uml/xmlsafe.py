"""One hardened lxml configuration for XML read from files crunch_uml does not control.

Model files (EA XMI) can come from anyone, so parsing must never:

* expand entities (no "billion laughs", no external entity file reads);
* touch the network (no DTD or schema fetches);
* grow unbounded trees (``huge_tree=False`` keeps libxml2's size and depth limits);
* accept a document type declaration at all: an EA export never has one.

The refusal is decided on the bytes, by :func:`scan_prolog`, *before* libxml2
sees them. Leaving it to the parsed tree made the error class depend on the
libxml2 build: a DOCTYPE whose internal subset holds a recursive entity is
refused by libxml2 itself with an ``XMLSyntaxError`` ("Detected an entity
reference loop"), and the tree that :func:`reject_doctype` wanted to inspect
never exists. Callers downstream translate the two into different messages
(``xml_forbidden`` versus ``xml_malformed``), so the same file must not answer
differently on another machine.

Use :func:`make_parser` for DOM parsing and :func:`reject_doctype` before and
after the parse. ``SAFE_PARSER_OPTIONS`` also serves ``iterparse`` callers.
"""

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

#: :func:`scan_prolog`: the root element starts and nothing forbidden preceded it.
PROLOG_CLEAN = "clean"
#: :func:`scan_prolog`: a markup declaration (DOCTYPE) precedes the root element.
PROLOG_DOCTYPE = "doctype"
#: :func:`scan_prolog`: the prolog does not end within the data offered.
PROLOG_TRUNCATED = "truncated"

# (byte-order mark, comment open, comment close, PI open, PI close, markup declaration)
_STR_MARKS = ("\ufeff", "<!--", "-->", "<?", "?>", "<!")
_BYTES_MARKS = (b"\xef\xbb\xbf", b"<!--", b"-->", b"<?", b"?>", b"<!")

_DOCTYPE_MESSAGE = "XML document type declarations (DOCTYPE) are not accepted."

# libxml2 words a refused DTD construct its own way, and not the same way in
# every version. These phrases occur for DTD and entity declarations only, never
# for an ordinary syntax error such as "Entity 'nbsp' not defined".
_DTD_SYNTAX_MARKERS = ("entity reference loop", "doctype", "internal subset", "external subset")


class XMLForbiddenError(CrunchException):
    """The XML document contains constructs that are refused for safety."""


def scan_prolog(data):
    """Walk the XML prolog of ``data`` (``str`` or ``bytes``) and say what it holds.

    The prolog is everything before the root element: an optional byte-order
    mark, whitespace, processing instructions (the XML declaration among them)
    and comments. The walk stops at the first character of the root element, so
    a ``<!DOCTYPE`` that merely appears *inside* the document - in a comment, in
    a CDATA section, in an attribute - is never mistaken for a declaration.

    Returns :data:`PROLOG_DOCTYPE` when a markup declaration precedes the root
    element, :data:`PROLOG_CLEAN` when the root element is reached without one,
    and :data:`PROLOG_TRUNCATED` when the prolog does not end within ``data``.

    The cost is proportional to the prolog, not to the document: a 41 MB export
    whose prolog is one XML declaration costs two ``startswith`` calls.
    """
    bom, comment_open, comment_close, pi_open, pi_close, declaration = (
        _BYTES_MARKS if isinstance(data, bytes) else _STR_MARKS
    )
    position = len(bom) if data.startswith(bom) else 0
    while True:
        while data[position : position + 1].isspace():
            position += 1
        if position >= len(data):
            return PROLOG_TRUNCATED
        if data.startswith(comment_open, position):
            end = data.find(comment_close, position + len(comment_open))
            if end < 0:
                return PROLOG_TRUNCATED
            position = end + len(comment_close)
        elif data.startswith(pi_open, position):
            end = data.find(pi_close, position + len(pi_open))
            if end < 0:
                return PROLOG_TRUNCATED
            position = end + len(pi_close)
        elif data.startswith(declaration, position):
            # A DOCTYPE is the only markup declaration XML allows here; anything
            # else opening with "<!" is untrusted input and refused with it.
            return PROLOG_DOCTYPE
        else:
            # The root element - or content that is no well-formed prolog at all,
            # which the parser reports far better than this walk could.
            return PROLOG_CLEAN


def make_parser(**overrides):
    """An ``etree.XMLParser`` with the hardened options (plus overrides such as ``encoding``)."""
    options = dict(SAFE_PARSER_OPTIONS)
    options["recover"] = False
    options.update(overrides)
    return etree.XMLParser(**options)


def reject_doctype(text=None, root=None):
    """Raise :class:`XMLForbiddenError` when a document type declaration is present.

    ``text`` (``str`` or ``bytes``) is walked over its prolog before parsing -
    see :func:`scan_prolog` - so the answer never depends on what this libxml2
    build makes of the declaration. ``root`` is the belt-and-braces check on a
    tree that did parse.
    """
    if text is not None and scan_prolog(text) == PROLOG_DOCTYPE:
        raise XMLForbiddenError(_DOCTYPE_MESSAGE)
    if root is not None:
        docinfo = root.getroottree().docinfo
        if docinfo.doctype or docinfo.internalDTD is not None or docinfo.externalDTD is not None:
            raise XMLForbiddenError(_DOCTYPE_MESSAGE)


def parse_bytes(data, encoding=None):
    """Parse XML bytes with the hardened parser and refuse DOCTYPEs."""
    reject_doctype(text=data)
    parser = make_parser(encoding=encoding) if encoding else make_parser()
    try:
        root = etree.fromstring(data, parser)
    except etree.XMLSyntaxError as e:
        # The net under the prolog walk: a DTD construct libxml2 refuses on its
        # own stays a refusal of the construct, not a report of broken XML.
        message = str(e).lower()
        if any(marker in message for marker in _DTD_SYNTAX_MARKERS):
            raise XMLForbiddenError(_DOCTYPE_MESSAGE) from e
        raise
    reject_doctype(root=root)
    return root
