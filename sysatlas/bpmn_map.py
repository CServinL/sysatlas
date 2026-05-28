"""Fluent builder for BPMN process diagrams."""
from __future__ import annotations

from typing import Literal

from sysatlas._bpmn_render import render_bpmn
from sysatlas._ontology.bpmn import (
    Activity, BPMNDiagram, Event, Flow, Gateway, Lane, Pool,
)
from sysatlas._render import copy_local_viewer

EventKind    = Literal["start", "end", "intermediate", "timer", "message", "error"]
ActivityKind = Literal["task", "user_task", "service_task", "subprocess", "call_activity"]
GatewayKind  = Literal["exclusive", "parallel", "inclusive", "event_based"]
FlowKind     = Literal["sequence", "message", "default", "conditional"]


class BPMNMap:
    """Build a BPMN process diagram one node at a time."""

    def __init__(self, title: str = "") -> None:
        self._pools: dict[str, Pool] = {}
        self._lanes: dict[str, Lane] = {}
        self._events: dict[str, Event] = {}
        self._activities: dict[str, Activity] = {}
        self._gateways: dict[str, Gateway] = {}
        self._flows: list[Flow] = []
        self._title = title

    @property
    def diagram(self) -> BPMNDiagram:
        return BPMNDiagram(
            title=self._title,
            pools=self._pools, lanes=self._lanes,
            events=self._events, activities=self._activities,
            gateways=self._gateways, flows=self._flows,
        )

    def pool(self, name: str, *, label: str | None = None) -> "BPMNMap":
        self._pools[name] = Pool(name=name, label=label)
        return self

    def lane(self, name: str, *, pool: str, label: str | None = None) -> "BPMNMap":
        if pool not in self._pools:
            self.pool(pool)
        self._lanes[name] = Lane(name=name, pool=pool, label=label)
        return self

    def event(self, name: str, *, kind: EventKind = "intermediate",
              lane: str | None = None, label: str | None = None) -> "BPMNMap":
        self._events[name] = Event(name=name, kind=kind, lane=lane, label=label)
        return self

    def activity(self, name: str, *, kind: ActivityKind = "task",
                 lane: str | None = None, label: str | None = None) -> "BPMNMap":
        self._activities[name] = Activity(name=name, kind=kind, lane=lane, label=label)
        return self

    def gateway(self, name: str, *, kind: GatewayKind = "exclusive",
                lane: str | None = None, label: str | None = None) -> "BPMNMap":
        self._gateways[name] = Gateway(name=name, kind=kind, lane=lane, label=label)
        return self

    def flow(self, source: str, target: str, *, kind: FlowKind = "sequence",
             label: str = "", condition: str = "") -> "BPMNMap":
        self._flows.append(Flow(source=source, target=target, kind=kind,
                                label=label, condition=condition))
        return self

    def show(self, viewer: str = "cdn") -> None:
        import os
        import tempfile
        import webbrowser
        html = render_bpmn(self.diagram, title=self._title, viewer=viewer)
        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
        tmp.write(html)
        tmp.close()
        if viewer == "local":
            copy_local_viewer(os.path.dirname(tmp.name))
        print(f"[sysatlas] → {tmp.name}")
        webbrowser.open(f"file://{tmp.name}")

    def save(self, path: str, viewer: str = "cdn") -> None:
        import os
        html = render_bpmn(self.diagram, title=self._title, viewer=viewer)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        if viewer == "local":
            copy_local_viewer(os.path.dirname(os.path.abspath(path)))
