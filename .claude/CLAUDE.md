# sysatlas

Interactive system and architecture diagram library.
Python describes the diagram; draw.io viewer renders interactive HTML.

Core flow: `SystemMap → mxGraph XML → draw.io viewer → .html`

## API surface

`SystemMap` is the only public class. Keep it that way.
Do not add a CLI entry point — this is a library.

## Output files

Generated `.html` files are in `.gitignore`. They are not committed.
The `.py` diagram scripts are the versioned source.

## Project venv

`.venv/` at repo root. No external dependencies (draw.io viewer bundled).

## Design principles

Before designing or changing layout, routing, ontology, or API behaviour,
read [`docs/design-principles.md`](../docs/design-principles.md). Two
non-negotiables:

- **Bounded complexity per view** — sysatlas targets low-complexity
  diagrams (rough budget: 5–10 components, 8–15 connections per view).
  Algorithms are tuned for this regime; degrading at higher counts is
  intentional.
- **Multi-view by default** — a system is described by several focused
  views, not one giant diagram. When a view gets dense, the right answer
  is to split it (by bounded context, layer, stakeholder concern, feature,
  or zoom level), not to fight the layout engine.

For the wider academic / industry context (ISO 42010, C4, ArchiMate,
UML / SysML / BPMN, layout algorithms, export formats, quality models,
domain modelling), see [`docs/state-of-the-art.md`](../docs/state-of-the-art.md).

## Diagram ontologies

Each supported diagram type has a typed ontology under
`sysatlas/_ontology/` and a prose spec under `docs/ontology/`.

**Before working on anything diagram-specific** (adding a feature to a
diagram type, debugging routing/placement for a particular diagram,
extending the builder API, writing tests), read the corresponding files:

| Diagram type | Schema | Doc |
|---|---|---|
| Layered architecture | `sysatlas/_ontology/architecture.py` | `docs/ontology/architecture.md` |
| Entity-Relationship | `sysatlas/_ontology/er.py` | `docs/ontology/er.md` |
| Sequence | `sysatlas/_ontology/sequence.py` | `docs/ontology/sequence.md` |
| Class (UML) | `sysatlas/_ontology/uml_class.py` | `docs/ontology/uml_class.md` |
| State machine | `sysatlas/_ontology/state_machine.py` | `docs/ontology/state_machine.md` |
| BPMN process | `sysatlas/_ontology/bpmn.py` | `docs/ontology/bpmn.md` |
| Tree (org / mindmap / etc.) | `sysatlas/_ontology/tree.py` | `docs/ontology/tree.md` |

Cross-cutting ontologies (apply to multiple diagram types, not a diagram
type themselves):

| Concern | Schema | Doc |
|---|---|---|
| ISO 42010 meta (Stakeholder/Concern/Viewpoint/View/AD) | `sysatlas/_ontology/iso42010.py` | `docs/ontology/iso42010.md` |
| Trace links across model kinds | `sysatlas/_ontology/trace.py` | `docs/ontology/trace.md` |
| Quality attributes (ISO 25010) | `sysatlas/_ontology/qualities.py` | `docs/ontology/qualities.md` |

Always read **both** the schema (Pydantic models, source of truth) and
the doc (semantics, validation rules, distinctions from neighbouring
types) before changing anything in that diagram's pipeline. The index
of all ontologies plus what was intentionally omitted lives at
`docs/ontology/README.md`. The short-term roadmap is `docs/todo.md`.
