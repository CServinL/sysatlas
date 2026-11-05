"""Graph metrics over a kept module set: fan-in/out, import cycles, cross-package edges.

Pure library code, no rendering. Every output list is sorted with an explicit
key so the result is byte-deterministic regardless of dict/set iteration order
or PYTHONHASHSEED.
"""
from __future__ import annotations

from typing import Callable

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from sysatlas._reflection.parser import Module

ROOT_GROUP = "(root)"
"""Sentinel group name for modules with no inferred/hinted group. Shared with
atlas.py so the cross-package rollup and the per-module group always agree."""


class ModuleMetrics(BaseModel):
    """Fan-in, fan-out and neighbours of one module."""
    model_config = ConfigDict(extra="forbid")

    name: str
    """Dotted module name — the stable key."""
    fan_in: int
    fan_out: int
    internal_deps: list[str] = Field(default_factory=list)
    """Kept modules this module imports, sorted."""
    dependents: list[str] = Field(default_factory=list)
    """Kept modules that import this one, sorted."""


class CrossPackageEdge(BaseModel):
    """Imports from one group into another, rolled up with examples."""
    model_config = ConfigDict(extra="forbid")

    src: str
    """Source group name, or ROOT_GROUP for ungrouped modules."""
    dst: str
    count: int
    examples: list[str] = Field(default_factory=list)
    """Up to 3 'a.b -> c.d' module-level edges backing this rollup, sorted."""


class GraphMetrics(BaseModel):
    """Metrics for the whole import graph: per-module numbers, cycles and cross-package edges."""
    model_config = ConfigDict(extra="forbid")

    node_count: int
    edge_count: int
    modules: list[ModuleMetrics] = Field(default_factory=list)
    """Per-module metrics, sorted by name."""
    cycles: list[list[str]] = Field(default_factory=list)
    """Import cycles (SCCs with >1 member); each member list sorted, cycles sorted."""
    cross_package: list[CrossPackageEdge] = Field(default_factory=list)

    def by_name(self) -> dict[str, ModuleMetrics]:
        return {m.name: m for m in self.modules}


def compute_metrics(
    modules: list[Module],
    group_of: Callable[[str], str | None],
) -> GraphMetrics:
    """Compute fan-in/out, cycles and cross-package rollup over the kept modules."""
    kept = {m.name for m in modules}
    edges: set[tuple[str, str]] = set()
    for m in modules:
        for imp in m.imports:
            if imp in kept and imp != m.name:
                edges.add((m.name, imp))

    fan_out: dict[str, set[str]] = {name: set() for name in kept}
    fan_in: dict[str, set[str]] = {name: set() for name in kept}
    for src, dst in edges:
        fan_out[src].add(dst)
        fan_in[dst].add(src)

    module_metrics = [
        ModuleMetrics(
            name=name,
            fan_in=len(fan_in[name]),
            fan_out=len(fan_out[name]),
            internal_deps=sorted(fan_out[name]),
            dependents=sorted(fan_in[name]),
        )
        for name in sorted(kept)
    ]

    graph = nx.DiGraph()
    graph.add_nodes_from(sorted(kept))
    graph.add_edges_from(sorted(edges))
    cycles = sorted(
        (sorted(scc) for scc in nx.strongly_connected_components(graph) if len(scc) > 1),
        key=lambda members: (len(members), members),
    )

    rollup: dict[tuple[str, str], list[str]] = {}
    for src, dst in sorted(edges):
        gs = group_of(src) or ROOT_GROUP
        gd = group_of(dst) or ROOT_GROUP
        if gs == gd:
            continue
        rollup.setdefault((gs, gd), []).append(f"{src} -> {dst}")
    cross_package = [
        CrossPackageEdge(src=gs, dst=gd, count=len(examples), examples=sorted(examples)[:3])
        for (gs, gd), examples in sorted(rollup.items())
    ]

    return GraphMetrics(
        node_count=len(kept),
        edge_count=len(edges),
        modules=module_metrics,
        cycles=cycles,
        cross_package=cross_package,
    )
