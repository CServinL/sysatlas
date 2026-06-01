"""Fluent builder for state machine diagrams.

Renders through the C4 layered engine: states become nodes, transitions
become edges, composite states become swimlane groups. BFS distance
from the initial pseudo-state drives layer assignment, so the diagram
flows top-to-bottom just like an architecture view.
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Literal

from sysatlas._ontology.state_machine import State, StateDiagram, Transition
from sysatlas._render import copy_local_viewer, render

StateKind = Literal["normal", "initial", "final", "choice", "composite"]

_NORMAL_STYLE = (
    "rounded=1;arcSize=30;whiteSpace=wrap;html=1;fillColor=#dbeafe;"
    "strokeColor=#1e40af;fontFamily=monospace;fontSize=11;"
)
_INITIAL_STYLE = (
    "ellipse;whiteSpace=wrap;html=1;fillColor=#1f2937;strokeColor=#1f2937;"
)
_FINAL_STYLE = (
    "shape=doubleEllipse;whiteSpace=wrap;html=1;fillColor=#ffffff;"
    "strokeColor=#1f2937;strokeWidth=2;"
)
_CHOICE_STYLE = (
    "rhombus;whiteSpace=wrap;html=1;fillColor=#fef9c3;strokeColor=#a16207;fontSize=10;"
)

_TRANSITION_STYLE = (
    "rounded=1;exitX={ex};exitY={ey};exitDx=0;exitDy=0;"
    "entryX={en};entryY={ny};entryDx=0;entryDy=0;"
    "strokeColor={color};strokeWidth=1.5;fontSize=10;"
    "labelBackgroundColor=#ffffff;labelBorderColor=none;"
    "endArrow=block;endFill=1;"
)


class StateMap:
    """Build a state machine one state and transition at a time."""

    def __init__(self, title: str = "") -> None:
        self._states: dict[str, State] = {}
        self._transitions: list[Transition] = []
        self._title = title

    @property
    def diagram(self) -> StateDiagram:
        return StateDiagram(title=self._title, states=self._states,
                            transitions=self._transitions)

    def state(self, name: str, *, kind: StateKind = "normal",
              label: str | None = None, parent: str | None = None,
              entry: str | None = None, exit: str | None = None,
              do: str | None = None) -> "StateMap":
        self._states[name] = State(
            name=name, kind=kind, label=label, parent=parent,
            entry_action=entry, exit_action=exit, do_activity=do,
        )
        return self

    def initial(self, name: str = "__initial__", *, parent: str | None = None) -> "StateMap":
        return self.state(name, kind="initial", parent=parent)

    def final(self, name: str = "__final__", *, parent: str | None = None) -> "StateMap":
        return self.state(name, kind="final", parent=parent)

    def transition(self, source: str, target: str, *, event: str = "",
                   guard: str = "", action: str = "") -> "StateMap":
        self._transitions.append(Transition(
            source=source, target=target,
            event=event, guard=guard, action=action,
        ))
        return self

    def _to_architecture(self):
        diagram = self.diagram
        states = diagram.states
        transitions = diagram.transitions

        adj: dict[str, list[str]] = defaultdict(list)
        for t in transitions:
            adj[t.source].append(t.target)

        rank: dict[str, int] = {}
        initials = [n for n, s in states.items() if s.kind == "initial"]
        queue: deque[str] = deque()
        for n in initials:
            rank[n] = 0
            queue.append(n)
        while queue:
            cur = queue.popleft()
            for nb in adj.get(cur, []):
                if nb not in rank:
                    rank[nb] = rank[cur] + 1
                    queue.append(nb)
        next_rank = max(rank.values(), default=-1) + 1
        for n in states:
            if n not in rank:
                rank[n] = next_rank
        terminal_rank = max(rank.values(), default=0) + 1
        for n, s in states.items():
            if s.kind == "final":
                rank[n] = terminal_rank

        max_rank = max(rank.values(), default=0)
        layer_order = [f"r{i}" for i in range(max_rank + 1)]

        nodes: dict[str, dict] = {}
        for name, s in states.items():
            base_label = (s.label or name)
            extras: list[str] = []
            if s.entry_action:
                extras.append(f"entry / {s.entry_action}")
            if s.do_activity:
                extras.append(f"do / {s.do_activity}")
            if s.exit_action:
                extras.append(f"exit / {s.exit_action}")
            label = base_label
            if extras:
                label += "<br><i>" + "<br>".join(extras) + "</i>"

            node: dict = {"layer": f"r{rank[name]}"}
            if s.parent:
                node["group"] = s.parent

            if s.kind == "initial":
                node.update({"label": " ", "style": _INITIAL_STYLE,
                             "width": 48, "height": 48})
            elif s.kind == "final":
                node.update({"label": " ", "style": _FINAL_STYLE,
                             "width": 52, "height": 52})
            elif s.kind == "choice":
                node.update({"label": base_label, "style": _CHOICE_STYLE,
                             "width": 60, "height": 60})
            elif s.kind == "composite":
                node.update({"label": label, "style": _NORMAL_STYLE})
            else:
                node.update({"label": label, "style": _NORMAL_STYLE})
            nodes[name] = node

        groups: dict[str, dict] = {}
        for name, s in states.items():
            if s.kind == "composite":
                groups[name] = {"label": s.label or name}

        edges: list[dict] = []
        for t in transitions:
            if t.source not in nodes or t.target not in nodes:
                continue
            parts: list[str] = []
            if t.event:
                parts.append(t.event)
            if t.guard:
                parts.append(f"[{t.guard}]")
            if t.action:
                parts.append(f"/ {t.action}")
            edges.append({
                "source": t.source, "target": t.target,
                "label": " ".join(parts),
                "color": "#1f2937",
                "style_full": _TRANSITION_STYLE,
            })

        return nodes, edges, groups, layer_order

    def show(self, viewer: str = "cdn") -> None:
        import os
        import tempfile
        import webbrowser
        nodes, edges, groups, layer_order = self._to_architecture()
        html = render(nodes, edges, groups, layer_order,
                      strategy="layered", title=self._title, viewer=viewer)
        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
        tmp.write(html)
        tmp.close()
        if viewer == "local":
            copy_local_viewer(os.path.dirname(tmp.name))
        print(f"[sysatlas] → {tmp.name}")
        webbrowser.open(f"file://{tmp.name}")

    def save(self, path: str, viewer: str = "cdn") -> None:
        import os
        nodes, edges, groups, layer_order = self._to_architecture()
        html = render(nodes, edges, groups, layer_order,
                      strategy="layered", title=self._title, viewer=viewer)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        if viewer == "local":
            copy_local_viewer(os.path.dirname(os.path.abspath(path)))
