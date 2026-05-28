"""Fluent builder for UML class diagrams."""
from __future__ import annotations

from typing import Literal

from sysatlas._class_render import render_class
from sysatlas._ontology.uml_class import (
    Attribute, Class, ClassDiagram, Method, Relation,
)
from sysatlas._render import copy_local_viewer

Visibility = Literal["public", "private", "protected", "package"]
ClassKind  = Literal["class", "abstract", "interface", "enum"]
RelationKind = Literal["inheritance", "implementation", "composition",
                       "aggregation", "association", "dependency"]


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

    def show(self, viewer: str = "cdn") -> None:
        import os
        import tempfile
        import webbrowser
        html = render_class(self.diagram, title=self._title, viewer=viewer)
        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
        tmp.write(html)
        tmp.close()
        if viewer == "local":
            copy_local_viewer(os.path.dirname(tmp.name))
        print(f"[sysatlas] → {tmp.name}")
        webbrowser.open(f"file://{tmp.name}")

    def save(self, path: str, viewer: str = "cdn") -> None:
        import os
        html = render_class(self.diagram, title=self._title, viewer=viewer)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        if viewer == "local":
            copy_local_viewer(os.path.dirname(os.path.abspath(path)))
