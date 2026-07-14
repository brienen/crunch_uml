"""Unit tests for the EA <-> canonical geometry conversions.

The reference strings come verbatim from the fixtures in test/data (see the
module docstring of crunch_uml.ea_geometry for the conventions).
"""

from crunch_uml import ea_geometry as geo


def test_parse_xmi_node_geometry():
    parsed = geo.parse_xmi_node_geometry("Left=90;Top=30;Right=210;Bottom=90;")
    assert parsed == {"x": 90.0, "y": 30.0, "width": 120.0, "height": 60.0}


def test_parse_xmi_node_geometry_on_edge_string_returns_none():
    assert geo.parse_xmi_node_geometry("SX=0;SY=0;EX=0;EY=0;EDGE=4;$LLB=;Path=;") is None
    assert geo.parse_xmi_node_geometry(None) is None
    assert geo.parse_xmi_node_geometry("") is None


def test_format_xmi_node_geometry_roundtrip():
    original = "Left=280;Top=30;Right=389;Bottom=110;"
    parsed = geo.parse_xmi_node_geometry(original)
    assert geo.format_xmi_node_geometry(**parsed) == original


def test_parse_qea_rect_flips_negative_top_bottom():
    # BeschermdeStatus in Monumenten.qea: RectTop=-30, RectLeft=280,
    # RectRight=389, RectBottom=-110 == XMI "Left=280;Top=30;Right=389;Bottom=110;"
    parsed = geo.parse_qea_rect(280, -30, 389, -110)
    assert parsed == {"x": 280.0, "y": 30.0, "width": 109.0, "height": 80.0}
    assert parsed == geo.parse_xmi_node_geometry("Left=280;Top=30;Right=389;Bottom=110;")


def test_format_qea_rect_roundtrip():
    rect = geo.format_qea_rect(280.0, 30.0, 109.0, 80.0)
    assert rect == {"RectLeft": 280.0, "RectTop": -30.0, "RectRight": 389.0, "RectBottom": -110.0}
    assert geo.parse_qea_rect(rect["RectLeft"], rect["RectTop"], rect["RectRight"], rect["RectBottom"]) == {
        "x": 280.0,
        "y": 30.0,
        "width": 109.0,
        "height": 80.0,
    }


def test_parse_qea_rect_none_values():
    assert geo.parse_qea_rect(None, -30, 389, -110) is None


def test_split_path_from_xmi_geometry():
    geometry = (
        "SCTR=1;SCME=1;SX=0;SY=0;EX=0;EY=0;EDGE=2;SCTR.LEFT=225;SCTR.TOP=-205;"
        "SCTR.RIGHT=256;SCTR.BOTTOM=-190;$LLB=;LLT=;LMT=;LMB=;LRT=;LRB=;IRHS=;ILHS=;"
        "Path=247:-205$256:-205$256:-190$247:-190$;"
    )
    base, path = geo.split_path_from_xmi_geometry(geometry)
    assert base.endswith("ILHS=;")
    assert "Path=" not in base
    assert path == "247:-205$256:-205$256:-190$247:-190$"

    base_empty, path_empty = geo.split_path_from_xmi_geometry("SX=0;SY=0;EX=0;EY=0;EDGE=4;$LLB=;ILHS=;Path=;")
    assert path_empty == ""
    assert geo.parse_path(path_empty, geo.XMI_PATH_SEPARATOR) == []

    no_path, none_path = geo.split_path_from_xmi_geometry("EDGE=1;$LLB=;")
    assert no_path == "EDGE=1;$LLB=;"
    assert none_path is None


def test_parse_path_flips_y_sign():
    assert geo.parse_path("247:-205$256:-205$", geo.XMI_PATH_SEPARATOR) == [
        {"x": 247.0, "y": 205.0},
        {"x": 256.0, "y": 205.0},
    ]
    # QEA uses ';' between pairs (t_diagramlinks.Path)
    assert geo.parse_path("500:-680;", geo.QEA_PATH_SEPARATOR) == [{"x": 500.0, "y": 680.0}]


