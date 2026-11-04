# sysatlas — App Spec

The **intended** design of sysatlas: what it is for, who uses it, what it
must do, and what it deliberately does not do. This is written by people,
ahead of and independent of the code.

Compare it with [`reflection/atlas.md`](reflection/atlas.md), the generated
mirror of how the code is *actually* organized, to see where the two have
drifted.

---

## 1. Purpose

Give software architects and AI coding assistants a way to keep an
architecture description and the code it describes in sync, in both
directions:

- **Forward** — describe a system as a design, before the code exists.
- **Backward** — read existing code and produce the same description from
  its real structure.

## 2. Users

| User | Needs |
|---|---|
| Software architect | Readable diagrams, split into focused views, that stay current |
| AI coding assistant | A deterministic, token-cheap way to understand a repo, and clear rules for using the library |
| Consuming repo (e.g. prisma-server, prisma-desktop) | A stable public API and a bundled guide and skill, installed with the package |

## 3. Capabilities

1. **Typed diagram builders** — architecture (`SystemMap`), `TreeMap`,
   `SequenceMap`, `ERMap`, `StateMap`, `ClassMap`, `BPMNMap`, each backed
   by a Pydantic ontology.
2. **Multi-view systems** — `System` groups several views under ISO 42010
   (stakeholders, concerns, viewpoints), with trace links across views and
   ISO 25010 quality attributes.
3. **Rendering** — a single self-contained interactive HTML file (draw.io
   viewer), no server needed.
4. **Reflection** — `reflect()` / `reflect_rust()` read Python and Rust
   source statically (never executing it) and produce a `SystemMap`, a
   `System`, or an architecture atlas.
5. **Architecture atlas** — a deterministic, bounded Markdown map of a
   repo's architecture: components and dependency tiers, entry points,
   external systems, data models, configuration, cycles and hotspots. It
   reports where the code departs from a declared architecture spec, lists
   architectural pattern candidates with their evidence, and lists what still
   needs documenting.
6. **Intent overlay** — a hand- or LLM-written JSON file with component
   purposes and architectural patterns, merged into the atlas and marked as
   not generated. Fingerprints flag entries that the code has outgrown.
7. **LLM support** — a bundled usage guide (`llm_guide()`) and two Claude Code
   skills (`skill("sysatlas")`, `skill("sysatlas-document")`), shipped inside
   the package.

## 4. Principles

Set out in [`design-principles.md`](design-principles.md). In short:

- **Bounded complexity per view** — about 5–10 components per diagram;
  splitting a dense view is the right answer, not a bigger canvas.
- **Multi-view by default.**
- **Determinism** — the same input gives byte-identical output, so
  generated files can be committed and diffed.
- **Static analysis only** — reflection never imports or runs the target
  code, so it is safe on broken or uncompiled projects.

## 5. Constraints

- A library, not a tool: no CLI entry point. `SystemMap` is the only public
  diagram class in the main API; everything under `sysatlas._*` is private.
- Pydantic for all data models; no `@dataclass`.
- Runtime dependencies stay small (`networkx`, `pydantic`); Rust support is
  an optional extra.
- Python 3.10 or newer.

## 6. Non-goals

- Large "everything on one canvas" diagrams. Use another tool for those.
- Deriving runtime behavior, requirements, or intent from code. Reflection
  reports structure only; the *why* comes from this spec and the
  human-authored intent overlay.
- Running or importing the code it analyzes.

## 7. Open items

Tracked in [`todo.md`](todo.md) and [`issues/`](issues/): draw.io layers
(0.4.0), Rust symbol extraction for the atlas, export interop, and
requirements linking.
