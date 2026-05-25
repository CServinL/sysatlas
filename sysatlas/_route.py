from __future__ import annotations

import heapq
from collections import defaultdict

CELL = 10            # grid resolution (px)
PAD  = 2             # obstacle padding in cells around each node (≥20px clearance)
NEAR_PENALTY = 15    # extra cost per cell adjacent to an obstacle
TURN_COST = 20       # extra weight for a 90-degree turn (favor straight runs)
STEP_COST = 1        # weight for a straight step
CONGEST_COST = 3     # per-cell cost for entering with the same direction as another edge
CROSS_COST = 1       # per-cell cost for entering perpendicular to another edge (cheap)
RIPUP_PASSES = 2     # extra reroute passes after initial routing

_SIDES = ("top", "bottom", "left", "right")

PORT_PITCH = 28   # vertical/horizontal spacing per port (label ~14 + gap ~14)
PORT_MARGIN = 12  # margin from edge of node to first/last port


def compute_node_heights(
    edges: list[dict],
    nodes_pos: dict[str, tuple[int, int]],
    default_h: int = 60,
) -> dict[str, int]:
    """For each node, compute height needed to fit all ports on its tallest side.

    Counts edges that would land on the left/right of each node (based on the
    perpendicular axis between source and target centers). Height = max(default,
    (n_max_ports - 1) * PORT_PITCH + 2*PORT_MARGIN).
    """
    from collections import defaultdict
    bboxes_w = 160  # NODE_W; for side-picking only, default width
    side_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for e in edges:
        s, t = e["source"], e["target"]
        if s not in nodes_pos or t not in nodes_pos or s == t:
            continue
        sx, sy = nodes_pos[s]
        tx, ty = nodes_pos[t]
        # vertical-overlap test using a default height; for height calculation
        # we only care about horizontal vs vertical port side
        sa = (sx, sy, sx + bboxes_w, sy + default_h)
        ta = (tx, ty, tx + bboxes_w, ty + default_h)
        side_s = _pick_side(sa, ta)
        side_t = _pick_side(ta, sa)
        side_counts[s][side_s] += 1
        side_counts[t][side_t] += 1

    heights: dict[str, int] = {}
    for name in nodes_pos:
        sides = side_counts.get(name, {})
        n_max = max(
            sides.get("left", 0),
            sides.get("right", 0),
        )
        needed = (n_max - 1) * PORT_PITCH + 2 * PORT_MARGIN if n_max > 1 else default_h
        heights[name] = max(default_h, needed)
    return heights


