# State of the Art

Index of standards, frameworks, notations, algorithms, and reference works
relevant to sysatlas. The purpose of this file is to know **where to read**
and **what to revisit** before designing or extending any feature, so we
don't reinvent the wheel.

Update this file whenever a useful reference is encountered.

Companion file: [design-principles.md](design-principles.md) — what
sysatlas optimizes for and what it deliberately does not. Read it before
designing anything; many decisions below are bounded by the principle that
sysatlas targets focused low-complexity diagrams and encourages splitting
into multiple views.

---

## 1. Architecture Description Frameworks

| Name | Origin | What it gives |
|---|---|---|
| **ISO/IEC/IEEE 42010:2011** | ISO | Vocabulary: Stakeholder, Concern, Viewpoint, View, Model Kind, Architecture Description (AD). The lingua franca of AD. |
| **C4 Model** | Simon Brown | System Context / Container / Component / Code. Lightweight, popular for software. |
| **ArchiMate 3.x** | The Open Group | Enterprise architecture: Business / Application / Technology layers with typed relations (composition, realization, serving, flow…). |
| **TOGAF** | The Open Group | Methodology/process (ADM). Not a notation. Useful for guiding *what* to describe. |
| **4+1 View Model** | Philippe Kruchten | Logical / Process / Development / Physical / Scenarios. Maps to ISO 42010 viewpoints. |
| **RM-ODP** | ISO | Enterprise / Information / Computational / Engineering / Technology viewpoints. Foundational for distributed systems. |
| **DoDAF / MODAF / NAF** | US/UK/NATO defence | Heavy frameworks, mostly too much for software but rich in concepts. |

## 2. Diagram Notations / Modelling Languages

| Name | Owner | Use |
|---|---|---|
| **UML 2.x** | OMG | Class, Sequence, Activity, State Machine, Deployment, Component, Use Case |
| **SysML** | OMG | Extends UML for systems engineering: Block Definition, Internal Block, Requirements, Parametric. |
| **BPMN 2.0** | OMG | Business processes: pools, lanes, events, activities, gateways. |
| **AADL** | SAE | Architecture Analysis & Design Language. Real-time and embedded. |
| **MARTE** | OMG | UML profile for real-time and embedded systems. |

## 3. Interchange Formats / Exportable Notations

| Format | Use |
|---|---|
| **GraphML** | XML standard for graphs. Wide tool support. |
| **DOT / Graphviz** | Text-based graph language; mature layout engines. |
| **Mermaid** | Text-to-diagram, embedded in GitHub, GitLab, Notion. Easy export target. |
| **PlantUML** | Text-to-UML, very popular for documentation. Easy export target. |
| **mxGraph / draw.io XML** | What sysatlas currently emits. |
| **Cytoscape JSON** | For graph analysis pipelines. |
| **GEXF** | XML graph format (Gephi). |
| **JSON Graph Format (JGF)** | JSON spec for graphs. |
| **JSON-LD / schema.org** | Semantic-web triples; useful if we ever want ontology interop. |

## 4. Layout Algorithms

| Algorithm / Tool | Notes |
|---|---|
| **Sugiyama (1981)** | Layered DAG layout. What sysatlas uses for layered diagrams. |
| **A\* maze routing** | Grid-based path-finding. What sysatlas uses for edges. |
| **Force-directed** | Fruchterman-Reingold, Kamada-Kawai. Default for non-layered. |
| **Orthogonal (TSM)** | Topology-Shape-Metrics, Tamassia. Rubber-band style. On the routing roadmap. |
| **Tree layouts** | Reingold-Tilford (top-down), radial (mind maps). |
| **HOLA** | Human-Like Orthogonal Layout, Wybrow et al. Aesthetic optimization. |
| **ELK** (Eclipse Layout Kernel) | State-of-the-art Java toolkit; full suite (layered, force, orthogonal, radial). **Reference only** — adopting it would break sysatlas's no-external-dep guarantee. |
| **DAGRE** | JS Sugiyama. Simple, widely used. Same dep-policy constraint as ELK. |

## 5. Quality Attributes

| Standard | Notes |
|---|---|
| **ISO/IEC 25010** | Software quality model: functional suitability, performance efficiency, compatibility, usability, reliability, security, maintainability, portability. Good vocabulary for tagging components/connections. |
| **FURPS+** | Functionality, Usability, Reliability, Performance, Supportability + design / implementation / interface / physical constraints. Older, simpler. |

## 6. Domain Modelling

| Approach | Concepts |
|---|---|
| **Domain-Driven Design (DDD)** (Evans) | Bounded Context, Aggregate, Entity, Value Object, Domain Event, Anti-Corruption Layer. |
| **Event Storming** (Brandolini) | Domain events, commands, aggregates, policies. Defined sticky-note color code. |
| **Event Modeling** (Adam Dymitruk) | Slice-by-slice flow of events with wireframes and read/write models. |
| **Context Mapping** (DDD) | Patterns of relationships between bounded contexts (Customer/Supplier, Conformist, Anti-Corruption Layer…). |

