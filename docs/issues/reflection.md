# Reflection — reverse flow

Read existing Python code, produce a validated `SystemMap` / `System`,
render it. The missing half of sysatlas.

## The three flows

| Flow | Input | Producer | Use case |
|---|---|---|---|
| **Forward** | Builder calls written by hand (or by an LLM from a brief) | Human / LLM | Greenfield design — capturing intent before code exists. |
| **Reverse** | Existing Python source tree | `sysatlas.reflect(path)` | Onboarding, audit, drift detection, "what did the LLM actually build?" |
| **Round-trip** | Reverse output **+** a thin forward "annotation overlay" (qualities / traces / viewpoints / groupings only) | `r.merge_with(blueprint)` | The realistic case: structure comes from code, semantics from a human. |

The forward and reverse flows must land on the **same ontology** (the
existing `_ontology/architecture.py` models). Anything reverse produces
is a normal `SystemMap` — no second renderer, no parallel schema.

## Design decisions (proposed)

1. **AST-only analysis.** `ast.parse()`, no `import`. Safe on broken
   code, no side effects, deterministic. Misses dynamic imports — accepted
   trade-off; user can patch via the hints file.
2. **Default granularity = module.** One `.py` file → one `Component`.
   Package directories become `Group`s. Classes and packages-as-components
   are follow-up granularities, not first cut.
3. **Connections = intra-project imports.** Skip stdlib + third-party
   (resolved by "does this module exist inside the scanned root"). No
   transitive collapsing in the first cut.
4. **Layers from top-level package names** with a small built-in
   heuristic table (`api|web|http` → `edge`, `services|domain` →
   `services`, `db|storage|persistence` → `data`, `infra|platform` →
   `infra`). Anything unmatched → `services`. Overridable via hints.
5. **Hints file = optional YAML next to the target** (`sysatlas.yaml`):
   `exclude`, `layer`, `group`, `rename`. Absence means pure-heuristic
   mode.
6. **Round-trip merge** = the blueprint's components/connections that
   match reflected ones get their `qualities`, `label`, `tech` merged
   in; blueprint components that don't match get added as user-asserted
   stubs (so the diff between intent and reality is visible).
7. **No CLI.** Library only (per `.claude/CLAUDE.md`). The reflection
   demo at `docs/reflection/module-map.py` is the canonical usage example.

## Public API sketch

```python
import sysatlas

r = sysatlas.reflect("sysatlas/")         # returns a Reflection
r.exclude("tests/*", "_vendor.py")
m = r.to_system_map(title="sysatlas internals")
m.show()

# round-trip: annotation overlay merged onto reflected structure
overlay = sysatlas.SystemMap(title="sysatlas internals")
overlay.add_component(
    "_route",
    qualities=[QualityAttribute(category="performance", criticality="high")],
)
merged = r.merge_with(overlay)
merged.show()
```

`sysatlas.reflect` and the `Reflection` class are the only new public
symbols.

## Module layout (proposed)

```
sysatlas/
└── _reflection/
    ├── __init__.py        — Reflection class, sysatlas.reflect entry point
    ├── parser.py          — AST walk: modules, imports, classes
    ├── resolve.py         — import string → in-tree module path
    ├── layers.py          — heuristic + hints application
    └── merge.py           — round-trip merge with a blueprint SystemMap
```

No new ontology — emits existing `architecture.py` types.

## LLM discoverability — the trigger

The backward flow only happens if the user's coding LLM knows sysatlas
exists and how to invoke it. After it finishes implementing a feature,
it should regenerate the affected diagrams. To make that automatic:

- Ship `sysatlas/LLM_GUIDE.md` inside the wheel (package-data in
  `pyproject.toml`).
- Public hooks: `sysatlas.llm_guide()` (returns the markdown string),
  `sysatlas.llm_guide_path()` (returns the absolute path on disk).
- Module docstring (5 lines): pointer at `sysatlas.llm_guide()`.
- README section "Using sysatlas with an AI coding assistant" with the
  one-liner the user pastes into their own `CLAUDE.md` / `.cursorrules`:
  > Before and after any code change, read sysatlas's LLM guide:
  > `python -c "import sysatlas; print(sysatlas.llm_guide())"`. Whenever
  > you add/remove/rename modules, regenerate the affected diagrams.

The guide itself tells the LLM the two halves of the loop:
1. **Read** the existing diagrams (where they live, how to find them).
2. **Regenerate** with `sysatlas.reflect(...)` + the project's
   annotation overlay after each feature.

Without this, milestones 1–5 are dead infrastructure no LLM will ever
invoke.

## Milestones

| # | Slice | Acceptance |
|---|---|---|
| 0 | LLM guide + public hooks + README section | `python -c "import sysatlas; print(sysatlas.llm_guide())"` prints the guide; wheel includes the .md. |
| 1 | AST parser + import resolver (`parser.py`, `resolve.py`) | Tests: scanning sysatlas itself returns the expected module graph; intra-project imports only. |
| 2 | Module-granularity `Reflection.to_system_map()` (`__init__.py`, `layers.py`) | `sysatlas.reflect("sysatlas/").to_system_map().show()` produces a recognisable diagram of sysatlas itself. |
| 3 | Hints file (`sysatlas.yaml`) | Test fixture project + hint overrides exclude tests dir and re-layer one module. |
| 4 | Round-trip merge (`merge.py`) | Blueprint with `qualities` on one reflected module appears as a badge on the rendered output. |
| 5 | Reflection demo: `docs/reflection/module-map.py` | Generates `module-map.html`; PNG committed; README table updated. |
| 6 | Class granularity (`granularity="class"`) | Optional follow-up; not in first PR. |

## Out of scope (for now)

- Dynamic import detection (plugin systems, `importlib.import_module(...)`).
- Type-driven connections (call graph, type-hint dependency). Imports
  only.
- Non-Python sources.
- Live "watch & regenerate" mode.
- Drift detection as a separate command — covered implicitly by
  round-trip merge.

## Open questions

None blocking. Reasonable defaults chosen above; user can redirect on
any of them once milestone 1 lands and they see the shape.
