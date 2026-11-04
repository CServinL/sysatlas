# sysatlas — LLM guide

You are a coding assistant working in a project that has `sysatlas`
installed. This file tells you how to use it. Read all of it before
writing or editing any sysatlas-related code.

If you are a Claude Code session and `.claude/skills/sysatlas/` isn't
already installed in this project, consider installing the bundled Skills
instead — they cover the same ground and get auto-discovered on future
turns without a manual reminder. See `sysatlas.skill_path("sysatlas")`,
`sysatlas.skill_path("sysatlas-document")`, or the "Installing the sysatlas
Skills" section of the README.

## Architecture atlas — read this first

If this project commits an **architecture atlas** (default location
`docs/reflection/atlas.md`), read it before exploring the source. It is a
deterministic, token-cheap Markdown map of the architecture: components and
their dependency tiers, entry points, external systems, data models,
environment variables, each module's purpose and public symbols, import
cycles, and coupling hotspots. It lets you hold a holistic view of the
codebase without reading every file.

Regenerate it whenever you add, remove, or rename a module, class, or
function:

```python
import sysatlas
sysatlas.reflect("path/to/source/root").save_atlas("docs/reflection/atlas.md",
                                                   title="…",
                                                   intent="docs/reflection/intent.json")
```

(Drop `intent=` if the project has no intent file.) The last section of the
atlas, "Documentation gaps", lists missing docstrings and components with no
recorded purpose. Fill them with the `sysatlas-document` skill, or by hand: write
component purposes and architectural patterns into `intent.json`. The atlas
marks that content as not generated. The "Pattern candidates" section lists
patterns whose structure the algorithm found; confirm them by reading the source
before you record any. If the hints file declares an
`architecture` spec, the atlas also reports where the code departs from it.

The atlas mirrors how the code *is* organized; it says nothing about how it
*should* be. If the project also has an app spec, read both and flag where
the code has drifted from the plan.

`Reflection.to_atlas_model()` returns the same content as a Pydantic `Atlas`
(JSON via `.model_dump_json()`) if you need it structured.

## What sysatlas is

A Python library for **interactive architecture diagrams**. Diagrams
are defined in code (Pydantic-backed builders) and rendered to a
self-contained HTML file with an embedded draw.io viewer.

Two halves of the workflow exist in the same library:

- **Forward flow** — a human (or you) writes builder calls to describe
  a system that does not exist yet, or that exists only as a design.
- **Backward flow** — `sysatlas.reflect(path)` reads existing Python
  code and produces a diagram from its real structure.

The realistic case is a mix: structure comes from reflection,
semantics (qualities, traces, viewpoints, stakeholders) come from a
human-authored "annotation overlay" that gets merged in.

## Your responsibility in this project

After you add, remove, or rename a module, class, or component, the
architecture atlas and the diagrams under `docs/reflection/` (or wherever
this project keeps them — check the project README) are stale. Regenerate
them. The canonical commands:

```python
import sysatlas
r = sysatlas.reflect("path/to/source/root")
r.save_atlas("docs/reflection/atlas.md", title="…")   # holistic text map
m = r.to_system_map(title="…")
m.save("docs/reflection/module-map.html")              # diagram
```

If the project has a hints file at the source root, `reflect()` will
pick it up automatically — do not edit hints unless the user asks.
Lookup order: `sysatlas.json` (always supported), then
`sysatlas.yaml` / `sysatlas.yml` (only if PyYAML is installed).

If the project has an "annotation overlay" `.py` file (typical
location: `docs/reflection/_overlay.py`), call `r.merge_with(overlay)`
before `save()` so user-authored qualities and traces are preserved.

