# Architecture Diagram — Ontology

A `sysatlas` *architecture diagram* depicts a software system as a set of
**components** (processes, services, containers) connected by directed
**connections**, organized into **layers** (vertical tiers) and optional
**groups** (logical clusters / swim lanes). It is the C4-container view,
with explicit layer ordering and optional off-page **connectors** for
long-span edges.

## Concepts

| Concept | Purpose | Example |
|---|---|---|
| `Layer` | Vertical tier; defines top-down flow order. | `edge`, `services`, `data` |
| `Group` | Logical cluster (swim lane / bounded context). | "Payments domain" |
| `Component` | A unit: process, service, database. | `API Gateway`, `Orders DB` |
| `Connection` | Directed edge between two components. | `Cart → Catalog (prices)` |
| `Connector` | Auto-generated pair of off-page glyphs for an edge that spans 3+ layers. | not user-declared |

## Pydantic schema

Source: `sysatlas/_ontology/architecture.py`

```python
class Layer(BaseModel):
    name: str
    label: str | None = None
    order: int = 0

class Group(BaseModel):
    name: str
    label: str | None = None
    color: str | None = None   # hex, e.g. "#dbeafe"

class Component(BaseModel):
    name: str                  # unique id
    label: str | None = None   # display text (defaults to name)
    tech: str | None = None    # stack tag, e.g. "PostgreSQL"
    group: str | None = None   # → Group.name
    layer: str | None = None   # → Layer.name

class Connection(BaseModel):
    source: str                # → Component.name
    target: str                # → Component.name
    label: str = ""            # e.g. "HTTPS", "publish"
    style: Literal["solid", "dashed", "dotted"] = "solid"
    color: str | None = None

class ArchitectureDiagram(BaseModel):
    title: str = ""
    strategy: Literal["layered"] = "layered"
    layers: list[Layer]
    groups: dict[str, Group]
    components: dict[str, Component]
    connections: list[Connection]
```

## Relations

- `Component.group → Group.name` — membership in a cluster (optional).
- `Component.layer → Layer.name` — assignment to a vertical tier (optional).
- `Connection(source, target) → Component.name × Component.name` — directed edge.
- `Layer.order` — defines top-down rendering order; lower order = higher in diagram.

## Validation rules (enforced at construction)

- `Group.color` must be hex (`#rrggbb` or `#rgb`) or `None`.
- `Connection.source != Connection.target` (no self-loops).
- Every `Component.group` must reference an existing `Group`.
- Every `Component.layer` must reference an existing `Layer`.
- Every `Connection.source` and `Connection.target` must reference an existing `Component`.

## Computed concepts (not user-declared)

These emerge from the layout pipeline, not from the input:

- **Port** — `{side: top|bottom|left|right, fraction: 0..1}` assigned per
  connection-end per component. Sides are picked from relative geometry;
  fractions distribute multiple edges along the side. See `_route._assign_ports`.
- **Route** — list of orthogonal waypoints between source and target ports,
  found by A\* maze routing.
- **Connector** — when a connection spans `≥ LONG_LAYER_THRESHOLD` layers
  (`_connectors.classify_edges`), it is rendered as a pair of off-page
  glyphs ("→ Target" near source, "← Source" near target) instead of a
  single long line. The connection itself stays in the model; only the
  rendering changes.

## Builder API (fluent)

`SystemMap` constructs an `ArchitectureDiagram` incrementally:

```python
import sysatlas

m = sysatlas.SystemMap(title="E-commerce", strategy="layered")
m.group("edge", label="Edge", color="#dbeafe")
m.add_component("API Gateway", group="edge", layer="edge", tech="Envoy")
m.add_component("Catalog",     group="services", layer="services", tech="Python")
m.connect("API Gateway", "Catalog", label="REST")
m.save("arch.html")
```

The underlying Pydantic model is accessible via `m.diagram` for
introspection, serialization, or round-tripping through JSON.
