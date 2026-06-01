# Builders

sysatlas exposes eight public builder classes. They share a fluent
style (method chaining, declarative construction) and produce
validated Pydantic models under the hood.

## At a glance

| Builder | Use it for | Output | Detail |
|---|---|---|---|
| `SystemMap` | A single architecture diagram (one canvas). Most common entry point. | One HTML view. | §SystemMap below |
| `System` | A multi-view Architecture Description (ISO 42010). Multiple diagrams + stakeholders / concerns / viewpoints + trace links between models. | Multi-tab HTML, plus optional trace-matrix HTML. | §System below |
| `TreeMap` | Any tree-shaped diagram: org chart, mind map, taxonomy, file tree. | One HTML view. | §TreeMap below |
| `SequenceMap` | UML sequence diagram: lifelines + ordered messages + activations + combined fragments. | One HTML view. | [`ontology/sequence.md`](ontology/sequence.md) §Builder |
| `ERMap` | Entity-Relationship diagram: entities with attribute rows + cardinality-labelled relationships. | One HTML view. | [`ontology/er.md`](ontology/er.md) §Builder |
| `StateMap` | State machine: states (incl. initial/final/composite) + transitions with event/guard/action. | One HTML view. | [`ontology/state_machine.md`](ontology/state_machine.md) §Builder |
| `ClassMap` | UML class diagram: classes with attrs/methods + six relation kinds (inheritance, association, …). | One HTML view. | [`ontology/uml_class.md`](ontology/uml_class.md) §Builder |
| `BPMNMap` | BPMN process: pools/lanes + events + activities + gateways + flows. | One HTML view. | [`ontology/bpmn.md`](ontology/bpmn.md) §Builder |

If you're not sure: start with `SystemMap`. Graduate to `System` when
you want to split one system across several focused diagrams. For
non-architecture diagrams, pick the matching `*Map` per the table.

`SequenceMap`, `ERMap`, `StateMap`, `ClassMap`, and `BPMNMap` follow
the same shape as the three documented in depth below (fluent
chaining, `.diagram` exposes the validated Pydantic instance,
`.show()` / `.save()` accept `viewer=`). Their kind-specific methods
are documented in the per-ontology pages linked in the table.

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

---

## Automatic behaviours

These are not user-controlled; the renderer applies them based on
diagram shape and topology. Mentioned here so the output isn't
surprising.

### Off-page connectors (long-span edges)

When a connection spans **three or more layers** (e.g. an `edge`
component talking directly to an `infra` component), sysatlas replaces
the single long line with a pair of small ellipse glyphs near each
endpoint. The source-side glyph says `↪ Target` and lives in the
gutter below the source node; the target-side glyph says `↩ Source`
above the target node. Keeps the diagram clean by avoiding edges that
cross the whole canvas. Threshold is `LONG_LAYER_THRESHOLD = 3` in
`sysatlas/_connectors.py`.

### Variable node height

When a node has **four or more connections on the same side**
(left/right typically), it grows vertically to fit the ports with
enough spacing. Default height is 60 px; each extra port adds
`PORT_PITCH = 28` px (label height + edge spacing). Other nodes in the
same layer keep their height; the row is sized to the tallest. See
`compute_node_heights` in `sysatlas/_route.py`.

### Bias toward vertical ports

For a layered diagram, edges between layers prefer top/bottom ports
even when the horizontal offset to the target is somewhat larger than
the vertical. The bias is 2× in `_pick_side` (`sysatlas/_route.py`):
horizontal port only when `|dx| > 2·|dy|`. This keeps the typical
top-down flow clean.

### Label collision avoidance, source bias

Edge labels are placed by scoring candidate positions along the edge.
Candidates near edge×edge crossings or overlapping with previously
placed labels are penalised; positions closer to the **source end** of
the edge are preferred (symmetric layouts get less label congestion in
the middle). A label is rejected if its perpendicular offset from the
edge would exceed `MAX_LABEL_OFFSET = 16` px. See
`_select_labels` in `sysatlas/_route.py`.

### Directional congestion (no collinear overlaps)

The A\* router tracks cell usage **per direction**. Two edges crossing
perpendicularly at a single point is cheap; two edges running in the
same direction over overlapping cell ranges (a collinear overlap) is
heavily penalised. Result: perpendicular crossings exist, parallel
overlaps don't.

### Group title rows are partial obstacles

Each group's title bar (top 24 px of the swimlane) blocks **horizontal**
movement for the router (a line running parallel on top of the text is
forbidden) but allows **vertical** movement (a line crossing through
perpendicularly is fine).

### Connector glyphs hard-block routing

Off-page connector glyphs (above) are treated as hard obstacles by the
router. Direct edges never cross them visually.

---

## Debugging

Pass `debug=True` to `SystemMap.show()` to get a layout report printed
to stdout. Example output:

```
── Gutter sizes (rank → px gap): {0: 100, 1: 152, 2: 110, 3: 100}
── Placement refinement ──────────────
  layer spread: layers [2, 4] expanded to 728px (65% of 1120px)
  layer centering shifts: [...]
  port swaps applied: 1
  swap [Catalog DB ↔ Cache]  cost ↓

── A* routed 16 direct, 3 via connectors ──
  swap+reroute swaps accepted: 1
  nodes grown for ports: {'API Gateway': 80, 'Catalog': 80}
  layout issues:
    edge through node : 0
    edge × edge       : 3
    collinear overlap : 0
    short/dangling    : 0
```

The four counters at the end are the **issue detector** in
`_report_issues`. The first two and the last are visual problems
sysatlas tries to drive to zero:

- `edge through node` → segment crosses a non-endpoint node's bbox. Must be zero in a good layout.
- `edge × edge` → two segments cross each other (orthogonal crossings). Some are unavoidable due to topology; tolerable.
- `collinear overlap` → two segments share the same y (horizontal) or x (vertical) over an overlapping range. Visually indistinguishable lines; must be zero.
- `short/dangling` → edge with no waypoints. Must be zero.

`debug=True` also enables the per-iteration placement-refinement
deltas, useful when tuning layout. Not exposed on `System.save()` (yet)
because System renders multiple views in one call.

---

## What `tech=` does

The `tech=` parameter on `add_component()` is stored as **metadata
only** — it does not appear in the rendered diagram. It's there to be
queried programmatically (`m.diagram.components[name].tech`) or to be
shown by future renderers that surface component metadata. The
in-diagram label is whatever you pass to `label=`, defaulting to
`name`. If you want the tech to be visible, include it in the label,
e.g. `add_component("Cache", label="Cache<br>(Redis)")`. Same for any
other `**meta` kwargs.
