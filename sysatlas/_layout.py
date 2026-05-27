from __future__ import annotations

import networkx as nx

from sysatlas._connectors import classify_edges
from sysatlas._place import refine_placement
from sysatlas._route import route_edges, compute_node_heights

NODE_W = 160
NODE_H = 60
X_GAP  = 80
Y_GAP  = 100   # minimum gap; expands dynamically per gutter
_GROUP_CHROME = 72   # fixed swimlane chrome stacked between adjacent
                     # sub-band node boxes: 24px bottom-pad of group A
                     # + 24px title bar of group B + 24px top-pad of group B.
SUB_GAP = 40         # visible whitespace between two adjacent group rectangles.

_MARGIN_X    = 80
_MARGIN_Y    = 80
_GUTTER_STEP = 14   # px to separate overlapping gutter segments


def compute_layout(
    nodes: dict[str, dict],
    edges: list[dict],
    layer_order: list[str],
    max_epochs: int = 10,
    debug: bool = False,
) -> tuple[dict[str, tuple[int, int]], dict[tuple[str, str], dict], dict[str, int]]:
    """
    Returns (pos, routes, node_heights).

    node_heights: per-node height overrides (only nodes that grew taller than NODE_H).
    """
    real_nodes = set(nodes.keys())
    G      = _build_dag(nodes, edges)
    rank   = _assign_ranks(G, nodes, layer_order)
    G_aug, rank_aug, dummy_chains = _insert_dummies(edges, rank, nodes)
    layers = _build_layers(rank_aug, G_aug)
    layers = _minimize_crossings(G_aug, layers)

    direct_edges, connector_edges = classify_edges(edges, rank)
    direct_set = {(e["source"], e["target"]) for e in direct_edges}

    # gutter sizing: count direct edges crossing each rank boundary, plus
    # space for connector glyphs landing in each gutter.
    y_gaps = _gutter_sizes(direct_edges, rank, len(layers), connector_edges)

    pos_all, _ = _assign_coords(layers, real_nodes, y_gaps, nodes_meta=nodes)
    pos = {n: pos_all[n] for n in nodes if n in pos_all}

    real_layers = [[n for n in layer if n in real_nodes] for layer in layers]
    if debug:
        print(f"\n── Gutter sizes (rank → px gap): {y_gaps}")
        print("── Placement refinement ──────────────")
    pos = refine_placement(pos, real_layers, edges, NODE_W, X_GAP,
                           nodes_meta=nodes, debug=debug)

    valid_edges: list[tuple[int, str, str]] = []
    for i, e in enumerate(edges):
        src, tgt = e["source"], e["target"]
        if (src, tgt) not in direct_set:
            continue
        if src in pos and tgt in pos and src != tgt:
            valid_edges.append((i, src, tgt))

    # compute per-node heights to fit all ports on the tallest side
    direct_edges_dicts = [{"source": s, "target": t} for _, s, t in valid_edges]
    node_heights = compute_node_heights(direct_edges_dicts, pos, default_h=NODE_H)

    # compute group label zones (top 24px of each group's bbox) so the router
    # treats them as hard obstacles — lines never cross group titles.
    label_zones = _group_label_zones(pos, nodes, layer_order, node_heights)

    # connector glyph zones — also hard obstacles so direct edges don't slice
    # through them visually. Source-side glyph below source, target-side above target.
    connector_zones = _connector_zones(connector_edges, pos, node_heights)

    routes = route_edges(pos, (NODE_W, NODE_H), valid_edges,
                         label_zones=label_zones,
                         block_zones=connector_zones,
                         node_heights=node_heights)

    # connector edges: emit a marker that render layer expands into 2 glyphs
    for e in connector_edges:
        src, tgt = e["source"], e["target"]
        if src in pos and tgt in pos:
            routes[(src, tgt)] = {"connector": True}

    # swap-and-reroute: try adjacent node swaps in each layer; keep if real
    # (post-A*) crossing count decreases.
    pos, routes, n_accepted = _swap_and_reroute(
        pos, routes, layers, real_nodes, valid_edges, connector_edges,
        label_zones=label_zones, node_heights=node_heights, debug=debug
    )

    if debug:
        print(f"\n── A* routed {len(valid_edges)} direct, "
              f"{len(connector_edges)} via connectors ──")
        if n_accepted:
            print(f"  swap+reroute swaps accepted: {n_accepted}")
        grew = {n: h for n, h in node_heights.items() if h > NODE_H}
        if grew:
            print(f"  nodes grown for ports: {grew}")
        _report_issues(pos, routes)

    return pos, routes, node_heights


