# Diagram Ontologies

sysatlas separates each diagram type into its own ontology. Each
ontology has:

1. A Pydantic schema (`sysatlas/_ontology/<type>.py`) — the source of truth.
2. A prose specification (`docs/ontology/<type>.md`) — what the concepts mean and why.
3. *(when implemented)* A public builder class that constructs and validates
   instances of the schema, plus a render pipeline.

## Diagram ontologies (Model Kinds)

| Type | Schema | Doc | Builder |
|---|---|---|---|
| Layered architecture (C4-container style) | `_ontology/architecture.py` | [architecture.md](architecture.md) | `sysatlas.SystemMap` |
| Entity–Relationship (ER) | `_ontology/er.py` | [er.md](er.md) | — |
| Sequence (UML) | `_ontology/sequence.py` | [sequence.md](sequence.md) | — |
| Class (UML) | `_ontology/uml_class.py` | [uml_class.md](uml_class.md) | — |
| State machine | `_ontology/state_machine.py` | [state_machine.md](state_machine.md) | — |
| BPMN process (simplified) | `_ontology/bpmn.py` | [bpmn.md](bpmn.md) | — |
| Tree (org / mindmap / taxonomy / filesystem) | `_ontology/tree.py` | [tree.md](tree.md) | — |

## Cross-cutting ontologies

These wrap or annotate the diagram ontologies; they don't define a
diagram type themselves.

| Concern | Schema | Doc |
|---|---|---|
| ISO/IEC/IEEE 42010 meta-ontology (Stakeholder, Concern, Viewpoint, View, ArchitectureDescription) | `_ontology/iso42010.py` | [iso42010.md](iso42010.md) |
| Trace links between entities across models | `_ontology/trace.py` | [trace.md](trace.md) |
| Quality attributes (ISO 25010) on components & connections | `_ontology/qualities.py` | [qualities.md](qualities.md) |
| Model Kinds — taxonomy naming each registered usage of an ontology | `_ontology/model_kind.py` + `_ontology/model_kinds.py` | [model_kinds.md](model_kinds.md) |

## Intentionally omitted

These were considered but skipped because they are equivalent or very
close to existing ontologies:

- **Deployment** (C4) — same primitives as `architecture` (component +
  connection + grouping). Express deployments via component `tech` and
  group labels.
- **Data Flow Diagram (DFD)** — same shape as `architecture`. The
  Process/DataStore/ExternalEntity distinction can be encoded in
  component `tech` or `meta`.
- **Network topology** — covered by `architecture`. Device/VLAN concepts
  encoded as component groups/tech.
- **Org chart** and **Mind map** — both unified under `tree` with a
  `flavor` tag.

If a future use case proves these need their own typed primitives, they
can be added as separate ontologies.

## Shared primitives

Some concepts recur across diagram types and may eventually move to a
shared base module:

- `Node` — any positioned visual element (rectangle, ellipse, actor).
- `Edge` — connection between nodes (directed or undirected).
- `Cluster` — grouping container (swim lane, boundary, subgraph).
- `Label` — text on a node, edge, or cluster.

The layout engine (`_layout`, `_place`, `_route`) consumes these
primitives, not the typed ontologies. Each ontology's builder is
responsible for projecting its typed concepts into the primitive graph
form the engine understands.
