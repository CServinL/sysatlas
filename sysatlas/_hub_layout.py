"""Hub-and-spoke layout for read/write-loop architectures.

One central component (the hub) is surrounded by four regions:

    ┌──────── interfaces (top) ────────┐
    │                                   │
    │   ┌── write ──┐    ┌── read ──┐   │
    │   │ source 1 │ →  │ consumer │   │
    │   │ source 2 │ →  │   ...    │   │
    │   └──────────┘    └──────────┘   │
    │            ↘ HUB ↙                │
    │   ┌─── external (bottom) ───┐    │
    │   └─────────────────────────┘    │
    └───────────────────────────────────┘

Components are assigned to a region by their `layer` value. Reserved
layer names (case-sensitive):

    "interfaces"  → top band, horizontal stack
    "write"       → left column, vertical stack (writes into hub)
    "hub"         → centre, single component expected
    "read"        → right column, vertical stack (reads from hub)
    "external"    → bottom band, horizontal stack

Edges are drawn as straight orthogonal segments between region anchors.
No A* routing; the hub strategy assumes the diagram is small enough
(bounded-complexity per view) that simple routing is sufficient.
"""
from __future__ import annotations

from collections import defaultdict

NODE_W = 160
NODE_H = 60
_GAP_X = 120
_GAP_Y = 80
_MARGIN = 100

_HUB_W = 220
_HUB_H = 140


def compute_hub_layout(
    nodes: dict[str, dict],
    edges: list[dict],
    layer_order: list[str],
    debug: bool = False,
) -> tuple[dict[str, tuple[int, int]], dict[tuple[str, str], dict], dict[str, int]]:
    """Place components in hub-and-spoke regions; return (pos, routes, node_heights)."""
    by_layer: dict[str, list[str]] = defaultdict(list)
    for n, data in nodes.items():
        by_layer[data.get("layer") or ""].append(n)

    interfaces = by_layer.get("interfaces", [])
    writes     = by_layer.get("write", [])
    hubs       = by_layer.get("hub", [])
    reads      = by_layer.get("read", [])
    externals  = by_layer.get("external", [])

    n_writes = max(1, len(writes))
    n_reads  = max(1, len(reads))
    rows_mid = max(n_writes, n_reads)
    mid_band_h = rows_mid * NODE_H + (rows_mid - 1) * _GAP_Y

    cx = _MARGIN + max(
        NODE_W + _GAP_X + _HUB_W // 2,
        len(interfaces) * (NODE_W + _GAP_X) // 2,
        len(externals)  * (NODE_W + _GAP_X) // 2,
    )

    top_y    = _MARGIN
    mid_top  = top_y + (NODE_H + _GAP_Y if interfaces else 0)
    hub_y    = mid_top + (mid_band_h - _HUB_H) // 2
    mid_end  = mid_top + mid_band_h
    bot_y    = mid_end + _GAP_Y

    pos: dict[str, tuple[int, int]] = {}
    node_heights: dict[str, int] = {}

    def _spread(xs_centre: int, names: list[str], gap: int = _GAP_X) -> list[int]:
        if not names:
            return []
        total = len(names) * NODE_W + (len(names) - 1) * gap
        start = xs_centre - total // 2
        return [start + i * (NODE_W + gap) for i in range(len(names))]

    for x, name in zip(_spread(cx, interfaces), interfaces):
        pos[name] = (x, top_y)

    for x, name in zip(_spread(cx, externals), externals):
        pos[name] = (x, bot_y)

    write_x = cx - (_HUB_W // 2 + _GAP_X + NODE_W)
    for i, name in enumerate(writes):
        y = mid_top + i * (NODE_H + _GAP_Y)
        pos[name] = (write_x, y)

    read_x = cx + _HUB_W // 2 + _GAP_X
    for i, name in enumerate(reads):
        y = mid_top + i * (NODE_H + _GAP_Y)
        pos[name] = (read_x, y)

    if hubs:
        hub_x = cx - _HUB_W // 2
        pos[hubs[0]] = (hub_x, hub_y)
        node_heights[hubs[0]] = _HUB_H
        # extra hubs (shouldn't happen, but tolerate) stack below
        for k, name in enumerate(hubs[1:], start=1):
            pos[name] = (hub_x, hub_y + k * (_HUB_H + _GAP_Y))
            node_heights[name] = _HUB_H

    routes: dict[tuple[str, str], dict] = {}
    for e in edges:
        s, t = e["source"], e["target"]
        if s in pos and t in pos:
            routes[(s, t)] = {"points": [], "exit_x": 0.5, "exit_y": 0.5,
                              "entry_x": 0.5, "entry_y": 0.5}

    return pos, routes, node_heights