def finalize_routing(
    pos: dict[str, tuple[int, int]],
    nodes: dict[str, dict],
    edges: list[dict],
    layer_order: list[str] | None = None,
    debug: bool = False,
) -> tuple[dict[tuple[str, str], dict], dict[str, int]]:
    """Strategy-agnostic post-placement pipeline.

    Reuses what `compute_layout` already builds — port-aware node heights,
    group label / connector obstacle zones, A* edge routing — so any
    placement engine (layered, hub, future strategies) gets the same
    routing quality without duplicating the work.

    Skips Sugiyama-only steps (rank-based connector classification,
    swap-and-reroute). Every edge between two placed nodes is treated
    as a direct edge and routed with A*.
    """
    layer_order = layer_order or []
    valid_edges: list[tuple[int, str, str]] = []
    for i, e in enumerate(edges):
        s, t = e["source"], e["target"]
        if s in pos and t in pos and s != t:
            valid_edges.append((i, s, t))

    direct_edges_dicts = [{"source": s, "target": t} for _, s, t in valid_edges]
    node_heights = compute_node_heights(direct_edges_dicts, pos, default_h=NODE_H)

    label_zones = _group_label_zones(pos, nodes, layer_order, node_heights)
    # No connector-glyph zones: non-Sugiyama strategies don't promote long
    # spans to off-page connectors.
    routes = route_edges(pos, (NODE_W, NODE_H), valid_edges,
                         label_zones=label_zones,
                         block_zones=[],
                         node_heights=node_heights)

    if debug:
        print(f"\n── A* routed {len(valid_edges)} edges (hub/non-Sugiyama) ──")
        _report_issues(pos, routes)

    return routes, node_heights


def _swap_and_reroute(pos, routes, layers, real_nodes, valid_edges, connector_edges, label_zones=None, node_heights=None, debug=False):
    """For each adjacent pair within each layer, try swapping their X positions.
    Re-route all edges with the new placement; keep the swap only if the cost
    decreases. Cost = crossings × 1000 + weighted edge-length, where the weight
    is the # of edges between the two endpoints (heavily-connected pairs penalized
    more for being far apart)."""
    from sysatlas._place import neighbor_weights
    edge_w = neighbor_weights(
        [{"source": s, "target": t} for _, s, t in valid_edges]
        + list(connector_edges)
    )

    def _weighted_length(pos_d) -> float:
        total = 0.0
        for n, w_map in edge_w.items():
            if n not in pos_d:
                continue
            for m, w in w_map.items():
                if m in pos_d:
                    total += w * (abs(pos_d[n][0] - pos_d[m][0])
                                  + abs(pos_d[n][1] - pos_d[m][1]))
        return total / 2  # each pair counted twice

    def _count_crossings(routes_d, pos_d):
        bboxes = {n: (x, y, x + NODE_W, y + NODE_H) for n, (x, y) in pos_d.items()}
        segments = []
        for (s, t), r in routes_d.items():
            if r.get("connector"):
                continue
            pts = r.get("points", [])
            if not pts or s not in pos_d or t not in pos_d:
                continue
            sx, sy = pos_d[s]
            tx, ty = pos_d[t]
            ex = sx + r.get("exit_x", 0.5) * NODE_W
            ey = sy + r.get("exit_y", 1.0) * NODE_H
            entx = tx + r.get("entry_x", 0.5) * NODE_W
            enty = ty + r.get("entry_y", 0.0) * NODE_H
            full = [(int(ex), int(ey))] + pts + [(int(entx), int(enty))]
            for i in range(len(full) - 1):
                segments.append((s, t, full[i], full[i + 1]))
        c = 0
        for i in range(len(segments)):
            si, ti, ai, bi = segments[i]
            for j in range(i + 1, len(segments)):
                sj, tj, aj, bj = segments[j]
                if {si, ti} & {sj, tj}:
                    continue
                if _segs_cross(ai, bi, aj, bj):
                    c += 1
        return c

    def _do_route(pos_d):
        cz = _connector_zones(connector_edges, pos_d, node_heights)
        r = route_edges(pos_d, (NODE_W, NODE_H), valid_edges,
                        label_zones=label_zones, block_zones=cz,
                        node_heights=node_heights)
        for e in connector_edges:
            s, t = e["source"], e["target"]
            if s in pos_d and t in pos_d:
                r[(s, t)] = {"connector": True}
        return r

    def _cost(routes_d, pos_d) -> float:
        # crossings × 200 keeps crossings dominant for low-weight diagrams,
        # but weighted_length matters enough that swaps don't separate
        # heavily-connected pairs.
        return _count_crossings(routes_d, pos_d) * 200 + _weighted_length(pos_d)

    cur_cost = _cost(routes, pos)
    accepted = 0

    for layer in layers:
        real = sorted([n for n in layer if n in pos and n in real_nodes],
                      key=lambda n: pos[n][0])
        for k in range(len(real) - 1):
            n1, n2 = real[k], real[k + 1]
            p1, p2 = pos[n1], pos[n2]
            pos[n1], pos[n2] = (p2[0], p1[1]), (p1[0], p2[1])
            new_routes = _do_route(pos)
            new_cost = _cost(new_routes, pos)
            if new_cost < cur_cost:
                routes = new_routes
                cur_cost = new_cost
                accepted += 1
                if debug:
                    print(f"    swap [{n1} ↔ {n2}]  cost ↓")
            else:
                pos[n1], pos[n2] = p1, p2

    return pos, routes, accepted


