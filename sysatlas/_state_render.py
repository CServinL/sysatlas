"""Render a StateDiagram to draw.io / mxGraph XML."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET

from sysatlas._render import _VIEWER_CONFIG, _html_shell, _viewer_tag
from sysatlas._state_layout import compute_state_layout

_STATE_STYLE = (
    "rounded=1;arcSize=30;whiteSpace=wrap;html=1;fillColor=#dbeafe;"
    "strokeColor=#374151;fontFamily=monospace;fontSize=11;"
)
_COMPOSITE_STYLE = (
    "rounded=1;arcSize=18;whiteSpace=wrap;html=1;fillColor=#f1f5f9;"
    "strokeColor=#374151;fontFamily=monospace;fontSize=11;fontStyle=1;"
    "align=left;verticalAlign=top;spacingLeft=8;spacingTop=4;"
)
_INITIAL_STYLE = (
    "ellipse;whiteSpace=wrap;html=1;fillColor=#1f2937;strokeColor=#1f2937;"
)
_FINAL_STYLE = (
    "ellipse;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#1f2937;strokeWidth=3;"
)
_CHOICE_STYLE = (
    "rhombus;whiteSpace=wrap;html=1;fillColor=#fef9c3;strokeColor=#a16207;fontSize=10;"
)
_TRANSITION_STYLE = (
    "endArrow=block;endFill=1;html=1;rounded=1;strokeColor=#1f2937;"
    "strokeWidth=1.5;fontSize=10;"
)


def build_state_xml(diagram) -> str:
    pos, size, kind, routes = compute_state_layout(diagram)

    root_el = ET.Element(
        "mxGraphModel",
        dx="1422", dy="762", grid="1", gridSize="10", guides="1", tooltips="1",
        connect="1", arrows="1", fold="1", page="1", pageScale="1",
        pageWidth="1169", pageHeight="827", math="0", shadow="0",
    )
    root = ET.SubElement(root_el, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    cell_id = 2
    state_cell_ids: dict[str, str] = {}

    composites = [n for n, k in kind.items() if k == "composite"]
    others = [n for n in pos if n not in composites]

    for name in composites:
        x, y = pos[name]
        w, h = size[name]
        s = diagram.states[name]
        label = (s.label or name)
        c = ET.SubElement(root, "mxCell", id=str(cell_id), value=label,
                          style=_COMPOSITE_STYLE, vertex="1", parent="1")
        ET.SubElement(c, "mxGeometry", x=str(x), y=str(y),
                      width=str(w), height=str(h), **{"as": "geometry"})
        state_cell_ids[name] = str(cell_id)
        cell_id += 1

    for name in others:
        x, y = pos[name]
        w, h = size[name]
        s = diagram.states[name]
        k = kind[name]
        if k == "initial":
            style, value = _INITIAL_STYLE, ""
        elif k == "final":
            style, value = _FINAL_STYLE, ""
        elif k == "choice":
            style, value = _CHOICE_STYLE, (s.label or "")
        else:
            extras: list[str] = []
            if s.entry_action:
                extras.append(f"entry / {s.entry_action}")
            if s.do_activity:
                extras.append(f"do / {s.do_activity}")
            if s.exit_action:
                extras.append(f"exit / {s.exit_action}")
            base = (s.label or name)
            value = base if not extras else base + "<br><i>" + "<br>".join(extras) + "</i>"
            style = _STATE_STYLE
        c = ET.SubElement(root, "mxCell", id=str(cell_id), value=value,
                          style=style, vertex="1", parent="1")
        ET.SubElement(c, "mxGeometry", x=str(x), y=str(y),
                      width=str(w), height=str(h), **{"as": "geometry"})
        state_cell_ids[name] = str(cell_id)
        cell_id += 1

    for r in routes:
        s_id = state_cell_ids.get(r["source"])
        t_id = state_cell_ids.get(r["target"])
        if not s_id or not t_id:
            continue
        c = ET.SubElement(root, "mxCell", id=str(cell_id), value=r["label"],
                          style=_TRANSITION_STYLE, edge="1",
                          source=s_id, target=t_id, parent="1")
        ET.SubElement(c, "mxGeometry", relative="1", **{"as": "geometry"})
        cell_id += 1

    return ET.tostring(root_el, encoding="unicode", xml_declaration=False)


def render_state(diagram, title: str = "", viewer: str = "cdn") -> str:
    xml = build_state_xml(diagram)
    xml_json = json.dumps(xml)
    config_json = json.dumps(_VIEWER_CONFIG)
    css = """
  body { display: flex; align-items: center; justify-content: center; }
  #diagram {
    border: 1px solid #cbd5e1;
    box-shadow: 0 4px 16px rgba(0,0,0,0.12);
    background: #ffffff;
    overflow: hidden;
    position: relative;
  }
"""
    body = '<div id="diagram"></div>'
    script = f"""
var xmlStr = {xml_json};
var config = {config_json};
var container = document.getElementById('diagram');
function setSize() {{
  container.style.width  = Math.round(window.innerWidth  * 0.85) + 'px';
  container.style.height = Math.round(window.innerHeight * 0.85) + 'px';
}}
setSize();
if (typeof GraphViewer === 'undefined') {{
  container.innerHTML = '<div style="padding:32px;font-family:sans-serif;color:#7f1d1d;">' +
    '<strong>draw.io viewer not loaded.</strong></div>';
}} else {{
  var xmlDoc = mxUtils.parseXml(xmlStr);
  var viewer = new GraphViewer(container, xmlDoc.documentElement, config);
  setTimeout(function() {{ if (viewer && viewer.graph) viewer.graph.fit(); }}, 50);
  window.addEventListener('resize', function() {{
    setSize();
    if (viewer && viewer.graph) viewer.graph.fit();
  }});
}}
"""
    return _html_shell(title, body, _viewer_tag(viewer), script, css)
