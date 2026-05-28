"""BPMN diagram layout.

Pools contain horizontal lanes. Inside each lane, nodes (events,
activities, gateways) are placed left-to-right in BFS order from start
events. Pools stack vertically.
"""
from __future__ import annotations

from collections import defaultdict, deque

POOL_HEADER_W = 30
LANE_HEADER_W = 24
LANE_H = 120
NODE_GAP = 60
LANE_PAD_X = 20
LANE_PAD_Y = 16
MARGIN = 30

ACTIVITY_W = 110
ACTIVITY_H = 60
EVENT_R = 28
GATEWAY_W = 44


def node_size(kind: str) -> tuple[int, int]:
    if kind in ("start", "end", "intermediate", "timer", "message", "error"):
        return EVENT_R * 2, EVENT_R * 2
    if kind in ("exclusive", "parallel", "inclusive", "event_based"):
        return GATEWAY_W, GATEWAY_W
    return ACTIVITY_W, ACTIVITY_H


def compute_bpmn_layout(diagram):
    """Return (positions, sizes, pool_rects, lane_rects, routes)."""
    pools = list(diagram.pools.values())
    lanes_by_pool: dict[str, list] = defaultdict(list)
    for lane in diagram.lanes.values():
        lanes_by_pool[lane.pool].append(lane)

    all_nodes: dict[str, tuple[str, str]] = {}  # name -> (kind_category, kind)
    node_lane: dict[str, str | None] = {}
    for e in diagram.events.values():
        all_nodes[e.name] = ("event", e.kind)
        node_lane[e.name] = e.lane
    for a in diagram.activities.values():
        all_nodes[a.name] = ("activity", a.kind)
        node_lane[a.name] = a.lane
    for g in diagram.gateways.values():
        all_nodes[g.name] = ("gateway", g.kind)
        node_lane[g.name] = g.lane

    nodes_by_lane: dict[str | None, list[str]] = defaultdict(list)
    for name, lane in node_lane.items():
        nodes_by_lane[lane].append(name)

    adj: dict[str, list[str]] = defaultdict(list)
    in_deg: dict[str, int] = defaultdict(int)
    for f in diagram.flows:
        if f.kind == "sequence" or f.kind == "default" or f.kind == "conditional":
            adj[f.source].append(f.target)
            in_deg[f.target] += 1

    order: dict[str, int] = {}
    starts = [n for n in all_nodes if in_deg[n] == 0 and all_nodes[n][0] == "event"]
    if not starts:
        starts = [n for n in all_nodes if in_deg[n] == 0]
    queue: deque[str] = deque()
    for s in starts:
        order[s] = 0
        queue.append(s)
    while queue:
        cur = queue.popleft()
        for nb in adj.get(cur, []):
            new_order = order[cur] + 1
            if nb not in order or new_order > order[nb]:
                order[nb] = new_order
                queue.append(nb)
    next_o = max(order.values(), default=-1) + 1
    for n in all_nodes:
        if n not in order:
            order[n] = next_o
            next_o += 1

    pool_rects: list[dict] = []
    lane_rects: list[dict] = []
    pos: dict[str, tuple[int, int]] = {}
    size: dict[str, tuple[int, int]] = {}

    pool_y = MARGIN
    inner_x = LANE_HEADER_W + LANE_PAD_X
    column_pitch = max(ACTIVITY_W, EVENT_R * 2, GATEWAY_W) + NODE_GAP
    max_order = max(order.values(), default=0)
    lane_inner_w = inner_x + (max_order + 1) * column_pitch + LANE_PAD_X

    for pool in pools:
        lanes = lanes_by_pool.get(pool.name, [])
        if not lanes:
            from sysatlas._ontology.bpmn import Lane
            lanes = [Lane(name=f"__default_{pool.name}__", pool=pool.name)]
            lanes_by_pool[pool.name] = lanes

        pool_h = LANE_H * len(lanes)
        pool_w = POOL_HEADER_W + lane_inner_w
        pool_x = MARGIN
        pool_rects.append({
            "name": pool.name,
            "label": pool.label or pool.name,
            "x": pool_x, "y": pool_y,
            "w": pool_w, "h": pool_h,
        })

        for i, lane in enumerate(lanes):
            lx = pool_x + POOL_HEADER_W
            ly = pool_y + i * LANE_H
            lane_rects.append({
                "name": lane.name,
                "label": lane.label or lane.name,
                "x": lx, "y": ly,
                "w": lane_inner_w, "h": LANE_H,
            })
            lane_center_y = ly + LANE_H // 2
            nodes_here = sorted(nodes_by_lane.get(lane.name, []), key=lambda n: order[n])
            for n in nodes_here:
                cat, kind = all_nodes[n]
                w, h = node_size(kind)
                nx = lx + LANE_HEADER_W + LANE_PAD_X + order[n] * column_pitch
                ny = lane_center_y - h // 2
                pos[n] = (nx, ny)
                size[n] = (w, h)
        pool_y += pool_h + MARGIN

    # Place nodes with no lane assignment into a fallback row
    orphans = nodes_by_lane.get(None, [])
    if orphans:
        ly = pool_y
        lane_rects.append({
            "name": "__orphan__", "label": "(no lane)",
            "x": MARGIN, "y": ly,
            "w": lane_inner_w + POOL_HEADER_W, "h": LANE_H,
        })
        for n in sorted(orphans, key=lambda x: order[x]):
            cat, kind = all_nodes[n]
            w, h = node_size(kind)
            nx = MARGIN + POOL_HEADER_W + LANE_PAD_X + order[n] * column_pitch
            ny = ly + LANE_H // 2 - h // 2
            pos[n] = (nx, ny)
            size[n] = (w, h)

    routes: list[dict] = []
    for f in diagram.flows:
        if f.source not in pos or f.target not in pos:
            continue
        routes.append({
            "source": f.source, "target": f.target,
            "kind": f.kind, "label": f.label,
        })
    return pos, size, pool_rects, lane_rects, routes, all_nodes
