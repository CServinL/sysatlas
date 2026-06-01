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

## Long-run advanced topics

Forward direction, not active work. Captured here so the ideas don't
get lost as the close-in roadmap turns over.

### Visual design & effects

The current renderer ships a fixed palette and the draw.io viewer's
defaults. There is a lot of room to make diagrams look like
something a senior architect would put on a slide deck without
post-processing.

- **Themes / dark mode** — configurable palette + stroke/fill rules,
  applied at the `_render.py` style layer. Today the palette is
  hardcoded per group; promote it to a `Theme` object the renderer
  consumes.
- **Icon packs** — render `tech=` as a recognisable glyph
  (AWS / GCP / Azure / K8s, generic shapes for DB / queue / cache,
  etc.) in the node's corner. The icons would ship as separate assets;
  see *Constraints* below.
- **Polish: shadows, gradients, glass** — depth cues at the mxGraph
  style layer. Cheap to add, big visual lift.
- **Edge motion** — animated direction indicators (small triangles
  flowing along the edge) on hover, to show data/flow direction
  without arrowhead clutter.
- **Hover highlight** — dim non-neighbours when hovering a node, so
  fan-in/fan-out reads at a glance.
- **Click-through to source** — for reflected diagrams, components
  hyperlink to their `path:line` in the repo (a `source=` field on
  `Component` carried through to the rendered HTML).
- **High-quality export** — SVG and PDF emitters next to the HTML
  output, for slide decks and print.
- **Mini-map** — viewport navigator overlay for large multi-view HTMLs.

### Deep-learning engines

Use ML where heuristics are running out of steam, *without* breaking
the no-external-dep guarantee for the core library.

- **Learned layout scoring** — train a small GNN to score Sugiyama
  variants (different barycenter seeds, swap sequences, port-side
  picks) on aesthetic criteria — crossings, label density,
  symmetry, edge length. The router still does the work; the model
  picks the best candidate.
- **Auto-grouping / auto-layering** — cluster components by name
  similarity, import-graph topology, and `tech=` to suggest `group=`
  and `layer=` assignments when the user didn't specify them. Useful
  on reflected output where layer inference today is a hardcoded
  regex table.
- **Auto-labelling** — predict a likely `layer` / `group` / `tech`
  from a component's neighbours and identifier. Could fold into
  Reflection's hints application.
- **Natural-language → diagram** — LLM that translates a prose brief
  ("a storefront with cart, catalog, payments via Stripe, async
  notifications via SES") into builder calls.
- **Diagram → critique** — LLM reads a rendered view (HTML or the
  underlying SystemMap) and flags clarity issues: dense label region,
  cluster that should be split, missing trace for an implied
  dependency.
- **Code → semantics** — extension of Reflection that detects
  candidate quality attributes (security-sensitive crypto calls,
  performance-critical hot loops) and trace links (a class that
  *realizes* a domain concept named in a sibling module).

### Constraints

The library's no-external-dep guarantee (one wheel, no runtime
downloads) shapes how these land:

- **Themes, shadows, edge motion, hover highlight, click-through,
  mini-map, SVG/PDF export** can ship in-tree — they are
  emission-layer changes, no new deps.
- **Icon packs** ship as assets; they bloat the wheel. Land them as
  an opt-in `sysatlas[icons]` extra (separate `sysatlas-icons`
  package or wheel data_files) so the core install stays small.
- **ML features** need a runtime (torch / onnxruntime / a hosted API).
  They belong in a sibling package — `sysatlas-ml`, or per-feature
  packages like `sysatlas-nl-builder` — so the core library remains
  zero-dep. Inference results feed back into the existing builders
  and hints files; the ML layer never replaces them.

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