def _report_issues(pos: dict[str, tuple[int, int]], routes: dict) -> None:
    """Scan rendered routes for edge-node crossings, edge-edge crossings,
    and dangling/short edges. Print summary in debug mode."""
    bboxes = {n: (x, y, x + NODE_W, y + NODE_H) for n, (x, y) in pos.items()}
    node_crossings: list[tuple[str, str, str]] = []  # (edge_src, edge_tgt, hit_node)
    short_edges:  list[tuple[str, str, int]] = []

    segments: list[tuple[str, str, tuple[int,int], tuple[int,int]]] = []
    for (s, t), r in routes.items():
        if r.get("connector"):
            continue
        pts = r.get("points", [])
        if not pts:
            short_edges.append((s, t, 0))
            continue
        # build full polyline including port pixels for accurate hit testing
        if s in pos and t in pos:
            sx, sy = pos[s]
            tx, ty = pos[t]
            ex = sx + r.get("exit_x", 0.5) * NODE_W
            ey = sy + r.get("exit_y", 1.0) * NODE_H
            entx = tx + r.get("entry_x", 0.5) * NODE_W
            enty = ty + r.get("entry_y", 0.0) * NODE_H
            full = [(int(ex), int(ey))] + pts + [(int(entx), int(enty))]
        else:
            full = pts
        for i in range(len(full) - 1):
            a, b = full[i], full[i + 1]
            segments.append((s, t, a, b))
            # check if segment passes through any non-(s,t) node bbox
            for n, bb in bboxes.items():
                if n == s or n == t:
                    continue
                if _seg_hits_bbox(a, b, bb):
                    node_crossings.append((s, t, n))

    # edge-edge crossings (count once)
    edge_crossings = 0
    for i in range(len(segments)):
        si, ti, ai, bi = segments[i]
        for j in range(i + 1, len(segments)):
            sj, tj, aj, bj = segments[j]
            if {si, ti} & {sj, tj}:
                continue  # shared endpoint, not a true crossing
            if _segs_cross(ai, bi, aj, bj):
                edge_crossings += 1

    # collinear overlaps: 2+ segments sharing the same y (horizontal) or x (vertical)
    # with overlapping ranges → visually indistinguishable lines
    overlaps = 0
    h_segs = [(s, t, a, b) for s, t, a, b in segments if a[1] == b[1]]
    v_segs = [(s, t, a, b) for s, t, a, b in segments if a[0] == b[0]]
    for i in range(len(h_segs)):
        si, ti, ai, bi = h_segs[i]
        y_i, lo_i, hi_i = ai[1], min(ai[0], bi[0]), max(ai[0], bi[0])
        for j in range(i + 1, len(h_segs)):
            sj, tj, aj, bj = h_segs[j]
            if {si, ti} & {sj, tj}:
                continue
            if aj[1] != y_i:
                continue
            lo_j, hi_j = min(aj[0], bj[0]), max(aj[0], bj[0])
            if min(hi_i, hi_j) - max(lo_i, lo_j) > 4:  # >4px overlap
                overlaps += 1
    for i in range(len(v_segs)):
        si, ti, ai, bi = v_segs[i]
        x_i, lo_i, hi_i = ai[0], min(ai[1], bi[1]), max(ai[1], bi[1])
        for j in range(i + 1, len(v_segs)):
            sj, tj, aj, bj = v_segs[j]
            if {si, ti} & {sj, tj}:
                continue
            if aj[0] != x_i:
                continue
            lo_j, hi_j = min(aj[1], bj[1]), max(aj[1], bj[1])
            if min(hi_i, hi_j) - max(lo_i, lo_j) > 4:
                overlaps += 1

    print(f"  layout issues:")
    print(f"    edge through node : {len(node_crossings)}")
    for s, t, n in node_crossings[:5]:
        print(f"      {s} → {t} crosses [{n}]")
    if len(node_crossings) > 5:
        print(f"      ... and {len(node_crossings) - 5} more")
    print(f"    edge × edge       : {edge_crossings}")
    print(f"    collinear overlap : {overlaps}")
    print(f"    short/dangling    : {len(short_edges)}")


