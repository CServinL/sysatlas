"""Reflection: code -> SystemMap.

Public entry point is sysatlas.reflect(path), defined in sysatlas/__init__.py.
This module holds the class.
"""
from __future__ import annotations

import fnmatch
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from sysatlas._reflection.layers import infer_group, infer_layer
from sysatlas._reflection.parser import ProjectGraph, scan
from sysatlas.system_map import SystemMap


class Hints(BaseModel):
    """Optional sysatlas.yaml content. All fields optional."""
    model_config = ConfigDict(extra="forbid")

    exclude: list[str] = Field(default_factory=list)
    layer: dict[str, str] = Field(default_factory=dict)
    group: dict[str, str] = Field(default_factory=dict)
    rename: dict[str, str] = Field(default_factory=dict)


class Reflection:
    """Result of scanning a source tree. Holds the graph; can render or merge."""

    def __init__(self, graph: ProjectGraph, hints: Hints | None = None) -> None:
        self._graph = graph
        self._hints = hints or Hints()
        self._extra_excludes: list[str] = []

    @property
    def graph(self) -> ProjectGraph:
        return self._graph

    @property
    def hints(self) -> Hints:
        return self._hints

    def exclude(self, *patterns: str) -> "Reflection":
        """Drop modules whose path matches any glob (relative to scan root)."""
        self._extra_excludes.extend(patterns)
        return self

    def _kept_modules(self) -> list:
        root = Path(self._graph.root)
        excludes = list(self._hints.exclude) + self._extra_excludes
        kept = []
        for m in self._graph.modules:
            rel = str(Path(m.path).relative_to(root)) if Path(m.path).is_relative_to(root) else m.path
            if any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(m.name, pat) for pat in excludes):
                continue
            kept.append(m)
        return kept

    def _display_name(self, modname: str) -> str:
        if modname in self._hints.rename:
            return self._hints.rename[modname]
        parts = modname.split(".")
        return parts[-1] or modname

    def _layer_for(self, modname: str) -> str:
        return self._hints.layer.get(modname) or infer_layer(modname)

    def _group_for(self, modname: str) -> str | None:
        if modname in self._hints.group:
            return self._hints.group[modname]
        return infer_group(modname)

    def to_system_map(self, title: str = "") -> SystemMap:
        """Build a SystemMap reflecting the scanned graph."""
        m = SystemMap(title=title or f"reflection: {Path(self._graph.root).name}")
        kept = self._kept_modules()
        kept_names = {mod.name for mod in kept}

        groups_added: set[str] = set()
        for mod in kept:
            group = self._group_for(mod.name)
            if group and group not in groups_added:
                m.group(group)
                groups_added.add(group)

        for mod in kept:
            m.add_component(
                self._display_name(mod.name),
                group=self._group_for(mod.name),
                layer=self._layer_for(mod.name),
                tech=mod.name,
            )

        seen_edges: set[tuple[str, str]] = set()
        for mod in kept:
            src = self._display_name(mod.name)
            for imp in mod.imports:
                if imp not in kept_names:
                    continue
                tgt = self._display_name(imp)
                if src == tgt:
                    continue
                key = (src, tgt)
                if key in seen_edges:
                    continue
                seen_edges.add(key)
                m.connect(src, tgt)
        return m

    def merge_with(self, overlay: SystemMap, title: str = "") -> SystemMap:
        """Reflect, then apply a user-authored annotation overlay."""
        from sysatlas._reflection.merge import merge_overlay
        reflected = self.to_system_map(title=title)
        return merge_overlay(reflected, overlay)


def reflect(path: str | Path, hints: Hints | None = None) -> Reflection:
    """Scan a Python source tree and return a Reflection.

    AST-only. Never imports the target code. If `hints=` is not passed,
    looks for sysatlas.json (always) or sysatlas.yaml (if PyYAML installed)
    next to the scan root and uses it.
    """
    if hints is None:
        from sysatlas._reflection.hints import load_hints
        hints = load_hints(path)
    return Reflection(scan(path), hints=hints)
