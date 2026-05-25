# Trace Links

Trace links connect entities across different models in an
`ArchitectureDescription`. A `Component` in an architecture model can be
linked to the `Class` that implements it, the `Lifeline` that represents
it in a sequence diagram, the `Requirement` it satisfies, etc.

Vocabulary derives from SysML / OMG; we use the most commonly recognised
link kinds.

## Concepts

| Concept | Purpose |
|---|---|
| `EntityRef` | A pointer to a named entity inside a named model: `(model, entity, kind?)`. |
| `TraceLink` | A directed semantic link: `source → target` with a `kind` and optional note. |
| `TraceLinkSet` | A named collection of links. |

## Link kinds

Drawn from SysML and common practice:

| Kind | Meaning |
|---|---|
| `realizes` | Source realizes (implements the concept of) target. |
| `implements` | Source provides the implementation of target's contract. |
| `refines` | Source is a more detailed version of target. |
| `satisfies` | Source satisfies the requirement target. |
| `represents` | Source visually/semantically represents target in another model kind. |
| `documents` | Source documents target (e.g. a diagram documents code). |
| `tested_by` | Source is tested by target. |
| `derives_from` | Source is derived from target. |
| `depends_on` | Source depends on target. |
| `describes` | Source describes target in a different model kind. |

## Schema

Source: `sysatlas/_ontology/trace.py`

```python
class EntityRef(BaseModel):
    model: str                       # → ArchitectureDescription.models key
    entity: str                      # entity name within that model
    kind: str | None = None          # optional hint: "component", "class", …

class TraceLink(BaseModel):
    source: EntityRef
    target: EntityRef
    kind: TraceLinkKind = "depends_on"
    note: str | None = None

class TraceLinkSet(BaseModel):
    name: str = "default"
    links: list[TraceLink]
```

## Resolver

```python
from sysatlas._ontology.trace import resolve_links

resolve_links(links, ad.models)
```

Walks each `EntityRef`. It must resolve to an entity in the named
model, where the entity is looked up against the model's natural entity
bucket (`.components`, `.classes`, `.entities`, `.actors`, `.states`,
`.activities`, `.nodes`, `.events`, `.gateways`). Raises `ValueError`
on the first dangling reference.

## Example

```python
from sysatlas._ontology.trace import EntityRef, TraceLink

links = [
    # The 'api' component in architecture/storefront is realized by the
    # APIController class in the UML class diagram.
    TraceLink(
        source=EntityRef(model="uml-storefront", entity="APIController", kind="class"),
        target=EntityRef(model="arch-storefront", entity="api",           kind="component"),
        kind="realizes",
    ),
    # The 'Checkout' use case is satisfied by the orders + payments flow.
    TraceLink(
        source=EntityRef(model="arch-checkout-flow", entity="orders", kind="component"),
        target=EntityRef(model="requirements",       entity="REQ-CHECKOUT-001"),
        kind="satisfies",
    ),
]
```

## Visualisation (future)

Trace links are not yet rendered. Expected behaviour when implemented:

- Inside a single view: dashed connector with the link kind as label.
- Across views: stub references on the other view's canvas (see
  [design-principles.md](../design-principles.md) §2 *Mechanism: stub
  references*).
- A dedicated "trace matrix" view-kind that shows links as a matrix
  (sources × targets).
