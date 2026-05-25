# Reflection

Diagrams of sysatlas itself, built with sysatlas.

Self-referential dog-fooding: every concept the library claims to model —
components, layers, multi-view splits, trace links, quality attributes —
should be expressible *about sysatlas*. This directory is where those
diagrams live, as both `.py` source (the canonical artefact) and rendered
`.html` output (regenerated on demand; not committed).

## Why this exists

- **Pressure test the API** — if drawing sysatlas in sysatlas is awkward,
  the API is wrong. The diagrams here are the most honest acceptance
  test we have.
- **Documentation** — the architecture / pipeline / ontology hierarchy
  is easier to grok visually than from prose alone.
- **Examples** — anyone reading the codebase can see how each feature
  is actually used end-to-end on a non-trivial system (sysatlas itself
  has multiple ontologies, a multi-stage pipeline, cross-cutting
  concerns — exactly the shape sysatlas is designed for).

## Layout

| File | What it diagrams |
|---|---|
| _(planned)_ `pipeline.py` | The layout/route/render pipeline as a layered architecture diagram. |
| _(planned)_ `ontology-tree.py` | The 7 model kinds + cross-cutting ontologies as a tree. |
| _(planned)_ `module-map.py` | Internal module dependencies (multi-view: by layer and by domain). |
| _(planned)_ `quality-map.py` | Components annotated with ISO 25010 qualities (which parts are perf-critical, which are correctness-critical). |

Add new reflection diagrams here as the library grows. Update this
README's table when you do.

## Conventions

- One `.py` per diagram (or `.System` instance per project).
- Run with `python docs/reflection/<file>.py` → opens HTML in browser
  via `.show()`.
- Do not commit generated `.html` files (already in `.gitignore`).
