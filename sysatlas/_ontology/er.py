"""Ontology for Entity-Relationship diagrams."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Cardinality = Literal["1", "0..1", "*", "1..*"]
"""Standard Chen/Crow's-foot cardinalities. '*' = many, '1..*' = one or more."""


class Attribute(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: str | None = None       # e.g. "varchar(64)", "int"
    is_key: bool = False          # primary key marker
    is_required: bool = False     # NOT NULL


class Entity(BaseModel):
    """A real-world thing whose data is stored: User, Order, Product."""
    model_config = ConfigDict(extra="allow")
    name: str
    label: str | None = None
    attributes: list[Attribute] = Field(default_factory=list)
    is_weak: bool = False         # weak entity = depends on another for identity


class Relationship(BaseModel):
    """A connection between two entities with cardinality on each side."""
    model_config = ConfigDict(extra="allow")
    name: str                                 # e.g. "places", "contains"
    source: str                               # → Entity.name
    target: str                               # → Entity.name
    source_card: Cardinality = "1"            # cardinality on source side
    target_card: Cardinality = "*"            # cardinality on target side
    is_identifying: bool = False              # required for weak-entity identity


class ERDiagram(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = ""
    entities: dict[str, Entity] = Field(default_factory=dict)
    relationships: list[Relationship] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_refs(self) -> "ERDiagram":
        for r in self.relationships:
            if r.source not in self.entities:
                raise ValueError(f"relationship {r.name!r} source {r.source!r} unknown")
            if r.target not in self.entities:
                raise ValueError(f"relationship {r.name!r} target {r.target!r} unknown")
        return self