def _seg_hits_bbox(a: tuple[int, int], b: tuple[int, int], bb: tuple[int, int, int, int]) -> bool:
    """True if segment a-b intersects the bbox interior (orthogonal segments only)."""
    x1, y1, x2, y2 = bb
    ax, ay = a
    bx, by = b
    if ax == bx:
        if not (x1 < ax < x2):
            return False
        lo, hi = (ay, by) if ay < by else (by, ay)
        return hi > y1 and lo < y2
    if ay == by:
        if not (y1 < ay < y2):
            return False
        lo, hi = (ax, bx) if ax < bx else (bx, ax)
        return hi > x1 and lo < x2
    return False


def _segs_cross(a1, a2, b1, b2) -> bool:
    """True if two orthogonal segments cross (one horizontal, one vertical, meeting in interior)."""
    a_horiz = a1[1] == a2[1]
    b_horiz = b1[1] == b2[1]
    if a_horiz == b_horiz:
        return False
    if a_horiz:
        hx1, hx2 = sorted([a1[0], a2[0]])
        hy = a1[1]
        vx = b1[0]
        vy1, vy2 = sorted([b1[1], b2[1]])
    else:
        hx1, hx2 = sorted([b1[0], b2[0]])
        hy = b1[1]
        vx = a1[0]
        vy1, vy2 = sorted([a1[1], a2[1]])
    return hx1 < vx < hx2 and vy1 < hy < vy2


def _group_label_zones(
    pos: dict[str, tuple[int, int]],
    nodes: dict[str, dict],
    layer_order: list[str],
    node_heights: dict[str, int] | None = None,
) -> list[tuple[int, int, int, int]]:
    node_heights = node_heights or {}
    """Return bboxes covering each group's title bar (top 24px of the swimlane).

    Computed from the bounding box of nodes in the group, with the same padding
    the renderer uses (24 startSize + 24 pad).
    """
    from collections import defaultdict
    grp_nodes: dict[str, list[str]] = defaultdict(list)
    for n, data in nodes.items():
        g = data.get("group")
        if g and n in pos:
            grp_nodes[g].append(n)
    zones: list[tuple[int, int, int, int]] = []
    for g, names in grp_nodes.items():
        xs = [pos[n][0] for n in names]
        ys = [pos[n][1] for n in names]
        pad = 24
        gx = min(xs) - pad
        gy = min(ys) - pad - 24      # matches _render group geometry
        gw = max(xs) + NODE_W - min(xs) + pad * 2
        # group label sits in the top 24px (swimlane startSize)
        zones.append((gx, gy, gx + gw, gy + 24))
    return zones


