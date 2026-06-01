"""ModelKind — taxonomy entry that names a *usage* of an Ontology.

An Ontology (under `sysatlas/_ontology/`) is the typed schema for a
conceptual domain: architecture, ER, sequence, state machine, etc.
A ModelKind is one named, registered *usage* of that schema with a
specific scope or set of conventions.

The same Ontology can back multiple ModelKinds. Example: the
`architecture` ontology backs the three C4 zoom levels — `c4-context`,
`c4-container`, `c4-component` — each is a distinct ModelKind with the
same underlying schema but different scope conventions.

ModelKinds are what an ISO 42010 Viewpoint references when it says
"this viewpoint constructs Views from these kinds of models".
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ModelKind(BaseModel):
    """A registered, named kind of model.

    `ontology` points at one of the schemas under `sysatlas/_ontology/`
    (module name without the prefix, e.g. 'architecture', 'sequence').
    `conventions` is free-text guidance — scope, notation rules,
    things this kind intentionally omits.
    """
    model_config = ConfigDict(extra="forbid")

    name: str
    ontology: str
    description: str | None = None
    conventions: str | None = None
