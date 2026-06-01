"""Bundled taxonomy of ModelKinds backed by sysatlas's built-in ontologies.

`DEFAULT_KINDS` is the canonical registry. Projects that want their own
taxonomy can ignore it and supply their own ModelKind dict to an
ArchitectureDescription. The names here are the names you reference
from `Viewpoint.model_kinds`.
"""
from __future__ import annotations

from sysatlas._ontology.model_kind import ModelKind


def _k(name: str, ontology: str, description: str, conventions: str | None = None) -> ModelKind:
    return ModelKind(name=name, ontology=ontology,
                     description=description, conventions=conventions)


DEFAULT_KINDS: dict[str, ModelKind] = {
    # C4 zoom levels — all backed by the `architecture` ontology, differ
    # only in scope.
    "c4-context": _k(
        "c4-context", "architecture",
        "Single system shown in its environment (users, neighbouring systems).",
        "One System box plus its external dependencies; no internal containers.",
    ),
    "c4-container": _k(
        "c4-container", "architecture",
        "Containers (apps, services, databases) that make up one system.",
        "5–10 containers per view; show technology choice (tech=).",
    ),
    "c4-component": _k(
        "c4-component", "architecture",
        "Components inside a single container.",
        "Only one container at a time; do not mix containers.",
    ),

    # UML kinds
    "uml-sequence": _k(
        "uml-sequence", "sequence",
        "Time-ordered interaction between participants (lifelines + messages).",
    ),
    "uml-class": _k(
        "uml-class", "uml_class",
        "Static OO structure: classes, attributes, methods, relations.",
    ),
    "uml-state": _k(
        "uml-state", "state_machine",
        "Discrete states and transitions of one entity over its lifecycle.",
    ),

    # Data
    "er-logical": _k(
        "er-logical", "er",
        "Logical data schema: entities, attributes, relationships with cardinality.",
    ),

    # Process
    "bpmn-subset": _k(
        "bpmn-subset", "bpmn",
        "Business process flow with pools/lanes, events, activities, gateways.",
        "Simplified BPMN 2.0 subset; full event-subprocess semantics omitted.",
    ),

    # Generic hierarchy — backs the Tree ontology and its flavors.
    "tree-org": _k(
        "tree-org", "tree",
        "Reporting / org-chart hierarchy.",
        "One root, single parent per node, finite depth.",
    ),
    "tree-mindmap": _k(
        "tree-mindmap", "tree",
        "Topic mind map from a central root.",
    ),
    "tree-taxonomy": _k(
        "tree-taxonomy", "tree",
        "Categorical hierarchy / taxonomy.",
    ),
    "tree-filesystem": _k(
        "tree-filesystem", "tree",
        "File / directory tree.",
    ),
}
