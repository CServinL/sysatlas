from __future__ import annotations

import json
import xml.etree.ElementTree as ET

from sysatlas._layout import NODE_W as _NODE_W, NODE_H as _NODE_H, compute_layout
from sysatlas._vendor import viewer_js, VIEWER_CDN

_PALETTE = [
    "#dbeafe", "#bbf7d0", "#fed7aa", "#e9d5ff",
    "#fef9c3", "#fecaca", "#a7f3d0", "#ddd6fe",
]

_NODE_STYLE  = "rounded=1;whiteSpace=wrap;html=1;arcSize=8;fillColor={fill};strokeColor=#374151;fontFamily=monospace;fontSize=11;"
_STUB_STYLE  = "rounded=1;whiteSpace=wrap;html=1;arcSize=8;dashed=1;fillColor=#f9fafb;strokeColor=#9ca3af;fontFamily=monospace;fontSize=10;fontColor=#6b7280;opacity=85;"
_GROUP_STYLE = "swimlane;startSize=24;fillColor={fill};strokeColor=#94a3b8;fontStyle=2;fontSize=11;opacity=20;"
# No edgeStyle — draw.io follows our explicit waypoints exactly.
_EDGE_BASE   = "rounded=1;exitX={ex};exitY={ey};exitDx=0;exitDy=0;entryX={en};entryY={ny};entryDx=0;entryDy=0;strokeColor={color};strokeWidth=1.5;fontSize=10;"
_EDGE_DASHED = "rounded=1;dashed=1;exitX={ex};exitY={ey};exitDx=0;exitDy=0;entryX={en};entryY={ny};entryDx=0;entryDy=0;strokeColor={color};strokeWidth=1.5;fontSize=10;"
_CONNECTOR_STYLE = "ellipse;whiteSpace=wrap;html=1;fillColor=#fef3c7;strokeColor=#92400e;fontFamily=monospace;fontSize=8;fontStyle=1;"
_CONNECTOR_W = 60
_CONNECTOR_H = 16
_CONNECTOR_GAP = 6

# Quality-attribute badges (ISO 25010). One letter + one color per category.
_QUALITY_LETTER = {
    "functional_suitability": "F",
    "performance_efficiency": "P",
    "compatibility":          "C",
    "usability":              "U",
    "reliability":            "R",
    "security":               "S",
    "maintainability":        "M",
    "portability":            "O",  # "O" for pOrtability (P taken)
}
_QUALITY_COLOR = {
    "functional_suitability": "#64748b",   # slate
    "performance_efficiency": "#a855f7",   # purple
    "compatibility":          "#0ea5e9",   # sky
    "usability":              "#10b981",   # emerald
    "reliability":            "#3b82f6",   # blue
    "security":               "#ef4444",   # red
    "maintainability":        "#84cc16",   # lime
    "portability":            "#f97316",   # orange
}
_BADGE_SIZE = 14
_BADGE_GAP = 2
_BADGE_STYLE = (
    "ellipse;whiteSpace=wrap;html=1;fillColor={fill};strokeColor=#ffffff;"
    "strokeWidth=1.5;fontColor=#ffffff;fontFamily=sans-serif;fontSize=9;fontStyle=1;"
)


def _badge_qualities(qualities: list[dict]) -> list[dict]:
    """Filter to qualities that warrant a badge (criticality >= high)."""
    return [q for q in (qualities or [])
            if q.get("criticality") in ("high", "critical")]

_VIEWER_CONFIG = {"nav": True, "resize": False, "toolbar": "zoom layers lightbox", "fit": True, "page": False}


def _palette(groups: dict[str, dict]) -> dict[str, str]:
    colors: dict[str, str] = {}
    idx = 0
    for name, cfg in groups.items():
        colors[name] = cfg.get("color") or _PALETTE[idx % len(_PALETTE)]
        idx += 1
    return colors


