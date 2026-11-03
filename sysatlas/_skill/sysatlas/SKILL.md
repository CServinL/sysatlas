---
name: sysatlas
description: Use when this project has the sysatlas package installed or imported (architecture diagrams, SystemMap, sysatlas.reflect(), docs/reflection/). Read the architecture atlas for a holistic view of the repo before exploring source, use the fluent builders correctly, and regenerate the atlas and diagrams after structural code changes (add/remove/rename module, class, or component).
user-invocable: true
---

# sysatlas — architecture diagrams & the holistic atlas

sysatlas is a Python library for interactive architecture diagrams
(Pydantic-backed fluent builders → self-contained HTML via a draw.io
viewer), plus a reverse flow that reads existing code into the same
diagram types.

## Read this first

If this project commits an architecture atlas (default location
`docs/reflection/atlas.md`), read it **before** exploring source. It's a
deterministic, token-cheap Markdown map of the repo's architecture:
components and their dependency tiers, entry points (routes, CLI commands,
tasks, scripts), external systems (databases, APIs, queues), data models,
environment variables, per-module purpose and symbols, import cycles,
coupling hotspots, and — if the hints file declares an `architecture` spec —
whether the code conforms to it. It gives a holistic view without reading
every file.

The atlas shows structure only. It does not say what a component is for; that
comes from `docs/reflection/intent.json`, which is hand- or LLM-written and
marked as such. When the atlas lists "Documentation gaps", use the
`sysatlas-document` skill to fill them.

## Forward vs. backward flow

Forward: write builder calls (`SystemMap`, `System`, `TreeMap`, …) to
describe a system as a design. Backward: `sysatlas.reflect(path)` reads
real Python (or Rust, via `reflect_rust`) and produces the same diagram
types — and the atlas — from actual code structure. Most real usage mixes
both: structure from reflection, semantics (qualities, traces, stakeholders)
from a hand-authored overlay merged in with `.merge_with(overlay)`.

## Public API surface

```python
import sysatlas

sysatlas.SystemMap      # one architecture diagram
sysatlas.System         # multi-view Architecture Description (ISO 42010)
sysatlas.TreeMap        # tree / org-chart / mindmap
sysatlas.SequenceMap    # UML sequence diagram
sysatlas.ERMap          # Entity-Relationship diagram
sysatlas.StateMap       # state machine / state chart
sysatlas.ClassMap       # UML class diagram
sysatlas.BPMNMap        # BPMN process diagram
sysatlas.reflect(path)  # reverse flow: code → Reflection → SystemMap / atlas
sysatlas.llm_guide()    # full plain-text usage guide
```

`Reflection` (from `reflect()` / `reflect_rust()`) exposes
`.to_system_map()`, `.to_system()`, `.merge_with(overlay)`, `.exclude(...)`,
and the atlas methods `.to_atlas()` / `.to_atlas_model()` / `.save_atlas(path)`.

## Your responsibility in this project

After you add, remove, or rename a module, class, or component, the
architecture atlas and the diagrams under `docs/reflection/` (or wherever
this project keeps them) are stale. Regenerating them is your job, not the
user's:

```python
import sysatlas
r = sysatlas.reflect("path/to/source/root")
r.save_atlas("docs/reflection/atlas.md", title="…",   # holistic text map
             intent="docs/reflection/intent.json")     # omit if no intent file
m = r.to_system_map(title="…")
m.save("docs/reflection/module-map.html")               # diagram
```

## Hard rules

- Use only the public symbols above; never import `sysatlas._*`.
- Use Pydantic for any new model; never `@dataclass`.
- Field names must match the ontology exactly — check the matching
  `sysatlas/_ontology/*.py` schema if unsure.
- Bounded complexity per view: ~5–10 components, 8–15 connections. Split
  a dense diagram across views with `System` instead of fighting layout.

## Where to find more

Full reference: `sysatlas.llm_guide()` for the complete plain-text guide,
`docs/builders.md` for per-kind builder methods, `docs/ontology/` for
per-diagram-type specs — all in the sysatlas source repo.