def test_format_path_roundtrip_both_separators():
    waypoints = [{"x": 247.0, "y": 205.0}, {"x": 256.0, "y": 205.0}]
    assert geo.format_path(waypoints, geo.XMI_PATH_SEPARATOR) == "247:-205$256:-205$"
    assert geo.format_path(waypoints, geo.QEA_PATH_SEPARATOR) == "247:-205;256:-205;"
    assert geo.format_path([], geo.XMI_PATH_SEPARATOR) == ""


def test_waypoints_json_roundtrip():
    waypoints = [{"x": 580.0, "y": 820.0}]
    assert geo.waypoints_from_json(geo.waypoints_to_json(waypoints)) == waypoints
    assert geo.waypoints_to_json([]) is None
    assert geo.waypoints_from_json(None) == []
    assert geo.waypoints_from_json("not json") == []


def test_split_hidden_from_style():
    style = "Mode=3;EOID=0E0961A5;SOID=0E0961A5;Color=-1;LWidth=0;Hidden=1;"
    base, hidden = geo.split_hidden_from_style(style)
    assert base == "Mode=3;EOID=0E0961A5;SOID=0E0961A5;Color=-1;LWidth=0;"
    assert hidden is True

    base0, hidden0 = geo.split_hidden_from_style("Mode=3;EOID=82633E89;SOID=608C235E;Color=-1;LWidth=0;Hidden=0;")
    assert hidden0 is False
    # QEA style strings carry no Hidden component
    base_none, hidden_none = geo.split_hidden_from_style("Mode=3;EOID=82633E89;SOID=608C235E;Color=-1;LWidth=0;")
    assert hidden_none is None
    assert base_none == "Mode=3;EOID=82633E89;SOID=608C235E;Color=-1;LWidth=0;"


def test_compose_xmi_edge_geometry_and_style():
    # QEA row for connector {15326145-...} in InkomenMIM.qea reassembles to
    # the exact XMI attribute values of the same connector in InkomenMIM.xml.
    qea_geometry = (
        "EDGE=1;SX=0;SY=0;EX=0;EY=0;$LLB=CX=17:CY=14:OX=0:OY=0:HDN=0:BLD=0:ITA=0:UND=0:CLR=-1:ALN=1:DIR=0:ROT=0;"
        "LLT=;LMT=CX=154:CY=14:OX=-9:OY=6:HDN=0:BLD=0:ITA=0:UND=0:CLR=-1:ALN=1:DIR=0:ROT=0;"
        "LMB=CX=58:CY=14:OX=24:OY=-120:HDN=1:BLD=0:ITA=0:UND=0:CLR=-1:ALN=1:DIR=0:ROT=0;"
        "LRT=;LRB=CX=17:CY=14:OX=0:OY=0:HDN=0:BLD=0:ITA=0:UND=0:CLR=-1:ALN=1:DIR=0:ROT=0;IRHS=;ILHS=;"
    )
    waypoints = geo.parse_path("500:-680;", geo.QEA_PATH_SEPARATOR)
    assert geo.compose_xmi_edge_geometry(qea_geometry, waypoints) == qea_geometry + "Path=500:-680$;"

    qea_style = "Mode=3;EOID=82633E89;SOID=608C235E;Color=-1;LWidth=0;"
    assert geo.compose_xmi_edge_style(qea_style, False) == qea_style + "Hidden=0;"
    assert geo.compose_xmi_edge_style(qea_style, True) == qea_style + "Hidden=1;"
    # A style that already carries Hidden stays untouched
    assert geo.compose_xmi_edge_style(qea_style + "Hidden=1;", True) == qea_style + "Hidden=1;"


def test_compose_xmi_edge_geometry_without_raw_geometry():
    composed = geo.compose_xmi_edge_geometry(None, [{"x": 10.0, "y": 20.0}])
    assert composed.startswith("SX=0;SY=0;")
    assert composed.endswith("Path=10:-20$;")


def test_format_num():
    assert geo.format_num(580.0) == "580"
    assert geo.format_num(-205.0) == "-205"
    assert geo.format_num(10.5) == "10.5"
