"""Sequence-diagram layout.

Actors get evenly-spaced vertical lifelines (columns). Messages are
laid out top-to-bottom in `order`. Activations and frames are rectangles
positioned from the same actor X / message Y grid.
"""
from __future__ import annotations

ACTOR_W = 140
ACTOR_H = 50
ACTOR_GAP = 80
MARGIN_X = 60
MARGIN_Y = 40
MSG_PITCH = 50
LIFELINE_BOTTOM_PAD = 40
ACTIVATION_W = 12
FRAME_PAD_X = 20
FRAME_PAD_Y = 16
FRAME_HEADER_H = 22


def compute_sequence_layout(diagram):
    """Return (actor_pos, msg_y, activation_rects, frame_rects, lifeline_bottom)."""
    actor_names = list(diagram.actors.keys())
    actor_x: dict[str, int] = {}
    for i, name in enumerate(actor_names):
        actor_x[name] = MARGIN_X + i * (ACTOR_W + ACTOR_GAP)

    msgs = sorted(diagram.messages, key=lambda m: m.order)
    msg_y: dict[int, int] = {}
    base_y = MARGIN_Y + ACTOR_H + 30
    for i, m in enumerate(msgs):
        msg_y[m.order] = base_y + i * MSG_PITCH

    last_y = base_y + max(len(msgs) - 1, 0) * MSG_PITCH
    lifeline_bottom = last_y + LIFELINE_BOTTOM_PAD

    activation_rects: list[dict] = []
    for a in diagram.activations:
        x = actor_x[a.actor] + ACTOR_W // 2 - ACTIVATION_W // 2
        y0 = msg_y.get(a.start_order, base_y)
        y1 = msg_y.get(a.end_order, last_y)
        activation_rects.append({
            "actor": a.actor,
            "x": x, "y": y0,
            "w": ACTIVATION_W, "h": max(y1 - y0, MSG_PITCH // 2),
        })

    frame_rects: list[dict] = []
    for f in diagram.frames:
        y0 = msg_y.get(f.start_order, base_y) - FRAME_PAD_Y - FRAME_HEADER_H
        y1 = msg_y.get(f.end_order, last_y) + FRAME_PAD_Y
        x0 = min(actor_x.values()) - FRAME_PAD_X
        x1 = max(actor_x.values()) + ACTOR_W + FRAME_PAD_X
        frame_rects.append({
            "kind": f.kind, "label": f.label,
            "x": x0, "y": y0,
            "w": x1 - x0, "h": y1 - y0,
        })

    return actor_x, msg_y, activation_rects, frame_rects, lifeline_bottom
