"""Group modules into architectural components and order them by dependency.

Deterministic: every iteration is over sorted keys, so the result does not
depend on dict / set order or PYTHONHASHSEED.

Steps:
1. Seed blocks: modules that share a (hinted or inferred) group start as one
   block; every other module is its own block. An inferred group that already
   exceeds the size cap is split by its next package level.
2. Merge blocks that import each other in a cycle.
3. Absorb a block into the one block that alone depends on it, when both sit
   in the same layer and the result stays small. A helper used by one caller
   is part of that caller.
4. Order the resulting blocks into tiers: tier 0 is what nothing depends on.
"""
from __future__ import annotations

from collections import Counter
from typing import Callable

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

MAX_COMPONENT_MODULES = 10
_EXAMPLES_PER_EDGE = 3


class ComponentCore(BaseModel):
    """One component: its modules, dependency tier and neighbours."""
    model_config = ConfigDict(extra="forbid")

    name: str
    modules: list[str]
    """Dotted module names, sorted."""
    tier: int
    depends_on: list[str] = Field(default_factory=list)
    dependents: list[str] = Field(default_factory=list)


class ComponentEdge(BaseModel):
    """Dependency of one component on another, with the module edges behind it."""
    model_config = ConfigDict(extra="forbid")

    src: str
    dst: str
    count: int
    examples: list[str] = Field(default_factory=list)


class ComponentGraph(BaseModel):
    """All components, the edges between them, and which component owns each module."""
    model_config = ConfigDict(extra="forbid")

    components: list[ComponentCore] = Field(default_factory=list)
    """Sorted by (tier, name)."""
    edges: list[ComponentEdge] = Field(default_factory=list)
    """Sorted by (src, dst)."""
    owner: dict[str, str] = Field(default_factory=dict)
    """Dotted module name -> component name."""


