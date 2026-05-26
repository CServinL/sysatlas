# sysatlas — full project index

This file is the **canonical entry point** for navigating the codebase
and docs. Every feature, file, demo, and ontology that exists in
sysatlas is reachable from here. Future sessions should read this
*after* `.claude/CLAUDE.md` to get the full app surface in one place.

## I want to…

| …intent | Read |
|---|---|
| understand what sysatlas is, in 30 seconds | [`../README.md`](../README.md) (elevator pitch) |
| see working code for every feature | [`demos/`](demos/) |
| understand the project philosophy | [`design-principles.md`](design-principles.md) |
| know which builder class to use | [`builders.md`](builders.md) |
| see all supported diagram types and their schemas | [`ontology/README.md`](ontology/README.md) |
| see how sysatlas relates to ISO 42010 / C4 / ArchiMate / UML / BPMN | [`state-of-the-art.md`](state-of-the-art.md) |
| know what's queued for the next sessions | [`todo.md`](todo.md) |
| see sysatlas diagrams of sysatlas itself | [`reflection/`](reflection/) |

---

## Public API

The full surface exposed from `import sysatlas`:

| Symbol | Kind | Doc | Source |
|---|---|---|---|
| `sysatlas.SystemMap` | Builder — single architecture diagram | [`builders.md`](builders.md) §SystemMap | `sysatlas/system_map.py` |
| `sysatlas.System` | Builder — multi-view Architecture Description | [`builders.md`](builders.md) §System | `sysatlas/system.py` |
| `sysatlas.TreeMap` | Builder — tree/org-chart/mindmap diagram | [`builders.md`](builders.md) §TreeMap | `sysatlas/tree_map.py` |

Every builder method (`group`, `add_component`, `connect`, `show`,
`save`, `stakeholder`, `concern`, `viewpoint`, `view`,
`architecture_model`, `trace`, `save_trace_matrix`, `add`,
`save_collection`) is documented in [`builders.md`](builders.md).

The underlying validated Pydantic instance is reachable via
`m.diagram` (SystemMap, TreeMap) or `s.description` (System).

---

## Diagram ontologies (Model Kinds)

Seven typed diagram kinds. Today only **architecture** and **tree**
are end-to-end (builder + render); the others ship schemas and
validation only, waiting on builder + render to be plugged in (order
in [`todo.md`](todo.md) §Ontology readiness).

| Ontology | Schema | Doc | Status |
|---|---|---|---|
| Layered architecture (C4 container) | `sysatlas/_ontology/architecture.py` | [`ontology/architecture.md`](ontology/architecture.md) | end-to-end (`SystemMap`/`System`) |
| Tree (org / mindmap / taxonomy / filesystem) | `sysatlas/_ontology/tree.py` | [`ontology/tree.md`](ontology/tree.md) | end-to-end (`TreeMap`) |
| Entity-Relationship | `sysatlas/_ontology/er.py` | [`ontology/er.md`](ontology/er.md) | schema only |
| Sequence (UML) | `sysatlas/_ontology/sequence.py` | [`ontology/sequence.md`](ontology/sequence.md) | schema only |
| Class (UML) | `sysatlas/_ontology/uml_class.py` | [`ontology/uml_class.md`](ontology/uml_class.md) | schema only |
| State machine | `sysatlas/_ontology/state_machine.py` | [`ontology/state_machine.md`](ontology/state_machine.md) | schema only |
| BPMN process (subset) | `sysatlas/_ontology/bpmn.py` | [`ontology/bpmn.md`](ontology/bpmn.md) | schema only |

## Cross-cutting ontologies

Apply across multiple model kinds. All end-to-end (Pydantic + builder
integration + render behaviour).

| Concern | Schema | Doc |
|---|---|---|
| ISO/IEC/IEEE 42010 meta (Stakeholder, Concern, Viewpoint, View, AD) | `sysatlas/_ontology/iso42010.py` | [`ontology/iso42010.md`](ontology/iso42010.md) |
| Trace links across model kinds (SysML vocabulary) | `sysatlas/_ontology/trace.py` | [`ontology/trace.md`](ontology/trace.md) |
| Quality attributes (ISO 25010) on components & connections | `sysatlas/_ontology/qualities.py` | [`ontology/qualities.md`](ontology/qualities.md) |