def build_xml(nodes: dict[str, dict], edges: list[dict], groups: dict[str, dict],
              layer_order: list[str], debug: bool = False,
              extra_edges: list[dict] | None = None) -> str:
    """Build mxGraph XML.

    `extra_edges` are appended AFTER the main layout/routing is done.
    They get rendered as straight dashed edges between known node positions
    without influencing the Sugiyama layer assignment. Each entry has
    `source`, `target`, optional `label`, optional `style`, optional `color`.
    """
    extra_edges = extra_edges or []
    colors = _palette(groups)
    pos, waypoints, node_heights = compute_layout(nodes, edges, layer_order, debug=debug)

    root_el = ET.Element("mxGraphModel", dx="1422", dy="762", grid="1",
                         gridSize="10", guides="1", tooltips="1",
                         connect="1", arrows="1", fold="1",
                         page="1", pageScale="1", pageWidth="1169",
                         pageHeight="827", math="0", shadow="0")
    root = ET.SubElement(root_el, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    # Separate hidden layer for trace overlays — togglable via the
    # viewer's layers toolbar button. Always declared so the toggle
    # always appears (even when there are zero overlays).
    ET.SubElement(root, "mxCell", id="trace-layer", parent="0",
                  value="Traces", visible="0")

    cell_id = 2
    group_cell_ids: dict[str, str] = {}

    for grp_name, grp_cfg in groups.items():
        grp_nodes = [n for n, d in nodes.items() if d.get("group") == grp_name]
        if not grp_nodes:
            continue
        xs = [pos[n][0] for n in grp_nodes]
        ys = [pos[n][1] for n in grp_nodes]
        pad = 24
        gx = min(xs) - pad
        gy = min(ys) - pad - 24
        gw = max(xs) + _NODE_W - min(xs) + pad * 2
        gh = max(pos[n][1] + node_heights.get(n, _NODE_H) for n in grp_nodes) - min(ys) + pad * 2 + 24
        fill = colors.get(grp_name, "#f1f5f9")
        cell = ET.SubElement(root, "mxCell",
                             id=str(cell_id),
                             value=grp_cfg.get("label", grp_name),
                             style=_GROUP_STYLE.format(fill=fill),
                             vertex="1", parent="1")
        ET.SubElement(cell, "mxGeometry",
                      x=str(gx), y=str(gy), width=str(gw), height=str(gh),
                      **{"as": "geometry"})
        group_cell_ids[grp_name] = str(cell_id)
        cell_id += 1

    node_cell_ids: dict[str, str] = {}
    for name, data in nodes.items():
        x, y = pos.get(name, (80, 80))
        grp = data.get("group")
        fill = colors.get(grp, "#f8fafc") if grp else "#f8fafc"
        label = (data.get("label") or name).replace("\n", "<br>")
        parent = group_cell_ids.get(grp, "1") if grp else "1"

        if grp and grp in group_cell_ids:
            tree = ET.ElementTree(root_el)
            geo = tree.find(f".//mxCell[@id='{group_cell_ids[grp]}']/mxGeometry")
            rx = x - int(geo.attrib["x"])
            ry = y - int(geo.attrib["y"])
        else:
            rx, ry = x, y

        h = node_heights.get(name, _NODE_H)
        is_stub = data.get("is_stub", False)
        if is_stub:
            defined_in = data.get("defined_in")
            stub_label = label
            if defined_in:
                stub_label = f"{label}<br><i style='font-size:8px'>→ {defined_in}</i>"
            cell = ET.SubElement(root, "mxCell",
                                 id=str(cell_id), value=stub_label,
                                 style=_STUB_STYLE,
                                 vertex="1", parent=parent)
        else:
            cell = ET.SubElement(root, "mxCell",
                                 id=str(cell_id), value=label,
                                 style=_NODE_STYLE.format(fill=fill),
                                 vertex="1", parent=parent)
        ET.SubElement(cell, "mxGeometry",
                      x=str(rx), y=str(ry),
                      width=str(_NODE_W), height=str(h),
                      **{"as": "geometry"})
        node_cell_ids[name] = str(cell_id)
        cell_id += 1

        # Quality-attribute badges: stacked horizontally along top-right.
        badges = _badge_qualities(data.get("qualities", []))
        for k, qa in enumerate(badges):
            cat = qa.get("category", "functional_suitability")
            color = _QUALITY_COLOR.get(cat, "#64748b")
            letter = _QUALITY_LETTER.get(cat, "?")
            bx = rx + _NODE_W - _BADGE_SIZE - 4 - k * (_BADGE_SIZE + _BADGE_GAP)
            by = ry - _BADGE_SIZE // 2
            badge = ET.SubElement(root, "mxCell",
                                  id=str(cell_id), value=letter,
                                  style=_BADGE_STYLE.format(fill=color),
                                  vertex="1", parent=parent)
            ET.SubElement(badge, "mxGeometry",
                          x=str(bx), y=str(by),
                          width=str(_BADGE_SIZE), height=str(_BADGE_SIZE),
                          **{"as": "geometry"})
            cell_id += 1

    # collect connector usage per node so multiple connectors don't overlap
    src_conn_offsets: dict[str, int] = {}
    tgt_conn_offsets: dict[str, int] = {}

    for edge in edges:
        src_name, tgt_name = edge["source"], edge["target"]
        src = node_cell_ids.get(src_name)
        tgt = node_cell_ids.get(tgt_name)
        if not src or not tgt:
            continue
        color  = edge.get("color") or "#6b7280"
        route  = waypoints.get((src_name, tgt_name), {})

        if route.get("connector"):
            # off-page connector pair: place in the gutter below source / above target
            sx, sy = pos.get(src_name, (0, 0))
            tx, ty = pos.get(tgt_name, (0, 0))
            s_off = src_conn_offsets.get(src_name, 0)
            t_off = tgt_conn_offsets.get(tgt_name, 0)
            src_conn_offsets[src_name] = s_off + 1
            tgt_conn_offsets[tgt_name] = t_off + 1

            # source-side: centered under source node, stacked horizontally if multiple
            scx = sx + (_NODE_W - _CONNECTOR_W) // 2 + s_off * (_CONNECTOR_W + 4)
            scy = sy + node_heights.get(src_name, _NODE_H) + _CONNECTOR_GAP
            # target-side: centered above target node, stacked horizontally
            tcx = tx + (_NODE_W - _CONNECTOR_W) // 2 + t_off * (_CONNECTOR_W + 4)
            tcy = ty - _CONNECTOR_H - _CONNECTOR_GAP

            label = edge.get("label") or ""
            src_label = f"&#x2937; {tgt_name}" + (f" [{label}]" if label else "")
            tgt_label = f"&#x2936; {src_name}" + (f" [{label}]" if label else "")

            # short connector line: from source bottom to source-side glyph,
            # and from target-side glyph to target top.
            # Render the glyph as a small ellipse vertex.
            src_glyph_id = str(cell_id)
            c = ET.SubElement(root, "mxCell",
                              id=src_glyph_id, value=src_label,
                              style=_CONNECTOR_STYLE,
                              vertex="1", parent="1")
            ET.SubElement(c, "mxGeometry",
                          x=str(scx), y=str(scy),
                          width=str(_CONNECTOR_W), height=str(_CONNECTOR_H),
                          **{"as": "geometry"})
            cell_id += 1

            tgt_glyph_id = str(cell_id)
            c = ET.SubElement(root, "mxCell",
                              id=tgt_glyph_id, value=tgt_label,
                              style=_CONNECTOR_STYLE,
                              vertex="1", parent="1")
            ET.SubElement(c, "mxGeometry",
                          x=str(tcx), y=str(tcy),
                          width=str(_CONNECTOR_W), height=str(_CONNECTOR_H),
                          **{"as": "geometry"})
            cell_id += 1

            # tiny connector stubs: source → src_glyph, tgt_glyph → target
            stub_style = _EDGE_BASE.format(color=color, ex=0.5, ey=1.0, en=0.5, ny=0.0)
            stub1 = ET.SubElement(root, "mxCell",
                                  id=str(cell_id), value="",
                                  style=stub_style,
                                  edge="1", source=src, target=src_glyph_id, parent="1")
            ET.SubElement(stub1, "mxGeometry", relative="1", **{"as": "geometry"})
            cell_id += 1

            stub2 = ET.SubElement(root, "mxCell",
                                  id=str(cell_id), value="",
                                  style=stub_style,
                                  edge="1", source=tgt_glyph_id, target=tgt, parent="1")
            ET.SubElement(stub2, "mxGeometry", relative="1", **{"as": "geometry"})
            cell_id += 1
            continue

        ex     = round(route.get("exit_x",  0.5), 4)
        ey     = round(route.get("exit_y",  1.0), 4)
        en     = round(route.get("entry_x", 0.5), 4)
        ny     = round(route.get("entry_y", 0.0), 4)
        tpl    = _EDGE_DASHED if edge.get("style") == "dashed" else _EDGE_BASE
        style  = tpl.format(color=color, ex=ex, ey=ey, en=en, ny=ny)
        cell   = ET.SubElement(root, "mxCell",
                               id=str(cell_id),
                               value=edge.get("label", ""),
                               style=style,
                               edge="1", source=src, target=tgt, parent="1")
        geo = ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
        pts = route.get("points", [])
        if pts:
            arr = ET.SubElement(geo, "Array", **{"as": "points"})
            for wx, wy in pts:
                ET.SubElement(arr, "mxPoint", x=str(wx), y=str(wy))

        # edge label geometry: position along edge + perpendicular offset
        if edge.get("label"):
            lx = route.get("label_x")
            ldx = route.get("label_dx", 0)
            ldy = route.get("label_dy", -10)
            if lx is not None:
                # mxGraph edge-label child geometry needs x in [-1,1] + offset
                lbl = ET.SubElement(root, "mxCell",
                                    id=str(cell_id + 10000),
                                    value=edge.get("label", ""),
                                    style="edgeLabel;html=1;align=center;verticalAlign=middle;resizable=0;points=[];fontSize=10;",
                                    vertex="1", connectable="0", parent=str(cell_id))
                lbl_geo = ET.SubElement(lbl, "mxGeometry",
                                        x=str(round(lx, 4)), y="0", relative="1",
                                        **{"as": "geometry"})
                ET.SubElement(lbl_geo, "mxPoint", x=str(ldx), y=str(ldy), **{"as": "offset"})
                # remove the value from the parent cell so it's not rendered twice
                cell.set("value", "")

        # quality-attribute badges on the edge: appended next to the label
        edge_badges = _badge_qualities(edge.get("qualities", []))
        if edge_badges:
            lx = route.get("label_x", 0.0)
            base_dx = route.get("label_dx", 0)
            base_dy = route.get("label_dy", -10)
            # stack badges to the right of (or above) the label
            for k, qa in enumerate(edge_badges):
                cat = qa.get("category", "functional_suitability")
                color = _QUALITY_COLOR.get(cat, "#64748b")
                letter = _QUALITY_LETTER.get(cat, "?")
                # offset perpendicular/parallel to the label
                off_dx = base_dx + (k + 1) * (_BADGE_SIZE + _BADGE_GAP)
                off_dy = base_dy
                badge = ET.SubElement(
                    root, "mxCell",
                    id=str(cell_id + 20000 + k), value=letter,
                    style=_BADGE_STYLE.format(fill=color),
                    vertex="1", connectable="0", parent=str(cell_id),
                )
                bgeo = ET.SubElement(
                    badge, "mxGeometry",
                    x=str(round(lx, 4)), y="0", relative="1",
                    width=str(_BADGE_SIZE), height=str(_BADGE_SIZE),
                    **{"as": "geometry"},
                )
                ET.SubElement(bgeo, "mxPoint", x=str(off_dx), y=str(off_dy),
                              **{"as": "offset"})
        cell_id += 1

    # Overlay extra_edges (trace links, etc.) — straight dashed lines between
    # known component cells. They are not part of the layout so they do not
    # influence Sugiyama; here we just append them to the rendered XML.
    for extra in extra_edges:
        src = node_cell_ids.get(extra["source"])
        tgt = node_cell_ids.get(extra["target"])
        if not src or not tgt:
            continue
        style = extra.get(
            "style",
            "rounded=0;dashed=1;strokeColor=#9333ea;strokeWidth=1.5;"
            "exitX=0.5;exitY=0.5;exitDx=0;exitDy=0;"
            "entryX=0.5;entryY=0.5;entryDx=0;entryDy=0;"
            "fontSize=10;fontColor=#7e22ce;"
        )
        cell = ET.SubElement(
            root, "mxCell",
            id=str(cell_id), value=extra.get("label", ""),
            style=style,
            edge="1", source=src, target=tgt, parent="trace-layer",
        )
        ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
        cell_id += 1

    return ET.tostring(root_el, encoding="unicode", xml_declaration=False)


def _html_shell(title: str, body: str, viewer_tag: str, app_script: str, extra_css: str = "") -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ height: 100%; background: #f1f5f9; font-family: sans-serif; }}
{extra_css}
</style>
</head>
<body>
{body}
{viewer_tag}
<script>{app_script}</script>
</body>
</html>"""


_VIEWER_LOCAL_NAME = "viewer-static.min.js"


def _viewer_tag(viewer: str) -> str:
    if viewer == "embed":
        return f"<script>{viewer_js()}</script>"
    if viewer == "local":
        return f'<script src="{_VIEWER_LOCAL_NAME}"></script>'
    return f'<script src="{VIEWER_CDN}"></script>'


def render(nodes, edges, groups, layer_order, strategy, title, debug: bool = False, viewer: str = "cdn") -> str:
    xml = build_xml(nodes, edges, groups, layer_order, debug=debug)
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
var viewerMode = {json.dumps(viewer)};

function setSize() {{
  container.style.width  = Math.round(window.innerWidth  * 0.8) + 'px';
  container.style.height = Math.round(window.innerHeight * 0.8) + 'px';
}}

setSize();

if (typeof GraphViewer === 'undefined' || typeof mxUtils === 'undefined') {{
  {_viewer_missing_js()}
}} else {{
  var xmlDoc = mxUtils.parseXml(xmlStr);
  var viewer = new GraphViewer(container, xmlDoc.documentElement, config);
  setTimeout(function() {{
    if (viewer && viewer.graph) viewer.graph.fit();
  }}, 50);
  window.addEventListener('resize', function() {{
    setSize();
    if (viewer && viewer.graph) viewer.graph.fit();
  }});
}}
"""
    return _html_shell(title, body, _viewer_tag(viewer), script, css)


def _viewer_missing_js() -> str:
    """JS snippet that renders a friendly error inside the diagram container."""
    return """
  var msg = '';
  if (viewerMode === 'cdn') {
    msg = '<strong>draw.io viewer not loaded.</strong><br>' +
          'Could not fetch <code>viewer-static.min.js</code> from the CDN.<br>' +
          'Check your internet connection, or regenerate with ' +
          "<code>viewer='local'</code> or <code>viewer='embed'</code>.";
  } else if (viewerMode === 'local') {
    msg = '<strong>draw.io viewer not loaded.</strong><br>' +
          'Expected <code>viewer-static.min.js</code> next to this HTML file but did not find it.<br>' +
          'Re-run save with the same path so the file is copied alongside.';
  } else {
    msg = '<strong>draw.io viewer not loaded.</strong><br>' +
          'The embedded viewer JS appears to be corrupted.';
  }
  container.innerHTML =
    '<div style="padding:32px;font-family:sans-serif;color:#7f1d1d;' +
    'background:#fef2f2;border:1px solid #fecaca;border-radius:6px;' +
    'max-width:560px;margin:auto;line-height:1.5;">' + msg + '</div>';
"""


def render_collection(diagrams: dict[str, str], title: str, viewer: str = "cdn") -> str:
    """diagrams: {name: xml_string}"""
    diagrams_json = json.dumps(diagrams)
    config_json = json.dumps(_VIEWER_CONFIG)

    css = """
  body { display: flex; height: 100%; }
  #sidebar {
    width: 200px; min-width: 200px;
    background: #1e293b;
    display: flex; flex-direction: column;
    padding: 16px 0;
  }
  #sidebar h2 {
    color: #94a3b8; font-size: 11px; font-weight: 600;
    letter-spacing: 0.08em; text-transform: uppercase;
    padding: 0 16px 12px;
  }
  #sidebar button {
    background: none; border: none; cursor: pointer;
    text-align: left; padding: 8px 16px;
    color: #cbd5e1; font-size: 13px; font-family: sans-serif;
    border-left: 3px solid transparent;
    transition: background 0.1s;
  }
  #sidebar button:hover { background: #334155; }
  #sidebar button.active {
    color: #f8fafc; border-left-color: #3b82f6;
    background: #334155;
  }
  #main {
    flex: 1; display: flex; align-items: center; justify-content: center;
    background: #f1f5f9;
  }
  #diagram {
    border: 1px solid #cbd5e1;
    box-shadow: 0 4px 16px rgba(0,0,0,0.12);
    background: #ffffff;
    overflow: hidden;
    position: relative;
  }
"""
    names = list(diagrams.keys())
    buttons = "\n".join(
        f'<button id="btn-{i}" onclick="loadDiagram({i})">{name}</button>'
        for i, name in enumerate(names)
    )
    body = f"""
<div id="sidebar">
  <h2>{title or "Diagrams"}</h2>
  {buttons}
</div>
<div id="main">
  <div id="diagram"></div>
</div>
"""
    script = f"""
var diagrams = {diagrams_json};
var names = {json.dumps(names)};
var config = {config_json};
var container = document.getElementById('diagram');
var viewer = null;
var viewerMode = {json.dumps(viewer)};

function setSize() {{
  var main = document.getElementById('main');
  container.style.width  = Math.round(main.offsetWidth  * 0.9) + 'px';
  container.style.height = Math.round(main.offsetHeight * 0.9) + 'px';
}}

if (typeof GraphViewer === 'undefined' || typeof mxUtils === 'undefined') {{
  {_viewer_missing_js()}
  throw new Error('viewer not loaded');
}}

function loadDiagram(idx) {{
  document.querySelectorAll('#sidebar button').forEach(function(b) {{ b.classList.remove('active'); }});
  document.getElementById('btn-' + idx).classList.add('active');
  setSize();
  container.innerHTML = '';
  var xmlDoc = mxUtils.parseXml(diagrams[names[idx]]);
  viewer = new GraphViewer(container, xmlDoc.documentElement, config);
  setTimeout(function() {{ if (viewer && viewer.graph) viewer.graph.fit(); }}, 50);
}}

window.addEventListener('resize', function() {{
  setSize();
  if (viewer && viewer.graph) viewer.graph.fit();
}});

loadDiagram(0);
"""
    return _html_shell(title, body, _viewer_tag(viewer), script, css)


def copy_local_viewer(dest_dir: str) -> None:
    """Copy the bundled viewer-static.min.js into dest_dir for viewer='local' mode."""
    import shutil
    from sysatlas._vendor import _VIEWER_PATH, viewer_js  # noqa
    viewer_js()  # ensure downloaded
    from pathlib import Path
    target = Path(dest_dir) / _VIEWER_LOCAL_NAME
    shutil.copyfile(_VIEWER_PATH, target)
