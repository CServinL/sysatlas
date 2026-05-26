# Builders

sysatlas exposes three public builder classes. They share a fluent style
(method chaining, declarative construction) and produce validated
Pydantic models under the hood.

## At a glance

| Builder | Use it for | Output |
|---|---|---|
| `SystemMap` | A single architecture diagram (one canvas). Most common entry point. | One HTML view. |
| `System` | A multi-view Architecture Description (ISO 42010). Multiple diagrams + stakeholders / concerns / viewpoints + trace links between models. | Multi-tab HTML, plus optional trace-matrix HTML. |
| `TreeMap` | Any tree-shaped diagram: org chart, mind map, taxonomy, file tree. | One HTML view. |

If you're not sure: start with `SystemMap`. Graduate to `System` when
you want to split one system across several focused diagrams.

## `SystemMap` — one architecture diagram

```python
import sysatlas

m = sysatlas.SystemMap(title="Storefront")
m.group("services", color="#dcfce7")
m.add_component("api", group="services", layer="services", tech="Envoy")
m.add_component("catalog", group="services", layer="services", tech="Python")
m.connect("api", "catalog", label="REST")
m.show()              # opens in browser
# or: m.save("out.html")
```

Public methods: `group`, `add_component`, `connect`, `show`, `save`.
`SystemMap.save_collection(...)` is a static helper for emitting several
SystemMaps to a multi-tab HTML without going through `System`.

The underlying Pydantic instance is at `m.diagram` (an `ArchitectureDiagram`).

See [`demos/architecture.py`](demos/architecture.py).

## `System` — multi-view Architecture Description

Use when one diagram would be too dense — split it across views and
let sysatlas keep their identity coherent.

```python
import sysatlas

s = sysatlas.System(title="E-Commerce")
s.viewpoint("container", model_kinds=["architecture"])

sf = s.architecture_model("storefront")
sf.add_component("Cart").add_component("Catalog").connect("Cart", "Catalog")

pm = s.architecture_model("payments")
pm.add_component("Payments").add_component("Gateway").connect("Payments", "Gateway")

s.view("storefront-view", viewpoint="container", models=["storefront"])
s.view("payments-view",   viewpoint="container", models=["payments"])

s.trace("storefront#Cart", "payments#Payments", kind="depends_on")
s.save("system.html")
s.save_trace_matrix("traces.html")
```

Public methods: `stakeholder`, `concern`, `viewpoint`, `view`,
`architecture_model`, `trace`, `save`, `show`, `save_trace_matrix`.

- Cross-view connections (a `connect()` to a component declared in
  another model) are auto-rendered as **stub nodes** in the secondary
  view — dashed, faded, with a "→ defining-view" hint.
- Trace links are rendered as **dashed purple overlay edges** within
  any view whose models contain both endpoints. They don't enter the
  Sugiyama layout.
- `save_trace_matrix(path)` writes a separate sources × targets HTML
  matrix for audit-style review.

The underlying Pydantic instance is at `s.description` (an
`ArchitectureDescription`).

See [`demos/multi_view.py`](demos/multi_view.py) and
[`demos/trace_matrix.py`](demos/trace_matrix.py).

## `TreeMap` — hierarchical tree

Pure parent → child structure, no cycles, exactly one root. Covers
org charts, mind maps, taxonomies, file trees.

```python
import sysatlas

t = sysatlas.TreeMap(title="Org", flavor="org")
t.add("CEO", kind="root")
t.add("CTO", parent="CEO")
t.add("CFO", parent="CEO")
t.add("VP Eng", parent="CTO")
t.show()
```

Public methods: `add`, `show`, `save`. The `flavor` field is reserved
for layout variants (today everything is top-down Reingold-Tilford;
radial is the natural follow-up for `flavor="mindmap"`).

See [`demos/tree.py`](demos/tree.py).

---

## Viewer modes

Every `show()` / `save()` accepts a `viewer=` parameter. Three modes:

| `viewer=` | HTML size | Requires | When to use |
|---|---|---|---|
| `"cdn"` (default) | ~20 KB | Internet at render time (loads draw.io viewer from CDN) | Most cases. Smallest file. |
| `"local"` | ~20 KB + `viewer-static.min.js` copied next to the HTML | None | Distributing offline; you'll ship both files. |
| `"embed"` | ~3.8 MB | None | Fully self-contained single file — emails, archives, screenshots. |

If the JS fails to load, the page shows a clear error message
(see `_render._viewer_missing_js`).

## Quality attributes (ISO 25010)

`Component` and `Connection` accept a `qualities=[QualityAttribute(...)]`
list. The renderer shows a coloured letter badge per quality whose
`criticality` is `high` or `critical`. See
[`ontology/qualities.md`](ontology/qualities.md) for the eight
categories and the colour key, and [`demos/qualities.py`](demos/qualities.py)
for a working example.

## Trace links (SysML)

Live at the `System` level via `s.trace("model#entity", "model#entity",
kind=...)`. Ten link kinds available: `realizes`, `implements`,
`refines`, `satisfies`, `represents`, `documents`, `tested_by`,
`derives_from`, `depends_on`, `describes`. See
[`ontology/trace.md`](ontology/trace.md).
