"""Ontology for BPMN process diagrams (simplified subset)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


EventKind    = Literal["start", "end", "intermediate", "timer", "message", "error"]
ActivityKind = Literal["task", "user_task", "service_task", "subprocess", "call_activity"]
GatewayKind  = Literal["exclusive", "parallel", "inclusive", "event_based"]
FlowKind     = Literal["sequence", "message", "default", "conditional"]


class Pool(BaseModel):
    """A participant (organization, system). Contains lanes."""
    model_config = ConfigDict(extra="forbid")
    name: str
    label: str | None = None


class Lane(BaseModel):
    """A horizontal swimlane inside a pool (role, department)."""
    model_config = ConfigDict(extra="forbid")
    name: str
    label: str | None = None
    pool: str                        # → Pool.name


class Event(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    label: str | None = None
    kind: EventKind = "intermediate"
    lane: str | None = None          # → Lane.name


class Activity(BaseModel):
    """A unit of work."""
    model_config = ConfigDict(extra="allow")
    name: str
    label: str | None = None
    kind: ActivityKind = "task"
    lane: str | None = None


class Gateway(BaseModel):
    """Branching/merging point."""
    model_config = ConfigDict(extra="allow")
    name: str
    label: str | None = None
    kind: GatewayKind = "exclusive"
    lane: str | None = None


class Flow(BaseModel):
    """Directed flow between two flow nodes (event/activity/gateway)."""
    model_config = ConfigDict(extra="allow")
    source: str
    target: str
    label: str = ""
    kind: FlowKind = "sequence"
    condition: str = ""              # for conditional flows


class BPMNDiagram(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = ""
    pools: dict[str, Pool] = Field(default_factory=dict)
    lanes: dict[str, Lane] = Field(default_factory=dict)
    events: dict[str, Event] = Field(default_factory=dict)
    activities: dict[str, Activity] = Field(default_factory=dict)
    gateways: dict[str, Gateway] = Field(default_factory=dict)
    flows: list[Flow] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> "BPMNDiagram":
        # lane→pool refs
        for lane in self.lanes.values():
            if lane.pool not in self.pools:
                raise ValueError(f"lane {lane.name!r} references unknown pool {lane.pool!r}")
        # node→lane refs
        all_nodes: dict[str, str] = {}     # name → "event"/"activity"/"gateway"
        for d, kind in (
            (self.events, "event"),
            (self.activities, "activity"),
            (self.gateways, "gateway"),
        ):
            for n, node in d.items():
                if node.lane and node.lane not in self.lanes:
                    raise ValueError(f"{kind} {n!r} references unknown lane {node.lane!r}")
                if n in all_nodes:
                    raise ValueError(f"name collision: {n!r} appears in {kind} and {all_nodes[n]}")
                all_nodes[n] = kind
        # flow endpoints
        for f in self.flows:
            if f.source not in all_nodes:
                raise ValueError(f"flow source {f.source!r} not a known node")
            if f.target not in all_nodes:
                raise ValueError(f"flow target {f.target!r} not a known node")
        return self
