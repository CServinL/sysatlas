"""Render a SequenceDiagram to draw.io / mxGraph XML."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET

from sysatlas._render import _VIEWER_CONFIG, _html_shell, _viewer_tag
from sysatlas._sequence_layout import (
    ACTOR_H, ACTOR_W, FRAME_HEADER_H, compute_sequence_layout,
)

_ACTOR_STYLE = (
    "rounded=0;whiteSpace=wrap;html=1;fillColor={fill};strokeColor=#374151;"
    "fontFamily=monospace;fontSize=11;"
)
_LIFELINE_STYLE = (
    "endArrow=none;dashed=1;strokeColor=#9ca3af;strokeWidth=1;"
)
_ACTIVATION_STYLE = (
    "rounded=0;whiteSpace=wrap;html=1;fillColor=#fef9c3;strokeColor=#a16207;"
    "fontSize=9;"
)
_FRAME_STYLE = (
    "rounded=0;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#6366f1;"
    "strokeWidth=1.5;dashed=0;align=left;verticalAlign=top;fontSize=10;"
    "fontStyle=1;spacingLeft=6;spacingTop=2;"
)
_MSG_STYLE = {
    "sync":    "endArrow=block;endFill=1;html=1;rounded=0;strokeColor=#1f2937;fontSize=10;",
    "async":   "endArrow=open;html=1;rounded=0;strokeColor=#1f2937;fontSize=10;",
    "reply":   "endArrow=open;dashed=1;html=1;rounded=0;strokeColor=#6b7280;fontSize=10;",
    "create":  "endArrow=open;dashed=1;html=1;rounded=0;strokeColor=#15803d;fontSize=10;",
    "destroy": "endArrow=block;endFill=1;html=1;rounded=0;strokeColor=#b91c1c;fontSize=10;",
}


def _actor_fill(kind: str) -> str:
    return {
        "actor":    "#e0e7ff",
        "system":   "#dbeafe",
        "boundary": "#fce7f3",
        "control":  "#fef9c3",
        "entity":   "#dcfce7",
    }.get(kind, "#f1f5f9")


def build_sequence_xml(diagram) -> str:
    actor_x, msg_y, activation_rects, frame_rects, lifeline_bottom = compute_sequence_layout(diagram)

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

    for fr in frame_rects:
        label = f"{fr['kind']}" + (f" [{fr['label']}]" if fr["label"] else "")
        c = ET.SubElement(root, "mxCell", id=str(cell_id), value=label,
                          style=_FRAME_STYLE, vertex="1", parent="1")
        ET.SubElement(c, "mxGeometry", x=str(fr["x"]), y=str(fr["y"]),
                      width=str(fr["w"]), height=str(fr["h"]),
                      **{"as": "geometry"})
        cell_id += 1
        hdr = ET.SubElement(root, "mxCell", id=str(cell_id), value="",
                            style="rounded=0;fillColor=#e0e7ff;strokeColor=#6366f1;",
                            vertex="1", parent="1")
        ET.SubElement(hdr, "mxGeometry", x=str(fr["x"]), y=str(fr["y"]),
                      width=str(max(60, 8 * len(label) + 16)), height=str(FRAME_HEADER_H),
                      **{"as": "geometry"})
        cell_id += 1

    actor_top_id: dict[str, str] = {}
    actor_bottom_id: dict[str, str] = {}
    for name, actor in diagram.actors.items():
        x = actor_x[name]
        fill = _actor_fill(actor.kind)
        label = (actor.label or name)
        c = ET.SubElement(root, "mxCell", id=str(cell_id), value=label,
                          style=_ACTOR_STYLE.format(fill=fill),
                          vertex="1", parent="1")
        ET.SubElement(c, "mxGeometry", x=str(x), y="40",
                      width=str(ACTOR_W), height=str(ACTOR_H),
                      **{"as": "geometry"})
        actor_top_id[name] = str(cell_id)
        cell_id += 1

        bot = ET.SubElement(root, "mxCell", id=str(cell_id), value=label,
                            style=_ACTOR_STYLE.format(fill=fill),
                            vertex="1", parent="1")
        ET.SubElement(bot, "mxGeometry", x=str(x), y=str(lifeline_bottom),
                      width=str(ACTOR_W), height=str(ACTOR_H),
                      **{"as": "geometry"})
        actor_bottom_id[name] = str(cell_id)
        cell_id += 1

        lifeline = ET.SubElement(root, "mxCell", id=str(cell_id), value="",
                                 style=_LIFELINE_STYLE, edge="1",
                                 source=actor_top_id[name],
                                 target=actor_bottom_id[name], parent="1")
        ET.SubElement(lifeline, "mxGeometry", relative="1", **{"as": "geometry"})
        cell_id += 1

    for rect in activation_rects:
        c = ET.SubElement(root, "mxCell", id=str(cell_id), value="",
                          style=_ACTIVATION_STYLE, vertex="1", parent="1")
        ET.SubElement(c, "mxGeometry", x=str(rect["x"]), y=str(rect["y"]),
                      width=str(rect["w"]), height=str(rect["h"]),
                      **{"as": "geometry"})
        cell_id += 1

    msgs = sorted(diagram.messages, key=lambda m: m.order)
    for m in msgs:
        y = msg_y[m.order]
        sx = actor_x[m.source] + ACTOR_W // 2
        tx = actor_x[m.target] + ACTOR_W // 2
        style = _MSG_STYLE.get(m.kind, _MSG_STYLE["sync"])
        c = ET.SubElement(root, "mxCell", id=str(cell_id), value=m.label,
                          style=style, edge="1", parent="1")
        geo = ET.SubElement(c, "mxGeometry", relative="1", **{"as": "geometry"})
        ET.SubElement(geo, "mxPoint", x=str(sx), y=str(y), **{"as": "sourcePoint"})
        ET.SubElement(geo, "mxPoint", x=str(tx), y=str(y), **{"as": "targetPoint"})
        cell_id += 1

    return ET.tostring(root_el, encoding="unicode", xml_declaration=False)


def render_sequence(diagram, title: str = "", viewer: str = "cdn") -> str:
    xml = build_sequence_xml(diagram)
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
