"""Render an ERDiagram to draw.io / mxGraph XML."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET

from sysatlas._er_layout import ATTR_ROW_H, HEADER_H, compute_er_layout
from sysatlas._render import _VIEWER_CONFIG, _html_shell, _viewer_tag

_ENTITY_HEADER_STYLE = (
    "rounded=0;whiteSpace=wrap;html=1;fillColor={fill};strokeColor=#374151;"
    "fontFamily=monospace;fontSize=12;fontStyle=1;align=center;"
)
_ATTR_STYLE = (
    "text;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;"
    "whiteSpace=wrap;html=1;fontFamily=monospace;fontSize=10;spacingLeft=8;"
)
_ENTITY_BORDER_STYLE = (
    "rounded=0;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#374151;"
    "strokeWidth={sw};"
)
_REL_STYLE = (
    "endArrow=none;html=1;rounded=0;strokeColor=#1f2937;strokeWidth=1.5;"
    "fontSize=10;"
)


def _entity_fill(is_weak: bool) -> str:
    return "#fef3c7" if is_weak else "#dbeafe"


def build_er_xml(diagram) -> str:
    pos, size, routes = compute_er_layout(diagram)

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
    entity_cell_ids: dict[str, str] = {}

    for name, entity in diagram.entities.items():
        x, y = pos[name]
        w, h = size[name]

        border = ET.SubElement(root, "mxCell", id=str(cell_id), value="",
                               style=_ENTITY_BORDER_STYLE.format(sw=("2" if entity.is_weak else "1.5")),
                               vertex="1", parent="1")
        ET.SubElement(border, "mxGeometry", x=str(x), y=str(y),
                      width=str(w), height=str(h),
                      **{"as": "geometry"})
        entity_cell_ids[name] = str(cell_id)
        cell_id += 1

        header = ET.SubElement(root, "mxCell", id=str(cell_id),
                               value=(entity.label or entity.name),
                               style=_ENTITY_HEADER_STYLE.format(fill=_entity_fill(entity.is_weak)),
                               vertex="1", parent="1")
        ET.SubElement(header, "mxGeometry", x=str(x), y=str(y),
                      width=str(w), height=str(HEADER_H),
                      **{"as": "geometry"})
        cell_id += 1

        for i, attr in enumerate(entity.attributes):
            marker = ""
            if attr.is_key:
                marker = "🔑 "
            elif attr.is_required:
                marker = "● "
            else:
                marker = "○ "
            type_str = f": {attr.type}" if attr.type else ""
            text = f"{marker}{attr.name}{type_str}"
            row = ET.SubElement(root, "mxCell", id=str(cell_id), value=text,
                                style=_ATTR_STYLE, vertex="1", parent="1")
            ET.SubElement(row, "mxGeometry",
                          x=str(x), y=str(y + HEADER_H + i * ATTR_ROW_H),
                          width=str(w), height=str(ATTR_ROW_H),
                          **{"as": "geometry"})
            cell_id += 1

    for (src, tgt, _key), r in routes.items():
        s_id = entity_cell_ids.get(src)
        t_id = entity_cell_ids.get(tgt)
        if not s_id or not t_id:
            continue
        label = f"{r['source_card']} {r['label']} {r['target_card']}"
        style = (_REL_STYLE
                 + f"exitX={r['exit_x']};exitY={r['exit_y']};exitDx=0;exitDy=0;"
                 + f"entryX={r['entry_x']};entryY={r['entry_y']};entryDx=0;entryDy=0;")
        c = ET.SubElement(root, "mxCell", id=str(cell_id), value=label,
                          style=style, edge="1", source=s_id, target=t_id, parent="1")
        geo = ET.SubElement(c, "mxGeometry", relative="1", **{"as": "geometry"})
        arr = ET.SubElement(geo, "Array", **{"as": "points"})
        for px, py in r["points"]:
            ET.SubElement(arr, "mxPoint", x=str(px), y=str(py))
        cell_id += 1

    return ET.tostring(root_el, encoding="unicode", xml_declaration=False)


def render_er(diagram, title: str = "", viewer: str = "cdn") -> str:
    xml = build_er_xml(diagram)
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
