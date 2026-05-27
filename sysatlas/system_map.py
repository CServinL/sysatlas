from __future__ import annotations

from sysatlas._ontology.architecture import (
    ArchitectureDiagram,
    Component,
    Connection,
    Group,
    Layer,
)
from sysatlas._render import build_xml, copy_local_viewer, render, render_collection


class SystemMap:
    """Builder for a layered architecture diagram. Stores its state as a
    Pydantic ArchitectureDiagram and exports plain dicts to the rendering layer."""

    def __init__(self, strategy: str = "layered", title: str = "", node_size: int = 60) -> None:
        self._diagram = ArchitectureDiagram(title=title, strategy=strategy)
        self._node_size = node_size

    @property
    def diagram(self) -> ArchitectureDiagram:
        """Return the validated Pydantic model — useful for introspection/tests."""
        return self._diagram

    def group(self, name: str, *, color: str | None = None, label: str | None = None) -> "SystemMap":
        self._diagram.groups[name] = Group(name=name, color=color, label=label or name)
        return self

    def add_component(self, name: str, *, label: str | None = None,
                      group: str | None = None, layer: str | None = None,
                      tech: str | None = None, **meta) -> "SystemMap":
        if layer and not any(l.name == layer for l in self._diagram.layers):
            self._diagram.layers.append(Layer(name=layer, order=len(self._diagram.layers)))
        self._diagram.components[name] = Component(
            name=name, label=label, group=group, layer=layer, tech=tech, **meta,
        )
        return self

    def connect(self, source: str, target: str, *, label: str = "",
                style: str = "solid", color: str | None = None, **meta) -> "SystemMap":
        # implicitly create components if user wires before declaring
        for node in (source, target):
            if node not in self._diagram.components:
                self._diagram.components[node] = Component(name=node)
        self._diagram.connections.append(Connection(
            source=source, target=target, label=label, style=style, color=color, **meta,
        ))
        return self

    # ── internal: legacy dict format expected by _render/_layout ────────────

    @property
    def _nodes(self) -> dict[str, dict]:
        return {n: c.model_dump(exclude={"name"}) for n, c in self._diagram.components.items()}

    @property
    def _edges(self) -> list[dict]:
        return [e.model_dump() for e in self._diagram.connections]

    @property
    def _groups(self) -> dict[str, dict]:
        return {n: g.model_dump(exclude={"name"}) for n, g in self._diagram.groups.items()}

    @property
    def _layer_order(self) -> list[str]:
        return [l.name for l in self._diagram.layers]

    @property
    def _strategy(self) -> str:
        return self._diagram.strategy

    @property
    def _title(self) -> str:
        return self._diagram.title

    # ── rendering ───────────────────────────────────────────────────────────

    def show(self, debug: bool = False, viewer: str = "cdn") -> None:
        import os
        import tempfile
        import webbrowser
        html = render(self._nodes, self._edges, self._groups, self._layer_order,
                      self._strategy, self._title, debug=debug, viewer=viewer)
        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
        tmp.write(html)
        tmp.close()
        if viewer == "local":
            copy_local_viewer(os.path.dirname(tmp.name))
        print(f"[sysatlas] → {tmp.name}")
        webbrowser.open(f"file://{tmp.name}")

    def save(self, path: str, viewer: str = "cdn") -> None:
        import os
        html = render(self._nodes, self._edges, self._groups, self._layer_order,
                      self._strategy, self._title, viewer=viewer)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        if viewer == "local":
            copy_local_viewer(os.path.dirname(os.path.abspath(path)))

    def _to_xml(self, extra_edges: list[dict] | None = None) -> str:
        return build_xml(self._nodes, self._edges, self._groups, self._layer_order,
                         extra_edges=extra_edges, strategy=self._strategy)

    @staticmethod
    def save_collection(diagrams: dict[str, "SystemMap"], path: str, title: str = "", viewer: str = "cdn") -> None:
        import os
        xmls = {name: m._to_xml() for name, m in diagrams.items()}
        html = render_collection(xmls, title, viewer=viewer)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        if viewer == "local":
            copy_local_viewer(os.path.dirname(os.path.abspath(path)))