def route_edges(
    nodes_pos: dict[str, tuple[int, int]],
    node_size: tuple[int, int],
    edges: list[tuple[int, str, str]],
    label_zones: list[tuple[int, int, int, int]] | None = None,
    block_zones: list[tuple[int, int, int, int]] | None = None,
    node_heights: dict[str, int] | None = None,
) -> dict[tuple[str, str], dict]:
    """A* maze routing over a coarse grid.

    label_zones: hard horizontal-block only (group title text — lines may
                 cross perpendicularly but never run parallel on top).
    block_zones: hard block in both directions (connector glyphs, etc.).
    """
    label_zones = label_zones or []
    block_zones = block_zones or []
    node_heights = node_heights or {}
    NW, NH = node_size
    bboxes = {n: (x, y, x + NW, y + node_heights.get(n, NH)) for n, (x, y) in nodes_pos.items()}

    min_x = min(b[0] for b in bboxes.values()) - 4 * CELL
    min_y = min(b[1] for b in bboxes.values()) - 4 * CELL
    max_x = max(b[2] for b in bboxes.values()) + 4 * CELL
    max_y = max(b[3] for b in bboxes.values()) + 4 * CELL

    cols = (max_x - min_x) // CELL + 1
    rows = (max_y - min_y) // CELL + 1

    def to_cell(px: float, py: float) -> tuple[int, int]:
        return (int((px - min_x) // CELL), int((py - min_y) // CELL))

    def to_px(cx: int, cy: int) -> tuple[int, int]:
        return (int(min_x + cx * CELL + CELL // 2),
                int(min_y + cy * CELL + CELL // 2))

    # label-zone cells: only HORIZONTAL movement is forbidden (a horizontal line
    # would run parallel on top of the text). Vertical lines may cross through.
    label_h_blocked: set[tuple[int, int]] = set()
    for (x1, y1, x2, y2) in label_zones:
        c1x, c1y = to_cell(x1, y1)
        c2x, c2y = to_cell(x2 - 1, y2 - 1)
        for cx in range(c1x, c2x + 1):
            for cy in range(c1y, c2y + 1):
                label_h_blocked.add((cx, cy))

    # full-block cells: connector glyphs, etc. — routes never cross them.
    full_blocked: set[tuple[int, int]] = set()
    for (x1, y1, x2, y2) in block_zones:
        c1x, c1y = to_cell(x1, y1)
        c2x, c2y = to_cell(x2 - 1, y2 - 1)
        for cx in range(c1x, c2x + 1):
            for cy in range(c1y, c2y + 1):
                full_blocked.add((cx, cy))

    # mark obstacles per node: separate bbox from PAD ring so we can allow
    # the path to *approach* (PAD) but never traverse (bbox).
    node_cells: dict[str, set[tuple[int, int]]] = {}
    node_bbox_cells: dict[str, set[tuple[int, int]]] = {}
    node_pad_cells: dict[str, set[tuple[int, int]]] = {}
    for n, (x1, y1, x2, y2) in bboxes.items():
        c1x, c1y = to_cell(x1, y1)
        c2x, c2y = to_cell(x2 - 1, y2 - 1)
        bbox_set, all_set = set(), set()
        for cx in range(c1x, c2x + 1):
            for cy in range(c1y, c2y + 1):
                bbox_set.add((cx, cy))
        for cx in range(c1x - PAD, c2x + PAD + 1):
            for cy in range(c1y - PAD, c2y + PAD + 1):
                all_set.add((cx, cy))
        node_bbox_cells[n] = bbox_set
        node_pad_cells[n] = all_set - bbox_set
        node_cells[n] = all_set

    all_blocked: set[tuple[int, int]] = set(full_blocked)
    for cells in node_cells.values():
        all_blocked |= cells

    # per-node halo: 1-cell ring around each node's blocked area.
    # During routing, halos of non-(src, tgt) nodes are treated as hard blocks.
    # halo of src/tgt stays soft (penalty only) so the path can reach the port.
    node_halo: dict[str, set[tuple[int, int]]] = {}
    for name, cells in node_cells.items():
        halo = set()
        for cx, cy in cells:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (cx + dx, cy + dy)
                    if n not in cells:
                        halo.add(n)
        node_halo[name] = halo

    # near_obstacle is now used only for the soft penalty on src/tgt's own halo
    near_obstacle: set[tuple[int, int]] = set()
    for halo in node_halo.values():
        near_obstacle |= halo

    ports = _assign_ports(edges, bboxes)

    # directional cell usage: cells used by horizontal segments (H) and by vertical (V).
    # Same-direction reuse is heavily penalized (would create overlap),
    # opposite-direction is cheap (just a perpendicular crossing).
    used_h: dict[tuple[int, int], int] = defaultdict(int)
    used_v: dict[tuple[int, int], int] = defaultdict(int)
    edge_cells: dict[int, list[tuple[int, int]]] = {}
    routes: dict[tuple[str, str], dict] = {}
    edge_keys: dict[int, tuple[str, str]] = {}

    def _route_one(i: int, src: str, tgt: str) -> None:
        port_s = ports[(i, "src")]
        port_t = ports[(i, "tgt")]
        sc = _port_cell(port_s, bboxes[src], to_cell, outside=True)
        tc = _port_cell(port_t, bboxes[tgt], to_cell, outside=True)
        # block all node bboxes + halos of OTHER nodes. PAD of src/tgt stays
        # available but treated as soft penalty (so path can approach the port
        # without sliding along the bbox edge).
        blocked = set(all_blocked)
        for n, halo in node_halo.items():
            if n == src or n == tgt:
                continue
            blocked |= halo
        # only unblock the PAD ring of src/tgt (NOT bbox interior)
        blocked -= node_pad_cells[src]
        blocked -= node_pad_cells[tgt]
        # soft penalty applies only to halos of OTHER nodes; src/tgt's own
        # PAD is fully free so the path can exit/enter cleanly (no penalty
        # for "dropping immediately" near the source).
        soft = set(near_obstacle) - node_pad_cells[src] - node_pad_cells[tgt]
        init_dir = _side_dir(port_s["side"])
        path = _astar(sc, tc, blocked, cols, rows, used_h, used_v, init_dir, soft, label_h_blocked)
        if not path:
            path = [sc, (tc[0], sc[1]), tc]
        edge_cells[i] = list(path)
        # mark each cell of the path with the direction we traversed it
        for k in range(len(path) - 1):
            ax, ay = path[k]
            bx, by = path[k + 1]
            if ax == bx:
                used_v[path[k]] += 1
                used_v[path[k + 1]] += 1
            elif ay == by:
                used_h[path[k]] += 1
                used_h[path[k + 1]] += 1
        px_path = [to_px(*c) for c in path]
        px_path = _anchor_path_to_ports(px_path, port_s, port_t)
        waypoints = _compact(px_path)
        full_path = [(int(port_s["px"]), int(port_s["py"]))] + waypoints + [(int(port_t["px"]), int(port_t["py"]))]
        candidates = _label_candidates(full_path)
        routes[(src, tgt)] = {
            "exit_x":  port_s["fx"], "exit_y":  port_s["fy"],
            "entry_x": port_t["fx"], "entry_y": port_t["fy"],
            "points":  waypoints,
            "label_x": candidates[0]["frac"],
            "label_dx": candidates[0]["dx"],
            "label_dy": candidates[0]["dy"],
            "_label_candidates": candidates,
        }
        edge_keys[i] = (src, tgt)

    def _edge_len(item):
        _, src, tgt = item
        sx, sy = nodes_pos[src]
        tx, ty = nodes_pos[tgt]
        return abs(sx - tx) + abs(sy - ty)

    for i, src, tgt in sorted(edges, key=_edge_len):
        _route_one(i, src, tgt)

    def _decrement_cells(i: int) -> None:
        path = edge_cells.get(i, [])
        for k in range(len(path) - 1):
            ax, ay = path[k]
            bx, by = path[k + 1]
            if ax == bx:
                used_v[path[k]] = max(0, used_v[path[k]] - 1)
                used_v[path[k + 1]] = max(0, used_v[path[k + 1]] - 1)
            elif ay == by:
                used_h[path[k]] = max(0, used_h[path[k]] - 1)
                used_h[path[k + 1]] = max(0, used_h[path[k + 1]] - 1)

    # port-swap pass disabled: the swap cost (Manhattan + bends) sometimes accepts
    # a worse port assignment because the bend count is misleading. Default sort
    # by neighbor Y is already good in most cases.
    # n_swaps = _try_port_swaps(edges, ports, bboxes, routes, _route_one, edge_cells, _decrement_cells)

    # rip-up & reroute: edges that share cells with many others get rerouted
    for _pass in range(RIPUP_PASSES):
        worst = _find_worst_crossers(edge_cells, n=max(1, len(edges) // 3))
        if not worst:
            break
        for i in worst:
            _decrement_cells(i)
            src, tgt = edge_keys[i]
            _route_one(i, src, tgt)

    # resolve label collisions: greedy selection of candidates
    _select_labels(routes)

    return routes


def _select_labels(routes: dict) -> None:
    """Greedy candidate selection:
    - Bias toward source end of the edge (cleaner for symmetric layouts).
    - Penalize candidates near edge×edge crossings.
    - Penalize candidates colliding with previously placed labels.
    - Reject candidates with offset > MAX_LABEL_OFFSET from own line.
    """
    LABEL_W, LABEL_H = 48, 14
    CROSSING_RADIUS = 30   # px

    def _box(pixel):
        return (pixel[0] - LABEL_W // 2, pixel[1] - LABEL_H // 2,
                pixel[0] + LABEL_W // 2, pixel[1] + LABEL_H // 2)

    def _overlap(a, b) -> int:
        ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
        iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
        return ix * iy

    # find all edge×edge crossing points (perpendicular segment intersections)
    segments = []  # (key, axis_horiz, axis_value, low, high)
    for key, r in routes.items():
        if r.get("connector"):
            continue
        pts = r.get("points", [])
        for i in range(len(pts) - 1):
            ax, ay = pts[i]
            bx, by = pts[i + 1]
            if ay == by:
                segments.append((key, True, ay, min(ax, bx), max(ax, bx)))
            elif ax == bx:
                segments.append((key, False, ax, min(ay, by), max(ay, by)))
    crossings: list[tuple[int, int]] = []
    for i in range(len(segments)):
        ki, hi, vi, lo_i, hi_i = segments[i]
        for j in range(i + 1, len(segments)):
            kj, hj, vj, lo_j, hi_j = segments[j]
            if ki == kj or set(ki) & set(kj):
                continue
            if hi == hj:
                continue
            # one horizontal, one vertical: intersection at (V.axis, H.axis)
            if hi:
                hx_lo, hx_hi, hy = lo_i, hi_i, vi
                vx, vy_lo, vy_hi = vj, lo_j, hi_j
            else:
                hx_lo, hx_hi, hy = lo_j, hi_j, vj
                vx, vy_lo, vy_hi = vi, lo_i, hi_i
            if hx_lo < vx < hx_hi and vy_lo < hy < vy_hi:
                crossings.append((vx, hy))

    def _crossing_penalty(pixel) -> int:
        px, py = pixel
        for cx, cy in crossings:
            if abs(cx - px) < CROSSING_RADIUS and abs(cy - py) < CROSSING_RADIUS:
                return 1
        return 0

    placed: list[tuple[tuple[int, int, int, int], tuple]] = []
    items = sorted(routes.items(), key=lambda kv: -len(kv[1].get("_label_candidates", [])))
    for key, r in items:
        cands = r.get("_label_candidates", [])
        if not cands:
            continue
        # determine total path length to compute per-candidate distance from source
        total_len = max((c["source_dist"] for c in cands), default=0)

        best = cands[0]
        best_score = 1e18
        for c in cands:
            own_dist = abs(c["dx"]) + abs(c["dy"])
            if own_dist > MAX_LABEL_OFFSET:
                continue
            # padding: keep label clear of source/target ports
            if c["source_dist"] < MIN_LABEL_FROM_PORT:
                continue
            if (total_len - c["source_dist"]) < MIN_LABEL_FROM_PORT:
                continue
            cb = _box(c["pixel"])
            collision = sum(_overlap(cb, pb) for pb, _ in placed)
            near_crossing = _crossing_penalty(c["pixel"])
            source_bias = c["source_dist"] * 0.5
            score = (collision * 100
                     + near_crossing * 200
                     + source_bias
                     + own_dist)
            if score < best_score:
                best_score = score
                best = c
        # if no candidate satisfied the padding, relax constraint and try again
        if best_score == 1e18:
            for c in cands:
                own_dist = abs(c["dx"]) + abs(c["dy"])
                if own_dist > MAX_LABEL_OFFSET:
                    continue
                cb = _box(c["pixel"])
                collision = sum(_overlap(cb, pb) for pb, _ in placed)
                score = collision * 100 + own_dist
                if score < best_score:
                    best_score = score
                    best = c
        placed.append((_box(best["pixel"]), key))
        r["label_x"]  = best["frac"]
        r["label_dx"] = best["dx"]
        r["label_dy"] = best["dy"]
        r.pop("_label_candidates", None)


def _try_port_swaps(edges, ports, bboxes, routes, route_one, edge_cells, decrement_cells) -> int:
    """For each (node, side) with 2+ edges, try swapping pairs of ports if the swap
    reduces cost. Returns count of accepted swaps."""
    n_accepted = 0
    by_side: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, src, tgt in edges:
        by_side[(src, ports[(i, "src")]["side"])].append(("src", i))
        by_side[(tgt, ports[(i, "tgt")]["side"])].append(("tgt", i))

    def _cost(i):
        """Manhattan distance from port pixels to other endpoint + bend count."""
        for ii, s, t in edges:
            if ii == i:
                ps = ports[(ii, "src")]
                pt = ports[(ii, "tgt")]
                d = abs(ps["px"] - pt["px"]) + abs(ps["py"] - pt["py"])
                pts = routes.get((s, t), {}).get("points", [])
                bends = max(0, len(pts) - 1)
                return d + bends * 30
        return 0

    for (node, side), members in by_side.items():
        if len({i for _, i in members}) < 2:
            continue
        # collect (which_end, edge_idx) tuples
        for a_idx in range(len(members)):
            for b_idx in range(a_idx + 1, len(members)):
                a_end, ia = members[a_idx]
                b_end, ib = members[b_idx]
                if ia == ib:
                    continue
                # current cost
                cost_before = _cost(ia) + _cost(ib)
                # swap fx/fy on the relevant ports
                pa = ports[(ia, a_end)]
                pb = ports[(ib, b_end)]
                pa["fx"], pb["fx"] = pb["fx"], pa["fx"]
                pa["fy"], pb["fy"] = pb["fy"], pa["fy"]
                pa["px"], pb["px"] = pb["px"], pa["px"]
                pa["py"], pb["py"] = pb["py"], pa["py"]
                # rip up the two edges' contribution
                for ec in (ia, ib):
                    decrement_cells(ec)
                # re-route both
                for ec in (ia, ib):
                    for ee in edges:
                        if ee[0] == ec:
                            route_one(ec, ee[1], ee[2])
                            break
                cost_after = _cost(ia) + _cost(ib)
                if cost_after >= cost_before:
                    # revert
                    pa["fx"], pb["fx"] = pb["fx"], pa["fx"]
                    pa["fy"], pb["fy"] = pb["fy"], pa["fy"]
                    pa["px"], pb["px"] = pb["px"], pa["px"]
                    pa["py"], pb["py"] = pb["py"], pa["py"]
                    for ec in (ia, ib):
                        decrement_cells(ec)
                    for ec in (ia, ib):
                        for ee in edges:
                            if ee[0] == ec:
                                route_one(ec, ee[1], ee[2])
                                break
                else:
                    n_accepted += 1
    return n_accepted


def _find_worst_crossers(
    edge_cells: dict[int, list[tuple[int, int]]],
    n: int,
) -> list[int]:
    """Return up to n edge indices ranked by total cell-overlap with other edges."""
    cell_to_edges: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, cells in edge_cells.items():
        for c in cells:
            cell_to_edges[c].append(i)
    score: dict[int, int] = defaultdict(int)
    for c, idxs in cell_to_edges.items():
        if len(idxs) <= 1:
            continue
        for i in idxs:
            score[i] += len(idxs) - 1
    return [i for i, _ in sorted(score.items(), key=lambda kv: -kv[1])[:n] if score[i] > 0]


# ── port assignment ───────────────────────────────────────────────────────────

def _assign_ports(
    edges: list[tuple[int, str, str]],
    bboxes: dict[str, tuple[int, int, int, int]],
) -> dict[tuple[int, str], dict]:
    """Pick a side for each end of each edge based on relative geometry,
    then distribute multiple edges on the same side along that side."""
    raw: list[tuple[int, str, str, str, str]] = []
    by_side: dict[tuple[str, str], list[int]] = defaultdict(list)

    for i, src, tgt in edges:
        side_s = _pick_side(bboxes[src], bboxes[tgt])
        side_t = _pick_side(bboxes[tgt], bboxes[src])
        raw.append((i, src, tgt, side_s, side_t))
        by_side[(src, side_s)].append(i)
        by_side[(tgt, side_t)].append(i)

    # for each (node, side), distribute ports along the side
    port_offsets: dict[tuple[int, str, str], float] = {}
    for (node, side), idxs in by_side.items():
        # sort by other endpoint position so ports are in nice order
        def sort_key(idx: int) -> float:
            for j, src, tgt, _, _ in raw:
                if j == idx:
                    other = tgt if src == node else src
                    return (bboxes[other][0] + bboxes[other][2]) / 2 \
                        if side in ("top", "bottom") \
                        else (bboxes[other][1] + bboxes[other][3]) / 2
            return 0.0
        idxs.sort(key=sort_key)
        n = len(idxs)
        for k, idx in enumerate(idxs):
            port_offsets[(idx, node, side)] = (k + 1) / (n + 1)

    ports: dict[tuple[int, str], dict] = {}
    for i, src, tgt, side_s, side_t in raw:
        frac_s = port_offsets[(i, src, side_s)]
        frac_t = port_offsets[(i, tgt, side_t)]
        ports[(i, "src")] = _port_info(bboxes[src], side_s, frac_s)
        ports[(i, "tgt")] = _port_info(bboxes[tgt], side_t, frac_t)
    return ports


def _pick_side(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> str:
    """Pick which side of box a faces box b.

    Uses overlap: vertical overlap → left/right; horizontal overlap → top/bottom.
    Without overlap, biases toward vertical (factor 2x) because layered diagrams
    expect cross-layer flow to be vertical even when dx is somewhat larger than dy.
    """
    ax = (a[0] + a[2]) / 2
    ay = (a[1] + a[3]) / 2
    bx = (b[0] + b[2]) / 2
    by = (b[1] + b[3]) / 2

    if not (b[3] <= a[1] or b[1] >= a[3]):
        return "right" if bx > ax else "left"
    if not (b[2] <= a[0] or b[0] >= a[2]):
        return "bottom" if by > ay else "top"
    # no overlap: bias toward vertical for cleaner layered flow
    if abs(by - ay) * 2 >= abs(bx - ax):
        return "bottom" if by > ay else "top"
    return "right" if bx > ax else "left"


def _port_info(bbox: tuple[int, int, int, int], side: str, frac: float) -> dict:
    """Compute pixel position + draw.io fractional coords for a port."""
    x1, y1, x2, y2 = bbox
    w, h = x2 - x1, y2 - y1
    if side == "top":
        return {"side": side, "px": x1 + frac * w, "py": y1, "fx": frac, "fy": 0.0}
    if side == "bottom":
        return {"side": side, "px": x1 + frac * w, "py": y2, "fx": frac, "fy": 1.0}
    if side == "left":
        return {"side": side, "px": x1, "py": y1 + frac * h, "fx": 0.0, "fy": frac}
    return {"side": side, "px": x2, "py": y1 + frac * h, "fx": 1.0, "fy": frac}


def _side_dir(side: str) -> tuple[int, int]:
    return {"top": (0, -1), "bottom": (0, 1), "left": (-1, 0), "right": (1, 0)}[side]


def _port_cell(port: dict, bbox, to_cell, outside: bool) -> tuple[int, int]:
    """Pick the grid cell just outside the node's bbox at the port location."""
    side = port["side"]
    dx, dy = _side_dir(side) if outside else (0, 0)
    cx, cy = to_cell(port["px"] + dx * CELL, port["py"] + dy * CELL)
    return (cx, cy)


# ── A* ────────────────────────────────────────────────────────────────────────

def _astar(
    start: tuple[int, int],
    goal: tuple[int, int],
    blocked: set[tuple[int, int]],
    cols: int,
    rows: int,
    used_h: dict[tuple[int, int], int],
    used_v: dict[tuple[int, int], int],
    init_dir: tuple[int, int],
    near_obstacle: set[tuple[int, int]],
    label_h_blocked: set[tuple[int, int]] | None = None,
) -> list[tuple[int, int]]:
    label_h_blocked = label_h_blocked or set()
    if start in blocked or goal in blocked:
        # nudge: allow start/goal even if technically blocked (port edge cases)
        blocked = blocked - {start, goal}

    def h(c):
        return abs(c[0] - goal[0]) + abs(c[1] - goal[1])

    # state = (cell, incoming_dir)
    start_state = (start, init_dir)
    open_heap: list = [(h(start), 0, start_state, None)]
    came_from: dict = {}
    g_score: dict = {start_state: 0}

    DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    while open_heap:
        _, g, state, parent = heapq.heappop(open_heap)
        cell, incoming = state

        if cell == goal:
            # reconstruct
            path = [cell]
            cur = (state, parent)
            while cur[1] is not None:
                prev_state, prev_parent = cur
                _, pdir = prev_state
                path.append(prev_parent[0])
                cur = (prev_parent, came_from.get(prev_parent))
            path.reverse()
            return path

        if g > g_score.get(state, 1e18):
            continue

        for d in DIRS:
            nx, ny = cell[0] + d[0], cell[1] + d[1]
            if nx < 0 or ny < 0 or nx >= cols or ny >= rows:
                continue
            nc = (nx, ny)
            if nc in blocked:
                continue
            # directional label block: horizontal movement banned in label zones
            is_horiz = d[0] != 0
            if is_horiz and nc in label_h_blocked:
                continue
            turn = TURN_COST if d != incoming else 0
            # directional congestion: same direction = heavy, perpendicular = light
            if is_horiz:
                cong = used_h.get(nc, 0) * CONGEST_COST + used_v.get(nc, 0) * CROSS_COST
            else:
                cong = used_v.get(nc, 0) * CONGEST_COST + used_h.get(nc, 0) * CROSS_COST
            near = NEAR_PENALTY if nc in near_obstacle else 0
            ng = g + STEP_COST + turn + cong + near
            nstate = (nc, d)
            if ng < g_score.get(nstate, 1e18):
                g_score[nstate] = ng
                came_from[nstate] = state
                heapq.heappush(open_heap, (ng + h(nc), ng, nstate, state))

    return []


# ── post-processing ──────────────────────────────────────────────────────────

def _anchor_path_to_ports(px_path: list[tuple[int, int]], port_s: dict, port_t: dict) -> list[tuple[int, int]]:
    """Prepend/append axis-aligned waypoints at each port so the first and
    last segments are guaranteed orthogonal and don't cross the source/target box.
    """
    if not px_path:
        return px_path
    pts = list(px_path)

    sx, sy = int(port_s["px"]), int(port_s["py"])
    if port_s["side"] in ("top", "bottom"):
        # vertical leg from port to first A* cell's y, then horizontal to A* cell
        leg = (sx, pts[0][1])
    else:
        leg = (pts[0][0], sy)
    if leg != pts[0]:
        pts.insert(0, leg)

    tx, ty = int(port_t["px"]), int(port_t["py"])
    if port_t["side"] in ("top", "bottom"):
        leg = (tx, pts[-1][1])
    else:
        leg = (pts[-1][0], ty)
    if leg != pts[-1]:
        pts.append(leg)

    return pts


MAX_LABEL_OFFSET = 16   # px; label can't be further than this from its own segment
MIN_LABEL_FROM_PORT = 25  # px; label can't be closer than this to source/target port


def _label_candidates(pts: list[tuple[int, int]]) -> list[dict]:
    """Generate a ranked list of candidate label placements for an edge.

    Each candidate is {frac, dx, dy, pixel, dir, segment_len}.
    The first candidate is the default (longest segment); rest are fallbacks.
    """
    if len(pts) < 2:
        return [{"frac": 0.0, "dx": 0, "dy": -10, "pixel": pts[0], "dir": "H", "segment_len": 0}]

    seg_lens = []
    total = 0.0
    for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        L = abs(bx - ax) + abs(by - ay)
        seg_lens.append(L)
        total += L
    if total == 0:
        return [{"frac": 0.0, "dx": 0, "dy": -10, "pixel": pts[0], "dir": "H", "segment_len": 0}]

    # generate candidates on each segment, biased toward source end.
    # positions along segment: 0.25 (preferred — near start of segment),
    # 0.5 (mid), 0.75 (toward end). We'll score and pick later.
    candidates: list[dict] = []
    for seg_i in range(len(seg_lens)):
        if seg_lens[seg_i] < 20:
            continue
        ax, ay = pts[seg_i]
        bx, by = pts[seg_i + 1]
        is_horiz = abs(bx - ax) >= abs(by - ay)
        for pos in (0.25, 0.5, 0.75):
            mx = int(ax + (bx - ax) * pos)
            my = int(ay + (by - ay) * pos)
            cum = sum(seg_lens[:seg_i]) + seg_lens[seg_i] * pos
            frac = (cum / total) * 2 - 1
            for off in (10, -10, 14, -14):
                if is_horiz:
                    dx, dy = 0, -off
                    pixel = (mx, my + dy)
                else:
                    dx, dy = off, 0
                    pixel = (mx + dx, my)
                candidates.append({
                    "frac": frac, "dx": dx, "dy": dy,
                    "pixel": pixel,
                    "dir": "H" if is_horiz else "V",
                    "segment_len": seg_lens[seg_i],
                    "segment_idx": seg_i,
                    "source_dist": cum,   # distance from source along path
                })
    return candidates or [{"frac": 0.0, "dx": 0, "dy": -10, "pixel": pts[0],
                           "dir": "H", "segment_len": 0, "segment_idx": 0,
                           "source_dist": 0.0}]


def _label_position(pts: list[tuple[int, int]]) -> tuple[float, int, int]:
    """Backward-compat: pick the top candidate (longest segment, midpoint)."""
    c = _label_candidates(pts)[0]
    return c["frac"], c["dx"], c["dy"]


def _compact(pts: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Remove collinear intermediate points so we keep only corners."""
    if len(pts) <= 2:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        ax, ay = out[-1]
        bx, by = pts[i]
        cx, cy = pts[i + 1]
        # collinear if both segments are horizontal or both vertical
        if (ax == bx == cx) or (ay == by == cy):
            continue
        out.append(pts[i])
    out.append(pts[-1])
    return out
