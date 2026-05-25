from __future__ import annotations

from collections import defaultdict

MAX_Y_OFFSET = 30   # max ±px each node can shift within its layer band


def neighbor_weights(edges: list[dict]) -> dict[str, dict[str, int]]:
    """For each node, build a {neighbor → connection count} map.

    The count is the number of edges between the two nodes (in either direction).
    Used as pull strength in placement: heavier weight = closer in the layout.
    """
    w: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for e in edges:
        s, t = e["source"], e["target"]
        if s == t:
            continue
        w[s][t] += 1
        w[t][s] += 1
    return w


def neighbors_by_strength(edges: list[dict], node: str) -> list[tuple[str, int]]:
    """Return [(neighbor, count), …] sorted by count descending.
    Higher-ranked neighbors should sit closer in the layout."""
    w = neighbor_weights(edges)
    return sorted(w[node].items(), key=lambda kv: -kv[1])


GROUP_WEIGHT = 0.4   # 0 = ignore groups, 1 = only cluster by group


def refine_placement(
    pos: dict[str, tuple[int, int]],
    layers: list[list[str]],
    edges: list[dict],
    node_w: int,
    x_gap: int,
    nodes_meta: dict[str, dict] | None = None,
    max_iters: int = 30,
    tol: float = 1.0,
    debug: bool = False,
) -> dict[str, tuple[int, int]]:
    """Iteratively slide nodes toward the barycenter of their neighbors,
    biased toward same-group siblings if nodes_meta is provided."""
    # weighted neighbor map: more edges = stronger pull
    weights = neighbor_weights(edges)
    adj: dict[str, list[str]] = defaultdict(list)
    for n, w_map in weights.items():
        if n not in pos:
            continue
        for m in w_map:
            if m in pos:
                adj[n].append(m)

    # group siblings per layer (for clustering)
    group_of: dict[str, str | None] = {}
    if nodes_meta:
        for n, m in nodes_meta.items():
            group_of[n] = m.get("group")
    siblings_in_layer: dict[str, list[str]] = defaultdict(list)
    for layer in layers:
        by_group: dict[str | None, list[str]] = defaultdict(list)
        for n in layer:
            by_group[group_of.get(n)].append(n)
        for g, mates in by_group.items():
            if g is None:
                continue
            for n in mates:
                siblings_in_layer[n] = [m for m in mates if m != n]

    pos = {n: (x, y) for n, (x, y) in pos.items()}
    pitch = node_w + x_gap

    for it in range(max_iters):
        new_pos = dict(pos)
        max_delta = 0.0

        for layer in layers:
            real = [n for n in layer if n in pos]
            if not real:
                continue

            # current y is fixed per layer
            y = pos[real[0]][1]

            # target x = blend(weighted barycenter of neighbors, group barycenter)
            # weighted: each neighbor's x is multiplied by edge-count to that neighbor,
            # so heavily-connected pairs converge toward each other faster.
            targets: dict[str, float] = {}
            for n in real:
                w_map = weights.get(n, {})
                nbrs = [(m, w) for m, w in w_map.items() if m in pos]
                if nbrs:
                    total_w = sum(w for _, w in nbrs)
                    edge_tgt = sum(w * pos[m][0] for m, w in nbrs) / total_w
                else:
                    edge_tgt = float(pos[n][0])
                mates = [m for m in siblings_in_layer.get(n, []) if m in pos]
                if mates:
                    group_tgt = sum(pos[m][0] for m in mates) / len(mates)
                    targets[n] = (1 - GROUP_WEIGHT) * edge_tgt + GROUP_WEIGHT * group_tgt
                else:
                    targets[n] = edge_tgt

            # damping: small step toward target each iteration
            alpha = 0.2
            ordered = sorted(real, key=lambda n: pos[n][0])  # keep current order
            damped = [(n, (1 - alpha) * pos[n][0] + alpha * targets[n]) for n in ordered]

            # resolve min-pitch conflicts using a balanced sweep:
            # forward sweep pushes right neighbors, backward sweep pulls left ones.
            xs = [x for _, x in damped]
            for i in range(1, len(xs)):
                if xs[i] < xs[i - 1] + pitch:
                    xs[i] = xs[i - 1] + pitch
            for i in range(len(xs) - 2, -1, -1):
                if xs[i] > xs[i + 1] - pitch:
                    xs[i] = xs[i + 1] - pitch

            for (n, _), nx in zip(damped, xs):
                nx_i = int(round(nx))
                ox, _ = pos[n]
                new_pos[n] = (nx_i, y)
                max_delta = max(max_delta, abs(nx_i - ox))

        pos = new_pos
        if debug:
            print(f"  place iter {it}: max Δx = {max_delta:.1f}")
        if max_delta < tol:
            break

    # Y-offset pass: each node shifts within ±MAX_Y_OFFSET toward neighbor barycenter Y
    pos = _refine_y(pos, layers, adj, debug=debug)

    # adjacent-swap layer ordering to reduce crossings (greedy local search)
    # disabled: endpoint-only cost diverges from A*-routed reality; needs reroute-in-loop
    # pos = _swap_minimize_crossings(pos, layers, edges, node_w, pitch, debug=debug)

    # spread narrow layers to match widest layer's span
    pos = _spread_layers(pos, layers, node_w, pitch, debug=debug)

    # global center pass: align each layer's center of mass to the same X
    pos = _center_layers(pos, layers, debug=debug)

    return pos


