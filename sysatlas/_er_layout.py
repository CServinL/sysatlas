"""ER-diagram layout.

Simple grid placement: entities flow left-to-right, wrapping into rows.
Entity height grows with attribute count. Relationship lines connect
right-of-source to left-of-target with an orthogonal elbow.
"""
from __future__ import annotations

ENTITY_W = 200
ATTR_ROW_H = 18
HEADER_H = 28
MIN_ENTITY_H = HEADER_H + ATTR_ROW_H
H_GAP = 80
V_GAP = 70
MARGIN = 40
COLS = 3


def entity_height(n_attrs: int) -> int:
    return HEADER_H + max(1, n_attrs) * ATTR_ROW_H


def compute_er_layout(diagram):
    """Return (positions, sizes, routes)."""
    entities = list(diagram.entities.values())
    pos: dict[str, tuple[int, int]] = {}
    size: dict[str, tuple[int, int]] = {}

    row_heights: list[int] = []
    for row_start in range(0, len(entities), COLS):
        row = entities[row_start:row_start + COLS]
        h = max((entity_height(len(e.attributes)) for e in row), default=MIN_ENTITY_H)
        row_heights.append(h)

    for i, e in enumerate(entities):
        col = i % COLS
        row = i // COLS
        x = MARGIN + col * (ENTITY_W + H_GAP)
        y = MARGIN + sum(row_heights[:row]) + row * V_GAP
        h = entity_height(len(e.attributes))
        pos[e.name] = (x, y)
        size[e.name] = (ENTITY_W, h)

    routes: dict[tuple[str, str, str], dict] = {}
    for i, r in enumerate(diagram.relationships):
        sp = pos.get(r.source)
        tp = pos.get(r.target)
        if not sp or not tp:
            continue
        sw, sh = size[r.source]
        tw, th = size[r.target]
        sx, sy = sp
        tx, ty = tp
        if tx >= sx:
            x0 = sx + sw
            x1 = tx
            ex, en = 1.0, 0.0
        else:
            x0 = sx
            x1 = tx + tw
            ex, en = 0.0, 1.0
        y0 = sy + sh // 2
        y1 = ty + th // 2
        mid_x = (x0 + x1) // 2
        routes[(r.source, r.target, r.name + str(i))] = {
            "points": [(mid_x, y0), (mid_x, y1)],
            "exit_x": ex, "exit_y": 0.5,
            "entry_x": en, "entry_y": 0.5,
            "label":  r.name,
            "source_card": r.source_card,
            "target_card": r.target_card,
        }
    return pos, size, routes
