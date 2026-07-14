"""Conversions between Enterprise Architect diagram geometry conventions and
the canonical coordinate system stored in the database.

Canonical system: origin in the top-left corner of the diagram, x grows to
the right, y grows downwards, all values positive (see the "Canonical diagram
geometry" note in :mod:`crunch_uml.db`).

EA conventions, verified against real exports:

* XMI extension *node* geometry (``Left=90;Top=30;Right=210;Bottom=90;``)
  uses positive Top/Bottom values.
* QEA ``t_diagramobjects`` stores negative RectTop/RectBottom (screen y is
  negated): ``x=RectLeft``, ``y=-RectTop``, ``width=RectRight-RectLeft``,
  ``height=RectTop-RectBottom``.
* *Edge* waypoints have negative y in both sources. XMI keeps the path inside
  the geometry attribute (``...;ILHS=;Path=x:y$x:y$;``) with ``$`` between
  pairs; QEA stores it in a separate ``Path`` column with ``;`` between pairs
  (``x:y;x:y;``).
* The XMI edge style string ends with ``Hidden=0;``/``Hidden=1;`` whereas QEA
  stores Hidden as a separate column.

The canonical database form mirrors the QEA columns: ``ea_geometry`` without
the Path part, ``ea_style`` without the Hidden part, and ``waypoints`` and
``hidden`` as separate fields. Both parsers normalize to this form, so the
same model imported from XMI or from a QEA repository yields identical rows;
renderers reassemble the EA strings from the parts.
"""

import json
import logging
import re

logger = logging.getLogger()

# x:y pair, e.g. "247:-205"; EA writes integers but be lenient about floats.
_PATH_PAIR_RE = re.compile(r"^(-?\d+(?:\.\d+)?):(-?\d+(?:\.\d+)?)$")
_NODE_GEOMETRY_RE = re.compile(
    r"Left=(-?\d+(?:\.\d+)?);Top=(-?\d+(?:\.\d+)?);Right=(-?\d+(?:\.\d+)?);Bottom=(-?\d+(?:\.\d+)?);"
)
_HIDDEN_RE = re.compile(r"Hidden=([01]);?")

XMI_PATH_SEPARATOR = "$"
QEA_PATH_SEPARATOR = ";"


def format_num(value):
    """Format a coordinate the way EA writes it: integral values without
    decimal point ("580", not "580.0")."""
    value = float(value)
    return str(int(value)) if value.is_integer() else str(value)


def parse_xmi_node_geometry(geometry):
    """Parse an XMI extension node geometry string into canonical values.

    Returns a dict with x/y/width/height, or None when the string does not
    contain the Left/Top/Right/Bottom block (e.g. it is an edge geometry).
    """
    if not geometry:
        return None
    match = _NODE_GEOMETRY_RE.search(geometry)
    if not match:
        return None
    left, top, right, bottom = (float(v) for v in match.groups())
    return {"x": left, "y": top, "width": right - left, "height": bottom - top}


def format_xmi_node_geometry(x, y, width, height):
    """Inverse of :func:`parse_xmi_node_geometry`."""
    return (
        f"Left={format_num(x)};Top={format_num(y)};" f"Right={format_num(x + width)};Bottom={format_num(y + height)};"
    )


def parse_qea_rect(rect_left, rect_top, rect_right, rect_bottom):
    """Parse QEA t_diagramobjects rectangle columns (negative top/bottom)
    into canonical values."""
    if rect_left is None or rect_top is None or rect_right is None or rect_bottom is None:
        return None
    return {
        "x": float(rect_left),
        "y": -float(rect_top),
        "width": float(rect_right) - float(rect_left),
        "height": float(rect_top) - float(rect_bottom),
    }


def format_qea_rect(x, y, width, height):
    """Inverse of :func:`parse_qea_rect`; returns RectLeft/RectTop/RectRight/RectBottom."""
    return {
        "RectLeft": x,
        "RectTop": -y,
        "RectRight": x + width,
        "RectBottom": -(y + height),
    }


def split_path_from_xmi_geometry(geometry):
    """Split an XMI edge geometry string into (base_without_path, path_str).

    The Path component is the last part of the geometry attribute
    ("...;ILHS=;Path=247:-205$256:-205$;"). path_str is returned without the
    "Path=" prefix and without the trailing ';' (None when no Path present).
    """
    if not geometry:
        return geometry, None
    idx = geometry.find("Path=")
    if idx < 0:
        return geometry, None
    base = geometry[:idx]
    path = geometry[idx + len("Path=") :]
    if path.endswith(";"):
        path = path[:-1]
    return base, path


def parse_path(path_str, pair_separator):
    """Parse an EA path string ("x:y$x:y$" or "x:y;x:y;") into canonical
    waypoints (y sign flipped). Returns a list of {"x": .., "y": ..} dicts;
    empty list when there are no waypoints."""
    waypoints = []
    if not path_str:
        return waypoints
    for pair in path_str.split(pair_separator):
        pair = pair.strip()
        if not pair:
            continue
        match = _PATH_PAIR_RE.match(pair)
        if not match:
            logger.debug(f"Could not parse path pair '{pair}' in path '{path_str}': skipped")
            continue
        waypoints.append({"x": float(match.group(1)), "y": -float(match.group(2))})
    return waypoints


def format_path(waypoints, pair_separator):
    """Inverse of :func:`parse_path`: canonical waypoints back to an EA path
    string (y sign flipped, trailing separator as EA writes it)."""
    if not waypoints:
        return ""
    return "".join(f"{format_num(wp['x'])}:{format_num(-wp['y'])}{pair_separator}" for wp in waypoints)


def waypoints_to_json(waypoints):
    """Serialize canonical waypoints for the database; None when empty so
    'no waypoints' and 'no information' look the same as absent geometry."""
    if not waypoints:
        return None
    return json.dumps(waypoints)


def waypoints_from_json(value):
    """Inverse of :func:`waypoints_to_json`."""
    if not value:
        return []
    try:
        waypoints = json.loads(value)
    except (TypeError, ValueError):
        logger.warning(f"Could not parse waypoints JSON '{value}': ignored")
        return []
    return waypoints if isinstance(waypoints, list) else []


def split_hidden_from_style(style):
    """Split an XMI edge style string into (style_without_hidden, hidden).

    hidden is None when the style carries no Hidden component (QEA styles
    never do; the flag lives in a separate column there).
    """
    if not style:
        return style, None
    match = _HIDDEN_RE.search(style)
    if not match:
        return style, None
    hidden = match.group(1) == "1"
    base = style[: match.start()] + style[match.end() :]
    return base, hidden


MINIMAL_EDGE_GEOMETRY = "SX=0;SY=0;EX=0;EY=0;EDGE=1;$LLB=;LLT=;LMT=;LMB=;LRT=;LRB=;IRHS=;ILHS=;"


def compose_xmi_edge_geometry(ea_geometry, waypoints):
    """Reassemble the XMI edge geometry attribute from the canonical parts.

    When no raw geometry was preserved a minimal valid string is generated,
    as EA requires the label placeholders to be present.
    """
    base = ea_geometry if ea_geometry else MINIMAL_EDGE_GEOMETRY
    return f"{base}Path={format_path(waypoints, XMI_PATH_SEPARATOR)};"


def compose_xmi_edge_style(ea_style, hidden):
    """Reassemble the XMI edge style attribute from the canonical parts."""
    base = ea_style or ""
    if "Hidden=" in base:
        return base
    if base and not base.endswith(";"):
        base += ";"
    return f"{base}Hidden={1 if hidden else 0};"
