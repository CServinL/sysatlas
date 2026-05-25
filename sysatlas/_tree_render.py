"""Render a TreeDiagram to draw.io / mxGraph XML.

Reuses the HTML shell from `_render` and emits nodes/edges with the
positions computed by `_tree_layout`.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET

from sysatlas._render import VIEWER_CDN, _VIEWER_CONFIG, _html_shell, _viewer_tag
from sysatlas._tree_layout import NODE_H, NODE_W, compute_tree_layout

_NODE_STYLE = (
    "rounded=1;whiteSpace=wrap;html=1;arcSize=14;"
    "fillColor={fill};strokeColor=#374151;fontFamily=monospace;fontSize=11;"
)
_EDGE_STYLE = (
    "rounded=1;exitX=0.5;exitY=1.0;exitDx=0;exitDy=0;"
    "entryX=0.5;entryY=0.0;entryDx=0;entryDy=0;"
    "strokeColor=#6b7280;strokeWidth=1.5;endArrow=none;"
)


def build_tree_xml(diagram, flavor: str = "generic") -> str:
    """Build mxGraph XML from a TreeDiagram instance."""
    nodes_dict = {n: tn.model_dump(exclude={"name"}) for n, tn in diagram.nodes.items()}
    edges_list = [
        {"source": tn.parent, "target": n}
        for n, tn in diagram.nodes.items()
        if tn.parent is not None
    ]
    pos, routes = compute_tree_layout(nodes_dict, edges_list, flavor=flavor)

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
    node_cell_ids: dict[str, str] = {}

    for name, tn in diagram.nodes.items():
        x, y = pos.get(name, (0, 0))
        fill = tn.color or _default_fill(tn.kind)
        label = (tn.label or name).replace("\n", "<br>")
        cell = ET.SubElement(
            root, "mxCell",
            id=str(cell_id), value=label,
            style=_NODE_STYLE.format(fill=fill),
            vertex="1", parent="1",
        )
        ET.SubElement(
            cell, "mxGeometry",
            x=str(x), y=str(y),
            width=str(NODE_W), height=str(NODE_H),
            **{"as": "geometry"},
        )
        node_cell_ids[name] = str(cell_id)
        cell_id += 1

    for (s, t), route in routes.items():
        src_id = node_cell_ids.get(s)
        tgt_id = node_cell_ids.get(t)
        if not src_id or not tgt_id:
            continue
        cell = ET.SubElement(
            root, "mxCell",
            id=str(cell_id), value="",
            style=_EDGE_STYLE,
            edge="1", source=src_id, target=tgt_id, parent="1",
        )
        geo = ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
        pts = route.get("points", [])
        if pts:
            arr = ET.SubElement(geo, "Array", **{"as": "points"})
            for wx, wy in pts:
                ET.SubElement(arr, "mxPoint", x=str(wx), y=str(wy))
        cell_id += 1

    return ET.tostring(root_el, encoding="unicode", xml_declaration=False)


def _default_fill(kind: str) -> str:
    return {
        "root": "#dbeafe",
        "branch": "#dcfce7",
        "leaf": "#fef9c3",
    }.get(kind, "#f8fafc")


def render_tree(diagram, title: str = "", flavor: str = "generic",
                viewer: str = "cdn") -> str:
    xml = build_tree_xml(diagram, flavor=flavor)
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