def _connector_zones(
    connector_edges: list[dict],
    pos: dict[str, tuple[int, int]],
    node_heights: dict[str, int] | None = None,
) -> list[tuple[int, int, int, int]]:
    """Approximate bboxes where connector glyphs will be rendered, so the
    router treats them as hard obstacles. Mirrors the rendering logic in
    _render.py: source-side glyph below source, target-side above target,
    horizontally stacked if multiple."""
    from collections import defaultdict
    from sysatlas._render import _CONNECTOR_W, _CONNECTOR_H, _CONNECTOR_GAP
    node_heights = node_heights or {}
    zones: list[tuple[int, int, int, int]] = []
    src_off: dict[str, int] = defaultdict(int)
    tgt_off: dict[str, int] = defaultdict(int)
    for e in connector_edges:
        s, t = e["source"], e["target"]
        if s in pos:
            sx, sy = pos[s]
            sh = node_heights.get(s, NODE_H)
            cx = sx + (NODE_W - _CONNECTOR_W) // 2 + src_off[s] * (_CONNECTOR_W + 4)
            cy = sy + sh + _CONNECTOR_GAP
            zones.append((cx, cy, cx + _CONNECTOR_W, cy + _CONNECTOR_H))
            src_off[s] += 1
        if t in pos:
            tx, ty = pos[t]
            cx = tx + (NODE_W - _CONNECTOR_W) // 2 + tgt_off[t] * (_CONNECTOR_W + 4)
            cy = ty - _CONNECTOR_H - _CONNECTOR_GAP
            zones.append((cx, cy, cx + _CONNECTOR_W, cy + _CONNECTOR_H))
            tgt_off[t] += 1
    return zones


def _gutter_sizes(
    direct_edges: list[dict],
    rank: dict[str, int],
    n_layers: int,
    connector_edges: list[dict] | None = None,
) -> dict[int, int]:
    """y_gap[r] = required gap between layer r and r+1.

    Components of the gap:
    - direct edges crossing it (14px channel each)
    - connector glyphs landing in it (30px each — source-side glyph below
      source layer, target-side glyph above target layer)
    - base margin (40px) so nothing crowds the layer boundaries
    """
    from collections import defaultdict
    connector_edges = connector_edges or []

    cross_count: dict[int, int] = defaultdict(int)
    for e in direct_edges:
        s, t = e["source"], e["target"]
        if s not in rank or t not in rank:
            continue
        a, b = sorted([rank[s], rank[t]])
        for r in range(a, b):
            cross_count[r] += 1

    # connector glyphs: source-side lives in gutter r=rank[s];
    # target-side lives in gutter r=rank[t]-1.
    connector_room: dict[int, int] = defaultdict(int)
    for e in connector_edges:
        s, t = e["source"], e["target"]
        if s in rank:
            connector_room[rank[s]] = max(connector_room[rank[s]], 30)
        if t in rank:
            connector_room[rank[t] - 1] = max(connector_room[rank[t] - 1], 30)

    return {
        r: max(Y_GAP, cross_count[r] * 14 + 40 + connector_room[r])
        for r in range(n_layers - 1)
    }


def _required_y_gaps(segs_per_rank: dict, overlap_ranks: set[int], current: dict) -> dict:
    new = dict(current)
    for r, n in segs_per_rank.items():
        needed = n * _GUTTER_STEP + 2 * _GUTTER_STEP
        new[r] = max(new.get(r, Y_GAP), needed)
    # ranks that still had overlapping segments after stagger need more space
    for r in overlap_ranks:
        new[r] = new.get(r, Y_GAP) + _GUTTER_STEP * 2
    return new


def _print_debug(epoch: int, stats: dict, y_gaps: dict) -> None:
    print(f"\n── Epoch {epoch} ──────────────────────────────")
    print(f"  forward          : {stats['forward']}")
    print(f"  same-layer       : {stats['same_layer']}")
    print(f"  segs/rank        : {dict(stats['segs_per_rank'])}")
    print(f"  overlap groups   : {stats['overlap_groups']}")
    print(f"  staggered        : {stats['staggered']}")
    print(f"  overlap ranks    : {stats['overlap_ranks']}")
    if y_gaps:
        print(f"  y_gaps           : {y_gaps}")


# ── DAG construction ──────────────────────────────────────────────────────────

def _build_dag(nodes: dict, edges: list[dict]) -> nx.DiGraph:
    G = nx.DiGraph()
    G.add_nodes_from(nodes)
    for e in edges:
        src, tgt = e["source"], e["target"]
        if src in nodes and tgt in nodes and src != tgt:
            G.add_edge(src, tgt)
            if not nx.is_directed_acyclic_graph(G):
                G.remove_edge(src, tgt)
    return G


# ── Rank assignment ───────────────────────────────────────────────────────────