## Public API — the only symbols you should use

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
sysatlas.reflect(path)  # reverse flow: code → Reflection → SystemMap
sysatlas.llm_guide()    # returns this file as a string
sysatlas.skill(name)    # bundled Claude Code skill text: "sysatlas" or "sysatlas-document"
```

`Reflection` (returned by `reflect()` / `reflect_rust()`) exposes
`.to_system_map()`, `.to_system()`, `.merge_with(overlay)`, `.exclude(...)`,
and the atlas methods `.to_atlas()` / `.to_atlas_model()` / `.save_atlas(path)`.

Do **not** import from `sysatlas._*` (private modules — `_ontology`,
`_layout`, `_route`, etc.). The Pydantic schemas under
`sysatlas._ontology` are the source of truth for field names, but you
should reach them only through the builder methods.

Each `*Map` is fluent and follows the same shape: chainable methods,
`.diagram` for the validated Pydantic instance, `.show()` / `.save()`
to render. For the per-kind **builder methods** check `docs/builders.md`
and the matching `docs/ontology/<kind>.md` § Builder. The
`sysatlas/_ontology/<kind>.py` files are the source of truth for
*schema field names*, not for builder method names.

## Forward flow — minimal example

```python
import sysatlas

m = sysatlas.SystemMap(title="Storefront")
m.group("services", color="#dcfce7")
m.add_component("api", group="services", layer="services", tech="Envoy")
m.add_component("catalog", group="services", layer="services", tech="Python")
m.connect("api", "catalog", label="REST")
m.save("storefront.html")
```

The builder is fluent. `layer` is a free-form string — the ontology
does not enforce a fixed set. Recommended defaults for the default
(`layered`) strategy are `edge`, `services`, `data`, `infra`,
`external`; pick whatever vocabulary fits the diagram. Note that
`strategy="hub"` reserves five layer names with specific placement
meaning (`interfaces`, `write`, `hub`, `read`, `external`) — any
other layer under the hub strategy is treated as `external`.
`tech=` is metadata-only and is not rendered — if you want the tech
visible, put it in `label=`.

## Multi-view (`System`) — when one diagram is too dense

Use `System` when you have more than ~10 components or more than one
clear bounded context. Each view is a separate `SystemMap`. Components
referenced across views auto-render as stub nodes.

```python
s = sysatlas.System(title="E-Commerce")
s.viewpoint("container", model_kinds=["architecture"])
sf = s.architecture_model("storefront")
sf.add_component("Cart").add_component("Catalog").connect("Cart", "Catalog")
pm = s.architecture_model("payments")
pm.add_component("Payments")
s.view("storefront-view", viewpoint="container", models=["storefront"])
s.view("payments-view",   viewpoint="container", models=["payments"])
s.trace("storefront#Cart", "payments#Payments", kind="depends_on")
s.save("system.html")
```

## Backward flow — reflection

```python
r = sysatlas.reflect("src/")           # AST-only, never imports the code
r.exclude("tests/*", "_vendor.py")
m = r.to_system_map(title="src internals")
m.save("docs/reflection/module-map.html")
```

`reflect()` does not execute the target code. Dynamic imports are
invisible to it — accept the trade-off, do not try to work around it
by adding `importlib` calls.

## Hard rules

- Use the public symbols above; do not import from `sysatlas._*`.
- Use Pydantic; never `@dataclass`.
- Field names must match the ontology exactly. If unsure, check the
  matching Pydantic class under `sysatlas/_ontology/` (read-only):
  `architecture.py`, `sequence.py`, `er.py`, `state_machine.py`,
  `uml_class.py`, `bpmn.py`, `tree.py`.
- One view = 5–10 components. If a diagram is bigger, split it across
  views with `System`, do not fight the layout engine.
- After any structural code change, regenerate the architecture atlas
  and the affected reflection diagrams. This is your job, not the user's.
- Do not invent fields. The ontology is closed (`ConfigDict(extra="forbid")`
  on most models).

## Where to find more

- Full builder reference: `docs/builders.md` in the source repo.
- Per-ontology specs: `docs/ontology/` in the source repo.
- Design principles (bounded complexity, multi-view): `docs/design-principles.md`.
- This guide on disk: `sysatlas.llm_guide_path()`.