def _swap_minimize_crossings(
    pos: dict[str, tuple[int, int]],
    layers: list[list[str]],
    edges: list[dict],
    node_w: int,
    pitch: int,
    max_passes: int = 5,
    debug: bool = False,
) -> dict[str, tuple[int, int]]:
    """Greedy adjacent-swap: for each pair of neighbors in a layer, swap their
    X positions if it reduces edge crossings to/from adjacent layers."""
    pos = dict(pos)
    # build per-layer ordered list of node names (sorted by x)
    layer_order: list[list[str]] = []
    for layer in layers:
        real = [n for n in layer if n in pos]
        layer_order.append(sorted(real, key=lambda n: pos[n][0]))

    # build adjacency map: node → set of neighbor names
    adj: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        s, t = e["source"], e["target"]
        if s in pos and t in pos and s != t:
            adj[s].add(t)
            adj[t].add(s)

    def _cost_at(li: int) -> float:
        """Combined cost: crossings × 100 + sum of |x_src - x_tgt| (edge length penalty).
        Uses the CURRENT positions implied by the layer ordering."""
        if not layer_order[li]:
            return 0
        c = 0
        length = 0.0
        for other_li in (li - 1, li + 1):
            if other_li < 0 or other_li >= len(layer_order):
                continue
            # positions in current layer based on order (uniform spacing)
            xs_this = {n: k for k, n in enumerate(layer_order[li])}
            xs_other = {n: k for k, n in enumerate(layer_order[other_li])}
            es: list[tuple[int, int]] = []
            for n in layer_order[li]:
                for m in adj[n]:
                    if m in xs_other:
                        es.append((xs_this[n], xs_other[m]))
                        length += abs(xs_this[n] - xs_other[m])
            for a in range(len(es)):
                for b in range(a + 1, len(es)):
                    (x1, y1), (x2, y2) = es[a], es[b]
                    if (x1 - x2) * (y1 - y2) < 0:
                        c += 1
        # crossings dominate; length only breaks ties between equally-crossing orderings
        return c * 1000 + length

    total_swaps = 0
    for _ in range(max_passes):
        any_swap = False
        for li, layer in enumerate(layer_order):
            for k in range(len(layer) - 1):
                before = _cost_at(li)
                layer[k], layer[k + 1] = layer[k + 1], layer[k]
                after = _cost_at(li)
                if after < before:
                    any_swap = True
                    total_swaps += 1
                else:
                    layer[k], layer[k + 1] = layer[k + 1], layer[k]
        if not any_swap:
            break

    # rewrite x positions to reflect new order, keeping layer center
    new_pos = dict(pos)
    for layer in layer_order:
        if not layer:
            continue
        xs = sorted(pos[n][0] for n in layer)
        # reassign sorted xs to nodes in new order
        for k, n in enumerate(layer):
            new_pos[n] = (xs[k], pos[n][1])

    if debug and total_swaps:
        print(f"  ordering swaps applied: {total_swaps}")
    return new_pos


