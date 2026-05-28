# Short-term TODO

What's queued next, in priority order. Each item links to relevant context.
Update as work lands.

See also: [state-of-the-art.md](state-of-the-art.md) for the catalogue of
standards we draw from, and [design-principles.md](design-principles.md)
for the non-negotiables every change is bounded by.

---

## Done

### 1. ISO 42010 meta-ontology  ✓

`sysatlas/_ontology/iso42010.py` + `docs/ontology/iso42010.md`.
Types: `Stakeholder`, `Concern`, `Viewpoint`, `View`, `ArchitectureDescription`.
Wraps existing Model Kinds without renaming anything.

### 2. Trace links across model kinds  ✓

`sysatlas/_ontology/trace.py` + `docs/ontology/trace.md`.
Types: `EntityRef`, `TraceLink`, `TraceLinkSet`. Resolver validates
endpoints against the AD's models. 10 link kinds from SysML / OMG vocab.

### 3. Quality attributes (ISO/IEC 25010)  ✓

`sysatlas/_ontology/qualities.py` + `docs/ontology/qualities.md`.
`QualityAttribute` field added to `architecture.Component` and
`architecture.Connection`. Other ontologies can adopt the same field on
demand.

---

## Next up

All four follow-ups from the AD round shipped:

- **AD builder** (`sysatlas.System`) ✓
- **Quality badges** on nodes ✓ (filtered to criticality ≥ high)
- **Cross-view stubs** ✓ (auto-detected on `System.save()`)
- **Trace links rendered** ✓ (dashed purple connectors within a view)

All four follow-ups from the polish round shipped:

- **Tree diagram end-to-end** ✓ — `sysatlas.TreeMap`, Reingold-Tilford
  top-down layout, draw.io render. Validates that the
  ontology + builder + render pattern replicates beyond C4.
- **Traces as post-layout overlay** ✓ — overlays no longer enter the
  Sugiyama Connection list; they are rendered as straight dashed edges
  between known node positions after layout is fixed.
- **Quality badges on edges** ✓ — `Connection.qualities` now render as
  ISO 25010 badges adjacent to the edge label.
- **Trace matrix view-kind** ✓ — `System.save_trace_matrix(path)` emits
  an HTML matrix of sources × targets with coloured kind tags + legend.

## Advanced backlog

- **Clickable / toggleable layer visibility** — draw.io has native
  layer toggling in its viewer toolbar (`layers` already in
  `_VIEWER_CONFIG`). Mapping our `layer_order` to mxGraph layers would
  let users show/hide tiers (`edge`, `services`, `data`, …) per view.
  Coexistence with the swim-lane groups needs design work — groups are
  cells, layers are parent-of-cells.
- **Builder ergonomics for non-architecture model kinds** — `TreeMap`
  set the pattern. Repeat for ER, sequence, UML class, state machine,
  BPMN (order in *Ontology readiness matrix* below).
- **Render-only stub placement** — stubs currently land wherever
  Sugiyama puts a node with no connections (i.e. arbitrary). Could be
  pinned to the edge of the canvas closest to where the trace overlay
  points.

---

## Ontology readiness matrix

Only `architecture` (C4-container) is end-to-end usable. The other six
diagram ontologies have schemas but no builder and no render pipeline.

| Ontology | Pydantic schema | Fluent builder | HTML render |
|---|:---:|:---:|:---:|
| architecture (C4 container) | ✓ | ✓ `SystemMap` / `System` | ✓ |
| tree | ✓ | ✓ `TreeMap` | ✓ |
| er | ✓ | ✓ `ERMap` | ✓ |
| sequence | ✓ | ✓ `SequenceMap` | ✓ |
| uml_class | ✓ | ✗ | ✗ |
| state_machine | ✓ | ✓ `StateMap` | ✓ |
| bpmn | ✓ | ✗ | ✗ |
| iso42010 (cross-cutting) | ✓ | ✓ (via `System`) | partial (multi-tab) |
| trace links (cross-cutting) | ✓ | ✓ (via `System.trace()`) | ✓ (dashed connectors) |
| qualities (cross-cutting) | ✓ | ✓ (Pydantic on Component/Connection) | ✓ (badges) |

### Recommended order to extend coverage

Tree shipped. Remaining order — easier layouts and simpler renders first:

| Order | Ontology | Natural layout | Render complexity | Reason |
|---|---|---|---|---|
| ~~1~~ | ~~tree~~ | ~~Reingold-Tilford~~ | ~~low~~ | **shipped** |
| ~~2~~ | ~~sequence~~ | ~~fixed vertical lifelines, time on Y~~ | ~~medium~~ | **shipped** |
| ~~3~~ | ~~er~~ | ~~grid placement~~ | ~~medium~~ | **shipped** |
| ~~4~~ | ~~state_machine~~ | ~~layered BFS-rank~~ | ~~medium~~ | **shipped** |
| 1 | uml_class | hierarchical (inheritance) or force | high | compartments (attrs, methods), 6 relation kinds, multiplicities |
| 2 | bpmn | horizontal time-flow with lanes | high | pools/lanes as swimlanes, gateway diamonds, event circles, multiple flow kinds |

The shared `_layout`, `_route`, `_place` primitives are reusable for any
of these once the per-ontology builder + style mapping is written.

---

## Explicitly deferred

### Export interop (Mermaid / PlantUML / DOT)

draw.io / mxGraph XML is already wide-spread and interoperable; not the
top friction point. Revisit when concrete demand appears.

### Versioning / evolution

Diagrams as snapshots is fine for now. Revisit when we have AD container
usage in real projects.

### Requirements linking

Useful but blocked on having a Requirements model kind first. Defer until
trace links land and we know how requirement objects should be modelled.

### Pattern templates

"Drop-in API Gateway" pre-built fragments. Defer until the AD container
exists; templates live more naturally there than at builder level.

---

## Gap summary (for orientation)

From [state-of-the-art.md](state-of-the-art.md) §9, current gaps in sysatlas:

| Gap | Status |
|---|---|
| No Stakeholders / Concerns / Viewpoints | **Done (item 1)** |
| No Trace links | **Done (item 2)** |
| No Quality attributes | **Done (item 3)** |
| No Export interop (Mermaid/PlantUML/DOT/GraphML) | Deferred |
| No Versioning / evolution | Deferred |
| No Requirements linking | Deferred (now unblocked by item 2; add a Requirements model kind when prioritised) |
| No Pattern templates | Deferred |
| No rendering for qualities / trace links | Open (see *Next up* above) |