## 7. Pattern Catalogues (reference, not notation)

- **GoF Design Patterns** — Gamma et al.
- **Enterprise Integration Patterns** — Hohpe & Woolf.
- **Microservices Patterns** — Chris Richardson.
- **Cloud Design Patterns** — Microsoft, AWS Well-Architected, Google SRE.

These could ship as pre-built templates ("drop in an API Gateway pattern").

## 8. Standards mapping for sysatlas

How our current artefacts align with the literature:

| sysatlas artefact | ISO 42010 concept | Closest external notation |
|---|---|---|
| `_ontology/architecture.py` | Model Kind | C4 Container |
| `_ontology/er.py` | Model Kind | Chen / Crow's-foot ER |
| `_ontology/sequence.py` | Model Kind | UML Sequence |
| `_ontology/uml_class.py` | Model Kind | UML Class |
| `_ontology/state_machine.py` | Model Kind | UML State Machine |
| `_ontology/bpmn.py` | Model Kind | BPMN 2.0 (subset) |
| `_ontology/tree.py` | Model Kind | UML composite / generic tree |
| `docs/ontology/*.md` | Viewpoint specification | — |
| `SystemMap` builder instance | Model | — |
| HTML render output | View | draw.io / mxGraph |

## 9. Known gaps in sysatlas

What ISO 42010 / the wider literature suggests we should add eventually:

1. **Stakeholders / Concerns** — explicit list per diagram so the *why* is captured, not just the *what*.
2. **Viewpoints formalized** — current `.md` docs describe primitives but don't enumerate stakeholders, concerns addressed, model kinds used, conventions, operations.
3. **Architecture Description container** — multiple views (architecture + sequence + state…) consolidated in one AD with shared identity, not just loose HTMLs.
4. **Trace links** — a Component in `architecture` should be referenceable from a Class in `uml_class`, a Lifeline in `sequence`, an Aggregate in DDD. Cross-model identity.
5. **Quality attributes** — taggable per Component / Connection (e.g. "Cache is performance-critical", "Auth is security-sensitive"). ISO 25010 vocabulary.
6. **Requirements** — link from Component / Class / State to a requirement spec.
7. **Pattern templates** — pre-built fragments for common patterns (API Gateway, Saga, Pub/Sub).
8. **Export interop** — emit Mermaid, PlantUML, DOT, GraphML so diagrams can live in GitHub READMEs and other tools.
9. **Versioning / evolution** — diagrams aren't snapshots; track change over time.

## 10. Recommended adoption priority

**Shipped:**

- **Trace links** between models — `sysatlas/_ontology/trace.py` (SysML vocab) + `System.trace()` overlay + matrix view-kind. See [`ontology/trace.md`](ontology/trace.md).
- **Quality attributes** (ISO 25010) as a field on Component / Connection — `sysatlas/_ontology/qualities.py`, rendered as letter badges on nodes and edges. See [`ontology/qualities.md`](ontology/qualities.md).
- **ISO 42010 vocabulary** — decided *against* renaming `Ontology` → `ModelKind` (the Ontology is the typed schema; a ModelKind is a named *usage* of an Ontology). Instead added a `ModelKind` taxonomy layer on top, with a bundled `DEFAULT_KINDS` registry (c4-context / c4-container / uml-sequence / …). See [`ontology/model_kinds.md`](ontology/model_kinds.md).

**Still high value / low cost — do soon:**

1. Add **Mermaid + PlantUML export** for interop.

**Consider after that — medium cost, real value:**

2. **ArchiMate** as an alternative architecture ontology for enterprise use.
3. **Evolve the in-house layout engines** before adopting external ones — add force-directed, orthogonal (TSM/HOLA), and channel-routing variants alongside the existing Sugiyama + A\*. Adopting ELK/DAGRE/etc. would pull in Java or JS runtime deps and break the no-external-dep policy that ships the draw.io viewer bundled; we'd rather invest in our own.
4. **Event Storming / DDD Context Map** as new ontologies.

**Probably not — low value for our scope:**

- Full **SysML / AADL** (overkill for software-system focus).
- Full **DoDAF / MODAF** (defence-heavy).
- Full **TOGAF** as process guidance (we are a notation library, not a methodology).

---

## How to use this file

- Before designing a new ontology, check sections **1, 2, 6** for existing
  standards covering the same concepts.
- Before writing a layout / routing algorithm, check section **4**.
- Before adding cross-cutting attributes, check section **5**.
- Before designing export, check section **3**.
- Before claiming a "new" abstraction, check section **8** to see whether
  the literature already names it.

Add entries as we encounter useful references; keep the priority list
(section **10**) honest and current.