def _assign_ranks(G: nx.DiGraph, nodes: dict, layer_order: list[str]) -> dict[str, int]:
    layer_to_rank = {layer: i for i, layer in enumerate(layer_order)}
    rank: dict[str, int] = {}

    for name, data in nodes.items():
        layer = data.get("layer")
        if layer and layer in layer_to_rank:
            rank[name] = layer_to_rank[layer]

    for node in nx.topological_sort(G):
        if node in rank:
            continue
        ranked_preds = [p for p in G.predecessors(node) if p in rank]
        rank[node] = (max(rank[p] for p in ranked_preds) + 1) if ranked_preds else 0

    for node in nodes:
        rank.setdefault(node, 0)

    return rank


# ── Dummy node insertion ──────────────────────────────────────────────────────

def _insert_dummies(
    edges: list[dict],
    rank: dict[str, int],
    real_nodes: dict,
) -> tuple[nx.DiGraph, dict[str, int], dict[tuple[str, str], list[str]]]:
    G_aug = nx.DiGraph()
    for name in real_nodes:
        G_aug.add_node(name, dummy=False)

    rank_aug = dict(rank)
    dummy_chains: dict[tuple[str, str], list[str]] = {}

    for edge in edges:
        src, tgt = edge["source"], edge["target"]
        if src not in rank or tgt not in rank:
            continue
        r_src, r_tgt = rank[src], rank[tgt]

        if r_tgt <= r_src + 1:
            G_aug.add_edge(src, tgt)
            continue

        chain: list[str] = []
        prev = src
        for r in range(r_src + 1, r_tgt):
            dummy = f"__dummy_{src}__{tgt}__{r}"
            G_aug.add_node(dummy, dummy=True)
            rank_aug[dummy] = r
            G_aug.add_edge(prev, dummy)
            chain.append(dummy)
            prev = dummy
        G_aug.add_edge(prev, tgt)
        dummy_chains[(src, tgt)] = chain

    return G_aug, rank_aug, dummy_chains


# ── Layer building ────────────────────────────────────────────────────────────

def _build_layers(rank: dict[str, int], G: nx.DiGraph) -> list[list[str]]:
    if not rank:
        return []
    max_rank = max(rank.values())
    layers: list[list[str]] = [[] for _ in range(max_rank + 1)]
    for node in G.nodes:
        layers[rank.get(node, 0)].append(node)
    return layers


# ── Crossing minimization (barycenter) ───────────────────────────────────────

def _minimize_crossings(G: nx.DiGraph, layers: list[list[str]], passes: int = 4) -> list[list[str]]:
    layers = [list(layer) for layer in layers]

    def _bary(node: str, neighbor_pos: dict[str, int], nbrs_fn) -> float:
        nbrs = [n for n in nbrs_fn(node) if n in neighbor_pos]
        return sum(neighbor_pos[n] for n in nbrs) / len(nbrs) if nbrs else float("inf")

    for _ in range(passes):
        for i in range(1, len(layers)):
            prev_pos = {n: j for j, n in enumerate(layers[i - 1])}
            layers[i].sort(key=lambda n: _bary(n, prev_pos, G.predecessors))
        for i in range(len(layers) - 2, -1, -1):
            next_pos = {n: j for j, n in enumerate(layers[i + 1])}
            layers[i].sort(key=lambda n: _bary(n, next_pos, G.successors))

    return layers


# ── Coordinate assignment ─────────────────────────────────────────────────────

