"""Ontology for tree-structured diagrams: org charts, mind maps, file trees,
taxonomies. A tree is a connected acyclic graph with a single root and unique
parent for every non-root node."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


NodeKind = Literal["root", "branch", "leaf"]
"""Optional semantic marker; layout doesn't depend on it."""


class TreeNode(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str                        # unique id
    label: str | None = None         # display text
    parent: str | None = None        # → TreeNode.name; None for root
    kind: NodeKind = "branch"
    icon: str | None = None          # optional icon hint
    color: str | None = None


class TreeDiagram(BaseModel):
    """Generic hierarchy. Use case is encoded via `flavor`:

    - 'org'      — reporting tree (Person/Role with ReportsTo).
    - 'mindmap'  — radial topic tree from a central root.
    - 'taxonomy' — generic categorical hierarchy.
    - 'filesystem' — file/directory tree.
    """
    model_config = ConfigDict(extra="forbid")
    title: str = ""
    flavor: Literal["org", "mindmap", "taxonomy", "filesystem", "generic"] = "generic"
    nodes: dict[str, TreeNode] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_tree_shape(self) -> "TreeDiagram":
        if not self.nodes:
            return self
        roots = [n for n in self.nodes.values() if n.parent is None]
        if len(roots) != 1:
            raise ValueError(f"tree must have exactly one root, found {len(roots)}")
        # all non-root parents must exist
        for n in self.nodes.values():
            if n.parent and n.parent not in self.nodes:
                raise ValueError(f"node {n.name!r} references unknown parent {n.parent!r}")
            if n.parent == n.name:
                raise ValueError(f"node {n.name!r} cannot be its own parent")
        # walk from root to detect cycles / disconnected nodes
        root = roots[0]
        seen: set[str] = set()
        stack = [root.name]
        while stack:
            cur = stack.pop()
            if cur in seen:
                raise ValueError(f"cycle detected at node {cur!r}")
            seen.add(cur)
            stack.extend(n.name for n in self.nodes.values() if n.parent == cur)
        missing = set(self.nodes) - seen
        if missing:
            raise ValueError(f"disconnected nodes (no path from root): {sorted(missing)}")
        return self
