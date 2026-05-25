# sysatlas

**Architecture diagrams that stay readable as systems grow.**

Most diagramming tools optimize for *expressiveness at any scale* — and
produce the famous "big ball of mud" diagrams nobody reads. sysatlas
goes the other way: targets focused, low-complexity views, and treats
splitting a large system into many small diagrams as a first-class
operation, not a workaround.

```python
import sysatlas

m = sysatlas.SystemMap(title="E-Commerce")
m.group("edge", color="#dbeafe")
m.group("services", color="#dcfce7")

m.add_component("API Gateway", group="edge",     layer="edge",     tech="Envoy")
m.add_component("Catalog",     group="services", layer="services", tech="Python")
m.add_component("Cart",        group="services", layer="services", tech="Go")

m.connect("API Gateway", "Catalog", label="REST")
m.connect("API Gateway", "Cart",    label="REST")
m.connect("Cart",        "Catalog", label="prices")

m.save("arch.html")           # interactive draw.io viewer, ~20KB
```

## What you get

- **Typed ontologies** (Pydantic) for 7 diagram kinds — architecture (C4
  container), ER, sequence, UML class, state machine, BPMN, tree.
- **ISO 42010 grounding** — Stakeholder / Concern / Viewpoint / View /
  Architecture Description compose multiple diagrams into one system.
- **Quality attributes** (ISO 25010) and **trace links** (SysML vocabulary)
  ride on top of any model.
- **Layout that does the work** — Sugiyama + A\* routing with port
  selection, label collision avoidance, no edges through nodes, no
  collinear overlaps. Bounded-complexity design means we can afford the
  expensive-but-pretty algorithms.
- **One artifact** — self-contained HTML (CDN link or fully embedded).
  No server, no extra dependencies at runtime.

## Install

```bash
pip install sysatlas
```

## Why this exists

Read [`docs/design-principles.md`](docs/design-principles.md) for the
non-negotiables (bounded complexity, multi-view by default) and
[`docs/state-of-the-art.md`](docs/state-of-the-art.md) for how sysatlas
positions against ArchiMate, C4, UML, BPMN, and the rest of the AD
literature. The 7 diagram ontologies are catalogued at
[`docs/ontology/README.md`](docs/ontology/README.md). What's queued next
is in [`docs/todo.md`](docs/todo.md).

## License

MIT
