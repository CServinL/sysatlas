"""Fluent builder for Entity-Relationship diagrams."""
from __future__ import annotations

from typing import Literal

from sysatlas._er_render import render_er
from sysatlas._ontology.er import Attribute, Entity, ERDiagram, Relationship
from sysatlas._render import copy_local_viewer

Cardinality = Literal["1", "0..1", "*", "1..*"]


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

    def show(self, viewer: str = "cdn") -> None:
        import os
        import tempfile
        import webbrowser
        html = render_er(self.diagram, title=self._title, viewer=viewer)
        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
        tmp.write(html)
        tmp.close()
        if viewer == "local":
            copy_local_viewer(os.path.dirname(tmp.name))
        print(f"[sysatlas] → {tmp.name}")
        webbrowser.open(f"file://{tmp.name}")

    def save(self, path: str, viewer: str = "cdn") -> None:
        import os
        html = render_er(self.diagram, title=self._title, viewer=viewer)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        if viewer == "local":
            copy_local_viewer(os.path.dirname(os.path.abspath(path)))
