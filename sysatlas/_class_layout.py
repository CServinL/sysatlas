"""UML class diagram layout.

Inheritance / implementation relations drive a hierarchical layout:
ancestors above descendants. Other relations (association, composition,
aggregation, dependency) don't affect layering — they overlay on the
hierarchy. Within a rank, classes are placed left-to-right.
"""
from __future__ import annotations

from collections import defaultdict

CLASS_W = 180
HEADER_H = 32
ROW_H = 18
SECTION_PAD = 4
H_GAP = 60
V_GAP = 80
MARGIN = 40
MIN_BODY_H = ROW_H


def class_height(klass) -> int:
    attrs = len(klass.attributes)
    methods = len(klass.methods)
    body_h = max(attrs * ROW_H, ROW_H) + max(methods * ROW_H, ROW_H) + SECTION_PAD
    return HEADER_H + body_h


def compute_class_layout(diagram):
    """Return (positions, sizes, routes)."""
    classes = diagram.classes
    relations = diagram.relations

    parents: dict[str, list[str]] = defaultdict(list)  # child -> ancestors
    for r in relations:
        if r.kind in ("inheritance", "implementation"):
            parents[r.source].append(r.target)

    rank: dict[str, int] = {}

    def _rank(n: str, stack: set[str]) -> int:
        if n in rank:
            return rank[n]
        if n in stack:
            return 0
        stack = stack | {n}
        if not parents[n]:
            rank[n] = 0
            return 0
        r = max(_rank(p, stack) for p in parents[n]) + 1
        rank[n] = r
        return r

    for name in classes:
        _rank(name, set())

    rows: dict[int, list[str]] = defaultdict(list)
    for name in classes:
        rows[rank[name]].append(name)

    pos: dict[str, tuple[int, int]] = {}
    size: dict[str, tuple[int, int]] = {}

    cur_y = MARGIN
    # Higher rank = further from root parent = lower in diagram.
    for r in sorted(rows):
        row = rows[r]
        row_h = max((class_height(classes[n]) for n in row), default=HEADER_H + MIN_BODY_H)
        x = MARGIN
        for n in row:
            h = class_height(classes[n])
            pos[n] = (x, cur_y + (row_h - h) // 2)
            size[n] = (CLASS_W, h)
            x += CLASS_W + H_GAP
        cur_y += row_h + V_GAP

    routes: list[dict] = []
    for r in relations:
        if r.source not in pos or r.target not in pos:
            continue
        routes.append({
            "source": r.source,
            "target": r.target,
            "kind": r.kind,
            "label": r.label,
            "source_mult": r.source_multiplicity,
            "target_mult": r.target_multiplicity,
        })
    return pos, size, routes
