"""Fluent builder for Entity-Relationship diagrams.

Renders through the C4 layered engine: entities become nodes (with
their attribute rows inlined as an HTML label), relationships become
edges with cardinality + verb-phrase labels.
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Literal

from sysatlas._ontology.er import Attribute, Entity, ERDiagram, Relationship
from sysatlas._render import copy_local_viewer, render

Cardinality = Literal["1", "0..1", "*", "1..*"]

_ENTITY_STYLE = (
    "rounded=0;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#1e40af;"
    "strokeWidth=1.5;fontFamily=monospace;fontSize=10;align=left;"
    "verticalAlign=top;spacingLeft=8;spacingRight=8;spacingTop=4;"
)
_WEAK_ENTITY_STYLE = (
    "rounded=0;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#a16207;"
    "strokeWidth=2.5;fontFamily=monospace;fontSize=10;align=left;"
    "verticalAlign=top;spacingLeft=8;spacingRight=8;spacingTop=4;"
)
_REL_STYLE = (
    "rounded=1;exitX={ex};exitY={ey};exitDx=0;exitDy=0;"
    "entryX={en};entryY={ny};entryDx=0;entryDy=0;"
    "strokeColor={color};strokeWidth=1.5;fontSize=10;"
    "labelBackgroundColor=#ffffff;labelBorderColor=none;endArrow=none;"
)

_ATTR_ROW_H = 16
_HEADER_H = 28


class ERMap:
    """Build an ER diagram one entity at a time."""

    def __init__(self, title: str = "") -> None:
        self._entities: dict[str, Entity] = {}
        self._relationships: list[Relationship] = []
        self._title = title

    @property
    def diagram(self) -> ERDiagram:
        return ERDiagram(title=self._title, entities=self._entities,
                         relationships=self._relationships)

    def entity(self, name: str, *, label: str | None = None,
               is_weak: bool = False) -> "ERMap":
        self._entities[name] = Entity(name=name, label=label, is_weak=is_weak,
                                      attributes=[])
        return self

    def attribute(self, entity: str, name: str, *, type: str | None = None,
                  is_key: bool = False, is_required: bool = False) -> "ERMap":
        if entity not in self._entities:
            self.entity(entity)
        self._entities[entity].attributes.append(Attribute(
            name=name, type=type, is_key=is_key, is_required=is_required,
        ))
        return self

    def relate(self, source: str, target: str, name: str = "", *,
               source_card: Cardinality = "1",
               target_card: Cardinality = "*",
               is_identifying: bool = False) -> "ERMap":
        for n in (source, target):
            if n not in self._entities:
                self.entity(n)
        self._relationships.append(Relationship(
            name=name or f"{source}_{target}",
            source=source, target=target,
            source_card=source_card, target_card=target_card,
            is_identifying=is_identifying,
        ))
        return self

    def _to_architecture(self):
        diagram = self.diagram
        entities = diagram.entities
        rels = diagram.relationships

        adj: dict[str, list[str]] = defaultdict(list)
        for r in rels:
            adj[r.source].append(r.target)

        rank: dict[str, int] = {}
        roots = [n for n in entities if not any(r.target == n for r in rels)] or list(entities)
        queue: deque[str] = deque()
        for n in roots:
            rank[n] = 0
            queue.append(n)
        while queue:
            cur = queue.popleft()
            for nb in adj.get(cur, []):
                if nb not in rank or rank[nb] < rank[cur] + 1:
                    rank[nb] = rank[cur] + 1
                    queue.append(nb)
        next_r = max(rank.values(), default=-1) + 1
        for n in entities:
            if n not in rank:
                rank[n] = next_r

        max_rank = max(rank.values(), default=0)
        layer_order = [f"r{i}" for i in range(max_rank + 1)]

        nodes: dict[str, dict] = {}
        for name, e in entities.items():
            header = e.label or e.name
            attr_lines: list[str] = []
            for a in e.attributes:
                if a.is_key:
                    marker = "<b>🔑</b>"
                elif a.is_required:
                    marker = "●"
                else:
                    marker = "○"
                type_str = f" : {a.type}" if a.type else ""
                attr_lines.append(f"{marker} {a.name}{type_str}")
            label = (
                f"<div style='text-align:center;font-weight:bold;border-bottom:1px solid #94a3b8;"
                f"padding-bottom:2px;margin-bottom:4px;'>{header}</div>"
                + "<br>".join(attr_lines)
            )
            h = _HEADER_H + max(1, len(e.attributes)) * _ATTR_ROW_H + 12
            nodes[name] = {
                "label": label,
                "layer": f"r{rank[name]}",
                "style": _WEAK_ENTITY_STYLE if e.is_weak else _ENTITY_STYLE,
                "height": h,
                "width": 180,
            }

        edges: list[dict] = []
        for r in rels:
            parts = [r.source_card, r.name, r.target_card]
            edges.append({
                "source": r.source, "target": r.target,
                "label": " ".join(p for p in parts if p),
                "color": "#1f2937",
                "style_full": _REL_STYLE,
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
