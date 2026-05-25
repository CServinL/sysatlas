"""Ontology for layered system-architecture diagrams (C4-container style).

Every concept is a Pydantic model. Validation runs at construction time so
malformed diagrams fail fast instead of producing weird layouts.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from sysatlas._ontology.qualities import QualityAttribute


EdgeStyle = Literal["solid", "dashed", "dotted"]


class Layer(BaseModel):
    """A vertical tier (e.g. 'edge', 'services', 'data')."""
    model_config = ConfigDict(extra="forbid")

    name: str
    label: str | None = None
    order: int = 0


class Group(BaseModel):
    """A logical cluster (swim lane / bounded context)."""
    model_config = ConfigDict(extra="forbid")

    name: str
    label: str | None = None
    color: str | None = None  # hex like "#dbeafe"

    @field_validator("color")
    @classmethod
    def _hex_or_none(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.startswith("#") or len(v) not in (4, 7):
            raise ValueError(f"color must be hex like '#dbeafe', got {v!r}")
        return v


class Component(BaseModel):
    """A process, service, or container."""
    model_config = ConfigDict(extra="allow")  # arbitrary user metadata

    name: str                  # unique identifier
    label: str | None = None   # display text (defaults to name)
    tech: str | None = None    # stack tag, e.g. "PostgreSQL"
    group: str | None = None   # references Group.name
    layer: str | None = None   # references Layer.name
    qualities: list[QualityAttribute] = Field(default_factory=list)
    """ISO 25010 quality attributes asserted about this component."""
    is_stub: bool = False
    """True when this component is a reference to one defined in another view."""
    defined_in: str | None = None
    """If is_stub, the view name where the canonical definition lives."""


class Connection(BaseModel):
    """A directed edge between two components."""
    model_config = ConfigDict(extra="allow")

    source: str            # references Component.name
    target: str            # references Component.name
    label: str = ""        # interaction name, e.g. "HTTPS", "publish"
    style: EdgeStyle = "solid"
    color: str | None = None
    qualities: list[QualityAttribute] = Field(default_factory=list)
    """ISO 25010 quality attributes asserted about this connection."""

    @model_validator(mode="after")
    def _no_self_loop(self) -> "Connection":
        if self.source == self.target:
            raise ValueError(f"self-loops not supported: {self.source}")
        return self


class ArchitectureDiagram(BaseModel):
    """Root container for the architecture ontology.

    Layers, groups, components and connections live here. Cross-references
    (component.group → Group.name, etc.) are validated on insert.
    """
    model_config = ConfigDict(extra="forbid")

    title: str = ""
    strategy: Literal["layered"] = "layered"
    layers: list[Layer] = Field(default_factory=list)
    groups: dict[str, Group] = Field(default_factory=dict)
    components: dict[str, Component] = Field(default_factory=dict)
    connections: list[Connection] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_references(self) -> "ArchitectureDiagram":
        layer_names = {l.name for l in self.layers}
        for name, c in self.components.items():
            if c.group and c.group not in self.groups:
                raise ValueError(f"component {name!r} references unknown group {c.group!r}")
            if c.layer and c.layer not in layer_names:
                raise ValueError(f"component {name!r} references unknown layer {c.layer!r}")
        for e in self.connections:
            if e.source not in self.components:
                raise ValueError(f"connection source {e.source!r} not a known component")
            if e.target not in self.components:
                raise ValueError(f"connection target {e.target!r} not a known component")
        return self
