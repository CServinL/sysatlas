"""Render a ClassDiagram to draw.io / mxGraph XML."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET

from sysatlas._class_layout import HEADER_H, ROW_H, SECTION_PAD, compute_class_layout
from sysatlas._render import _VIEWER_CONFIG, _html_shell, _viewer_tag

_HEADER_STYLE = (
    "rounded=0;whiteSpace=wrap;html=1;fillColor={fill};strokeColor=#374151;"
    "fontFamily=monospace;fontSize=12;fontStyle={fs};align=center;"
)
_ROW_STYLE = (
    "text;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;"
    "whiteSpace=wrap;html=1;fontFamily=monospace;fontSize=10;spacingLeft=8;"
)
_DIVIDER_STYLE = (
    "rounded=0;fillColor=#cbd5e1;strokeColor=#cbd5e1;"
)
_BORDER_STYLE = (
    "rounded=0;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#374151;strokeWidth=1.5;"
)
_VIS_GLYPH = {"public": "+", "private": "-", "protected": "#", "package": "~"}
_REL_STYLE = {
    "inheritance":    "endArrow=block;endFill=0;html=1;rounded=0;strokeColor=#1f2937;strokeWidth=1.5;",
    "implementation": "endArrow=block;endFill=0;dashed=1;html=1;rounded=0;strokeColor=#1f2937;strokeWidth=1.5;",
    "composition":    "endArrow=open;startArrow=diamondThin;startFill=1;startSize=14;html=1;rounded=0;strokeColor=#1f2937;",
    "aggregation":    "endArrow=open;startArrow=diamondThin;startFill=0;startSize=14;html=1;rounded=0;strokeColor=#1f2937;",
    "association":    "endArrow=open;html=1;rounded=0;strokeColor=#1f2937;",
    "dependency":     "endArrow=open;dashed=1;html=1;rounded=0;strokeColor=#6b7280;",
}


def _header_fill(kind: str) -> tuple[str, str]:
    """Return (fill_color, font_style)."""
    return {
        "class":     ("#dbeafe", "1"),
        "abstract":  ("#dbeafe", "3"),
        "interface": ("#e0e7ff", "1"),
        "enum":      ("#fef3c7", "1"),
    }.get(kind, ("#dbeafe", "1"))


def build_class_xml(diagram) -> str:
    pos, size, routes = compute_class_layout(diagram)

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
    class_cell_ids: dict[str, str] = {}

    for name, klass in diagram.classes.items():
        x, y = pos[name]
        w, h = size[name]

        border = ET.SubElement(root, "mxCell", id=str(cell_id), value="",
                               style=_BORDER_STYLE, vertex="1", parent="1")
        ET.SubElement(border, "mxGeometry", x=str(x), y=str(y),
                      width=str(w), height=str(h), **{"as": "geometry"})
        class_cell_ids[name] = str(cell_id)
        cell_id += 1

        fill, fs = _header_fill(klass.kind)
        header_label = (klass.label or klass.name)
        if klass.kind == "interface":
            header_label = "«interface»<br>" + header_label
        elif klass.kind == "abstract":
            header_label = "«abstract»<br>" + header_label
        elif klass.kind == "enum":
            header_label = "«enum»<br>" + header_label
        header = ET.SubElement(root, "mxCell", id=str(cell_id),
                               value=header_label,
                               style=_HEADER_STYLE.format(fill=fill, fs=fs),
                               vertex="1", parent="1")
        ET.SubElement(header, "mxGeometry", x=str(x), y=str(y),
                      width=str(w), height=str(HEADER_H), **{"as": "geometry"})
        cell_id += 1

        attr_y = y + HEADER_H
        for i, a in enumerate(klass.attributes):
            glyph = _VIS_GLYPH.get(a.visibility, "+")
            type_str = f": {a.type}" if a.type else ""
            text = f"{glyph} {a.name}{type_str}"
            if a.is_static:
                text = f"<u>{text}</u>"
            row = ET.SubElement(root, "mxCell", id=str(cell_id), value=text,
                                style=_ROW_STYLE, vertex="1", parent="1")
            ET.SubElement(row, "mxGeometry", x=str(x), y=str(attr_y + i * ROW_H),
                          width=str(w), height=str(ROW_H), **{"as": "geometry"})
            cell_id += 1
        attrs_h = max(len(klass.attributes), 1) * ROW_H
        divider_y = attr_y + attrs_h
        div = ET.SubElement(root, "mxCell", id=str(cell_id), value="",
                            style=_DIVIDER_STYLE, vertex="1", parent="1")
        ET.SubElement(div, "mxGeometry", x=str(x), y=str(divider_y),
                      width=str(w), height=str(SECTION_PAD), **{"as": "geometry"})
        cell_id += 1

        meth_y = divider_y + SECTION_PAD
        for i, m in enumerate(klass.methods):
            glyph = _VIS_GLYPH.get(m.visibility, "+")
            params = ", ".join(m.params)
            ret = f": {m.return_type}" if m.return_type else ""
            text = f"{glyph} {m.name}({params}){ret}"
            if m.is_static:
                text = f"<u>{text}</u>"
            if m.is_abstract:
                text = f"<i>{text}</i>"
            row = ET.SubElement(root, "mxCell", id=str(cell_id), value=text,
                                style=_ROW_STYLE, vertex="1", parent="1")
            ET.SubElement(row, "mxGeometry", x=str(x), y=str(meth_y + i * ROW_H),
                          width=str(w), height=str(ROW_H), **{"as": "geometry"})
            cell_id += 1

    for r in routes:
        s_id = class_cell_ids.get(r["source"])
        t_id = class_cell_ids.get(r["target"])
        if not s_id or not t_id:
            continue
        style = _REL_STYLE.get(r["kind"], _REL_STYLE["association"])
        label = r["label"]
        c = ET.SubElement(root, "mxCell", id=str(cell_id), value=label,
                          style=style + "fontSize=10;", edge="1",
                          source=s_id, target=t_id, parent="1")
        ET.SubElement(c, "mxGeometry", relative="1", **{"as": "geometry"})
        cell_id += 1

        for mult, off_x in ((r["source_mult"], -0.45), (r["target_mult"], 0.45)):
            if not mult:
                continue
            lbl = ET.SubElement(root, "mxCell", id=str(cell_id), value=mult,
                                style="text;html=1;align=center;fontSize=9;",
                                vertex="1", connectable="0", parent="1")
            geo = ET.SubElement(lbl, "mxGeometry",
                                x=str(off_x), relative="1", **{"as": "geometry"})
            ET.SubElement(geo, "mxPoint", x="0", y="0", **{"as": "offset"})
            cell_id += 1

    return ET.tostring(root_el, encoding="unicode", xml_declaration=False)


def render_class(diagram, title: str = "", viewer: str = "cdn") -> str:
    xml = build_class_xml(diagram)
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
