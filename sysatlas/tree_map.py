"""Fluent builder for a tree diagram (org chart, mindmap, taxonomy, …).

Mirrors the SystemMap API but for the Tree ontology. Uses Reingold-
Tilford-style top-down layout from _tree_layout.
"""
from __future__ import annotations

from typing import Literal

from sysatlas._ontology.tree import TreeDiagram, TreeNode
from sysatlas._render import copy_local_viewer
from sysatlas._tree_render import render_tree


TreeFlavor = Literal["org", "mindmap", "taxonomy", "filesystem", "generic"]


class TreeMap:
    """Build a tree diagram one node at a time."""

    def __init__(self, title: str = "", flavor: TreeFlavor = "generic") -> None:
        self._diagram = TreeDiagram(title=title, flavor=flavor)

    @property
    def diagram(self) -> TreeDiagram:
        return self._diagram

    def add(self, name: str, *, parent: str | None = None,
            label: str | None = None, kind: str | None = None,
            color: str | None = None, icon: str | None = None) -> "TreeMap":
        """Add a node. `parent=None` means root (only one allowed)."""
        node_kind = kind or ("root" if parent is None else "branch")
        self._diagram.nodes[name] = TreeNode(
            name=name, parent=parent, label=label,
            kind=node_kind, color=color, icon=icon,
        )
        return self

    def show(self, viewer: str = "cdn") -> None:
        import os
        import tempfile
        import webbrowser
        html = render_tree(self._diagram, title=self._diagram.title,
                           flavor=self._diagram.flavor, viewer=viewer)
        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
        tmp.write(html)
        tmp.close()
        if viewer == "local":
            copy_local_viewer(os.path.dirname(tmp.name))
        print(f"[sysatlas] → {tmp.name}")
        webbrowser.open(f"file://{tmp.name}")

    def save(self, path: str, viewer: str = "cdn") -> None:
        import os
        html = render_tree(self._diagram, title=self._diagram.title,
                           flavor=self._diagram.flavor, viewer=viewer)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        if viewer == "local":
            copy_local_viewer(os.path.dirname(os.path.abspath(path)))
