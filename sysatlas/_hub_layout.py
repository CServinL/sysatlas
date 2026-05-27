"""Hub-and-spoke placement for read/write-loop architectures.

This module only computes node positions. Edge routing (A*, port
assignment, obstacle avoidance, label placement) is delegated to the
strategy-agnostic `_layout.finalize_routing` so the hub strategy gets
the same routing quality as the layered strategy without duplicating
work.

Region assignment by `Component.layer`:

    "interfaces"  → top band, horizontal stack
    "write"       → left column, vertical stack (writes into hub)
    "hub"         → centre, single component expected (rendered taller)
    "read"        → right column, vertical stack (reads from hub)
    "external"    → bottom band, horizontal stack
"""
from __future__ import annotations

from collections import defaultdict

from sysatlas._layout import NODE_W, NODE_H, finalize_routing

_GAP_X = 120
_GAP_Y = 80
_MARGIN = 100

_HUB_W = 220
_HUB_H = 140


def _spread(xs_centre: int, names: list[str], gap: int = _GAP_X) -> list[int]:
    if not names:
        return []
    total = len(names) * NODE_W + (len(names) - 1) * gap
    start = xs_centre - total // 2
    return [start + i * (NODE_W + gap) for i in range(len(names))]


_RESERVED = ("interfaces", "write", "hub", "read", "external")


def _place(nodes: dict[str, dict]) -> tuple[dict[str, tuple[int, int]], dict[str, int]]:
    by_layer: dict[str, list[str]] = defaultdict(list)
    for n, data in nodes.items():
        layer = data.get("layer")
        # Unknown layers fall into "external" so every node gets a position.
        if layer not in _RESERVED:
            layer = "external"
        by_layer[layer].append(n)

    interfaces = by_layer.get("interfaces", [])
    writes     = by_layer.get("write", [])
    hubs       = by_layer.get("hub", [])
    reads      = by_layer.get("read", [])
    externals  = by_layer.get("external", [])

    rows_mid = max(1, len(writes), len(reads))
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

    for x, name in zip(_spread(cx, interfaces), interfaces):
        pos[name] = (x, top_y)
    for x, name in zip(_spread(cx, externals), externals):
        pos[name] = (x, bot_y)

    write_x = cx - (_HUB_W // 2 + _GAP_X + NODE_W)
    for i, name in enumerate(writes):
        pos[name] = (write_x, mid_top + i * (NODE_H + _GAP_Y))

    read_x = cx + _HUB_W // 2 + _GAP_X
    for i, name in enumerate(reads):
        pos[name] = (read_x, mid_top + i * (NODE_H + _GAP_Y))

    if hubs:
        hub_x = cx - _HUB_W // 2
        pos[hubs[0]] = (hub_x, hub_y)
        node_heights[hubs[0]] = _HUB_H
        for k, name in enumerate(hubs[1:], start=1):
            pos[name] = (hub_x, hub_y + k * (_HUB_H + _GAP_Y))
            node_heights[name] = _HUB_H

    return pos, node_heights


def compute_hub_layout(
    nodes: dict[str, dict],
    edges: list[dict],
    layer_order: list[str],
    debug: bool = False,
) -> tuple[dict[str, tuple[int, int]], dict[tuple[str, str], dict], dict[str, int]]:
    """Place nodes hub-and-spoke, then route edges with the shared A* pipeline."""
    pos, hub_heights = _place(nodes)
    routes, node_heights = finalize_routing(pos, nodes, edges,
                                            layer_order=layer_order,
                                            fixed_heights=hub_heights,
                                            debug=debug)
    return pos, routes, node_heights