class _Block(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    members: set[str]


def compute_components(
    names: list[str],
    edges: set[tuple[str, str]],
    group_of: Callable[[str], str | None],
    layer_of: Callable[[str], str],
    label_of: Callable[[str], str],
) -> ComponentGraph:
    """Cluster `names` (dotted module names) into components over `edges` (src imports dst)."""
    degree: Counter[str] = Counter(m for edge in edges for m in edge)
    blocks = _seed_blocks(sorted(names), group_of, label_of)
    blocks = _merge_cycles(blocks, edges, degree)
    blocks = _absorb_private_helpers(blocks, edges, layer_of)
    blocks = _unique_names(blocks, degree)
    return _build_graph(blocks, edges)


def _seed_blocks(
    names: list[str], group_of: Callable[[str], str | None], label_of: Callable[[str], str]
) -> dict[str, _Block]:
    by_group: dict[str, list[str]] = {}
    for n in names:
        group = group_of(n)
        by_group.setdefault(group or f"\0{n}", []).append(n)

    blocks: dict[str, _Block] = {}
    for key in sorted(by_group):
        members = by_group[key]
        if key.startswith("\0"):
            blocks[f"m:{members[0]}"] = _Block(name=label_of(members[0]), members=set(members))
        elif len(members) > MAX_COMPONENT_MODULES and all(_is_path_group(n, key) for n in members):
            for n in members:
                sub = _subpackage(n)
                if sub is None:
                    blocks[f"m:{n}"] = _Block(name=label_of(n), members={n})
                else:
                    blocks.setdefault(f"g:{key}.{sub}", _Block(name=f"{key}.{sub}", members=set())).members.add(n)
        else:
            blocks[f"g:{key}"] = _Block(name=key, members=set(members))
    return blocks


def _is_path_group(name: str, group: str) -> bool:
    """True when `group` is the package segment of `name` (an inferred group, not a hinted label)."""
    parts = name.split(".")
    return len(parts) > 1 and parts[1] == group


def _subpackage(name: str) -> str | None:
    """Next package level below the group: 'pkg.grp.sub.mod' -> 'sub'; None for 'pkg.grp.mod'."""
    parts = name.split(".")
    return parts[2] if len(parts) > 3 else None


def _block_edges(
    blocks: dict[str, _Block], edges: set[tuple[str, str]]
) -> set[tuple[str, str]]:
    key_of = {m: k for k, b in blocks.items() for m in b.members}
    return {
        (key_of[s], key_of[d])
        for s, d in edges
        if s in key_of and d in key_of and key_of[s] != key_of[d]
    }


def _merge_cycles(
    blocks: dict[str, _Block], edges: set[tuple[str, str]], degree: Counter[str]
) -> dict[str, _Block]:
    graph = nx.DiGraph()
    graph.add_nodes_from(sorted(blocks))
    graph.add_edges_from(sorted(_block_edges(blocks, edges)))
    merged: dict[str, _Block] = {}
    for scc in sorted(sorted(s) for s in nx.strongly_connected_components(graph)):
        if len(scc) == 1:
            merged[scc[0]] = blocks[scc[0]]
            continue
        lead = min(scc, key=lambda k: (-sum(degree[m] for m in blocks[k].members), blocks[k].name, k))
        merged[f"s:{scc[0]}"] = _Block(
            name=blocks[lead].name,
            members={m for k in scc for m in blocks[k].members},
        )
    return merged


def _block_layer(block: _Block, layer_of: Callable[[str], str]) -> str:
    counts = Counter(layer_of(m) for m in block.members)
    return sorted(counts, key=lambda layer: (-counts[layer], layer))[0]


def _absorb_private_helpers(
    blocks: dict[str, _Block],
    edges: set[tuple[str, str]],
    layer_of: Callable[[str], str],
) -> dict[str, _Block]:
    layer = {k: _block_layer(b, layer_of) for k, b in blocks.items()}
    deps: dict[str, set[str]] = {k: set() for k in blocks}
    dependents: dict[str, set[str]] = {k: set() for k in blocks}
    for src, dst in _block_edges(blocks, edges):
        deps[src].add(dst)
        dependents[dst].add(src)

    merged = True
    while merged:
        merged = False
        for key in sorted(blocks, key=lambda k: (len(blocks[k].members), blocks[k].name, k)):
            if key not in blocks or len(dependents[key]) != 1:
                continue
            (target,) = dependents[key]
            if len(blocks[key].members) + len(blocks[target].members) > MAX_COMPONENT_MODULES:
                continue
            if layer[key] != layer[target]:
                continue
            blocks[target].members |= blocks[key].members
            for dep in deps.pop(key):
                dependents[dep].discard(key)
                deps[target].add(dep)
                dependents[dep].add(target)
            deps[target].discard(key)
            del dependents[key], blocks[key], layer[key]
            layer[target] = _block_layer(blocks[target], layer_of)
            merged = True
    return blocks


def _unique_names(blocks: dict[str, _Block], degree: Counter[str]) -> dict[str, _Block]:
    """Keep a clashing name on the biggest block; qualify the others with their lead module."""
    by_name: dict[str, list[str]] = {}
    for key in sorted(blocks):
        by_name.setdefault(blocks[key].name, []).append(key)
    for name, keys in by_name.items():
        if len(keys) < 2:
            continue
        keys.sort(key=lambda k: (-len(blocks[k].members), k))
        for key in keys[1:]:
            lead = min(blocks[key].members, key=lambda m: (-degree[m], m))
            blocks[key].name = f"{name} ({lead})"
    return blocks


def _build_graph(blocks: dict[str, _Block], edges: set[tuple[str, str]]) -> ComponentGraph:
    name_of = {k: b.name for k, b in blocks.items()}
    key_of = {m: k for k, b in blocks.items() for m in b.members}
    rolled: dict[tuple[str, str], list[str]] = {}
    for src, dst in sorted(edges):
        if src not in key_of or dst not in key_of or key_of[src] == key_of[dst]:
            continue
        rolled.setdefault((name_of[key_of[src]], name_of[key_of[dst]]), []).append(
            f"{src} -> {dst}"
        )
    graph = nx.DiGraph()
    graph.add_nodes_from(sorted(name_of.values()))
    graph.add_edges_from(sorted(rolled))

    tier: dict[str, int] = {}
    for node in nx.lexicographical_topological_sort(graph):
        tier[node] = 1 + max((tier[p] for p in graph.predecessors(node)), default=-1)

    components = [
        ComponentCore(
            name=b.name,
            modules=sorted(b.members),
            tier=tier[b.name],
            depends_on=sorted(graph.successors(b.name)),
            dependents=sorted(graph.predecessors(b.name)),
        )
        for b in blocks.values()
    ]
    return ComponentGraph(
        components=sorted(components, key=lambda c: (c.tier, c.name)),
        edges=[
            ComponentEdge(src=s, dst=d, count=len(ex), examples=ex[:_EXAMPLES_PER_EDGE])
            for (s, d), ex in sorted(rolled.items())
        ],
        owner={m: name_of[k] for m, k in sorted(key_of.items())},
    )