---

## Features → where they live

A flat catalogue: every visible behaviour mapped to where it's
implemented and documented.

| Feature | Doc | Source |
|---|---|---|
| Sugiyama layered placement | [`state-of-the-art.md`](state-of-the-art.md) §4 | `sysatlas/_layout.py` |
| Iterative barycenter X refinement | — | `sysatlas/_place.py` |
| Y-offset per node within layer band | — | `sysatlas/_place.py` |
| Narrow-layer horizontal spread | — | `sysatlas/_place.py` |
| Adjacent-swap layer ordering (re-routes per swap) | — | `sysatlas/_place.py` |
| Connection-weighted neighbor preference | — | `sysatlas/_place.py` (`neighbor_weights`) |
| Dynamic gutter height per rank | — | `sysatlas/_layout.py` (`_gutter_sizes`) |
| Variable node height (4+ ports on a side) | [`builders.md`](builders.md) §Automatic behaviours | `sysatlas/_route.py` (`compute_node_heights`) |
| A\* maze routing | [`state-of-the-art.md`](state-of-the-art.md) §4 | `sysatlas/_route.py` |
| Directional congestion (no collinear overlaps) | [`builders.md`](builders.md) §Automatic behaviours | `sysatlas/_route.py` |
| PAD halo as hard obstacle (no edge-through-node) | — | `sysatlas/_route.py` |
| Group title row blocks horizontal routing only | [`builders.md`](builders.md) §Automatic behaviours | `sysatlas/_route.py` |
| Rip-up & reroute pass | — | `sysatlas/_route.py` |
| Port-side picking (with vertical bias 2×) | [`builders.md`](builders.md) §Automatic behaviours | `sysatlas/_route.py` (`_pick_side`) |
| Label collision avoidance + source bias | [`builders.md`](builders.md) §Automatic behaviours | `sysatlas/_route.py` (`_select_labels`) |
| Issue detection (edge through node / crossings / overlaps) | [`builders.md`](builders.md) §Debugging | `sysatlas/_layout.py` (`_report_issues`) |
| Off-page connectors for long-span edges | [`builders.md`](builders.md) §Automatic behaviours | `sysatlas/_connectors.py` |
| Quality badges on nodes | [`builders.md`](builders.md) §Quality attributes, [`ontology/qualities.md`](ontology/qualities.md) | `sysatlas/_render.py` |
| Quality badges on connections | [`builders.md`](builders.md) §Quality attributes | `sysatlas/_render.py` |
| Cross-view stub auto-detection | [`builders.md`](builders.md) §System | `sysatlas/system.py` (`_inject_stubs`) |
| Trace link overlay (dashed purple edges) | [`builders.md`](builders.md) §Trace links, [`ontology/trace.md`](ontology/trace.md) | `sysatlas/system.py` (`_collect_trace_overlays`) |
| Trace matrix HTML view | [`builders.md`](builders.md) §Trace links | `sysatlas/_trace_matrix.py` |
| Multi-tab HTML output | [`builders.md`](builders.md) §System | `sysatlas/_render.py` (`render_collection`) |
| Three viewer modes (cdn / local / embed) | [`builders.md`](builders.md) §Viewer modes | `sysatlas/_render.py` (`_viewer_tag`), `sysatlas/_vendor.py` |
| Friendly error when viewer JS fails to load | — | `sysatlas/_render.py` (`_viewer_missing_js`) |
| Bounded complexity philosophy | [`design-principles.md`](design-principles.md) | — |
| Multi-view splitting as first-class | [`design-principles.md`](design-principles.md), [`builders.md`](builders.md) §System | `sysatlas/system.py` |
| `tech=` is metadata-only | [`builders.md`](builders.md) §What `tech=` does | `sysatlas/_render.py` |
| Debug mode (`show(debug=True)`) | [`builders.md`](builders.md) §Debugging | `sysatlas/_layout.py` |

---

## Source tree

