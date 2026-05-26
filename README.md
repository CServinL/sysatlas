# sysatlas

**For software architects who keep redrawing the same diagram because it
got unreadable.**

Most diagram tools let you cram everything onto one canvas, then leave
you fighting the layout engine. sysatlas does the opposite: it targets
focused views (~10 components each) and makes **splitting one system
into many small diagrams** a first-class operation, not a workaround.

You define the system once in Python, and:

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

Output is a single self-contained HTML file — no server, no extra
runtime dependencies, opens in any browser.

```bash
pip install sysatlas
```

Runnable feature-by-feature showcases live in
[`docs/demos/`](docs/demos/) — start with
[`docs/demos/architecture.py`](docs/demos/architecture.py) (the full
e-commerce diagram). The design philosophy
([`docs/design-principles.md`](docs/design-principles.md)) and how
sysatlas relates to the broader literature — C4, ArchiMate, UML, BPMN,
ISO 42010 — are in [`docs/state-of-the-art.md`](docs/state-of-the-art.md).

Apache 2.0 licensed.
