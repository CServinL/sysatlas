"""Fluent builder for UML class diagrams.

Renders through the C4 layered engine: classes become nodes (with
attributes/methods inlined as an HTML label), inheritance edges
drive layer assignment (parents on top), other relations overlay.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Literal

from sysatlas._ontology.uml_class import (
    Attribute, Class, ClassDiagram, Method, Relation,
)
from sysatlas._render import copy_local_viewer, render

Visibility = Literal["public", "private", "protected", "package"]
ClassKind  = Literal["class", "abstract", "interface", "enum"]
RelationKind = Literal["inheritance", "implementation", "composition",
                       "aggregation", "association", "dependency"]

_CLASS_STYLE = {
    "class":     "rounded=0;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#1e40af;strokeWidth=1.5;fontFamily=monospace;fontSize=10;align=left;verticalAlign=top;spacingLeft=8;spacingRight=8;spacingTop=4;",
    "abstract":  "rounded=0;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#1e40af;strokeWidth=1.5;fontFamily=monospace;fontSize=10;align=left;verticalAlign=top;spacingLeft=8;spacingRight=8;spacingTop=4;",
    "interface": "rounded=0;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#7e22ce;strokeWidth=1.5;fontFamily=monospace;fontSize=10;align=left;verticalAlign=top;spacingLeft=8;spacingRight=8;spacingTop=4;",
    "enum":      "rounded=0;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#a16207;strokeWidth=1.5;fontFamily=monospace;fontSize=10;align=left;verticalAlign=top;spacingLeft=8;spacingRight=8;spacingTop=4;",
}
_VIS_GLYPH = {"public": "+", "private": "-", "protected": "#", "package": "~"}

_REL_STYLE = {
    "inheritance":    "rounded=1;exitX={ex};exitY={ey};exitDx=0;exitDy=0;entryX={en};entryY={ny};entryDx=0;entryDy=0;strokeColor={color};strokeWidth=1.5;fontSize=10;labelBackgroundColor=#ffffff;labelBorderColor=none;endArrow=block;endFill=0;endSize=14;",
    "implementation": "rounded=1;dashed=1;exitX={ex};exitY={ey};exitDx=0;exitDy=0;entryX={en};entryY={ny};entryDx=0;entryDy=0;strokeColor={color};strokeWidth=1.5;fontSize=10;labelBackgroundColor=#ffffff;labelBorderColor=none;endArrow=block;endFill=0;endSize=14;",
    "composition":    "rounded=1;exitX={ex};exitY={ey};exitDx=0;exitDy=0;entryX={en};entryY={ny};entryDx=0;entryDy=0;strokeColor={color};strokeWidth=1.5;fontSize=10;labelBackgroundColor=#ffffff;labelBorderColor=none;endArrow=open;startArrow=diamondThin;startFill=1;startSize=14;",
    "aggregation":    "rounded=1;exitX={ex};exitY={ey};exitDx=0;exitDy=0;entryX={en};entryY={ny};entryDx=0;entryDy=0;strokeColor={color};strokeWidth=1.5;fontSize=10;labelBackgroundColor=#ffffff;labelBorderColor=none;endArrow=open;startArrow=diamondThin;startFill=0;startSize=14;",
    "association":    "rounded=1;exitX={ex};exitY={ey};exitDx=0;exitDy=0;entryX={en};entryY={ny};entryDx=0;entryDy=0;strokeColor={color};strokeWidth=1.5;fontSize=10;labelBackgroundColor=#ffffff;labelBorderColor=none;endArrow=open;",
    "dependency":     "rounded=1;dashed=1;exitX={ex};exitY={ey};exitDx=0;exitDy=0;entryX={en};entryY={ny};entryDx=0;entryDy=0;strokeColor={color};strokeWidth=1.5;fontSize=10;labelBackgroundColor=#ffffff;labelBorderColor=none;endArrow=open;",
}

_HEADER_H = 32
_ROW_H = 16


def _stereotype(kind: str) -> str:
    if kind == "interface": return "«interface»"
    if kind == "abstract":  return "«abstract»"
    if kind == "enum":      return "«enum»"
    return ""


class ClassMap:
    """Build a UML class diagram one class at a time."""

    def __init__(self, title: str = "") -> None:
        self._classes: dict[str, Class] = {}
        self._relations: list[Relation] = []
        self._title = title

    @property
    def diagram(self) -> ClassDiagram:
        return ClassDiagram(title=self._title, classes=self._classes,
                            relations=self._relations)

    def cls(self, name: str, *, kind: ClassKind = "class",
            label: str | None = None) -> "ClassMap":
        self._classes[name] = Class(name=name, kind=kind, label=label,
                                    attributes=[], methods=[])
        return self

    def attribute(self, cls: str, name: str, *, type: str | None = None,
                  visibility: Visibility = "public",
                  is_static: bool = False) -> "ClassMap":
        if cls not in self._classes:
            self.cls(cls)
        self._classes[cls].attributes.append(Attribute(
            name=name, type=type, visibility=visibility, is_static=is_static,
        ))
        return self

    def method(self, cls: str, name: str, *, return_type: str | None = None,
               params: list[str] | None = None,
               visibility: Visibility = "public",
               is_static: bool = False, is_abstract: bool = False) -> "ClassMap":
        if cls not in self._classes:
            self.cls(cls)
        self._classes[cls].methods.append(Method(
            name=name, return_type=return_type, params=params or [],
            visibility=visibility, is_static=is_static, is_abstract=is_abstract,
        ))
        return self

    def relate(self, source: str, target: str, *, kind: RelationKind = "association",
               label: str = "", source_multiplicity: str = "",
               target_multiplicity: str = "") -> "ClassMap":
        for n in (source, target):
            if n not in self._classes:
                self.cls(n)
        self._relations.append(Relation(
            source=source, target=target, kind=kind, label=label,
            source_multiplicity=source_multiplicity,
            target_multiplicity=target_multiplicity,
        ))
        return self

    def _to_architecture(self):
        classes = self._classes
        relations = self._relations

        parents: dict[str, list[str]] = defaultdict(list)
        for r in relations:
            if r.kind in ("inheritance", "implementation"):
                parents[r.source].append(r.target)

        rank: dict[str, int] = {}

        def _rank(n: str, stack: set[str]) -> int:
            if n in rank:
                return rank[n]
            if n in stack:
                return 0
            stack = stack | {n}
            if not parents[n]:
                rank[n] = 0
                return 0
            r = max(_rank(p, stack) for p in parents[n]) + 1
            rank[n] = r
            return r

        for n in classes:
            _rank(n, set())

        max_rank = max(rank.values(), default=0)
        layer_order = [f"r{i}" for i in range(max_rank + 1)]

        nodes: dict[str, dict] = {}
        for name, k in classes.items():
            stereotype = _stereotype(k.kind)
            header = (k.label or k.name)
            header_html = (
                "<div style='text-align:center;font-weight:bold;"
                "border-bottom:1px solid #94a3b8;padding-bottom:2px;margin-bottom:4px;'>"
                + (f"<i>{stereotype}</i><br>" if stereotype else "")
                + header + "</div>"
            )
            attr_lines: list[str] = []
            for a in k.attributes:
                g = _VIS_GLYPH.get(a.visibility, "+")
                ts = f" : {a.type}" if a.type else ""
                txt = f"{g} {a.name}{ts}"
                if a.is_static:
                    txt = f"<u>{txt}</u>"
                attr_lines.append(txt)
            method_lines: list[str] = []
            for m in k.methods:
                g = _VIS_GLYPH.get(m.visibility, "+")
                ps = ", ".join(m.params)
                rt = f" : {m.return_type}" if m.return_type else ""
                txt = f"{g} {m.name}({ps}){rt}"
                if m.is_static:
                    txt = f"<u>{txt}</u>"
                if m.is_abstract:
                    txt = f"<i>{txt}</i>"
                method_lines.append(txt)
            body = "<br>".join(attr_lines)
            if method_lines:
                if attr_lines:
                    body += (
                        "<div style='border-top:1px solid #94a3b8;"
                        "margin-top:4px;padding-top:2px;'></div>"
                    )
                body += "<br>".join(method_lines)
            label = header_html + body
            h = _HEADER_H + (len(k.attributes) + len(k.methods)) * _ROW_H + 16
            if stereotype:
                h += _ROW_H

            nodes[name] = {
                "label": label,
                "layer": f"r{rank[name]}",
                "style": _CLASS_STYLE.get(k.kind, _CLASS_STYLE["class"]),
                "height": h,
            }

        edges: list[dict] = []
        for r in relations:
            parts: list[str] = []
            if r.source_multiplicity:
                parts.append(r.source_multiplicity)
            if r.label:
                parts.append(r.label)
            if r.target_multiplicity:
                parts.append(r.target_multiplicity)
            edges.append({
                "source": r.source, "target": r.target,
                "label": " ".join(parts),
                "color": "#1f2937",
                "style_full": _REL_STYLE.get(r.kind, _REL_STYLE["association"]),
            })

        return nodes, edges, {}, layer_order

    def show(self, viewer: str = "cdn") -> None:
        import os
        import tempfile
        import webbrowser
        nodes, edges, groups, layer_order = self._to_architecture()
        html = render(nodes, edges, groups, layer_order,
                      strategy="layered", title=self._title, viewer=viewer)
        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
        tmp.write(html)
        tmp.close()
        if viewer == "local":
            copy_local_viewer(os.path.dirname(tmp.name))
        print(f"[sysatlas] → {tmp.name}")
        webbrowser.open(f"file://{tmp.name}")

    def save(self, path: str, viewer: str = "cdn") -> None:
        import os
        nodes, edges, groups, layer_order = self._to_architecture()
        html = render(nodes, edges, groups, layer_order,
                      strategy="layered", title=self._title, viewer=viewer)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        if viewer == "local":
            copy_local_viewer(os.path.dirname(os.path.abspath(path)))