```
sysatlas/
├── __init__.py                 — public exports: SystemMap, System, TreeMap
├── system_map.py               — SystemMap builder (single architecture)
├── system.py                   — System builder (multi-view AD + traces)
├── tree_map.py                 — TreeMap builder
├── _layout.py                  — Sugiyama; calls into _place, _route; issue detector
├── _place.py                   — barycenter refinement, swap-and-reroute, narrow-layer spread
├── _route.py                   — A* routing, port assignment, label placement
├── _connectors.py              — long-span edge → off-page connector classification
├── _render.py                  — mxGraph XML emission, HTML shell, badges, stubs
├── _tree_layout.py             — Reingold-Tilford for TreeMap
├── _tree_render.py             — tree-specific draw.io emission
├── _trace_matrix.py            — HTML matrix view-kind for trace links
├── _vendor.py                  — draw.io viewer JS download / bundle
└── _ontology/
    ├── __init__.py
    ├── architecture.py         — Component, Connection, Layer, Group, ArchitectureDiagram
    ├── bpmn.py                 — Pool, Lane, Event, Activity, Gateway, Flow, BPMNDiagram
    ├── er.py                   — Entity, Attribute, Relationship, ERDiagram
    ├── iso42010.py             — Stakeholder, Concern, Viewpoint, View, ArchitectureDescription
    ├── qualities.py            — QualityAttribute (ISO 25010)
    ├── sequence.py             — Actor, Message, Activation, Frame, SequenceDiagram
    ├── state_machine.py        — State, Transition, StateDiagram
    ├── trace.py                — EntityRef, TraceLink, TraceLinkSet, resolve_links
    ├── tree.py                 — TreeNode, TreeDiagram
    └── uml_class.py            — Class, Attribute, Method, Relation, ClassDiagram
```

## Docs tree

```
docs/
├── README.md                   — THIS FILE (full app index)
├── design-principles.md        — bounded complexity, multi-view, non-negotiables
├── state-of-the-art.md         — ISO 42010, C4, ArchiMate, UML, BPMN, layout algorithms
├── builders.md                 — when to use each builder + viewer modes + auto behaviours + debugging
├── todo.md                     — short-term roadmap (done / open / advanced / deferred)
├── ontology/
│   ├── README.md               — index of model kinds + cross-cutting
│   ├── architecture.md
│   ├── er.md
│   ├── sequence.md
│   ├── uml_class.md
│   ├── state_machine.md
│   ├── bpmn.md
│   ├── tree.md
│   ├── iso42010.md
│   ├── trace.md
│   └── qualities.md
├── demos/                      — runnable feature showcases + previews
│   ├── README.md               — embeds PNG + links to .py + .html per demo
│   ├── architecture.py / .html / .png
│   ├── tree.py / .html / .png
│   ├── multi_view.py / .html / .png
│   ├── qualities.py / .html / .png
│   ├── trace_matrix.py / .html / .png  (+ trace_matrix_table)
│   ├── html/                   — committed CDN renders (~10–25 KB each)
│   └── img/                    — committed PNG previews
└── reflection/                 — sysatlas diagrams of sysatlas (dog-fooding)
    └── README.md               — skeleton; planned: pipeline.py, ontology-tree.py, module-map.py, quality-map.py
```

---

## Roadmap pointers

- **Active backlog**: [`todo.md`](todo.md) §Next up
- **Advanced experiments**: [`todo.md`](todo.md) §Advanced backlog (clickable layer toggle, builder ergonomics for remaining ontologies, smarter stub placement)
- **Deferred** (waiting on real demand): [`todo.md`](todo.md) §Explicitly deferred (Mermaid/PlantUML export, versioning, requirements linking, pattern templates)
- **Ontology readiness matrix**: [`todo.md`](todo.md) §Ontology readiness matrix (which kinds are end-to-end vs schema-only)
- **Recommended extension order**: sequence → ER → state_machine → uml_class → bpmn (rationale in `todo.md`)

---

## Reading this file in a new session

When picking up this codebase in a fresh session, read in order:

1. `.claude/CLAUDE.md` — project-specific Claude conventions
2. **this file** (`docs/README.md`) — full app surface
3. `docs/todo.md` — what's queued next
4. Any specific doc the current task touches (linked from the tables above)
