"""Render a BPMNDiagram to draw.io / mxGraph XML."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET

from sysatlas._bpmn_layout import compute_bpmn_layout
from sysatlas._render import _FIT_JS, _VIEWER_CONFIG, _html_shell, _viewer_tag

_POOL_STYLE = (
    "shape=swimlane;startSize=30;horizontal=0;fillColor=#f8fafc;"
    "strokeColor=#475569;fontSize=11;fontStyle=1;align=center;"
)
_LANE_STYLE = (
    "shape=swimlane;startSize=24;horizontal=0;fillColor=#ffffff;"
    "strokeColor=#94a3b8;fontSize=10;align=center;"
)
_ACTIVITY_STYLE = {
    "task":         "rounded=1;arcSize=18;whiteSpace=wrap;html=1;fillColor=#dbeafe;strokeColor=#1e40af;fontSize=10;",
    "user_task":    "rounded=1;arcSize=18;whiteSpace=wrap;html=1;fillColor=#dcfce7;strokeColor=#15803d;fontSize=10;",
    "service_task": "rounded=1;arcSize=18;whiteSpace=wrap;html=1;fillColor=#fef3c7;strokeColor=#a16207;fontSize=10;",
    "subprocess":   "rounded=1;arcSize=18;whiteSpace=wrap;html=1;fillColor=#e9d5ff;strokeColor=#7e22ce;fontSize=10;strokeWidth=2;",
    "call_activity":"rounded=1;arcSize=18;whiteSpace=wrap;html=1;fillColor=#fce7f3;strokeColor=#be185d;fontSize=10;strokeWidth=2;",
}
_EVENT_STYLE = {
    "start":        "ellipse;whiteSpace=wrap;html=1;fillColor=#dcfce7;strokeColor=#15803d;strokeWidth=2;fontSize=9;",
    "end":          "ellipse;whiteSpace=wrap;html=1;fillColor=#fecaca;strokeColor=#b91c1c;strokeWidth=3;fontSize=9;",
    "intermediate": "ellipse;whiteSpace=wrap;html=1;fillColor=#fef3c7;strokeColor=#a16207;strokeWidth=2;fontSize=9;",
    "timer":        "ellipse;whiteSpace=wrap;html=1;fillColor=#fef3c7;strokeColor=#a16207;strokeWidth=2;fontSize=9;",
    "message":      "ellipse;whiteSpace=wrap;html=1;fillColor=#dbeafe;strokeColor=#1e40af;strokeWidth=2;fontSize=9;",
    "error":        "ellipse;whiteSpace=wrap;html=1;fillColor=#fecaca;strokeColor=#b91c1c;strokeWidth=2;fontSize=9;",
}
_GATEWAY_STYLE = {
    "exclusive":   "rhombus;whiteSpace=wrap;html=1;fillColor=#fef9c3;strokeColor=#a16207;fontSize=14;fontStyle=1;",
    "parallel":    "rhombus;whiteSpace=wrap;html=1;fillColor=#dcfce7;strokeColor=#15803d;fontSize=14;fontStyle=1;",
    "inclusive":   "rhombus;whiteSpace=wrap;html=1;fillColor=#fce7f3;strokeColor=#be185d;fontSize=14;fontStyle=1;",
    "event_based": "rhombus;whiteSpace=wrap;html=1;fillColor=#dbeafe;strokeColor=#1e40af;fontSize=14;fontStyle=1;",
}
_GATEWAY_GLYPH = {
    "exclusive": "✕", "parallel": "+", "inclusive": "O", "event_based": "◇",
}
_FLOW_STYLE = {
    "sequence":    "endArrow=block;endFill=1;html=1;rounded=0;strokeColor=#1f2937;fontSize=10;",
    "message":     "endArrow=open;dashed=1;html=1;rounded=0;strokeColor=#6366f1;fontSize=10;",
    "default":     "endArrow=block;endFill=1;html=1;rounded=0;strokeColor=#1f2937;startArrow=oval;startFill=0;startSize=8;fontSize=10;",
    "conditional": "endArrow=block;endFill=1;html=1;rounded=0;strokeColor=#1f2937;startArrow=diamondThin;startFill=0;startSize=10;fontSize=10;",
}


def build_bpmn_xml(diagram) -> str:
    pos, size, pool_rects, lane_rects, routes, all_nodes = compute_bpmn_layout(diagram)

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

    for p in pool_rects:
        c = ET.SubElement(root, "mxCell", id=str(cell_id), value=p["label"],
                          style=_POOL_STYLE, vertex="1", parent="1")
        ET.SubElement(c, "mxGeometry", x=str(p["x"]), y=str(p["y"]),
                      width=str(p["w"]), height=str(p["h"]), **{"as": "geometry"})
        cell_id += 1

    for l in lane_rects:
        c = ET.SubElement(root, "mxCell", id=str(cell_id), value=l["label"],
                          style=_LANE_STYLE, vertex="1", parent="1")
        ET.SubElement(c, "mxGeometry", x=str(l["x"]), y=str(l["y"]),
                      width=str(l["w"]), height=str(l["h"]), **{"as": "geometry"})
        cell_id += 1

    node_cell_ids: dict[str, str] = {}
    for name, (cat, kind) in all_nodes.items():
        if name not in pos:
            continue
        x, y = pos[name]
        w, h = size[name]
        if cat == "event":
            style = _EVENT_STYLE.get(kind, _EVENT_STYLE["intermediate"])
            label = diagram.events[name].label or name
        elif cat == "activity":
            style = _ACTIVITY_STYLE.get(kind, _ACTIVITY_STYLE["task"])
            label = diagram.activities[name].label or name
        else:
            style = _GATEWAY_STYLE.get(kind, _GATEWAY_STYLE["exclusive"])
            label = _GATEWAY_GLYPH.get(kind, "")
        c = ET.SubElement(root, "mxCell", id=str(cell_id), value=label,
                          style=style, vertex="1", parent="1")
        ET.SubElement(c, "mxGeometry", x=str(x), y=str(y),
                      width=str(w), height=str(h), **{"as": "geometry"})
        node_cell_ids[name] = str(cell_id)
        cell_id += 1

    for r in routes:
        s_id = node_cell_ids.get(r["source"])
        t_id = node_cell_ids.get(r["target"])
        if not s_id or not t_id:
            continue
        style = _FLOW_STYLE.get(r["kind"], _FLOW_STYLE["sequence"])
        c = ET.SubElement(root, "mxCell", id=str(cell_id), value=r["label"],
                          style=style, edge="1",
                          source=s_id, target=t_id, parent="1")
        ET.SubElement(c, "mxGeometry", relative="1", **{"as": "geometry"})
        cell_id += 1

    return ET.tostring(root_el, encoding="unicode", xml_declaration=False)


def render_bpmn(diagram, title: str = "", viewer: str = "cdn") -> str:
    xml = build_bpmn_xml(diagram)
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
{_FIT_JS}
var xmlStr = {xml_json};
var config = {config_json};
var container = document.getElementById('diagram');
function setSize() {{
  container.style.width  = Math.round(window.innerWidth  * 0.85) + 'px';
  container.style.height = Math.round(window.innerHeight * 0.85) + 'px';
}}
setSize();
if (typeof GraphViewer === 'undefined' || typeof mxUtils === 'undefined') {{
  container.innerHTML = '<div style="padding:32px;font-family:sans-serif;color:#7f1d1d;">' +
    '<strong>draw.io viewer not loaded.</strong></div>';
}} else {{
  var xmlDoc = mxUtils.parseXml(xmlStr);
  var viewer = new GraphViewer(container, xmlDoc.documentElement, config);
  setTimeout(function() {{ fitGraph(viewer, container); }}, 50);
  window.addEventListener('resize', function() {{
    setSize();
    fitGraph(viewer, container);
  }});
}}
"""
    return _html_shell(title, body, _viewer_tag(viewer), script, css)
