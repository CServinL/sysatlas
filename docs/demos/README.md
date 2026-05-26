# Demos

Curated runnable showcases — one file per feature. Each demo exercises
one capability in isolation so we (and anyone reading the codebase) can
see it work end-to-end. The full e-commerce diagram in `architecture.py`
doubles as the quickstart.

Generated `.html` is in `.gitignore`; run any demo to produce one
locally.

## How to run

```bash
python docs/demos/<name>.py
```

Each script ends with `.show()` or saves to `/tmp/sysatlas_<name>.html`.

## What's here

| Demo | What it shows |
|---|---|
| `architecture.py` | Full e-commerce C4-container diagram (also serves as the quickstart) — `SystemMap` |
| `tree.py` | Org-chart tree via `TreeMap` (top-down Reingold-Tilford) |
| `multi_view.py` | Multi-view AD via `System` with cross-view stubs |
| `qualities.py` | ISO 25010 quality badges on nodes and edges |
| `trace_matrix.py` | Trace links rendered as both dashed overlay and HTML matrix |

When adding a new diagram capability, drop a self-contained demo here
and update this table.

## Distinction from neighbouring directories

| Directory | Purpose |
|---|---|
| `docs/demos/` | Feature-by-feature showcase. Each script focuses on one capability. |
| `docs/reflection/` | sysatlas-diagrams-of-sysatlas (dog-fooding). |
| `docs/ontology/` | Per-ontology specs (Pydantic schemas + semantics). |
