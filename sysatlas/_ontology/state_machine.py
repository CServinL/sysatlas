"""Ontology for state machine / state chart diagrams."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


StateKind = Literal["normal", "initial", "final", "choice", "composite"]


class State(BaseModel):
    """A discrete state. 'composite' contains child states; 'initial'/'final' are pseudo-states."""
    model_config = ConfigDict(extra="allow")
    name: str
    label: str | None = None
    kind: StateKind = "normal"
    parent: str | None = None         # → State.name (for nested states)
    entry_action: str | None = None
    exit_action: str | None = None
    do_activity: str | None = None


class Transition(BaseModel):
    """A directed transition between two states."""
    model_config = ConfigDict(extra="allow")
    source: str                       # → State.name
    target: str                       # → State.name
    event: str = ""                   # trigger event
    guard: str = ""                   # boolean condition
    action: str = ""                  # side effect on transition


class StateDiagram(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = ""
    states: dict[str, State] = Field(default_factory=dict)
    transitions: list[Transition] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> "StateDiagram":
        # exactly one initial state expected (warn-via-error if zero or >1)
        initials = [s for s in self.states.values() if s.kind == "initial"]
        if self.states and len(initials) == 0:
            raise ValueError("state diagram must have at least one initial state")
        # transitions must reference known states
        for t in self.transitions:
            if t.source not in self.states:
                raise ValueError(f"transition source {t.source!r} unknown")
            if t.target not in self.states:
                raise ValueError(f"transition target {t.target!r} unknown")
            if self.states[t.source].kind == "final":
                raise ValueError(f"state {t.source!r} is final and cannot have outgoing transitions")
        # parent references
        for s in self.states.values():
            if s.parent and s.parent not in self.states:
                raise ValueError(f"state {s.name!r} has unknown parent {s.parent!r}")
        return self
