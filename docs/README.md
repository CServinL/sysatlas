# Documentation index

Pick a starting point based on what you're trying to do.

## I want to…

| …intent | Read |
|---|---|
| understand what sysatlas is, in 30 seconds | [`../README.md`](../README.md) |
| see working code for every feature | [`demos/`](demos/) |
| understand the project philosophy | [`design-principles.md`](design-principles.md) |
| know which builder class to use | [`builders.md`](builders.md) |
| see all supported diagram types and their schemas | [`ontology/README.md`](ontology/README.md) |
| see how sysatlas relates to ISO 42010 / C4 / ArchiMate / UML / BPMN | [`state-of-the-art.md`](state-of-the-art.md) |
| know what's queued for the next sessions | [`todo.md`](todo.md) |
| see sysatlas diagrams of sysatlas itself | [`reflection/`](reflection/) |

## Sections

- **[`demos/`](demos/)** — runnable feature-by-feature showcases.
  `architecture.py` doubles as the quickstart.
- **[`ontology/`](ontology/)** — per-diagram-type schemas and semantics
  (Pydantic models + prose specs). Seven diagram ontologies plus three
  cross-cutting ones (ISO 42010 meta, trace links, ISO 25010 qualities).
- **[`reflection/`](reflection/)** — diagrams of sysatlas itself, built
  with sysatlas. Dog-fooding.
- **[`design-principles.md`](design-principles.md)** — bounded
  complexity, multi-view by default, and why both are non-negotiable.
- **[`state-of-the-art.md`](state-of-the-art.md)** — catalogue of
  standards, frameworks, layout algorithms, and reference works we
  draw from (or deliberately don't).
- **[`builders.md`](builders.md)** — when to use `SystemMap` vs
  `System` vs `TreeMap`, plus viewer modes (cdn / local / embed).
- **[`todo.md`](todo.md)** — short-term roadmap with done / open /
  deferred / advanced sections.
