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

Active queue is empty — the AD round, polish round, and the
complete-ontology round all shipped. Pick from *Advanced backlog* or
*Explicitly deferred* next.

### Done since last review

- **All five remaining ontologies shipped end-to-end** ✓ —
  `SequenceMap`, `ERMap`, `StateMap`, `ClassMap`, `BPMNMap`.
  `state_machine` / `er` / `uml_class` route through the C4 layered
  engine; `sequence` and `bpmn` keep custom layouts that fit their
  semantics. See `docs/demos/{sequence,er,state_machine,uml_class,bpmn}.{py,html,png}`.
- **ModelKind taxonomy** ✓ — `sysatlas/_ontology/model_kind.py` +
  `model_kinds.py` (`DEFAULT_KINDS` registry). Adds a taxonomy layer
  above the existing Ontologies without renaming anything. See
  [`ontology/model_kinds.md`](ontology/model_kinds.md).
- **Per-node height threaded through layout** ✓ — `_assign_coords`
  now reads each node's `height` override from `nodes_meta` so
  ER/UML class boxes no longer bleed into the layer below them.
- **Off-page connectors opt-out** ✓ — `edge.no_connector=True` forces
  direct routing even on long-span edges. Used by `StateMap` so
  state-machine diagrams never grow off-page glyphs.

## Advanced backlog

- **Clickable / toggleable layer visibility** — draw.io has native
  layer toggling in its viewer toolbar (`layers` already in
  `_VIEWER_CONFIG`). Mapping our `layer_order` to mxGraph layers would
  let users show/hide tiers (`edge`, `services`, `data`, …) per view.
  Coexistence with the swim-lane groups needs design work — groups are
  cells, layers are parent-of-cells.
- **Evolve in-house layout engines** — add force-directed, orthogonal
  (TSM/HOLA), and channel-routing variants alongside the existing
  Sugiyama + A\*. Avoid pulling in ELK/DAGRE per the no-external-dep
  policy. Rationale: [`state-of-the-art.md`](state-of-the-art.md) §10.
- **Render-only stub placement** — stubs currently land wherever
  Sugiyama puts a node with no connections (i.e. arbitrary). Could be
  pinned to the edge of the canvas closest to where the trace overlay
  points.

---

## Ontology readiness matrix

All diagram ontologies are end-to-end usable (Pydantic schema + fluent
builder + render pipeline).

| Ontology | Pydantic schema | Fluent builder | HTML render |
|---|:---:|:---:|:---:|
| architecture (C4 container) | ✓ | ✓ `SystemMap` / `System` | ✓ |
| tree | ✓ | ✓ `TreeMap` | ✓ |
| er | ✓ | ✓ `ERMap` | ✓ |
| sequence | ✓ | ✓ `SequenceMap` | ✓ |
| uml_class | ✓ | ✓ `ClassMap` | ✓ |
| state_machine | ✓ | ✓ `StateMap` | ✓ |
| bpmn | ✓ | ✓ `BPMNMap` | ✓ |
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
| ~~5~~ | ~~uml_class~~ | ~~inheritance-ranked layered~~ | ~~high~~ | **shipped** |
| ~~6~~ | ~~bpmn~~ | ~~swimlane + BFS row~~ | ~~high~~ | **shipped** |

All originally schema-only ontologies are now end-to-end. No remaining
items in the readiness queue.

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
