"""Ontology for UML sequence diagrams."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


MessageKind = Literal["sync", "async", "reply", "create", "destroy"]
FrameKind   = Literal["alt", "opt", "loop", "par", "critical"]


class Actor(BaseModel):
    """A participant: user, system, service. Has a vertical lifeline."""
    model_config = ConfigDict(extra="allow")
    name: str
    label: str | None = None
    kind: Literal["actor", "system", "boundary", "control", "entity"] = "system"


class Message(BaseModel):
    """A directed call between actors at a point in time."""
    model_config = ConfigDict(extra="allow")
    source: str                    # → Actor.name
    target: str                    # → Actor.name
    label: str = ""                # method/operation name
    kind: MessageKind = "sync"
    order: int = 0                 # sequence index (top-to-bottom)


class Activation(BaseModel):
    """Period where an actor is actively executing (rectangle on lifeline)."""
    model_config = ConfigDict(extra="forbid")
    actor: str                     # → Actor.name
    start_order: int               # message order where activation starts
    end_order: int                 # message order where it ends


class Frame(BaseModel):
    """Combined fragment wrapping a range of messages: alt/opt/loop/par."""
    model_config = ConfigDict(extra="forbid")
    kind: FrameKind
    label: str = ""                # condition / guard
    start_order: int
    end_order: int


class SequenceDiagram(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = ""
    actors: dict[str, Actor] = Field(default_factory=dict)
    messages: list[Message] = Field(default_factory=list)
    activations: list[Activation] = Field(default_factory=list)
    frames: list[Frame] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_refs(self) -> "SequenceDiagram":
        for m in self.messages:
            if m.source not in self.actors:
                raise ValueError(f"message source {m.source!r} unknown")
            if m.target not in self.actors:
                raise ValueError(f"message target {m.target!r} unknown")
        for a in self.activations:
            if a.actor not in self.actors:
                raise ValueError(f"activation actor {a.actor!r} unknown")
            if a.start_order > a.end_order:
                raise ValueError(f"activation start_order > end_order on {a.actor!r}")
        for f in self.frames:
            if f.start_order > f.end_order:
                raise ValueError(f"frame {f.kind!r} start_order > end_order")
        return self