def _spread_layers(
    pos: dict[str, tuple[int, int]],
    layers: list[list[str]],
    node_w: int,
    pitch: int,
    target_ratio: float = 0.65,
    debug: bool = False,
) -> dict[str, tuple[int, int]]:
    """For sparse layers, enforce a wider min pitch (proportional to the widest
    layer's span). Doesn't fully stretch — uses target_ratio of widest span as goal."""
    spans: list[tuple[int, int, int]] = []
    for i, layer in enumerate(layers):
        real = [n for n in layer if n in pos]
        if not real:
            continue
        xs = [pos[n][0] for n in real]
        spans.append((i, min(xs), max(xs) + node_w))
    if not spans:
        return pos

    max_span = max(hi - lo for _, lo, hi in spans)
    target_span = int(max_span * target_ratio)
    new_pos = dict(pos)
    moved_layers = []
    for i, lo, hi in spans:
        real = sorted([n for n in layers[i] if n in pos], key=lambda n: pos[n][0])
        if len(real) < 2:
            continue
        cur_span = hi - lo
        if cur_span >= target_span:
            continue  # already wide enough
        # expand to target_span centered on current center
        center = (lo + hi) // 2
        new_lo = center - target_span // 2
        gap = (target_span - len(real) * node_w) // (len(real) - 1)
        if gap < pitch - node_w:
            continue
        for k, n in enumerate(real):
            new_x = new_lo + k * (node_w + gap)
            new_pos[n] = (new_x, pos[n][1])
        moved_layers.append(i)
    if debug and moved_layers:
        print(f"  layer spread: layers {moved_layers} expanded to {target_span}px ({target_ratio:.0%} of {max_span}px)")
    return new_pos


def _center_layers(
    pos: dict[str, tuple[int, int]],
    layers: list[list[str]],
    debug: bool = False,
) -> dict[str, tuple[int, int]]:
    """Compute the global center of mass across all layers, then shift each
    layer so its own center matches the global center. Keeps layers balanced."""
    all_real = [n for layer in layers for n in layer if n in pos]
    if not all_real:
        return pos
    global_cx = sum(pos[n][0] for n in all_real) / len(all_real)

    new_pos = dict(pos)
    shifts = []
    for layer in layers:
        real = [n for n in layer if n in pos]
        if not real:
            continue
        layer_cx = sum(pos[n][0] for n in real) / len(real)
        dx = int(round(global_cx - layer_cx))
        if dx != 0:
            for n in real:
                x, y = pos[n]
                new_pos[n] = (x + dx, y)
        shifts.append(dx)
    if debug:
        print(f"  layer centering shifts: {shifts}")
    return new_pos


def _refine_y(
    pos: dict[str, tuple[int, int]],
    layers: list[list[str]],
    adj: dict[str, list[str]],
    debug: bool = False,
) -> dict[str, tuple[int, int]]:
    """Shift each node up or down within ±MAX_Y_OFFSET toward neighbor Y barycenter.
    Nodes in the same layer keep their relative ordering (no swaps)."""
    new_pos = dict(pos)
    moved = 0
    for layer in layers:
        if not layer:
            continue
        base_y = pos[layer[0]][1]
        for n in layer:
            nbrs = [m for m in adj[n] if m in pos]
            if not nbrs:
                continue
            avg_y = sum(pos[m][1] for m in nbrs) / len(nbrs)
            # bias toward neighbor avg, but clamp to ±MAX_Y_OFFSET around base
            delta = avg_y - base_y
            delta = max(-MAX_Y_OFFSET, min(MAX_Y_OFFSET, delta))
            new_y = int(round(base_y + 0.5 * delta))
            if new_y != pos[n][1]:
                moved += 1
            new_pos[n] = (pos[n][0], new_y)
    if debug:
        print(f"  Y-offset: shifted {moved} nodes (±{MAX_Y_OFFSET}px max)")
    return new_pos
