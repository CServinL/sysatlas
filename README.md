# sysatlas

**For software architects who keep redrawing the same diagram because it
got unreadable — and for the AI coding assistants that keep the
diagrams in sync with the code.**

Most diagram tools let you cram everything onto one canvas, then leave
you fighting the layout engine. sysatlas does the opposite: focused
views (~10 components each), and **splitting one system into many
small diagrams** is a first-class operation.

It works in both directions:

### Forward — design before code

You describe a system in Python and:

- **Split** it into focused views — *storefront*, *payments*,
  *async backbone* — each one fits on a slide.
- **Cross-reference** between views with auto-detected stub nodes, so a
  component defined in one view shows up as a ghost reference in others.
- **Annotate** components with ISO 25010 quality attributes
  (`security: critical`, `performance: high`) — rendered as coloured
  badges.
- **Trace** how things relate across views (`Cart depends_on Payments`,
  `APIController realizes API`) using SysML link vocabulary.
- **Ground** the whole thing in ISO 42010 (Stakeholders / Concerns /
  Viewpoints / Views) so the *why* is captured alongside the *what*.

### Backward — reflect after the code lands

You point sysatlas at an existing source tree and it reads the real
structure:

```python
import sysatlas
r = sysatlas.reflect("src/")
m = r.to_system_map(title="src internals")
m.save("docs/reflection/module-map.html")
```

Static AST analysis — no execution, safe on broken code. The output
is the same `SystemMap` the forward flow produces, so a thin
human-authored "annotation overlay" (qualities, traces, viewpoints)
can be merged onto reflected structure via `r.merge_with(overlay)`.
Drift between intent and reality becomes visible instead of silent.

### The intended loop

1. **Plan** the change with a forward-flow diagram on a feature branch.
2. **Implement** the feature.
3. **Reflect** the branch (`sysatlas.reflect(...)`) and commit the
   regenerated diagrams alongside the code. Reviewers see structure
   and intent change together.

Output is a single self-contained HTML file — no server, no extra
runtime dependencies, opens in any browser.

```bash
pip install sysatlas
```

## Using sysatlas with an AI coding assistant

sysatlas ships a guide aimed at LLMs. Tell your coding assistant
(Claude Code, Cursor, Aider, …) to read it before working on this
repo. The one-liner to paste into your `CLAUDE.md` / `.cursorrules` /
`AGENTS.md`:

> Before editing this project, read sysatlas's LLM guide:
> `python -c "import sysatlas; print(sysatlas.llm_guide())"`.
> After any structural change (add/remove/rename modules or
> components), regenerate the affected diagrams under
> `docs/reflection/` using `sysatlas.reflect(...)` and commit them
> with the code change.

The guide tells the assistant exactly which symbols are public, which
fields the ontology accepts, and that diagrams are part of the
deliverable — not an afterthought.

## Where to look

- Runnable feature-by-feature showcases live in
  [`docs/demos/`](docs/demos/) — start with
  [`docs/demos/architecture.py`](docs/demos/architecture.py).
- Design philosophy: [`docs/design-principles.md`](docs/design-principles.md).
- Full app index: [`docs/README.md`](docs/README.md).
- How sysatlas relates to C4 / ArchiMate / UML / BPMN / ISO 42010:
  [`docs/state-of-the-art.md`](docs/state-of-the-art.md).

Apache 2.0 licensed.
