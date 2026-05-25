"""ISO/IEC/IEEE 42010:2011 meta-ontology.

Wraps our per-diagram-type Model Kinds (architecture, er, sequence, …)
in the standard vocabulary: Stakeholder, Concern, Viewpoint, View,
Architecture Description.

This is the *meta* layer — it does not replace the typed Model Kinds,
it composes them into a coherent description of a system as required
by the standard.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Stakeholder(BaseModel):
    """Someone with an interest in (a concern about) the system.

    Examples: 'developer', 'platform-ops', 'security', 'product-manager',
    'end-user'.
    """
    model_config = ConfigDict(extra="forbid")
    name: str
    role: str | None = None
    description: str | None = None


class Concern(BaseModel):
    """What a stakeholder cares about.

    Examples: 'request-latency', 'deployability', 'data-residency',
    'cost', 'PII-handling'.
    """
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str | None = None
    stakeholders: list[str] = Field(default_factory=list)
    """Names of stakeholders for whom this concern matters."""


class Viewpoint(BaseModel):
    """Recipe for constructing a view: which concerns it addresses, which
    model kinds it uses, conventions/operations it expects."""
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str | None = None
    concerns: list[str] = Field(default_factory=list)
    """Concern names this viewpoint addresses."""
    model_kinds: list[str] = Field(default_factory=list)
    """Names of the Model Kinds this viewpoint uses (e.g. 'architecture',
    'sequence'). Matches the module names under sysatlas/_ontology/."""
    conventions: str | None = None
    """Free-text conventions (notation, style, omissions) the viewpoint enforces."""


class View(BaseModel):
    """A view of the system, conforming to a viewpoint, containing one or
    more models (instances of the viewpoint's model kinds)."""
    model_config = ConfigDict(extra="allow")
    name: str
    viewpoint: str
    """Name of the Viewpoint this view conforms to."""
    description: str | None = None
    models: list[str] = Field(default_factory=list)
    """Names of models (held in the enclosing ArchitectureDescription) that
    compose this view."""


class ArchitectureDescription(BaseModel):
    """The top-level container per ISO 42010.

    Holds the stakeholders, the concerns they have, the viewpoints used
    to address those concerns, the views that follow each viewpoint, and
    the actual models that populate the views. Trace links across models
    can also live here (see `_ontology/trace.py`).
    """
    model_config = ConfigDict(extra="allow")
    title: str = ""
    description: str | None = None
    stakeholders: dict[str, Stakeholder] = Field(default_factory=dict)
    concerns: dict[str, Concern] = Field(default_factory=dict)
    viewpoints: dict[str, Viewpoint] = Field(default_factory=dict)
    views: dict[str, View] = Field(default_factory=dict)
    models: dict[str, Any] = Field(default_factory=dict)
    """Models are typed by their respective Model Kind (ArchitectureDiagram,
    ERDiagram, etc.). Kept as Any here so the meta-ontology doesn't depend
    on every concrete Model Kind."""

    @model_validator(mode="after")
    def _check_refs(self) -> "ArchitectureDescription":
        # concern → stakeholder refs
        for c in self.concerns.values():
            for s in c.stakeholders:
                if s not in self.stakeholders:
                    raise ValueError(
                        f"concern {c.name!r} references unknown stakeholder {s!r}"
                    )
        # viewpoint → concern refs
        for v in self.viewpoints.values():
            for c in v.concerns:
                if c not in self.concerns:
                    raise ValueError(
                        f"viewpoint {v.name!r} references unknown concern {c!r}"
                    )
        # view → viewpoint + model refs
        for view in self.views.values():
            if view.viewpoint not in self.viewpoints:
                raise ValueError(
                    f"view {view.name!r} references unknown viewpoint {view.viewpoint!r}"
                )
            for m in view.models:
                if m not in self.models:
                    raise ValueError(
                        f"view {view.name!r} references unknown model {m!r}"
                    )
        return self
