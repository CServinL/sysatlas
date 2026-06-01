# Model Kinds — taxonomy on top of the Ontologies

An **Ontology** under `sysatlas/_ontology/` is a typed schema for a
conceptual domain — `architecture` defines `Component`, `Connection`,
`Layer`; `sequence` defines `Actor`, `Message`, `Activation`; and so on.
The Ontology is the *language*.

A **ModelKind** is a registered, named *usage* of an Ontology with a
specific scope or set of conventions. It is the taxonomy entry that
ISO/IEC/IEEE 42010 Viewpoints reference when they say
*"this Viewpoint constructs Views from these kinds of models."*

The same Ontology can back many ModelKinds. The clearest example is
C4: `c4-context`, `c4-container`, and `c4-component` are three distinct
ModelKinds, all backed by the single `architecture` Ontology — they
only differ in scope (one System / its containers / one container's
components).

## Why both layers?

| Layer | Answers | Lives in |
|---|---|---|
| Ontology | *What concepts exist and how do they relate?* | `sysatlas/_ontology/<name>.py` (Pydantic schemas) |
| ModelKind | *What is this kind of model called, and what's its scope?* | `sysatlas/_ontology/model_kinds.py` (registry of `ModelKind` instances) |

The Ontology is stable per domain. ModelKinds are how you carve that
domain into named, scope-specific usages that stakeholders recognise.

## Schema

Source: `sysatlas/_ontology/model_kind.py`

```python
class ModelKind(BaseModel):
    name: str                       # 'c4-container', 'uml-sequence', ...
    ontology: str                   # 'architecture', 'sequence', 'er', ...
    description: str | None = None
    conventions: str | None = None  # scope / notation / what's intentionally omitted
```

## Bundled registry

`sysatlas._ontology.model_kinds.DEFAULT_KINDS` ships the canonical
taxonomy for the Ontologies that come with sysatlas:

| Name | Ontology | Scope |
|---|---|---|
| `c4-context` | `architecture` | one System in its environment |
| `c4-container` | `architecture` | containers inside one system |
| `c4-component` | `architecture` | components inside one container |
| `uml-sequence` | `sequence` | time-ordered interactions |
| `uml-class` | `uml_class` | static OO structure |
| `uml-state` | `state_machine` | states + transitions of one entity |
| `er-logical` | `er` | logical data schema |
| `bpmn-subset` | `bpmn` | process flow with pools/lanes |
| `tree-org` / `tree-mindmap` / `tree-taxonomy` / `tree-filesystem` | `tree` | hierarchy variants |

## Using ModelKinds in an Architecture Description

```python
from sysatlas._ontology.iso42010 import (
    ArchitectureDescription, Concern, Stakeholder, View, Viewpoint,
)
from sysatlas._ontology.model_kind import ModelKind

ad = ArchitectureDescription(
    stakeholders={"dev": Stakeholder(name="dev")},
    concerns={"deployability": Concern(name="deployability", stakeholders=["dev"])},
    model_kinds={
        # Optional: register project-local kinds the bundled registry doesn't cover.
        "ddd-context": ModelKind(name="ddd-context", ontology="architecture",
                                 description="DDD bounded context"),
    },
    viewpoints={
        "container-vp": Viewpoint(
            name="container-vp",
            concerns=["deployability"],
            model_kinds=["c4-container", "ddd-context"],
        ),
    },
)
```

Viewpoint validation accepts:

1. ModelKind names from the local `model_kinds` field
2. ModelKind names from `DEFAULT_KINDS`
3. Raw Ontology names (`"architecture"`, `"sequence"`, …) as a
   backwards-compat fallback for pre-taxonomy code

## Distinction from a Viewpoint

A Viewpoint *consumes* ModelKinds — it's the recipe that says
*"to address this Concern, construct a View using these ModelKinds
under these conventions."* A ModelKind is the raw ingredient; a
Viewpoint is the recipe; a View is the dish.
