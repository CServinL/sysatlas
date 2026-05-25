"""Top-down tree layout (simplified Reingold-Tilford).

Produces (pos, routes) tuples compatible with the architecture pipeline
so we can reuse the draw.io rendering primitives in _render.
"""
from __future__ import annotations

from collections import defaultdict

NODE_W = 140
NODE_H = 50
H_GAP = 30       # min horizontal gap between sibling subtrees
V_GAP = 70       # vertical gap between depth levels
MARGIN = 40


def compute_tree_layout(
    nodes: dict[str, dict],
    edges: list[dict],
    flavor: str = "generic",
) -> tuple[dict[str, tuple[int, int]], dict[tuple[str, str], dict]]:
    """Lay out a tree top-down.

    `flavor` is reserved for future variants (radial for mindmaps, etc.);
    today everything renders top-down.
    """
    children: dict[str, list[str]] = defaultdict(list)
    parents: dict[str, str | None] = {n: None for n in nodes}
    for e in edges:
        s, t = e["source"], e["target"]
        if s in nodes and t in nodes:
            children[s].append(t)
            parents[t] = s

    roots = [n for n, p in parents.items() if p is None]
    if len(roots) != 1:
        raise ValueError(f"tree must have exactly one root, got {len(roots)}")
    root = roots[0]

    # Post-order: compute subtree leaf width
    leaf_width: dict[str, int] = {}

    def _measure(n: str) -> int:
        kids = children.get(n, [])
        if not kids:
            leaf_width[n] = 1
            return 1
        total = sum(_measure(k) for k in kids)
        leaf_width[n] = total
        return total

    _measure(root)

    # Pre-order: assign x positions
    pos: dict[str, tuple[int, int]] = {}
    pitch_x = NODE_W + H_GAP
    pitch_y = NODE_H + V_GAP

    def _place(n: str, x_offset: int, depth: int) -> None:
        kids = children.get(n, [])
        if not kids:
            x = x_offset + (NODE_W // 2)
            pos[n] = (x_offset, MARGIN + depth * pitch_y)
            return
        # place children first
        cursor = x_offset
        for k in kids:
            w = leaf_width[k] * pitch_x
            _place(k, cursor, depth + 1)
            cursor += w
        # center this node over its children
        first_kid = kids[0]
        last_kid = kids[-1]
        center_x = (pos[first_kid][0] + pos[last_kid][0]) // 2
        pos[n] = (center_x, MARGIN + depth * pitch_y)

    _place(root, MARGIN, 0)

    # Edges: orthogonal "elbow" — parent.bottom-center → mid-y → child.top-center
    routes: dict[tuple[str, str], dict] = {}
    for e in edges:
        s, t = e["source"], e["target"]
        if s not in pos or t not in pos:
            continue
        sx, sy = pos[s]
        tx, ty = pos[t]
        # exit bottom-center of source, enter top-center of target
        sxc = sx + NODE_W // 2
        sye = sy + NODE_H
        txc = tx + NODE_W // 2
        tye = ty
        mid_y = (sye + tye) // 2
        points = [(sxc, mid_y), (txc, mid_y)]
        routes[(s, t)] = {
            "exit_x": 0.5, "exit_y": 1.0,
            "entry_x": 0.5, "entry_y": 0.0,
            "points": points,
            "label_x": 0.0,
            "label_dx": 0,
            "label_dy": -8,
        }
    return pos, routes
