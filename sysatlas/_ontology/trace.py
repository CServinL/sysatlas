"""Trace links between entities in different models.

A `Component` in an architecture model can be linked to the `Class` that
implements it, or to a `Lifeline` that represents it in a sequence
diagram, etc. Vocabulary comes from SysML / OMG (realizes, refines,
satisfies, …).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


TraceLinkKind = Literal[
    "realizes",      # source realizes (implements the concept of) target
    "implements",    # source provides the implementation of target's contract
    "refines",       # source is a more detailed version of target
    "satisfies",     # source satisfies the requirement target
    "represents",    # source visually/semantically represents target in another model
    "documents",     # source documents target (e.g. a diagram documents code)
    "tested_by",     # source is tested by target
    "derives_from",  # source is derived from target
    "depends_on",    # source depends on target
    "describes",     # source describes target in different model kind
]
"""Standard SysML/OMG-derived trace link kinds."""


class EntityRef(BaseModel):
    """A reference to a named entity inside a named model.

    `model` matches a key in `ArchitectureDescription.models`. `entity`
    matches an entity name within that model (e.g. a `Component.name`,
    `Class.name`, `Actor.name`, etc.).

    `kind` is an optional hint about the entity's type within its model
    (e.g. 'component', 'class', 'actor'). It is informational; the
    resolver only checks that `entity` exists in `model`.
    """
    model_config = ConfigDict(extra="forbid")
    model: str
    entity: str
    kind: str | None = None

    def __str__(self) -> str:
        return f"{self.model}#{self.entity}"


class TraceLink(BaseModel):
    """A directed semantic link from one entity to another, typically
    crossing model boundaries (different Model Kinds)."""
    model_config = ConfigDict(extra="allow")
    source: EntityRef
    target: EntityRef
    kind: TraceLinkKind = "depends_on"
    note: str | None = None


def resolve_links(
    links: list[TraceLink],
    models: dict[str, object],
) -> list[TraceLink]:
    """Validate every link's endpoints exist. Returns the same list
    unchanged or raises ValueError on the first dangling reference.

    `models` is the `ArchitectureDescription.models` dict. The function
    looks up `entity` names against whatever attribute each model uses
    to hold entities (e.g. `.components`, `.classes`, `.entities`).
    """
    def _entity_keys(m: object) -> set[str]:
        # Try common entity-bucket names used by our Model Kinds.
        for attr in ("components", "classes", "entities", "actors",
                     "states", "activities", "nodes", "events", "gateways"):
            bucket = getattr(m, attr, None)
            if isinstance(bucket, dict):
                return set(bucket)
        return set()

    for link in links:
        for end_name, ref in (("source", link.source), ("target", link.target)):
            if ref.model not in models:
                raise ValueError(
                    f"trace link {end_name} references unknown model {ref.model!r}"
                )
            keys = _entity_keys(models[ref.model])
            if ref.entity not in keys:
                raise ValueError(
                    f"trace link {end_name} references unknown entity "
                    f"{ref.entity!r} in model {ref.model!r}"
                )
    return links


class TraceLinkSet(BaseModel):
    """A collection of trace links, optionally with a name."""
    model_config = ConfigDict(extra="forbid")
    name: str = "default"
    links: list[TraceLink] = Field(default_factory=list)
