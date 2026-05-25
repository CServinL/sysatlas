"""Ontology for UML class diagrams."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Visibility = Literal["public", "private", "protected", "package"]
ClassKind  = Literal["class", "abstract", "interface", "enum"]
RelationKind = Literal["inheritance", "implementation", "composition", "aggregation",
                       "association", "dependency"]


class Attribute(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: str | None = None
    visibility: Visibility = "public"
    is_static: bool = False


class Method(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    return_type: str | None = None
    params: list[str] = Field(default_factory=list)   # ["x: int", "y: str"]
    visibility: Visibility = "public"
    is_static: bool = False
    is_abstract: bool = False


class Class(BaseModel):
    """A class, abstract class, interface, or enum."""
    model_config = ConfigDict(extra="allow")
    name: str
    label: str | None = None
    kind: ClassKind = "class"
    attributes: list[Attribute] = Field(default_factory=list)
    methods: list[Method] = Field(default_factory=list)


class Relation(BaseModel):
    """A relationship between two classes."""
    model_config = ConfigDict(extra="allow")
    source: str                       # → Class.name
    target: str                       # → Class.name
    kind: RelationKind = "association"
    label: str = ""                   # role / multiplicity text
    source_multiplicity: str = ""     # e.g. "1", "0..*"
    target_multiplicity: str = ""


class ClassDiagram(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = ""
    classes: dict[str, Class] = Field(default_factory=dict)
    relations: list[Relation] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_refs(self) -> "ClassDiagram":
        for r in self.relations:
            if r.source not in self.classes:
                raise ValueError(f"relation source {r.source!r} unknown")
            if r.target not in self.classes:
                raise ValueError(f"relation target {r.target!r} unknown")
            if r.source == r.target and r.kind == "inheritance":
                raise ValueError(f"class {r.source!r} cannot inherit from itself")
        return self
