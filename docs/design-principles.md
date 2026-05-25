# Design Principles

What sysatlas optimizes for, and what it deliberately does not. These
principles bound every algorithmic and API decision in the library.

---

## 1. Bounded complexity per view

**Diagrams that try to show everything show nothing.** Past a certain
density (~15 nodes, ~25 edges as a rough guide), any layout — no matter
how clever — becomes a tangle that costs the reader more attention than
it saves.

sysatlas targets **focused, low-complexity diagrams**. The algorithms in
`_layout`, `_route`, and `_place` are tuned for the small-to-medium
regime (single-digit to low-double-digit node counts). They will keep
working at higher counts, but the output quality degrades; that is by
design — the right answer at that scale is to **split** the view.

### Budget heuristics

| Metric | Sweet spot | Warn | Hard ceiling (consider splitting) |
|---|---|---|---|
| Components per view | 5–10 | 15 | 20 |
| Connections per view | 8–15 | 25 | 35 |
| Layers | 3–5 | 6 | 7 |
| Ports per node side | 1–3 | 4 | 5 |

These are rules of thumb, not enforced limits. Future work: emit a
warning when a view exceeds the warn threshold, and expose a `--strict`
mode that refuses to render past the hard ceiling.

---

## 2. Multi-view by default

A real system is described not by one diagram but by **several
complementary views**, each focused on a sub-concern or sub-domain.
Examples in an e-commerce platform:

| View | What it shows | What it omits |
|---|---|---|
| **Storefront** | Catalog, Cart, Search, CDN | Payments internals, Ops/Infra |
| **Checkout flow** | Cart → Orders → Payments → Notifications | Catalog browsing, Ops |
| **Payments** | Payments service, gateway adapters, fraud detection, audit trail | Storefront, async background work |
| **Async backbone** | Event bus, workers, consumers, retry/DLQ | UI, sync request paths |
| **Data layer** | All stores + the services that own them | UI, async flows |
| **Ops view** | Tracing, Metrics, Logging, what they observe | Domain logic |

Each view is itself a sysatlas diagram. The same component (e.g.
`Payments`) may appear in several views; the views are connected by
shared identity, not by trying to fit everything on one canvas.

### Splitting heuristics

When a view crosses the warn threshold, candidate split lines are
(in priority order):

1. **By bounded context / domain** (DDD natural seams). Payments is a
   different bounded context from Storefront — they should not share a
   diagram unless the diagram is *about* their boundary.
2. **By layer** (e.g. all of "edge" + selected services in one view,
   "data + storage" in another).
3. **By stakeholder concern** (Ops view, Security view, Dev view).
4. **By feature / user journey** (Checkout flow, Search flow,
   Registration flow).
5. **By zoom level** (C4-style: Context → Container → Component).

### Mechanism: stub references

When component `X` lives in view A but is referenced from view B, view
B shows `X` as a **stub** — a visually distinct node (dashed border,
faded fill) labelled with `X` and a pointer to view A. This keeps each
view self-contained while preserving cross-view identity.

This is not yet implemented; see *Roadmap* below.

---

## 3. Why bounded, multi-view is a differentiator

Most diagramming tools optimize for **expressiveness at any scale** —
draw anything you want, no matter how dense. The result is the famous
"big ball of mud" architecture diagram nobody reads.

sysatlas deliberately optimizes for the **readable subset**:

- Algorithms tuned for low complexity (better-looking small diagrams,
  not "OK-looking" large ones).
- API encourages splitting (multiple `SystemMap` instances per
  project, cross-referenced).
- Defaults discourage cramming (port counts trigger node growth, label
  collisions force spreading, etc.).
- Quality detector (`_report_issues`) treats density artefacts —
  crossings, label collisions, near-overlaps — as warnings the user
  should *act on*, not as inevitabilities to live with.

A user who needs a 200-node enterprise super-diagram should pick a
different tool. A user who wants 10 readable views of the same system,
each one fitting on a slide, should pick sysatlas.

---

## 4. Implications for the layout/routing pipeline

- We can use expensive-per-diagram algorithms (A\* with rip-up + reroute,
  swap-and-reroute with full re-routing, multiple barycenter iterations)
  because each diagram is small.
- We prioritize **visual quality** (zero collinear overlaps, edges never
  cross node interiors, labels never overlap labels) over raw rendering
  speed.
- Per-edge optimizations (port assignment, label placement, crossing
  avoidance) can be quadratic in edge count because edge counts are
  bounded.
- Heuristics are tuned at small N. Behaviour at very large N is not
  validated.

---

## 5. Roadmap (not implemented yet)

These follow from the principles above:

1. **Budget warnings** — `_report_issues` should also report when a
   diagram exceeds the warn threshold for nodes / edges / ports.
2. **First-class View concept** — an `ArchitectureDescription` container
   that holds multiple views and tracks shared identity (a `Payments`
   component referenced from several views resolves to the same entity).
3. **Stub-node rendering** — when a connection references a component
   defined in another view, render it as a dashed/faded stub with a
   cross-reference label.
4. **Suggested split** — when a view is too dense, the tool suggests a
   split line (by group, layer, or detected cluster) and can produce
   the split views automatically.
5. **View composition** — given several views, produce a combined view
   on request (e.g. for an "overview" page) while keeping the focused
   views as the canonical primary artefacts.

See also: [state-of-the-art.md](state-of-the-art.md) for the wider
academic and industry context; [ontology/README.md](ontology/README.md)
for the typed model kinds these views build on.