def _assign_coords(
    layers: list[list[str]],
    real_nodes: set[str],
    y_gaps: dict[int, int] | None = None,
    nodes_meta: dict[str, dict] | None = None,
) -> tuple[dict[str, tuple[int, int]], dict[int, int]]:
    """Returns (pos, layer_tops) where layer_tops[r] = y coordinate of rank r.

    When a layer hosts >1 distinct group, its real nodes are sub-banded:
    each group gets its own y inside the layer (stable order by first
    appearance). Layer height grows accordingly.
    """
    y_gaps = y_gaps or {}
    nodes_meta = nodes_meta or {}
    pos: dict[str, tuple[int, int]] = {}
    layer_tops: dict[int, int] = {}

    def _band_index(layer: list[str]) -> tuple[dict[str | None, int], int]:
        order: list[str | None] = []
        for n in layer:
            if n not in real_nodes:
                continue
            g = nodes_meta.get(n, {}).get("group")
            if g not in order:
                order.append(g)
        if not order:
            return ({}, 1)
        return ({g: i for i, g in enumerate(order)}, len(order))

    cumulative_y = _MARGIN_Y
    prev_layer_h = 0
    for r, layer in enumerate(layers):
        if r > 0:
            cumulative_y += prev_layer_h + y_gaps.get(r - 1, Y_GAP)
        layer_top = cumulative_y
        layer_tops[r] = layer_top

        band_of, n_bands = _band_index(layer)
        prev_layer_h = NODE_H + (n_bands - 1) * (NODE_H + _GROUP_CHROME + SUB_GAP)
        center_y = layer_top + (prev_layer_h - NODE_H) // 2

        def _y_for(name: str) -> int:
            if name not in real_nodes:
                return center_y
            g = nodes_meta.get(name, {}).get("group")
            return layer_top + band_of.get(g, 0) * (NODE_H + _GROUP_CHROME + SUB_GAP)

        real = [n for n in layer if n in real_nodes]
        if not real:
            for i, n in enumerate(layer):
                pos[n] = (_MARGIN_X + i * (NODE_W + X_GAP), center_y)
            continue

        total_w = len(real) * NODE_W + max(0, len(real) - 1) * X_GAP
        x_start = max(_MARGIN_X, 600 - total_w // 2)

        for i, n in enumerate(real):
            pos[n] = (x_start + i * (NODE_W + X_GAP), _y_for(n))

        # dummies: proportional x within real-node centre span; y = layer middle
        cx_min = x_start + NODE_W // 2
        cx_max = x_start + (len(real) - 1) * (NODE_W + X_GAP) + NODE_W // 2
        n_all  = len(layer)
        for i, n in enumerate(layer):
            if n in real_nodes:
                continue
            frac = i / max(n_all - 1, 1) if n_all > 1 else 0.5
            pos[n] = (int(cx_min + frac * (cx_max - cx_min)), center_y)

    return pos, layer_tops


# ── Edge routing ──────────────────────────────────────────────────────────────

def _compute_edge_routes(
    edges: list[dict],
    rank: dict[str, int],
    rank_aug: dict[str, int],
    dummy_chains: dict[tuple[str, str], list[str]],
    pos_all: dict[str, tuple[int, int]],
    layer_tops: dict[int, int],
    y_gaps: dict[int, int],
) -> tuple[dict[tuple[str, str], dict], dict]:
    from collections import defaultdict

    valid: list[tuple[int, str, str]] = []
    out_per_node: dict[str, list] = defaultdict(list)
    in_per_node:  dict[str, list] = defaultdict(list)
    segs_per_rank: dict[int, int]  = defaultdict(int)

    for i, e in enumerate(edges):
        src, tgt = e["source"], e["target"]
        if src not in pos_all or tgt not in pos_all:
            continue
        if rank.get(tgt, 0) <= rank.get(src, 0):
            continue
        valid.append((i, src, tgt))
        out_per_node[src].append((i, pos_all[tgt][0]))
        in_per_node[tgt].append((i, pos_all[src][0]))
        for r in range(rank.get(src, 0), rank.get(tgt, 0)):
            segs_per_rank[r] += 1

    exit_frac:  dict[int, float] = {}
    entry_frac: dict[int, float] = {}

    for items in out_per_node.values():
        items.sort(key=lambda x: x[1])
        n = len(items)
        for k, (idx, _) in enumerate(items):
            exit_frac[idx] = (k + 1) / (n + 1)

    for items in in_per_node.values():
        items.sort(key=lambda x: x[1])
        n = len(items)
        for k, (idx, _) in enumerate(items):
            entry_frac[idx] = (k + 1) / (n + 1)

    def _gutter_y(r_a: int) -> int:
        lt  = layer_tops.get(r_a, _MARGIN_Y + r_a * (NODE_H + Y_GAP))
        gap = y_gaps.get(r_a, Y_GAP)
        return lt + NODE_H + gap // 2

    routes: dict[tuple[str, str], dict] = {}

    # forward cross-layer edges
    for i, src, tgt in valid:
        ex = exit_frac.get(i, 0.5)
        en = entry_frac.get(i, 0.5)
        sx = pos_all[src][0]
        tx = pos_all[tgt][0]
        exit_px  = sx + ex * NODE_W
        entry_px = tx + en * NODE_W

        chain = [src] + dummy_chains.get((src, tgt), []) + [tgt]
        pts: list[tuple[int, int]] = []

        for seg in range(len(chain) - 1):
            a, b = chain[seg], chain[seg + 1]
            if a not in pos_all or b not in pos_all:
                continue
            r_a = rank_aug.get(a, rank.get(a, 0))
            gy  = _gutter_y(r_a)
            ax  = exit_px  if seg == 0              else pos_all[a][0] + NODE_W / 2
            bx  = entry_px if seg == len(chain) - 2 else pos_all[b][0] + NODE_W / 2
            pts.append((int(ax), gy))
            if abs(ax - bx) > 1:
                pts.append((int(bx), gy))

        routes[(src, tgt)] = {
            "exit_x": ex, "exit_y": 1.0,
            "entry_x": en, "entry_y": 0.0,
            "points": pts,
        }

    # same-layer edges: bump below the layer
    same_by_rank: dict[int, list] = defaultdict(list)
    for e in edges:
        src, tgt = e["source"], e["target"]
        if (src, tgt) in routes:
            continue
        if src not in pos_all or tgt not in pos_all:
            continue
        if rank.get(src, 0) != rank.get(tgt, 0):
            continue
        same_by_rank[rank[src]].append((src, tgt))

    n_same = 0
    for r, pairs in same_by_rank.items():
        ly = layer_tops.get(r, _MARGIN_Y + r * (NODE_H + Y_GAP))
        pairs.sort(key=lambda p: abs(pos_all[p[0]][0] - pos_all[p[1]][0]))
        for k, (src, tgt) in enumerate(pairs):
            below_y = ly + NODE_H + (k + 1) * _GUTTER_STEP
            ex_px   = pos_all[src][0] + NODE_W * 0.5
            en_px   = pos_all[tgt][0] + NODE_W * 0.5
            routes[(src, tgt)] = {
                "exit_x": 0.5, "exit_y": 1.0,
                "entry_x": 0.5, "entry_y": 1.0,
                "points": [(int(ex_px), below_y), (int(en_px), below_y)],
            }
            n_same += 1

    # stagger overlapping gutter segments
    n_groups, n_staggered, overlap_ranks = _stagger_gutter_segments(routes, layer_tops)

    stats = {
        "forward":        len(valid),
        "same_layer":     n_same,
        "segs_per_rank":  segs_per_rank,
        "overlap_groups": n_groups,
        "staggered":      n_staggered,
        "overlap_ranks":  overlap_ranks,
    }
    return routes, stats


def _stagger_gutter_segments(routes: dict, layer_tops: dict[int, int]) -> tuple[int, int, set[int]]:
    """Vertically separate horizontal segments that share the same gutter y."""
    from collections import defaultdict

    # build reverse map: gutter_y → rank (approximate: pick rank whose gutter is closest)
    def _y_to_rank(gy: int) -> int:
        best_r, best_d = 0, 10**9
        for r, lt in layer_tops.items():
            d = abs(gy - (lt + NODE_H))
            if d < best_d:
                best_d, best_r = d, r
        return best_r

    gutter: dict[int, list] = defaultdict(list)
    for key, route in routes.items():
        pts = route["points"]
        for i in range(len(pts) - 1):
            ax, ay = pts[i]
            bx, by = pts[i + 1]
            if ay == by:
                gutter[ay].append((key, i, min(ax, bx), max(ax, bx)))

    n_groups = n_staggered = 0
    overlap_ranks: set[int] = set()

    for gy, segs in gutter.items():
        if len(segs) <= 1:
            continue
        segs.sort(key=lambda s: s[2])

        groups: list[list] = []
        cur = [segs[0]]
        cur_max = segs[0][3]
        for seg in segs[1:]:
            if seg[2] <= cur_max:
                cur.append(seg)
                cur_max = max(cur_max, seg[3])
            else:
                groups.append(cur)
                cur = [seg]
                cur_max = seg[3]
        groups.append(cur)

        for group in groups:
            n = len(group)
            if n <= 1:
                continue
            n_groups  += 1
            n_staggered += n
            overlap_ranks.add(_y_to_rank(gy))
            for k, (key, pi, _, _) in enumerate(group):
                new_y = gy + int((k - (n - 1) / 2) * _GUTTER_STEP)
                pts = routes[key]["points"]
                ax, _ = pts[pi]
                bx, _ = pts[pi + 1]
                pts[pi]     = (ax, new_y)
                pts[pi + 1] = (bx, new_y)

    return n_groups, n_staggered, overlap_ranks
