"""State-machine layout.

Layered top-down placement: initial state on top, final on bottom,
others arranged by BFS distance from initial. Composite states
contain their children; the parent box is sized to enclose them.
"""
from __future__ import annotations

from collections import defaultdict, deque

STATE_W = 130
STATE_H = 50
PSEUDO_R = 24
H_GAP = 60
V_GAP = 70
MARGIN = 40
COMPOSITE_PAD = 18
COMPOSITE_HEADER_H = 24


def compute_state_layout(diagram):
    """Return (positions, sizes, kinds, routes)."""
    states = diagram.states
    transitions = diagram.transitions

    children: dict[str | None, list[str]] = defaultdict(list)
    for s in states.values():
        children[s.parent].append(s.name)

    pos: dict[str, tuple[int, int]] = {}
    size: dict[str, tuple[int, int]] = {}
    kind: dict[str, str] = {n: s.kind for n, s in states.items()}

    def _layout_group(parent_name: str | None, origin_x: int, origin_y: int) -> tuple[int, int]:
        kids = children[parent_name]
        if not kids:
            return (0, 0)

        adj: dict[str, list[str]] = defaultdict(list)
        for t in transitions:
            if t.source in kids and t.target in kids:
                adj[t.source].append(t.target)

        initials = [k for k in kids if states[k].kind == "initial"]
        rank: dict[str, int] = {}
        queue: deque[str] = deque()
        if initials:
            for k in initials:
                rank[k] = 0
                queue.append(k)
        else:
            rank[kids[0]] = 0
            queue.append(kids[0])

        while queue:
            cur = queue.popleft()
            for nb in adj.get(cur, []):
                if nb not in rank:
                    rank[nb] = rank[cur] + 1
                    queue.append(nb)
        max_rank = max(rank.values(), default=0)
        for k in kids:
            if k not in rank:
                rank[k] = max_rank + 1
            if states[k].kind == "final":
                rank[k] = max(rank.values()) + 1

        rows: dict[int, list[str]] = defaultdict(list)
        for k in kids:
            rows[rank[k]].append(k)

        cur_y = origin_y
        max_right = origin_x
        row_keys = sorted(rows)
        for r in row_keys:
            row_states = rows[r]
            row_h = STATE_H
            child_widths: list[int] = []
            for n in row_states:
                if states[n].kind == "composite":
                    cw, ch = _layout_group(n, 0, 0)
                    child_widths.append(cw)
                    row_h = max(row_h, ch + COMPOSITE_HEADER_H + COMPOSITE_PAD * 2)
                elif states[n].kind in ("initial", "final", "choice"):
                    child_widths.append(PSEUDO_R * 2)
                else:
                    child_widths.append(STATE_W)

            row_w = sum(child_widths) + H_GAP * max(len(row_states) - 1, 0)
            x = origin_x
            for i, n in enumerate(row_states):
                w = child_widths[i]
                if states[n].kind == "composite":
                    inner_w, inner_h = _layout_group(n, x + COMPOSITE_PAD,
                                                     cur_y + COMPOSITE_HEADER_H + COMPOSITE_PAD)
                    cw = inner_w + COMPOSITE_PAD * 2
                    ch = inner_h + COMPOSITE_HEADER_H + COMPOSITE_PAD * 2
                    pos[n] = (x, cur_y)
                    size[n] = (cw, ch)
                    x += cw + H_GAP
                elif states[n].kind in ("initial", "final", "choice"):
                    pos[n] = (x, cur_y + (row_h - PSEUDO_R * 2) // 2)
                    size[n] = (PSEUDO_R * 2, PSEUDO_R * 2)
                    x += PSEUDO_R * 2 + H_GAP
                else:
                    pos[n] = (x, cur_y + (row_h - STATE_H) // 2)
                    size[n] = (STATE_W, STATE_H)
                    x += STATE_W + H_GAP
            max_right = max(max_right, x - H_GAP)
            cur_y += row_h + V_GAP
        return (max_right - origin_x, cur_y - V_GAP - origin_y)

    _layout_group(None, MARGIN, MARGIN)

    routes: list[dict] = []
    for i, t in enumerate(transitions):
        if t.source not in pos or t.target not in pos:
            continue
        routes.append({
            "source": t.source, "target": t.target,
            "label": _transition_label(t),
            "idx": i,
        })
    return pos, size, kind, routes


def _transition_label(t) -> str:
    parts: list[str] = []
    if t.event:
        parts.append(t.event)
    if t.guard:
        parts.append(f"[{t.guard}]")
    if t.action:
        parts.append(f"/ {t.action}")
    return " ".join(parts)
